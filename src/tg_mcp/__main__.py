"""Entry point: python -m tg_mcp

Starts the MCP server with stdio transport.
No Telegram connection is made here — that happens lazily on first tool call.
"""

import asyncio
import sys

from tg_mcp.config import configure_logging, logger


def main() -> None:
    configure_logging()
    logger.info("tg_mcp.startup", extra={"version": "0.1.0"})

    try:
        from tg_mcp.server import run_server

        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("tg_mcp.shutdown", extra={"reason": "keyboard_interrupt"})
        sys.exit(0)
    except Exception:
        logger.exception("tg_mcp.fatal")
        sys.exit(1)


if __name__ == "__main__":
    main()
