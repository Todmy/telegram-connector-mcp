"""MCP server — 5 static tools, stdio transport.

Tools:
    tg_feed       — Read channel messages (readOnly, idempotent)
    tg_overview   — Channel/folder overview (readOnly, idempotent)
    tg_search_ops — Discover operations (readOnly, idempotent)
    tg_describe_op — Get operation schema (readOnly, idempotent)
    tg_execute    — Run any operation (conservative: not readOnly, not idempotent)

All responses use TextContent. Errors use the 4-part format:
what happened / expected / example / recovery hint.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from tg_mcp import catalog
from tg_mcp.cache import Cache
from tg_mcp.catalog import OperationError
from tg_mcp.client import TelegramClient, TelegramConnectionError, TelegramFloodWait
from tg_mcp.config import ConfigError, Settings, load_settings, logger

# ---------------------------------------------------------------------------
# Structured error helper
# ---------------------------------------------------------------------------


def _error_text(
    what: str,
    expected: str,
    example: str,
    recovery: str,
) -> str:
    """Build a 4-part structured error message."""
    return (
        f"Error: {what}\n"
        f"Expected: {expected}\n"
        f"Example: {example}\n"
        f"\u2192 {recovery}"
    )


# ---------------------------------------------------------------------------
# Module-level state (initialized in run_server)
# ---------------------------------------------------------------------------

_settings: Settings | None = None
_tg_client: TelegramClient | None = None
_cache: Cache | None = None

# Create the FastMCP server instance
mcp = FastMCP(
    "tg-mcp",
    instructions="Telegram MCP server — full client capabilities for Claude Code",
)


# ---------------------------------------------------------------------------
# Tool annotations
# ---------------------------------------------------------------------------

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    destructiveHint=False,
    openWorldHint=False,
)

_READ_ONLY_OPEN = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    destructiveHint=False,
    openWorldHint=True,
)

_EXECUTE = ToolAnnotations(
    readOnlyHint=False,
    idempotentHint=False,
    destructiveHint=False,
    openWorldHint=True,
)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


@mcp.tool(
    name="tg_feed",
    description=(
        "Fetch recent messages from one or more Telegram channels/groups. "
        "Returns messages with author, date, text, views, reactions, reply count. "
        "For single-channel deep dive, use channel handle. "
        "For multi-channel digest, omit channel to get cross-channel feed sorted by time. "
        "Truncates message text at 300 chars by default \u2014 use include_full_text=true for complete content. "
        "For searching by keyword across channels, use tg_search_ops to find the search operation instead."
    ),
    annotations=_READ_ONLY_OPEN,
)
async def tg_feed(
    channel: str | None = None,
    limit: int = 20,
    hours: int = 24,
    fields: list[str] | None = None,
    include_full_text: bool = False,
    folder: str | None = None,
) -> str:
    """Read channel messages."""
    errors = _validate_feed_params(limit, hours)
    if errors:
        return errors

    # Placeholder: actual implementation in Phase 3+ ops
    return _error_text(
        "tg_feed is not yet implemented",
        "this tool will fetch messages from Telegram channels",
        'tg_feed channel="@llm_under_hood" limit=10',
        "implementation is in progress \u2014 operations will be added in subsequent phases",
    )


@mcp.tool(
    name="tg_overview",
    description=(
        "Overview of subscribed channels, groups, and folders with activity metrics. "
        "Returns channel list with subscriber count, post frequency, unread count, and last post date. "
        "Default sort: by unread count (most unread first). Use sort parameter to change. "
        "For detailed stats on a single channel, use tg_search_ops to find the channel_stats operation. "
        'For managing folders (create, move channels), use tg_search_ops query="folders".'
    ),
    annotations=_READ_ONLY_OPEN,
)
async def tg_overview(
    sort: str = "unread",
    folder: str | None = None,
    min_subscribers: int = 0,
    type: str = "all",
    limit: int = 50,
    fields: list[str] | None = None,
) -> str:
    """Channel/folder overview."""
    valid_sorts = {"unread", "activity", "subscribers", "name", "last_post"}
    if sort not in valid_sorts:
        return _error_text(
            f"Invalid sort value: {sort!r}",
            f"one of: {', '.join(sorted(valid_sorts))}",
            'tg_overview sort="activity"',
            "use one of the listed sort options",
        )

    valid_types = {"channels", "groups", "all"}
    if type not in valid_types:
        return _error_text(
            f"Invalid type filter: {type!r}",
            f"one of: {', '.join(sorted(valid_types))}",
            'tg_overview type="channels"',
            "use 'channels', 'groups', or 'all'",
        )

    if limit < 1 or limit > 500:
        return _error_text(
            f"limit must be 1-500, got: {limit}",
            "integer between 1 and 500",
            "tg_overview limit=100",
            "use a value in the valid range",
        )

    if min_subscribers < 0:
        return _error_text(
            f"min_subscribers must be non-negative, got: {min_subscribers}",
            "integer >= 0",
            "tg_overview min_subscribers=1000",
            "use 0 or a positive number",
        )

    # Placeholder
    return _error_text(
        "tg_overview is not yet implemented",
        "this tool will show channel/folder overview",
        "tg_overview sort=activity",
        "implementation is in progress",
    )


@mcp.tool(
    name="tg_search_ops",
    description=(
        "Search the operations catalog by keyword or category. "
        "Returns matching operation names with one-line descriptions. "
        "Use this to discover what Telegram operations are available before calling tg_describe_op or tg_execute. "
        "Categories: channels, messages, interact, folders, analytics."
    ),
    annotations=_READ_ONLY,
)
async def tg_search_ops(
    query: str,
    category: str | None = None,
) -> str:
    """Discover operations in the catalog."""
    if not query or not query.strip():
        return _error_text(
            "query parameter is required and cannot be empty",
            "keyword to search operations by name or description",
            'tg_search_ops query="react"',
            "provide a search keyword",
        )

    query = query.strip()

    try:
        results = catalog.search(query=query, category=category)
    except ValueError as exc:
        return _error_text(
            str(exc),
            "valid category or None",
            'tg_search_ops query="react" category="interact"',
            f"valid categories: {', '.join(sorted(catalog.VALID_CATEGORIES))}",
        )

    if not results:
        cat_note = f" in category {category!r}" if category else ""
        available_cats = catalog.list_categories()
        cat_hint = f"Available categories: {', '.join(available_cats)}" if available_cats else ""

        return (
            f'0 operations matching "{query}"{cat_note}.\n'
            f"Try: broader keywords, different spelling, or remove category filter.\n"
            f"{cat_hint}\n"
            f"\u2192 Operations are added in ops/ modules. Current total: {catalog.count()}"
        )

    lines = [f'ops[{len(results)}] matching "{query}":']
    for op in results:
        destructive_flag = " [DESTRUCTIVE]" if op.destructive else ""
        lines.append(f"  {op.name} \u2014 {op.description}{destructive_flag}")

    lines.append("")
    lines.append(f'\u2192 To see full schema: tg_describe_op name="{results[0].name}"')
    lines.append(f'\u2192 To execute: tg_execute op="{results[0].name}" params={{...}}')

    return "\n".join(lines)


@mcp.tool(
    name="tg_describe_op",
    description=(
        "Get the full schema (parameters, types, defaults, description) for a specific operation. "
        "Call tg_search_ops first to find the operation name, then this to see how to use it."
    ),
    annotations=_READ_ONLY,
)
async def tg_describe_op(name: str) -> str:
    """Get operation schema."""
    if not name or not name.strip():
        return _error_text(
            "name parameter is required",
            "operation name from tg_search_ops results",
            'tg_describe_op name="react_to_message"',
            "call tg_search_ops first to find operation names",
        )

    name = name.strip()

    try:
        return catalog.describe(name)
    except OperationError as exc:
        return exc.format()


@mcp.tool(
    name="tg_execute",
    description=(
        "Execute any operation from the catalog by name with parameters. "
        "Always call tg_describe_op first to see required parameters. "
        "For destructive operations (unsubscribe, delete), returns confirmation prompt \u2014 pass confirm=true to proceed. "
        "Rate-limited: Telegram enforces FloodWait \u2014 if hit, returns wait time."
    ),
    annotations=_EXECUTE,
)
async def tg_execute(
    op: str,
    params: dict[str, Any] | None = None,
    confirm: bool = False,
    response_format: str = "concise",
) -> str:
    """Execute a catalog operation."""
    if not op or not op.strip():
        return _error_text(
            "op parameter is required",
            "operation name from tg_search_ops results",
            'tg_execute op="react_to_message" params={"channel": "@handle", "message_id": 123, "emoji": "fire"}',
            "call tg_search_ops to find operations, then tg_describe_op for their schemas",
        )

    op = op.strip()

    valid_formats = {"concise", "detailed"}
    if response_format not in valid_formats:
        return _error_text(
            f"Invalid response_format: {response_format!r}",
            f"one of: {', '.join(sorted(valid_formats))}",
            'tg_execute op="..." response_format="concise"',
            "use 'concise' (TOON, default) or 'detailed' (full data)",
        )

    if _tg_client is None:
        return _error_text(
            "Telegram client not initialized",
            "server started with valid config",
            "python -m tg_mcp",
            "check ~/.tg-mcp/.env configuration",
        )

    try:
        tg = await _tg_client.get()
    except TelegramConnectionError as exc:
        return _error_text(
            str(exc),
            "connected Telegram session",
            "python -m tg_mcp.auth",
            "run auth command or check network connectivity",
        )
    except TelegramFloodWait as exc:
        return _error_text(
            f"Rate limited by Telegram. Waited {exc.seconds}s.",
            "no rate limiting",
            "retry after the wait period",
            f"wait {exc.seconds}s before retrying \u2014 Telegram enforces this server-side",
        )

    try:
        result = await catalog.execute(
            name=op,
            client=tg,
            cache=_cache,
            params=params,
            confirm=confirm,
        )

        if isinstance(result, str):
            return result
        return str(result) if result is not None else "Done."

    except OperationError as exc:
        return exc.format()
    except TelegramFloodWait as exc:
        return _error_text(
            f"Rate limited by Telegram during operation. Waited {exc.seconds}s.",
            "no rate limiting",
            "retry after the wait period",
            f"wait {exc.seconds}s \u2014 this is enforced by Telegram, cannot bypass",
        )
    except Exception as exc:
        logger.exception("server.execute_error", extra={"op": op})
        return _error_text(
            f"Operation {op!r} failed: {type(exc).__name__}: {exc}",
            "successful operation execution",
            f'tg_describe_op name="{op}" to verify parameters',
            "check the error message and retry with corrected parameters",
        )


# ---------------------------------------------------------------------------
# Param validation helpers
# ---------------------------------------------------------------------------


def _validate_feed_params(limit: int, hours: int) -> str | None:
    """Validate tg_feed parameters. Returns error string or None."""
    if limit < 1 or limit > 100:
        return _error_text(
            f"limit must be 1-100, got: {limit}",
            "integer between 1 and 100",
            "tg_feed limit=20",
            "use a value in the valid range",
        )
    if hours < 1 or hours > 720:
        return _error_text(
            f"hours must be 1-720 (max 30 days), got: {hours}",
            "integer between 1 and 720",
            "tg_feed hours=24",
            "use hours=168 for one week, hours=720 for 30 days",
        )
    return None


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------


async def run_server() -> None:
    """Initialize and run the MCP server with stdio transport."""
    global _settings, _tg_client, _cache

    # Load config — fail fast if misconfigured
    try:
        _settings = load_settings()
    except ConfigError as exc:
        logger.error("server.config_error", extra={"error": str(exc)})
        raise SystemExit(f"Configuration error:\n{exc}") from exc

    # Create Telegram client wrapper (lazy — no connection yet)
    _tg_client = TelegramClient(_settings)

    # Create cache instance
    _cache = Cache()

    # Import ops to trigger @operation() registration
    import tg_mcp.ops  # noqa: F401

    logger.info(
        "server.starting",
        extra={
            "tools": 5,
            "operations": catalog.count(),
            "categories": catalog.list_categories(),
        },
    )

    try:
        await mcp.run_stdio_async()
    finally:
        if _tg_client is not None:
            await _tg_client.disconnect()

        from tg_mcp.db import close_db
        await close_db()

        logger.info("server.stopped")
