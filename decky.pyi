"""
Type stub for Decky Loader's ``decky`` runtime module.

This module is injected by Decky Loader and does NOT exist in the
plugin source tree.  The stub silences Pylance / Pyright import warnings.
"""

from typing import Any

DECKY_PLUGIN_DIR: str
DECKY_PLUGIN_SETTINGS_DIR: str
DECKY_PLUGIN_RUNTIME_DIR: str
DECKY_PLUGIN_LOG_DIR: str
DECKY_USER_HOME: str

async def emit(event: str, *args: Any, **kwargs: Any) -> None: ...
