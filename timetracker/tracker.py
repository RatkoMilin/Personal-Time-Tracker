"""Background tracker thread.

Every few seconds it samples idle time and the foreground window, records app
activity, takes optional screenshots and detects idle periods and sleep. It
never touches the UI: it posts events to a queue that the UI thread drains.
"""

from __future__ import annotations

import os
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import platform_win
from .config import Settings
from .db import Database


@dataclass
class IdleEvent:
    """The user came back after being idle while the timer was running."""
    entry_id: int
    idle_start: float
    idle_end: float


@dataclass
class ReminderEvent:
    """The user has been active for a while without a running timer."""
    active_seconds: float


@dataclass
class LongTimerEvent:
    """The timer has been running for a long time (forgotten timer?)."""
    entry_id: int
    seconds: float


class Tracker(threading.Thread):
    def __init__(self, db: Database, settings: Settings, events: queue.Queue, screenshot_dir: Path,
                 platform=platform_win, clock=time.time, interval: float = 2.0):
        super().__init__(name="tracker", daemon=True)
        self.db = db
        self.settings = settings
        self.events = events
        self.screenshot_dir = Path(screenshot_dir)
        self.platform = platform
        self.clock = clock
        self.interval = interval
        self._stop = threading.Event()

        self._last_tick: float | None = None
        self._idle_since: float | None = None
        self._idle_entry_id: int | None = None
        self._span_id: int | None = None
        self._span_key: tuple | None = None
        self._span_end = 0.0
        self._active_without_timer = 0.0
        self._last_reminder = 0.0
        self._long_timer_notified: int | None = None
        self._last_screenshot = 0.0
        self._last_cleanup = 0.0
        self.current_app: tuple[str, str] | None = None
        self.error: str | None = None

    # ------------------------------------------------------------ lifecycle

    def run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.tick()
                self.error = None
            except Exception as exc:  # keep tracking even if one sample fails
                self.error = f"{type(exc).__name__}: {exc}"

    def stop(self) -> None:
        self._stop.set()

    # ----------------------------------------------------------------- core

    @property
    def idle_threshold(self) -> float:
        return max(1, int(self.settings["idle_minutes"])) * 60.0

    def tick(self, now: float | None = None) -> None:
        now = self.clock() if now is None else now
        prev = self._last_tick
        self._last_tick = now
        gap = (now - prev) if prev is not None else 0.0

        idle = self.platform.idle_seconds()
        window = self.platform.active_window()  # None: locked screen or nothing focused
        running = self.db.running_entry()
        threshold = self.idle_threshold

        self._detect_idle(now, prev, gap, idle, running, threshold)
        is_idle = idle >= threshold or self._idle_since is not None

        self._record_activity(now, prev, gap, window, running, is_idle)
        self._maybe_screenshot(now, running, is_idle)
        self._maybe_remind(now, gap, idle, running)
        self._maybe_long_timer(now, running)
        if now - self._last_cleanup > 6 * 3600:
            self._last_cleanup = now
            self.cleanup(now)

    def _detect_idle(self, now, prev, gap, idle, running, threshold) -> None:
        if not self.settings["idle_detection"] or running is None:
            self._idle_since = None
            return
        if self._idle_since is None:
            if prev is not None and gap >= threshold:
                # The loop did not run: the laptop was asleep or hibernating.
                self._start_idle(max(prev, running.start_ts), running.id)
            elif idle >= threshold:
                self._start_idle(max(now - idle, running.start_ts), running.id)
        if self._idle_since is not None and idle < threshold:
            # The user is back.
            if running.id == self._idle_entry_id and now - self._idle_since >= threshold:
                self.events.put(IdleEvent(running.id, self._idle_since, now))
            self._idle_since = None
            self._idle_entry_id = None

    def _start_idle(self, since: float, entry_id: int) -> None:
        self._idle_since = since
        self._idle_entry_id = entry_id
        # Samples taken before idle was confirmed are not real activity.
        self.db.trim_activity_after(since)
        self._close_span()

    def _record_activity(self, now, prev, gap, window, running, is_idle) -> None:
        self.current_app = window
        mode = self.settings["activity_mode"]
        if (mode == "off" or (mode == "timer" and running is None) or is_idle or window is None):
            self._close_span()
            return
        app, title = window
        entry_id = running.id if running else None
        key = (app, title[:500], entry_id)
        max_gap = self.interval * 3
        if key == self._span_key and self._span_id is not None and now - self._span_end <= max_gap:
            self.db.extend_activity(self._span_id, now)
        else:
            start = prev if prev is not None and gap <= max_gap else now
            self._span_id = self.db.add_activity(app, title[:500], start, now, entry_id)
            self._span_key = key
        self._span_end = now

    def _close_span(self) -> None:
        self._span_id = None
        self._span_key = None

    def _maybe_screenshot(self, now, running, is_idle) -> None:
        if not self.settings["screenshots"] or running is None or is_idle:
            return
        interval = max(1, int(self.settings["screenshot_interval_min"])) * 60
        if now - self._last_screenshot < interval:
            return
        self._last_screenshot = now
        stamp = datetime.fromtimestamp(now)
        path = self.screenshot_dir / stamp.strftime("%Y-%m-%d") / stamp.strftime("%H-%M-%S.jpg")
        if self.platform.take_screenshot(path):
            self.db.add_screenshot(now, str(path), running.id)

    def _maybe_remind(self, now, gap, idle, running) -> None:
        minutes = int(self.settings["reminder_minutes"])
        if minutes <= 0 or running is not None:
            self._active_without_timer = 0.0
            return
        if idle < 60 and gap < 60:
            self._active_without_timer += gap
        else:
            self._active_without_timer = 0.0
        if self._active_without_timer >= minutes * 60 and now - self._last_reminder >= minutes * 60:
            self._last_reminder = now
            self.events.put(ReminderEvent(self._active_without_timer))
            self._active_without_timer = 0.0

    def _maybe_long_timer(self, now, running) -> None:
        hours = int(self.settings["long_timer_hours"])
        if hours <= 0 or running is None or self._long_timer_notified == running.id:
            return
        if now - running.start_ts >= hours * 3600:
            self._long_timer_notified = running.id
            self.events.put(LongTimerEvent(running.id, now - running.start_ts))

    def cleanup(self, now: float) -> None:
        days = int(self.settings["screenshot_retention_days"])
        if days <= 0:
            return
        for shot in self.db.pop_screenshots_before(now - days * 86400):
            try:
                os.remove(shot.path)
            except OSError:
                pass
