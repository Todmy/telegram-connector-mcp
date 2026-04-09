"""Telethon client wrapper — lazy connect, auto-reconnect, FloodWait handling.

The client connects on first actual use, not on import or MCP server startup.
Session file is stored at ~/.tg-mcp/session.session.
"""

from __future__ import annotations

import asyncio
import os
import stat
from pathlib import Path

from telethon import TelegramClient as _TelethonClient
from telethon.errors import FloodWaitError

from tg_mcp.config import Settings, logger


class TelegramConnectionError(Exception):
    """Raised when Telegram connection cannot be established."""


class TelegramFloodWait(Exception):
    """Raised when Telegram rate-limits us. Contains wait duration."""

    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        super().__init__(
            f"Rate limited by Telegram. Retry in {seconds}s. "
            f"This is enforced server-side and cannot be bypassed."
        )


class TelegramClient:
    """Lazy-connecting Telethon wrapper with defensive error handling.

    - Connects on first get() call, not on construction.
    - Auto-reconnect is handled by Telethon internally.
    - FloodWaitError: waits the required time, then raises TelegramFloodWait.
    - 30s timeout on connection.
    - Validates session file permissions (should be 600).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: _TelethonClient | None = None
        self._connect_lock = asyncio.Lock()
        self._connected = False

    @property
    def session_path(self) -> Path:
        return self._settings.session_path

    def _check_session_file(self) -> None:
        """Validate session file exists and has safe permissions."""
        path = self.session_path
        if not path.exists():
            raise TelegramConnectionError(
                f"Session file not found at {path}\n"
                f"Expected: Telethon session file from prior authentication\n"
                f"Example: python -m tg_mcp.auth\n"
                f"Recovery: run the auth command to create a session"
            )

        try:
            file_stat = os.stat(path)
            mode = stat.S_IMODE(file_stat.st_mode)
            if mode & (stat.S_IRGRP | stat.S_IROTH | stat.S_IWGRP | stat.S_IWOTH):
                logger.warning(
                    "client.session_permissions_unsafe",
                    extra={"path": str(path), "mode": oct(mode)},
                )
                try:
                    os.chmod(path, 0o600)
                    logger.info("client.session_permissions_fixed", extra={"path": str(path)})
                except OSError:
                    pass
        except OSError:
            pass

    async def get(self) -> _TelethonClient:
        """Get a connected Telethon client. Connects lazily on first call."""
        if self._connected and self._client is not None:
            if self._client.is_connected():
                return self._client
            logger.warning("client.connection_dropped")
            self._connected = False

        async with self._connect_lock:
            if self._connected and self._client is not None and self._client.is_connected():
                return self._client

            return await self._connect()

    async def _connect(self) -> _TelethonClient:
        """Establish connection to Telegram. Internal — called under lock."""
        self._check_session_file()

        session_str = str(self.session_path.with_suffix(""))

        self._client = _TelethonClient(
            session_str,
            api_id=self._settings.api_id,
            api_hash=self._settings.api_hash,
            timeout=30,
            auto_reconnect=True,
        )

        try:
            logger.info("client.connecting")
            await asyncio.wait_for(self._client.connect(), timeout=30.0)

            if not await self._client.is_user_authorized():
                raise TelegramConnectionError(
                    "Session exists but is not authorized.\n"
                    "Expected: authorized Telethon session\n"
                    "Example: python -m tg_mcp.auth\n"
                    "Recovery: re-run the auth command — session may have expired"
                )

            self._connected = True
            logger.info("client.connected")
            return self._client

        except FloodWaitError as e:
            logger.warning(
                "client.flood_wait_on_connect",
                extra={"wait_seconds": e.seconds},
            )
            await asyncio.sleep(e.seconds)
            raise TelegramFloodWait(e.seconds) from e

        except asyncio.TimeoutError:
            raise TelegramConnectionError(
                "Connection to Telegram timed out after 30s.\n"
                "Expected: successful MTProto connection\n"
                "Example: check network connectivity\n"
                "Recovery: retry in a few seconds — Telegram may be temporarily unreachable"
            )
        except (TelegramConnectionError, TelegramFloodWait):
            raise
        except Exception as exc:
            raise TelegramConnectionError(
                f"Failed to connect to Telegram: {exc}\n"
                f"Expected: successful connection with valid session\n"
                f"Example: python -m tg_mcp.auth to re-authenticate\n"
                f"Recovery: check network, verify session file, re-auth if needed"
            ) from exc

    async def disconnect(self) -> None:
        """Gracefully disconnect from Telegram."""
        self._connected = False
        if self._client is not None:
            try:
                await self._client.disconnect()
                logger.info("client.disconnected")
            except Exception:
                logger.exception("client.disconnect_error")
            finally:
                self._client = None

    async def __aenter__(self) -> TelegramClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.disconnect()
