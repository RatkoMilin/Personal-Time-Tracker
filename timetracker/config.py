"""Data directory and user settings (stored as JSON next to the database)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import APP_ID

DEFAULTS: dict = {
    # Ask what to do with time without keyboard/mouse input (0 minutes = off).
    "idle_minutes": 5,
    "always_on_top": False,
    "skin": "matrix",
    "sounds": True,
    "show_playlist": True,
    # Minimizing shows a small see-through bar at the bottom of the screen instead of hiding the app.
    "mini_bar": True,
    # Release builds check GitHub for a newer version and install it by themselves.
    "auto_update": True,
    "window_pos": "",
    # Productivity meter: extra words that mark a window as productive / distracting, on top of the
    # built-in rules (Google Docs, Word, ... vs. YouTube, Facebook, Instagram, shopping sites).
    "extra_productive": [],
    "extra_distracting": [],
}


def data_dir() -> Path:
    override = os.environ.get("PTT_DATA_DIR")
    if override:
        path = Path(override)
    elif sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        path = Path(base) / APP_ID
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        path = Path(base) / "personal-time-tracker"
    path.mkdir(parents=True, exist_ok=True)
    return path


class Settings:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "settings.json")
        self._values = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                stored = json.load(f)
        except (OSError, ValueError):
            return
        if isinstance(stored, dict):
            for key, value in stored.items():
                if key in DEFAULTS and type(value) is type(DEFAULTS[key]):
                    self._values[key] = value

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._values, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def __getitem__(self, key: str):
        return self._values[key]

    def __setitem__(self, key: str, value) -> None:
        if key not in DEFAULTS:
            raise KeyError(key)
        self._values[key] = value

    def update(self, values: dict) -> None:
        for key, value in values.items():
            self[key] = value
        self.save()
