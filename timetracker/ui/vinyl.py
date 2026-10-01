"""Lofi skin: a record player next to the clock.

The record spins while the timer runs; the tonearm travels from the outer edge to the label over one
45-minute side of the task's time, then the record is turned over (side A, B, A, ...). On pause the
needle lifts and the record stops; when the timer stops the arm goes back to its rest.
"""

from __future__ import annotations

import math
import tkinter as tk

from . import skin
from .skin import px

SIDE = 45 * 60  # seconds per side of the record
WOOD, WOOD_DARK, VINYL, GROOVE = "#9a6a48", "#6e4a33", "#15121c", "#2a2436"
LABELS = ("#f2a65a", "#e8899a")  # side A amber, side B pink


def side(seconds: float) -> int:
    """0 for side A, 1 for side B, 2 for A again, ..."""
    return int(max(0.0, seconds) // SIDE)


def progress(seconds: float) -> float:
    """How far the needle has travelled on the current side (0 at the edge, 1 at the label)."""
    return (max(0.0, seconds) % SIDE) / SIDE


class Turntable(tk.Canvas):
    """set(seconds, state) on every tick; the record spins on its own while playing."""

    def __init__(self, master, on_flip=None, width: float = 52, height: float = 44):
        self.w, self.h = px(width), px(height)
        super().__init__(master, width=self.w, height=self.h, bg=skin.T.lcd_bg, highlightthickness=0)
        self.on_flip = on_flip
        self.seconds, self.state = 0.0, "stopped"
        self.sides: int | None = None
        self.angle = 0.0
        self._spinning = False
        self.draw()

    def set(self, seconds: float, state: str) -> None:
        now = side(seconds)
        if self.sides is not None and state == "playing" and now > self.sides and self.on_flip:
            self.on_flip()  # a side is done: the record is turned over
        self.seconds, self.state, self.sides = seconds, state, now
        if state == "playing" and not self._spinning:
            self._spinning = True
            self._spin()
        self.draw()

    def _spin(self) -> None:
        if not self.winfo_exists():
            return
        if self.state != "playing":
            self._spinning = False
            return
        self.angle = (self.angle + 0.35) % (2 * math.pi)
        self.draw()
        self.after(70, self._spin)

    def draw(self) -> None:
        self.delete("all")
        w, h = self.w, self.h
        skin.round_rect(self, 1, 1, w - 1, h - 1, px(4), fill=WOOD, outline=WOOD_DARK)
        cx, cy, r = w * 0.4, h / 2, h * 0.42
        self.create_oval(cx - r - px(1), cy - r - px(1), cx + r + px(1), cy + r + px(1), fill="#3a3346", outline="")
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=VINYL, outline="")
        for k in (0.86, 0.72, 0.58):
            self.create_oval(cx - r * k, cy - r * k, cx + r * k, cy + r * k, outline=GROOVE)
        self.create_arc(cx - r * 0.9, cy - r * 0.9, cx + r * 0.9, cy + r * 0.9, start=110, extent=40, style="arc",
                        outline="#4a4260")  # a static shine on the vinyl
        lr = r * 0.34
        label = LABELS[side(self.seconds) % 2]
        self.create_oval(cx - lr, cy - lr, cx + lr, cy + lr, fill=label, outline="")
        mx, my = cx + math.cos(self.angle) * lr * 0.62, cy + math.sin(self.angle) * lr * 0.62
        self.create_oval(mx - px(1.4), my - px(1.4), mx + px(1.4), my + px(1.4), fill="#3a2a1a", outline="")
        self.create_oval(cx - px(1), cy - px(1), cx + px(1), cy + px(1), fill="#e8e0d0", outline="")
        # Tonearm: pivot top right; on the record while playing or paused, at rest when stopped.
        pivot = (w - px(7), px(7))
        self.create_oval(pivot[0] - px(3), pivot[1] - px(3), pivot[0] + px(3), pivot[1] + px(3), fill="#c9c2b6",
                         outline="#6e6a64")
        if self.state == "stopped":
            needle = (w - px(7), h - px(8))
        else:
            a = math.radians(20)  # the needle meets the record a little below the right-hand side
            rr = r * (0.95 - 0.55 * progress(self.seconds))
            needle = (cx + math.cos(a) * rr, cy + math.sin(a) * rr)
        lift = px(2) if self.state == "paused" else 0
        if lift:  # the arm's shadow on the record shows it is raised
            self.create_line(*pivot, needle[0], needle[1], fill="#2a2436", width=max(1, px(1.5)))
        self.create_line(pivot[0], pivot[1], needle[0] - lift, needle[1] - lift, fill="#d8d2c6",
                         width=max(1, px(1.6)), capstyle="round")
        hx, hy = needle[0] - lift, needle[1] - lift
        self.create_rectangle(hx - px(1.6), hy - px(1.6), hx + px(1.6), hy + px(1.6), fill="#e8e0d0", outline="")
