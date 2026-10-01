"""Peščani sat skin: an hourglass next to the clock and an oasis that grows around the playlist.

The hourglass runs one 25-minute round (a pomodoro) of the task's time: the sand falls while the timer
runs, freezes in mid-air on pause, and when a round is full the glass turns over and starts again.
Every full round leaves a small dune beside the title.
"""

from __future__ import annotations

import math
import tkinter as tk

from . import skin
from .skin import px

ROUND = 25 * 60  # seconds per turn of the glass
SAND, SAND_DARK, GLASS, WOOD = "#e2b866", "#b98a3c", "#fffaf0", "#7a5230"


def rounds_done(seconds: float) -> int:
    return int(max(0.0, seconds) // ROUND)


def fill(seconds: float) -> float:
    """How much of the current round has run through (0: all sand on top, 1: all at the bottom)."""
    return (max(0.0, seconds) % ROUND) / ROUND


class Hourglass(tk.Canvas):
    """The glass itself. set() is called on every tick; on_flip is called when a round completes."""

    def __init__(self, master, on_flip=None, width: float = 30, height: float = 44):
        self.w, self.h = px(width), px(height)
        super().__init__(master, width=self.w, height=self.h, bg=skin.T.lcd_bg, highlightthickness=0)
        self.on_flip = on_flip
        self.seconds, self.running = 0.0, False
        self.rounds: int | None = None
        self.stream_offset = 0
        self.flipping = False
        self.draw()

    def set(self, seconds: float, running: bool) -> None:
        done = rounds_done(seconds)
        turned = self.rounds is not None and running and done > self.rounds
        self.seconds, self.running, self.rounds = seconds, running, done
        if self.flipping:
            return
        if turned:
            self.flip()
            return
        self.stream_offset = (self.stream_offset + 1) % 6
        self.draw()

    def flip(self) -> None:
        """Turn the glass over (a round is done) and play its sound."""
        self.flipping = True
        if self.on_flip:
            self.on_flip()
        frames = 12

        def step(i=1):
            if not self.winfo_exists():
                return
            if i > frames:
                self.flipping = False
                self.draw()
                return
            self.draw(angle=math.pi * i / frames, full_top=False)
            self.after(35, step, i + 1)

        step()

    def draw(self, angle: float = 0.0, full_top: bool | None = None) -> None:
        self.delete("all")
        w, h = self.w, self.h
        cx, cy = w / 2, h / 2
        ca, sa = math.cos(angle), math.sin(angle)

        def pt(x, y):  # rotate around the middle (for the flip)
            dx, dy = x - cx, y - cy
            return cx + dx * ca - dy * sa, cy + dx * sa + dy * ca

        def poly(points, **kw):
            return self.create_polygon([v for p in points for v in pt(*p)], **kw)

        cap = px(3)
        top, bottom = cap + px(1), h - cap - px(1)
        half = w / 2 - px(5)
        neck = px(1.6)
        bulb = (bottom - top) / 2
        f = 1.0 if full_top is False else fill(self.seconds)  # mid-turn: all the sand has run down

        def edge(y):  # half-width of the glass at height y
            d = abs(y - cy) / bulb
            return neck + (half - neck) * d

        # Sand left on top: a funnel down to the neck, its surface lower the less is left.
        left = 1 - f
        if left > 0.005:
            level = cy - bulb * math.sqrt(left)
            poly([(cx - edge(level), level), (cx + edge(level), level), (cx + neck, cy), (cx - neck, cy)],
                 fill=SAND, outline="")
        # Sand at the bottom: a pile rising from the base, a little mound in the middle.
        if f > 0.005:
            height = bulb * (1 - math.sqrt(1 - f))
            surface = bottom - height
            mound = min(px(4), height * 0.6)
            poly([(cx - edge(bottom), bottom), (cx + edge(bottom), bottom), (cx + edge(surface), surface),
                  (cx, surface - mound), (cx - edge(surface), surface)], fill=SAND, outline="", smooth=False)
            poly([(cx - edge(bottom) * 0.5, bottom), (cx, surface - mound * 0.6), (cx + edge(bottom) * 0.15, bottom)],
                 fill=SAND_DARK, outline="")
        # The falling stream: moving while the timer runs, frozen in mid-air on pause.
        if 0.005 < left and f > 0 and angle == 0 and self.seconds > 0:
            stream_end = bottom - bulb * (1 - math.sqrt(1 - f)) - px(2)
            line = self.create_line(*pt(cx, cy), *pt(cx, stream_end), fill=SAND_DARK, width=max(1, px(1.4)),
                                    dash=(2, 2))
            if self.running:
                self.itemconfigure(line, dashoffset=self.stream_offset)
        # Glass outline and the wooden caps.
        outline = [(cx - half, top), (cx + half, top), (cx + neck, cy), (cx + half, bottom), (cx - half, bottom),
                   (cx - neck, cy)]
        poly(outline, fill="", outline=GLASS, width=max(1, px(1.2)))
        for y in (top - cap, bottom):
            poly([(cx - half - px(3), y), (cx + half + px(3), y), (cx + half + px(3), y + cap),
                  (cx - half - px(3), y + cap)], fill=WOOD, outline="")
        for x in (cx - half - px(1.5), cx + half + px(1.5)):  # the posts
            self.create_line(*pt(x, top), *pt(x, bottom), fill=WOOD, width=max(1, px(1.4)))


def draw_dune(c: tk.Canvas, cx: float, base: float, width: float, color: str = SAND) -> None:
    """A small dune: a smooth hump with a shadowed lee side."""
    hgt = width * 0.38
    c.create_polygon(cx - width / 2, base, cx - width * 0.1, base - hgt, cx + width * 0.15, base - hgt * 0.9,
                     cx + width / 2, base, fill=color, outline="", smooth=True)
    c.create_polygon(cx - width * 0.1, base - hgt, cx + width * 0.15, base - hgt * 0.9, cx + width / 2, base,
                     cx + width * 0.05, base, fill=skin.blend(color, SAND_DARK, 0.45), outline="", smooth=True)


def draw_palm(c: tk.Canvas, x: float, base: float, size: float, lean: float = 1.0) -> None:
    """A palm tree: a curved trunk and a crown of drooping fronds."""
    top_x, top_y = x + lean * size * 0.25, base - size
    c.create_line(x, base, x + lean * size * 0.05, base - size * 0.5, top_x, top_y, fill="#a07c50",
                  width=max(2, size * 0.12), smooth=True, capstyle="round")
    for k in range(6):
        a = math.radians(-170 + k * 34)
        ex, ey = top_x + math.cos(a) * size * 0.55, top_y + math.sin(a) * size * 0.3 + size * 0.18
        mx, my = top_x + math.cos(a) * size * 0.3, top_y - size * 0.08
        c.create_line(top_x, top_y, mx, my, ex, ey, fill="#7aa260", width=max(2, size * 0.12), smooth=True,
                      capstyle="round")
    c.create_oval(top_x - size * 0.06, top_y - size * 0.02, top_x + size * 0.08, top_y + size * 0.1, fill="#8a6a40",
                  outline="")
