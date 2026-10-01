"""Productive / neutral / distracting classification of the foreground window, and daily totals.

Only the category and a short label (the matched rule, or the program name) are stored,
never the window title, so document names, e-mail subjects and pages stay private.
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import dataclass, field

from .db import Database

PRODUCTIVE, NEUTRAL, DISTRACTING = "productive", "neutral", "distracting"
CATEGORIES = (PRODUCTIVE, NEUTRAL, DISTRACTING)

# Each rule: (label, programs (exe names), title patterns). Titles are matched case-insensitively as
# regular expressions; browsers put the site name in the title, e.g. "Cat video - YouTube - Google Chrome".
DEFAULT_PRODUCTIVE = [
    ("Google Docs", [], [r"google docs", r"google dokumenti"]),
    ("Google Sheets", [], [r"google sheets", r"google tabele"]),
    ("Google Slides", [], [r"google slides", r"google prezentacije"]),
    ("Word", ["winword.exe"], [r"microsoft word", r"\bword online\b", r"- word$"]),
    ("Excel", ["excel.exe"], [r"microsoft excel", r"\bexcel online\b"]),
    ("PowerPoint", ["powerpnt.exe"], [r"microsoft powerpoint", r"\bpowerpoint online\b"]),
    ("OneNote", ["onenote.exe", "onenoteim.exe"], [r"\bonenote\b"]),
    ("LibreOffice", ["soffice.exe", "soffice.bin", "swriter.exe", "scalc.exe", "simpress.exe"], [r"libreoffice"]),
    ("Notion", ["notion.exe"], [r"\bnotion\b"]),
    ("Obsidian", ["obsidian.exe"], []),
    ("Overleaf", [], [r"\boverleaf\b"]),
]
DEFAULT_DISTRACTING = [
    ("YouTube", [], [r"\byoutube\b"]),
    ("Facebook", [], [r"\bfacebook\b", r"\bmessenger\b"]),
    ("Instagram", [], [r"\binstagram\b"]),
    ("TikTok", [], [r"\btiktok\b"]),
    ("Netflix", [], [r"\bnetflix\b"]),
    ("Reddit", [], [r"\breddit\b"]),
    ("X / Twitter", [], [r"\btwitter\b", r"/ x$"]),
    ("Kupovina", [], [r"\bamazon\b", r"\bebay\b", r"aliexpress", r"\btemu\b", r"\bshein\b", r"\bzalando\b",
                      r"\betsy\b", r"kupujemprodajem", r"\bananas\b", r"\bgigatron\b", r"\bwinwin\b",
                      r"\bshop\b", r"webshop", r"e-shop", r"online prodavnica", r"\bkorpa\b", r"\bcart\b"]),
]

_BROWSER_SUFFIX = re.compile(r"\s+[-—]\s+(google chrome|mozilla firefox|microsoft​? edge|opera|brave|vivaldi)$",
                             re.IGNORECASE)


def _compile(rules: list) -> list[tuple[str, set[str], list[re.Pattern]]]:
    out = []
    for label, programs, patterns in rules:
        out.append((label, {p.lower() for p in programs}, [re.compile(p, re.IGNORECASE) for p in patterns]))
    return out


def program_name(exe: str) -> str:
    return exe[:-4] if exe.lower().endswith(".exe") else (exe or "nepoznato")


def _extra(words) -> list:
    """Simple user words from settings.json: "figma" matches titles, "figma.exe" the program."""
    rules = []
    for w in words or ():
        w = str(w).strip()
        if w:
            exe = [w] if w.lower().endswith(".exe") else []
            rules.append((program_name(w), exe, [] if exe else [re.escape(w)]))
    return rules


class Classifier:
    def __init__(self, extra_productive=(), extra_distracting=()):
        # Distracting rules win: "Word tips - YouTube" is YouTube, not Word.
        self.rules = ([(DISTRACTING, r) for r in _compile(_extra(extra_distracting) + DEFAULT_DISTRACTING)]
                      + [(PRODUCTIVE, r) for r in _compile(_extra(extra_productive) + DEFAULT_PRODUCTIVE)])

    def classify(self, exe: str, title: str) -> tuple[str, str]:
        """Return (category, label) for a foreground window."""
        exe_l = (exe or "").lower()
        title = _BROWSER_SUFFIX.sub("", (title or "").strip())
        for category, (label, programs, patterns) in self.rules:
            if exe_l in programs or any(p.search(title) for p in patterns):
                return category, label
        return NEUTRAL, program_name(exe)


@dataclass
class DaySummary:
    seconds: dict[str, float] = field(default_factory=lambda: {c: 0.0 for c in CATEGORIES})
    labels: dict[str, list[tuple[str, float]]] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return sum(self.seconds.values())

    def share(self, category: str) -> float:
        return self.seconds[category] / self.total if self.total else 0.0


def summarize(db: Database, a: float, b: float, now: float | None = None) -> DaySummary:
    """Seconds per category (and per label inside each category) of computer activity in [a, b)."""
    now = time.time() if now is None else now
    per_label: dict[str, dict[str, float]] = {c: defaultdict(float) for c in CATEGORIES}
    out = DaySummary()
    for start, end, category, label in db.activity_between(a, b):
        secs = max(0.0, min(end, b, now) - max(start, a))
        if category not in out.seconds:
            category = NEUTRAL
        out.seconds[category] += secs
        per_label[category][label] += secs
    out.labels = {c: sorted(per_label[c].items(), key=lambda x: x[1], reverse=True) for c in CATEGORIES}
    return out
