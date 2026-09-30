"""Aggregations for the reports tab and CSV export."""

from __future__ import annotations

import csv
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from . import timeutil
from .db import Database, Entry

NO_PROJECT = "(bez projekta)"
NO_PROJECT_COLOR = "#9aa0a6"


def overlap(start: float, end: float, a: float, b: float) -> float:
    return max(0.0, min(end, b) - max(start, a))


@dataclass
class ProjectTotal:
    project_id: int | None
    name: str
    color: str
    seconds: float = 0.0
    billable_seconds: float = 0.0
    amount: float = 0.0


@dataclass
class Summary:
    start: float
    end: float
    total: float = 0.0
    billable: float = 0.0
    amount: float = 0.0
    entries: int = 0
    by_project: list[ProjectTotal] = field(default_factory=list)
    by_day: dict[date, float] = field(default_factory=dict)
    by_description: list[tuple[str, str, float]] = field(default_factory=list)


def summarize(db: Database, a: float, b: float, now: float | None = None) -> Summary:
    now = time.time() if now is None else now
    projects = db.project_map()
    summary = Summary(a, b)
    totals: dict[int | None, ProjectTotal] = {}
    by_day = {d: 0.0 for d in timeutil.days_in_range(a, b)}
    by_desc: dict[tuple[str, str], float] = defaultdict(float)

    for e in db.entries_between(a, b):
        end = e.end_ts if e.end_ts is not None else now
        secs = overlap(e.start_ts, end, a, b)
        if secs <= 0:
            continue
        p = projects.get(e.project_id) if e.project_id is not None else None
        pt = totals.get(e.project_id if p else None)
        if pt is None:
            pt = ProjectTotal(p.id, p.name, p.color) if p else ProjectTotal(None, NO_PROJECT, NO_PROJECT_COLOR)
            totals[pt.project_id] = pt
        pt.seconds += secs
        summary.total += secs
        summary.entries += 1
        if e.billable:
            pt.billable_seconds += secs
            summary.billable += secs
            if p and p.hourly_rate:
                money = secs / 3600 * p.hourly_rate
                pt.amount += money
                summary.amount += money
        by_desc[(e.description or "(bez opisa)", pt.name)] += secs
        for d in timeutil.days_in_range(max(e.start_ts, a), min(end, b)):
            ds, de = timeutil.day_bounds(d)
            if d in by_day:
                by_day[d] += overlap(max(e.start_ts, a), min(end, b), ds, de)

    summary.by_project = sorted(totals.values(), key=lambda t: t.seconds, reverse=True)
    summary.by_day = by_day
    summary.by_description = sorted(((d, p, s) for (d, p), s in by_desc.items()), key=lambda x: x[2],
                                    reverse=True)
    return summary


def app_display_name(exe: str) -> str:
    name = exe[:-4] if exe.lower().endswith(".exe") else exe
    return name or "nepoznato"


def app_usage(db: Database, a: float, b: float, only_tracked: bool = False) -> list[tuple[str, float]]:
    """Seconds per application in [a, b). only_tracked limits to time with a running timer."""
    totals: dict[str, float] = defaultdict(float)
    for act in db.activity_between(a, b):
        if only_tracked and act.entry_id is None:
            continue
        totals[app_display_name(act.app)] += overlap(act.start_ts, act.end_ts, a, b)
    return sorted(totals.items(), key=lambda x: x[1], reverse=True)


def title_usage(db: Database, a: float, b: float, app: str | None = None,
                limit: int = 50) -> list[tuple[str, str, float]]:
    """Seconds per (app, window title) in [a, b), optionally filtered by app display name."""
    totals: dict[tuple[str, str], float] = defaultdict(float)
    for act in db.activity_between(a, b):
        name = app_display_name(act.app)
        if app is not None and name != app:
            continue
        totals[(name, act.title or "(bez naslova)")] += overlap(act.start_ts, act.end_ts, a, b)
    rows = sorted(((n, t, s) for (n, t), s in totals.items()), key=lambda x: x[2], reverse=True)
    return rows[:limit]


def tracked_vs_active(db: Database, a: float, b: float) -> tuple[float, float]:
    """(seconds of computer activity, of which covered by a running timer)."""
    active = tracked = 0.0
    for act in db.activity_between(a, b):
        secs = overlap(act.start_ts, act.end_ts, a, b)
        active += secs
        if act.entry_id is not None:
            tracked += secs
    return active, tracked


def export_csv(db: Database, path: str, a: float, b: float, currency: str = "EUR",
               now: float | None = None) -> int:
    """Write entries overlapping [a, b) to a CSV file that Excel opens correctly. Returns row count."""
    now = time.time() if now is None else now
    projects = db.project_map()
    entries: list[Entry] = sorted(db.entries_between(a, b), key=lambda e: e.start_ts)
    # utf-8-sig + semicolon: Excel with European regional settings opens it without an import wizard.
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Datum", "Početak", "Kraj", "Trajanje (h:mm:ss)", "Sati (decimalno)", "Projekat",
                    "Opis", "Naplativo", f"Iznos ({currency})"])
        for e in entries:
            end = e.end_ts if e.end_ts is not None else now
            secs = end - e.start_ts
            p = projects.get(e.project_id) if e.project_id is not None else None
            amount = secs / 3600 * p.hourly_rate if (p and e.billable) else 0.0
            w.writerow([
                timeutil.fmt_date(e.start_ts),
                timeutil.fmt_time(e.start_ts),
                timeutil.fmt_time(end) if e.end_ts is not None else "(u toku)",
                timeutil.fmt_clock(secs),
                f"{secs / 3600:.2f}".replace(".", ","),
                p.name if p else "",
                e.description,
                "da" if e.billable else "ne",
                f"{amount:.2f}".replace(".", ","),
            ])
    return len(entries)
