"""Maslačak skin: a dandelion clock down the right side of the window and a meadow in the distance.

The flower is a 24-petal clock. At noon all petals are yellow; every hour two more (clockwise from the
top) turn into grey seeds, so at midnight it is a full seed head. Between 00:00 and 01:00 a click blows
it: the seeds fly off and the little gentleman on the stem slides down into the grass. After that two
yellow petals come back every hour, and the gentleman returns at noon. Seeds nobody blew by 01:00 are
taken by the wind.
"""

from __future__ import annotations

import math
import random
import tkinter as tk
from datetime import datetime

from . import skin
from .skin import px

PETALS = 24
YELLOW, SEED, NONE = "y", "s", ""


def state(now: datetime, blown_day: str) -> tuple[list[str], bool, bool]:
    """(petals, gentleman present, can be blown) for a moment; blown_day is the date it was last blown."""
    h = now.hour
    if h >= 12:
        grey = 2 * (h - 12)
        return [SEED if i < grey else YELLOW for i in range(PETALS)], True, False
    if h == 0 and blown_day != now.date().isoformat():
        return [SEED] * PETALS, True, True
    yellow = 2 * h
    return [YELLOW if i < yellow else NONE for i in range(PETALS)], False, False


def field_yellow(now: datetime) -> bool:
    """The far meadow is grey seed heads in the morning and yellow from noon to midnight."""
    return now.hour >= 12


# ------------------------------------------------------------------ drawing


def draw_field(c: tk.Canvas, x0: float, x1: float, y0: float, y1: float, yellow: bool, seed: int = 3,
               tags: str = "field") -> None:
    """A meadow seen from afar: green bands with tiny dandelions, smaller towards the horizon."""
    steps = 8
    for i in range(steps):
        a, b = y0 + (y1 - y0) * i / steps, y0 + (y1 - y0) * (i + 1) / steps
        c.create_rectangle(x0, a, x1, b + 1, fill=skin.blend("#d8edc6", "#a9d38c", i / (steps - 1)), outline="",
                           tags=tags)
    rnd = random.Random(seed)
    flower = ("#f4c430", "#e0a800") if yellow else ("#d6d6d6", "#a8a8a8")
    for row in range(4):
        y = y0 + (y1 - y0) * (0.18 + row * 0.24)
        r = px(0.8 + row * 0.55)
        x = x0 + rnd.uniform(0, px(9))
        while x < x1:
            yy = y + rnd.uniform(-px(2), px(2))
            c.create_line(x, yy, x, yy + r * 2.5, fill="#7fae62", tags=tags)
            c.create_oval(x - r, yy - r, x + r, yy + r, fill=flower[0], outline=flower[1] if r > px(1.5) else "",
                          tags=tags)
            x += rnd.uniform(px(7), px(15)) + row * px(2)


def petal_points(cx: float, cy: float, angle: float, r0: float, r1: float, width: float) -> list[float]:
    """A narrow ray floret with a toothed tip, pointing outwards at angle (radians)."""
    ca, sa = math.cos(angle), math.sin(angle)

    def at(r, side):
        return cx + ca * r - sa * side, cy + sa * r + ca * side

    pts = [at(r0, 0), at(r0 + (r1 - r0) * 0.3, -width / 2), at(r1 - px(1.5), -width / 2), at(r1, -width / 4),
           at(r1 - px(1), 0), at(r1, width / 4), at(r1 - px(1.5), width / 2), at(r0 + (r1 - r0) * 0.3, width / 2)]
    return [v for p in pts for v in p]


def draw_seed(c: tk.Canvas, cx: float, cy: float, angle: float, r: float, tags) -> None:
    """A dandelion seed: thin stalk from the center and a small parachute (pappus) at its end."""
    ca, sa = math.cos(angle), math.sin(angle)
    ex, ey = cx + ca * r, cy + sa * r
    c.create_line(cx + ca * px(4), cy + sa * px(4), ex, ey, fill="#b9b9b9", tags=tags)
    for k in range(-3, 4):
        a = angle + k * 0.32
        c.create_line(ex, ey, ex + math.cos(a) * px(6), ey + math.sin(a) * px(6), fill="#d2d2d2", tags=tags)
    c.create_oval(ex - 1, ey - 1, ex + 1, ey + 1, fill="#9a9a9a", outline="", tags=tags)


def draw_gentleman(c: tk.Canvas, sx: float, sy: float, tags="man") -> None:
    """The little gentleman holding the stem (at x=sx) with his left hand and left leg.

    He faces us, so his left side is towards the stem on our right. Black top hat, long curled moustache,
    short golden ornamental waistcoat over a white shirt.
    """
    ink, skin_c = "#2b2b2b", "#f1cfb0"
    bx = sx - px(11)  # body axis
    top = sy - px(22)
    lw = max(1, px(1.6))
    # Legs: left leg bent with the foot hooked on the stem, right leg hanging.
    c.create_line(bx + px(2), top + px(27), bx + px(7), top + px(33), sx - px(1), top + px(31), fill="#3a3540",
                  width=max(2, px(2.4)), capstyle="round", joinstyle="round", tags=tags)
    c.create_line(bx - px(2), top + px(27), bx - px(3), top + px(35), bx - px(5), top + px(41), fill="#3a3540",
                  width=max(2, px(2.4)), capstyle="round", joinstyle="round", tags=tags)
    c.create_oval(sx - px(3), top + px(29), sx + px(1), top + px(33), fill=ink, outline="", tags=tags)
    c.create_oval(bx - px(8), top + px(40), bx - px(3), top + px(43), fill=ink, outline="", tags=tags)
    # Arms: the left one reaches up to the stem, the right one waves.
    c.create_line(bx + px(3), top + px(15), bx + px(7), top + px(10), sx - px(1), top + px(7), fill="#f7f4ee",
                  width=max(2, px(2.2)), capstyle="round", joinstyle="round", tags=tags)
    c.create_line(bx - px(3), top + px(15), bx - px(8), top + px(18), bx - px(11), top + px(13), fill="#f7f4ee",
                  width=max(2, px(2.2)), capstyle="round", joinstyle="round", tags=tags)
    for hx, hy in ((sx - px(1), top + px(7)), (bx - px(11), top + px(13))):
        c.create_oval(hx - px(1.6), hy - px(1.6), hx + px(1.6), hy + px(1.6), fill=skin_c, outline="", tags=tags)
    # Body: white shirt, short golden waistcoat with little ornaments, dark trousers.
    c.create_rectangle(bx - px(3.5), top + px(21), bx + px(3.5), top + px(28), fill="#3a3540", outline="",
                       tags=tags)
    c.create_polygon(bx - px(4), top + px(13), bx + px(4), top + px(13), bx + px(4), top + px(22),
                     bx - px(4), top + px(22), fill="#f7f4ee", outline=ink, width=1, tags=tags)
    c.create_polygon(bx - px(4), top + px(14), bx - px(1), top + px(14), bx, top + px(20), bx + px(1), top + px(14),
                     bx + px(4), top + px(14), bx + px(4), top + px(21), bx, top + px(22.5), bx - px(4),
                     top + px(21), fill="#d4a017", outline="#8a6510", width=1, tags=tags)
    for oy in (16.5, 19):
        for ox in (-2.6, 2.6):
            c.create_oval(bx + px(ox) - 1, top + px(oy) - 1, bx + px(ox) + 1, top + px(oy) + 1, fill="#fff3c4",
                          outline="", tags=tags)
    # Head, moustache and top hat.
    hr = px(4.5)
    hy = top + px(8)
    c.create_oval(bx - hr, hy - hr, bx + hr, hy + hr, fill=skin_c, outline="#c9a184", tags=tags)
    c.create_oval(bx - px(2.2), hy - px(1), bx - px(1.2), hy, fill=ink, outline="", tags=tags)
    c.create_oval(bx + px(1.2), hy - px(1), bx + px(2.2), hy, fill=ink, outline="", tags=tags)
    for d in (-1, 1):  # long moustache curling up at the ends
        c.create_line(bx, hy + px(2), bx + d * px(3), hy + px(2.6), bx + d * px(6), hy + px(2), bx + d * px(7),
                      hy + px(0.4), bx + d * px(6), hy - px(0.6), bx + d * px(5.2), hy + px(0.4), fill=ink,
                      width=lw, smooth=True, capstyle="round", tags=tags)
    c.create_rectangle(bx - px(7), hy - hr - px(0.5), bx + px(7), hy - hr + px(1), fill=ink, outline="", tags=tags)
    c.create_rectangle(bx - px(4), hy - hr - px(9), bx + px(4), hy - hr, fill=ink, outline="", tags=tags)
    c.create_rectangle(bx - px(4), hy - hr - px(2.5), bx + px(4), hy - hr - px(1.2), fill="#5a5560", outline="",
                       tags=tags)


class DandelionColumn(tk.Canvas):
    """The flower, its stem and the gentleman, drawn in a strip down the right side of the window.

    bands() returns the background gradient stops [(y, color), ...] so the strip matches the sections
    on its left. on_blow(day) is called when the seeds are blown (to remember it for the night).
    """

    WIDTH = 92

    def __init__(self, master, bands, blown_day, on_blow, clock=datetime.now):
        super().__init__(master, width=px(self.WIDTH), bg=skin.T.body, highlightthickness=0, cursor="")
        self.bands, self.blown_day, self.on_blow, self.clock = bands, blown_day, on_blow, clock
        self.key = None
        self.animating = False
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Button-1>", self._clicked)

    # geometry
    def head(self) -> tuple[float, float, float]:
        w = self.winfo_width()
        r = px(34)
        return w * 0.52, px(6) + r, r

    def stem_x(self, y: float) -> float:
        cx = self.head()[0]
        return cx + math.sin(y / px(40)) * px(3)

    def man_y(self) -> float:
        return max(self.head()[1] + px(70), self.winfo_height() * 0.5)

    def field_top(self) -> float:
        return self.winfo_height() - px(34)

    def current(self) -> tuple:
        now = self.clock()
        petals, man, can_blow = state(now, self.blown_day())
        return tuple(petals), man, can_blow, field_yellow(now), tuple(self.bands()), self.winfo_height()

    def refresh(self) -> None:
        """Redraw when the clock moved the flower on (called from the window's tick)."""
        if self.animating:
            return
        key = self.current()
        if key == self.key:
            return
        came_back = self.key is not None and key[1] and not self.key[1]
        self.draw()
        if came_back:
            self._man_climbs_up()

    def draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10 or h < 10:
            return
        self.key = self.current()
        petals, man, can_blow, yellow = self.key[:4]
        stops = self.bands() or [(0, skin.T.body), (h, skin.T.body)]
        for y in range(0, h, 2):
            self.create_line(0, y, w, y, fill=self._color_at(stops, y), width=2)
        cx, cy, r = self.head()
        ft = self.field_top()
        stem = [(self.stem_x(y), y) for y in range(int(cy), int(h) + px(4), px(6))]
        self.create_line(stem, fill="#5f8f44", width=max(3, px(4)), smooth=True, capstyle="round")
        self.create_line([(x - px(1), y) for x, y in stem], fill="#8fbf6a", width=1, smooth=True)
        for a in (-0.9, -0.4, 0.4, 0.9):  # bracts curling down under the head
            self.create_line(cx + math.sin(a) * px(6), cy + px(6), cx + math.sin(a) * px(11), cy + px(13),
                             cx + math.sin(a) * px(13), cy + px(11), fill="#5f8f44", width=max(1, px(1.6)),
                             smooth=True)
        self._draw_head(petals)
        self.config(cursor="hand2" if can_blow else "")
        if man:
            draw_gentleman(self, self.stem_x(self.man_y()), self.man_y())
        draw_field(self, 0, w, ft, h, yellow, seed=11)

    @staticmethod
    def _color_at(stops, y) -> str:
        for (y0, c0), (y1, c1) in zip(stops, stops[1:]):
            if y0 <= y <= y1:
                return skin.blend(c0, c1, (y - y0) / max(1, y1 - y0))
        return stops[-1][1] if y > stops[-1][0] else stops[0][1]

    def _draw_head(self, petals) -> None:
        cx, cy, r = self.head()
        seeds = [i for i, p in enumerate(petals) if p == SEED]
        if seeds:  # the faint grey puff of a seed head
            self.create_oval(cx - r * 0.8, cy - r * 0.8, cx + r * 0.8, cy + r * 0.8, fill="#f3f1f1", outline="")
        for i, kind in enumerate(petals):
            a = -math.pi / 2 + i * 2 * math.pi / PETALS
            if kind == YELLOW:
                self.create_polygon(petal_points(cx, cy, a, px(6), r, px(6)), fill="#f6c71c", outline="#d9a400",
                                    tags=("petal", f"petal{i}"))
            elif kind == SEED:
                draw_seed(self, cx, cy, a, r - px(6), ("seed", f"seed{i}"))
        yellow = sum(p == YELLOW for p in petals)
        disc = "#e8ac0c" if yellow else "#9c8a4a"
        self.create_oval(cx - px(7), cy - px(7), cx + px(7), cy + px(7), fill=disc, outline="#b07c00" if yellow
                         else "#6e6030")
        if not yellow:  # the bare receptacle: little pits where the seeds sat
            rnd = random.Random(5)
            for _ in range(12):
                a, d = rnd.uniform(0, 6.28), rnd.uniform(0, px(5))
                x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
                self.create_oval(x - 0.8, y - 0.8, x + 0.8, y + 0.8, fill="#6e6030", outline="")

    # ------------------------------------------------------------ blowing

    def _clicked(self, event) -> None:
        cx, cy, r = self.head()
        if math.hypot(event.x - cx, event.y - cy) <= r + px(4):
            self.blow()

    def blow(self) -> bool:
        """Blow the seed head (only between 00:00 and 01:00 before it was blown)."""
        if self.animating or not self.current()[2]:
            return False
        self.animating = True
        self.on_blow(self.clock().date().isoformat())
        rnd = random.Random()
        flights = {i: (rnd.uniform(-2.2, -0.5) * skin.S, rnd.uniform(-1.8, 0.2) * skin.S, rnd.uniform(0, 6.28))
                   for i in range(PETALS)}
        ft = self.field_top()
        self.tag_raise("field")
        frames = 60

        def step(i=0):
            if not self.winfo_exists():
                return
            if i >= frames:
                self.animating = False
                self.draw()
                return
            for k, (vx, vy, phase) in flights.items():
                self.move(f"seed{k}", vx, vy + math.sin(i / 4 + phase) * 0.8)
            if self.coords("man") and self.bbox("man")[1] < ft + px(6):
                self.move("man", 0, 2.5 * skin.S)  # slides down the stem into the grass
            self.tag_raise("field")
            self.after(40, step, i + 1)

        step()
        return True

    def _man_climbs_up(self) -> None:
        """At noon the gentleman climbs back up from the grass."""
        if not self.coords("man"):
            return
        start = self.field_top() + px(10) - (self.man_y() - px(22))
        self.move("man", 0, start)
        self.tag_raise("field")
        frames = 40
        self.animating = True

        def step(i=0):
            if not self.winfo_exists():
                return
            if i >= frames:
                self.animating = False
                return
            self.move("man", 0, -start / frames)
            self.tag_raise("field")
            self.after(40, step, i + 1)

        step()


class FieldStrip(tk.Canvas):
    """The far meadow along the bottom of the window (left of the dandelion strip)."""

    def __init__(self, master, clock=datetime.now):
        super().__init__(master, height=px(34), bg=skin.T.body, highlightthickness=0)
        self.clock = clock
        self.yellow = None
        self.bind("<Configure>", lambda e: self.draw())

    def refresh(self) -> None:
        if field_yellow(self.clock()) != self.yellow:
            self.draw()

    def draw(self) -> None:
        self.delete("all")
        self.yellow = field_yellow(self.clock())
        draw_field(self, 0, self.winfo_width(), 0, self.winfo_height(), self.yellow, seed=4)


class GradientStrip(tk.Canvas):
    """A thin strip blending one section color into the next."""

    def __init__(self, master, top: str, bottom: str, height: float = 10):
        super().__init__(master, height=px(height), bg=top, highlightthickness=0)
        self.top, self.bottom = top, bottom
        self.bind("<Configure>", lambda e: self.draw())

    def draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        for y in range(h):
            self.create_line(0, y, w, y, fill=skin.blend(self.top, self.bottom, y / max(1, h - 1)))
