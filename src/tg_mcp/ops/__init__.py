"""Operations auto-loader.

Imports all .py modules in the ops/ directory at package import time.
This triggers @operation() decorators, registering ops into the catalog.

Import errors are logged but do NOT crash the server — a broken ops module
should not prevent other operations from working.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from tg_mcp.config import logger


def _auto_import_ops() -> None:
    """Discover and import all operation modules in this package."""
    package_dir = Path(__file__).parent

    for module_info in pkgutil.iter_modules([str(package_dir)]):
        module_name = f"tg_mcp.ops.{module_info.name}"
        try:
            importlib.import_module(module_name)
            logger.debug("ops.loaded", extra={"op_module": module_name})
        except Exception:
            logger.exception(
                "ops.load_failed",
                extra={"op_module": module_name},
            )


_auto_import_ops()
