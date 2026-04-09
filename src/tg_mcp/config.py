"""Configuration loader and structured logging setup.

Loads settings from ~/.tg-mcp/.env via python-dotenv.
Validates all required fields at load time — fails fast with clear messages.
Configures JSON-formatted logging with rotation to ~/.tg-mcp/logs/.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when configuration is invalid or missing.

    Always includes: what's wrong, what was expected, example, recovery hint.
    """


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated, immutable application settings."""

    api_id: int
    api_hash: str
    phone: str
    data_dir: Path

    @property
    def session_path(self) -> Path:
        return self.data_dir / "session.session"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "tg_mcp.db"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"


def _resolve_data_dir(raw: str | None) -> Path:
    """Resolve and create the data directory."""
    raw = raw or "~/.tg-mcp"
    path = Path(os.path.expandvars(os.path.expanduser(raw)))
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigError(
            f"Cannot create data directory: {path}\n"
            f"Expected: writable directory path\n"
            f"Example: TG_MCP_DATA_DIR=~/.tg-mcp\n"
            f"Recovery: check permissions on parent directory — {exc}"
        ) from exc
    return path


def _load_env(data_dir: Path) -> None:
    """Load .env file from data directory."""
    env_path = data_dir / ".env"
    if not env_path.is_file():
        raise ConfigError(
            f".env file not found at {env_path}\n"
            f"Expected: .env file with TG_API_ID, TG_API_HASH, TG_PHONE\n"
            f"Example: cp .env.example {env_path} && edit {env_path}\n"
            f"Recovery: create {env_path} with your Telegram API credentials from https://my.telegram.org"
        )
    load_dotenv(env_path, override=False)


def _require_env(name: str, human_name: str) -> str:
    """Get a required environment variable or raise ConfigError."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(
            f"Required setting {name} is missing or empty\n"
            f"Expected: {human_name}\n"
            f"Example: {name}=12345\n"
            f"Recovery: set {name} in ~/.tg-mcp/.env"
        )
    return value


def load_settings() -> Settings:
    """Load and validate all settings. Fails fast on any problem."""
    data_dir = _resolve_data_dir(os.environ.get("TG_MCP_DATA_DIR"))
    _load_env(data_dir)

    # API_ID must be a positive integer
    raw_api_id = _require_env("TG_API_ID", "Telegram API ID (integer from my.telegram.org)")
    try:
        api_id = int(raw_api_id)
    except ValueError:
        raise ConfigError(
            f"TG_API_ID must be an integer, got: {raw_api_id!r}\n"
            f"Expected: numeric API ID from https://my.telegram.org\n"
            f"Example: TG_API_ID=12345678\n"
            f"Recovery: check your API credentials at https://my.telegram.org"
        )
    if api_id <= 0:
        raise ConfigError(
            f"TG_API_ID must be positive, got: {api_id}\n"
            f"Expected: numeric API ID from https://my.telegram.org\n"
            f"Example: TG_API_ID=12345678\n"
            f"Recovery: check your API credentials at https://my.telegram.org"
        )

    # API_HASH must be a 32-char hex string
    api_hash = _require_env("TG_API_HASH", "Telegram API hash (hex string from my.telegram.org)")
    if len(api_hash) != 32 or not all(c in "0123456789abcdef" for c in api_hash.lower()):
        raise ConfigError(
            f"TG_API_HASH must be a 32-character hex string, got: {api_hash[:8]}...\n"
            f"Expected: 32 hex chars from https://my.telegram.org\n"
            f"Example: TG_API_HASH=0123456789abcdef0123456789abcdef\n"
            f"Recovery: copy the exact hash from https://my.telegram.org/apps"
        )

    # Phone number in international format
    phone = _require_env("TG_PHONE", "phone number in international format")
    if not phone.startswith("+"):
        raise ConfigError(
            f"TG_PHONE must start with '+' (international format), got: {phone[:4]}...\n"
            f"Expected: phone number like +380501234567\n"
            f"Example: TG_PHONE=+380501234567\n"
            f"Recovery: use international format with country code"
        )

    return Settings(
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        data_dir=data_dir,
    )


# ---------------------------------------------------------------------------
# Structured logging (JSON to file + plain to stderr)
# ---------------------------------------------------------------------------


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("op", "duration_ms", "error", "params", "version", "reason"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val

        if record.exc_info and record.exc_info[1] is not None:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, ensure_ascii=False, default=str)


def configure_logging() -> None:
    """Set up logging: JSON to rotating file + concise stderr.

    Safe to call multiple times (idempotent via handler check).
    """
    root = logging.getLogger("tg_mcp")

    if root.handlers:
        return

    root.setLevel(logging.DEBUG)
    root.propagate = False  # Don't leak to MCP SDK's rich handler

    # File handler: JSON, rotating, 5MB x 3
    try:
        data_dir = Path(os.path.expanduser(
            os.environ.get("TG_MCP_DATA_DIR", "~/.tg-mcp")
        ))
        log_dir = data_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "tg_mcp.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(_JsonFormatter())
        root.addHandler(file_handler)
    except OSError:
        pass  # Proceed without file logging

    # Stderr handler: WARNING+ only (MCP uses stdio for protocol)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    )
    root.addHandler(stderr_handler)


# Shared logger
logger = logging.getLogger("tg_mcp")
