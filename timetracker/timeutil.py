"""Helpers for parsing and formatting dates, times and durations.

All timestamps are stored as POSIX epoch seconds (float) and displayed in local time.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta

DATE_FMT = "%d.%m.%Y"
TIME_FMT = "%H:%M"

WEEKDAYS = ["Ponedeljak", "Utorak", "Sreda", "Četvrtak", "Petak", "Subota", "Nedelja"]


def now() -> float:
    return time.time()


def fmt_clock(seconds: float) -> str:
    """Format as H:MM:SS (used for the running timer and entry durations)."""
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def fmt_hours(seconds: float) -> str:
    """Format as a compact human string, e.g. '2h 05m' or '12m'."""
    minutes = max(0, int(round(seconds / 60)))
    h, m = divmod(minutes, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def fmt_decimal_hours(seconds: float) -> str:
    return f"{seconds / 3600:.2f}"


def fmt_date(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime(DATE_FMT)


def fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime(TIME_FMT)


def fmt_day_header(d: date, today: date | None = None) -> str:
    today = today or date.today()
    if d == today:
        label = "Danas"
    elif d == today - timedelta(days=1):
        label = "Juče"
    else:
        label = WEEKDAYS[d.weekday()]
    return f"{label}, {d.strftime(DATE_FMT)}"


def parse_date(text: str) -> date:
    """Accept 30.09.2026, 30.9.2026, 30.09.2026. and 2026-09-30."""
    text = text.strip().rstrip(".")
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Neispravan datum: '{text}' (očekujem dd.mm.gggg)")


def parse_time(text: str) -> tuple[int, int]:
    """Accept 9:05, 09:05, 905, 0905, 9 and 9.05."""
    raw = text.strip().replace(".", ":")
    if not raw:
        raise ValueError("Vreme je prazno")
    if ":" in raw:
        hh, _, mm = raw.partition(":")
    elif raw.isdigit() and len(raw) in (3, 4):
        hh, mm = raw[:-2], raw[-2:]
    else:
        hh, mm = raw, "0"
    try:
        h, m = int(hh), int(mm)
    except ValueError:
        raise ValueError(f"Neispravno vreme: '{text}' (očekujem HH:MM)") from None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Neispravno vreme: '{text}'")
    return h, m


def to_ts(d: date, hm: tuple[int, int]) -> float:
    return datetime(d.year, d.month, d.day, hm[0], hm[1]).timestamp()


def parse_duration(text: str) -> float:
    """Parse '1:30', '1h 30m', '90m', '1.5' (hours) into seconds."""
    raw = text.strip().lower().replace(",", ".")
    if not raw:
        raise ValueError("Trajanje je prazno")
    if ":" in raw:
        parts = raw.split(":")
        nums = [int(p) for p in parts]
        while len(nums) < 3:
            nums.append(0)
        h, m, s = nums[:3]
        return h * 3600 + m * 60 + s
    if "h" in raw or "m" in raw:
        total = 0.0
        num = ""
        for ch in raw:
            if ch.isdigit() or ch == ".":
                num += ch
            elif ch == "h":
                total += float(num or 0) * 3600
                num = ""
            elif ch == "m":
                total += float(num or 0) * 60
                num = ""
        if num:
            total += float(num) * 60
        return total
    return float(raw) * 3600


def day_start(d: date) -> float:
    return datetime(d.year, d.month, d.day).timestamp()


def day_bounds(d: date) -> tuple[float, float]:
    return day_start(d), day_start(d + timedelta(days=1))


def ts_to_date(ts: float) -> date:
    return datetime.fromtimestamp(ts).date()


def period_bounds(kind: str, today: date | None = None) -> tuple[float, float]:
    """Return [start, end) epoch bounds for a named period."""
    today = today or date.today()
    if kind == "today":
        a, b = today, today + timedelta(days=1)
    elif kind == "yesterday":
        a, b = today - timedelta(days=1), today
    elif kind == "this_week":
        a = today - timedelta(days=today.weekday())
        b = a + timedelta(days=7)
    elif kind == "last_week":
        b = today - timedelta(days=today.weekday())
        a = b - timedelta(days=7)
    elif kind == "this_month":
        a = today.replace(day=1)
        b = (a + timedelta(days=32)).replace(day=1)
    elif kind == "last_month":
        b = today.replace(day=1)
        a = (b - timedelta(days=1)).replace(day=1)
    elif kind == "this_year":
        a = today.replace(month=1, day=1)
        b = a.replace(year=a.year + 1)
    else:
        raise ValueError(f"Nepoznat period: {kind}")
    return day_start(a), day_start(b)


def days_in_range(a: float, b: float) -> list[date]:
    """All local calendar days touched by [a, b)."""
    if b <= a:
        return []
    d = ts_to_date(a)
    last = ts_to_date(b - 1e-6)
    out = []
    while d <= last:
        out.append(d)
        d += timedelta(days=1)
    return out
