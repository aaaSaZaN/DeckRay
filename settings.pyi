"""
Type stub for Decky Loader's SettingsManager.

This module is provided by Decky Loader at runtime and does NOT exist
in the plugin's own codebase.  This stub exists solely so that static
analysers (Pylance / Pyright) can resolve `from settings import SettingsManager`
without errors.
"""

from typing import Any, Optional


class SettingsManager:
    """Decky Loader settings persistence helper."""

    def __init__(self, name: str = "settings", settings_directory: str = "") -> None: ...
    def read(self) -> None: ...
    def commit(self) -> None: ...
    def getSetting(self, key: str, defaults: Any = None) -> Any: ...
    def setSetting(self, key: str, value: Any) -> None: ...
