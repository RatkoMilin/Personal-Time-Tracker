"""Totals and CSV export."""

from __future__ import annotations

import csv
import time

from . import timeutil
from .db import Database


def overlap(start: float, end: float, a: float, b: float) -> float:
    return max(0.0, min(end, b) - max(start, a))


def total_between(db: Database, a: float, b: float, now: float | None = None) -> float:
    """Tracked seconds inside [a, b), counting the running entry up to now."""
    now = time.time() if now is None else now
    return sum(overlap(e.start_ts, e.end_ts if e.end_ts is not None else now, a, b)
               for e in db.entries_between(a, b))


def export_csv(db: Database, path: str, a: float, b: float, now: float | None = None) -> int:
    """Write entries overlapping [a, b) to a CSV that Excel opens directly. Returns the row count."""
    now = time.time() if now is None else now
    projects = db.project_names()
    entries = db.entries_between(a, b)
    # utf-8-sig + semicolon + decimal comma: opens in Excel with European regional settings.
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Datum", "Od", "Do", "Trajanje", "Sati", "Projekat", "Zadatak"])
        for e in entries:
            end = e.end_ts if e.end_ts is not None else now
            secs = end - e.start_ts
            w.writerow([
                timeutil.fmt_date(e.start_ts),
                timeutil.fmt_time(e.start_ts),
                timeutil.fmt_time(end) if e.end_ts is not None else "(u toku)",
                timeutil.fmt_clock(secs),
                f"{secs / 3600:.2f}".replace(".", ","),
                projects.get(e.project_id, ""),
                e.description,
            ])
    return len(entries)
