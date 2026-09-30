"""Background idle watcher.

Every few seconds it checks how long there has been no keyboard/mouse input and
whether the laptop was asleep. While the timer runs it posts IdleStart as soon
as the idle limit is reached (so a reminder can pop up right away) and IdleEnd
when the user is back. The UI thread drains the queue.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass

from . import platform_win
from .config import Settings
from .db import Database


@dataclass
class IdleStart:
    """No input for the idle limit (or the laptop slept) while the timer ran."""
    entry_id: int
    idle_start: float


@dataclass
class IdleEnd:
    """The user is back after an IdleStart."""
    entry_id: int
    idle_start: float
    idle_end: float


class Tracker(threading.Thread):
    def __init__(self, db: Database, settings: Settings, events: queue.Queue, platform=platform_win,
                 clock=time.time, interval: float = 2.0):
        super().__init__(name="tracker", daemon=True)
        self.db = db
        self.settings = settings
        self.events = events
        self.platform = platform
        self.clock = clock
        self.interval = interval
        self._stop = threading.Event()
        self._last_tick: float | None = None
        self._idle_since: float | None = None
        self._idle_entry_id: int | None = None

    def run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.tick()
            except Exception:  # a failed sample must not kill the thread
                pass

    def stop(self) -> None:
        self._stop.set()

    def tick(self, now: float | None = None) -> None:
        now = self.clock() if now is None else now
        prev, self._last_tick = self._last_tick, now
        minutes = int(self.settings["idle_minutes"])
        running = self.db.running_entry()
        if minutes <= 0 or running is None:
            self._idle_since = None
            return
        threshold = minutes * 60.0
        idle = self.platform.idle_seconds()
        if self._idle_since is None:
            since = None
            if prev is not None and now - prev >= threshold:
                since = max(prev, running.start_ts)  # the loop did not run: the laptop was asleep
            elif idle >= threshold:
                since = max(now - idle, running.start_ts)
            if since is not None:
                self._idle_since, self._idle_entry_id = since, running.id
                self.events.put(IdleStart(running.id, since))
        if self._idle_since is not None and idle < threshold:
            self.events.put(IdleEnd(self._idle_entry_id, self._idle_since, now))
            self._idle_since = None
