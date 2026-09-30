"""Data directory and user settings (stored as JSON next to the database)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import APP_ID

DEFAULTS: dict = {
    # Idle detection: prompt to discard time when there was no keyboard/mouse input.
    "idle_detection": True,
    "idle_minutes": 5,
    # App/window tracking: "off", "timer" (only while the timer runs) or "always".
    "activity_mode": "timer",
    # Screenshots (Time Doctor style). Off by default: they are a privacy risk
    # and mostly useless for personal tracking.
    "screenshots": False,
    "screenshot_interval_min": 10,
    "screenshot_retention_days": 30,
    # Remind to start the timer after N minutes of activity without one (0 = off).
    "reminder_minutes": 10,
    # Show a notification when the timer has been running for N hours (0 = off).
    "long_timer_hours": 4,
    "minimize_to_tray": True,
    "start_minimized": False,
    "autostart": False,
    "currency": "EUR",
    "daily_goal_hours": 8,
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
                if key in DEFAULTS and isinstance(value, type(DEFAULTS[key])):
                    self._values[key] = value
                elif key in DEFAULTS and isinstance(DEFAULTS[key], float) and isinstance(value, int):
                    self._values[key] = float(value)

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

    def as_dict(self) -> dict:
        return dict(self._values)
