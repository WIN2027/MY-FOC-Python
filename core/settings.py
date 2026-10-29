# -*- coding: utf-8 -*-
"""控制中心设置：统一使用项目目录下的 settings.ini。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings

from .theme import APP_DIR

SETTINGS_PATH = APP_DIR / "settings.ini"


class AppSettings:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else SETTINGS_PATH
        self.qsettings = QSettings(str(self.path), QSettings.IniFormat)

    def get(self, key: str, default: Any = None, value_type=None):
        if value_type is not None:
            return self.qsettings.value(key, default, value_type)
        return self.qsettings.value(key, default)

    def set(self, key: str, value: Any):
        self.qsettings.setValue(key, value)

    def sync(self):
        self.qsettings.sync()

    def remove(self, key: str):
        self.qsettings.remove(key)
