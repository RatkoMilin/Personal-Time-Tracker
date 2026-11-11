"""Seven skins with a little scene next to the clock that follows the task's time.

Suši: a conveyor belt runs while you work, and a plate lands on the stack every 10 minutes.
Lale: a field of tulips whose buds open one by one over an hour of the task and close on pause;
  every full hour a tulip is planted beside the title.
Lazi tofu: wok hei, a wok over a red-hot flame; PLAY (or a click) tosses it, the food flying and turning.
Vijača: a capoeirista skipping rope; every click is a jump worth today's minutes of work times the
  productive share, and the points lift the skin through levels of color.
Kuglanje: a pin falls every 6 minutes and the full hour rolls a strike; a click on the lane starts a
  game of bowling (bowling.py), its score sheet beside the title.
Prozor: the playlist is the window, dusk shining through the holes of its roller blind; over 90 minutes
  the light goes from gold to orange, pink, violet and night, and on pause the blind is let down.
  (No scene of its own: the player follows dusk_phase and tints the list.)
Korporealnost: a figure crouches against the gallery wall and slowly rises over an hour of the task; he
  sinks back on pause and bends again after three hours without a break.

Every scene takes set(seconds, state) on each tick and calls on_event when its milestone is reached
while the timer runs (the skin's "flip" sound).
"""

from __future__ import annotations

import math
import random
import tkinter as tk

from . import skin
from .skin import blend, px

PLATE = 10 * 60  # Suši
PIN = 6 * 60  # Kuglanje
DUSK = 90 * 60  # Prozor: one sunset
HOUR = 3600


def plates(seconds: float) -> int:
    return int(max(0.0, seconds) // PLATE)


def hours(seconds: float) -> int:
    return int(max(0.0, seconds) // HOUR)


def hour_progress(seconds: float) -> float:
    return (max(0.0, seconds) % HOUR) / HOUR


def pins_down(seconds: float) -> int:
    return int((max(0.0, seconds) % HOUR) // PIN)


def dusk(seconds: float) -> float:
    """How far the sun has set (0..1), one sunset per 90 minutes of the task."""
    return (max(0.0, seconds) % DUSK) / DUSK


DUSK_STOPS = ((0.0, "#ffd27a"), (0.35, "#ffa04d"), (0.6, "#ff6f7d"), (0.8, "#a86bd6"), (0.95, "#3b3f8a"),
              (1.0, "#3b3f8a"))


def dusk_phase(seconds: float) -> int:
    """Which part of the sunset it is: 0 gold, 1 orange, 2 pink, 3 violet, 4 night."""
    f = dusk(seconds)
    return sum(1 for at, _ in DUSK_STOPS[1:5] if f >= at)


def light_color(seconds: float) -> str:
    """The color of the light coming through the blind."""
    f = dusk(seconds)
    for (a, c1), (b, c2) in zip(DUSK_STOPS, DUSK_STOPS[1:]):
        if a <= f <= b:
            return blend(c1, c2, (f - a) / max(1e-9, b - a))
    return DUSK_STOPS[-1][1]


def rise(seconds: float) -> float:
    """Korporealnost: how far the figure has risen (0 crouched, 1 standing), over an hour of the task."""
    return min(1.0, max(0.0, seconds) / HOUR)


SINK = 15 * 60  # on pause he sinks back down over 15 minutes
TIRED_AFTER = 3 * 3600  # working this long without a pause he starts to bend again, over the next hour


def posture(task_seconds: float, state: str, run_seconds: float = 0.0, paused_seconds: float = 0.0) -> float:
    """How far the figure stands (0 crouched, 1 upright): he rises with the task, sinks back while it is
    paused, drops at once when it stops, and bends again after three hours without a break."""
    if state == "stopped":
        return 0.0
    t = rise(task_seconds)
    if state == "paused":
        return t * max(0.0, 1 - paused_seconds / SINK)
    if run_seconds > TIRED_AFTER:
        t *= 1 - 0.85 * min(1.0, (run_seconds - TIRED_AFTER) / HOUR)
    return t


class Scene(tk.Canvas):
    """Base: a canvas in the LCD panel; subclasses draw, `milestone` says when on_event fires."""

    width, height = 44, 44
    frame_ms = 0  # an own animation loop while the timer runs (0: none)

    def __init__(self, master, on_event=None):
        self.w, self.h = px(self.width), px(self.height)
        super().__init__(master, width=self.w, height=self.h, bg=skin.T.lcd_bg, highlightthickness=0)
        self.on_event = on_event
        self.seconds, self.state = 0.0, "stopped"
        self.mark: int | None = None
        self.frame = 0
        self._looping = False
        self.draw()

    def milestone(self, seconds: float) -> int:
        return hours(seconds)

    def set(self, seconds: float, state: str) -> None:
        now = self.milestone(seconds)
        reached = self.mark is not None and state == "playing" and now > self.mark
        self.seconds, self.state, self.mark = seconds, state, now
        if reached:
            self.reached()
        if self.frame_ms and state == "playing" and not self._looping:
            self._looping = True
            self._loop()
        self.draw()

    def reached(self) -> None:
        if self.on_event:
            self.on_event()

    def _loop(self) -> None:
        if not self.winfo_exists():
            return
        if self.state != "playing":
            self._looping = False
            self.draw()
            return
        self.frame += 1
        self.draw()
        self.after(self.frame_ms, self._loop)

    def draw(self) -> None:
        raise NotImplementedError


# ------------------------------------------------------------------ Suši

PLATE_COLORS = ("#f4f1ea", "#c8323c", "#2f5d9a", "#d9a63a", "#3a3a3a")


def draw_nigiri(c: tk.Canvas, x: float, y: float, w: float, topping: str | None = "#f08a5d") -> None:
    """A piece of nigiri from the side: a rice block and a slice of fish with fat stripes."""
    h = w * 0.42
    skin.round_rect(c, x - w / 2, y - h / 2, x + w / 2, y + h / 2, h / 2, fill="#fbf7ef", outline="#d8d0c0")
    if topping:
        skin.round_rect(c, x - w * 0.56, y - h * 0.95, x + w * 0.56, y - h * 0.15, h * 0.4, fill=topping, outline="")
        for k in (-0.25, 0.05, 0.35):
            c.create_line(x + w * k, y - h * 0.85, x + w * (k + 0.12), y - h * 0.25, fill=blend(topping, "#ffffff", 0.55))


def draw_maki(c: tk.Canvas, x: float, y: float, r: float) -> None:
    """A maki roll seen from the top: nori ring, rice, a salmon and cucumber center."""
    c.create_oval(x - r, y - r, x + r, y + r, fill="#1d2a22", outline="")
    c.create_oval(x - r * 0.78, y - r * 0.78, x + r * 0.78, y + r * 0.78, fill="#fbf7ef", outline="")
    c.create_oval(x - r * 0.32, y - r * 0.32, x + r * 0.05, y + r * 0.2, fill="#f08a5d", outline="")
    c.create_oval(x + r * 0.02, y - r * 0.15, x + r * 0.34, y + r * 0.3, fill="#8bbf3f", outline="")


class SushiBelt(Scene):
    """The belt runs while the timer runs; a plate is stacked every 10 minutes."""

    width, height = 62, 44
    frame_ms = 90

    def milestone(self, seconds: float) -> int:
        return plates(seconds)

    def draw(self) -> None:
        self.delete("all")
        w, h = self.w, self.h
        top, bot = px(4), px(17)
        skin.round_rect(self, px(1), top, w - px(1), bot, px(6), fill="#3b3b40", outline="#26262a")
        shift = (self.frame * px(1.5)) % px(20)
        for k in range(-1, int(w / px(20)) + 2):  # chevrons on the moving belt
            x = k * px(20) - shift + px(10)
            self.create_line(x + px(3), top + px(3), x, (top + bot) / 2, x + px(3), bot - px(3), fill="#55555c")
        for k in range(-1, int(w / px(30)) + 2):  # plates riding on it
            x = k * px(30) - shift * 1.5 % px(30) + px(15)
            if px(4) < x < w - px(4):
                color = PLATE_COLORS[(k + self.frame // 20) % 4]
                self.create_oval(x - px(7), top + px(2), x + px(7), bot - px(2), fill=color, outline="#26262a")
                draw_nigiri(self, x, (top + bot) / 2, px(9), "#f08a5d" if k % 2 else "#e85d5d")
        n = plates(self.seconds)
        base = h - px(3)
        for i in range(min(n, 9)):  # the stack of empty plates
            y = base - i * px(2.6)
            color = PLATE_COLORS[i % 4]
            self.create_oval(px(4), y - px(3), px(26), y + px(1), fill=color, outline="#26262a")
        if n:
            self.create_text(px(31), base - px(4), anchor="w", text=f"×{n}", fill=skin.T.lcd_on,
                             font=skin.T.font("mono", 8, "bold"))


# ------------------------------------------------------------------ Lale

TULIP_COLORS = ("#ec9aa8", "#f4c2cf", "#f3dc9a", "#cdb4e6", "#f6bf9e")  # soft pastels
STEM, LEAF, BUD = "#86b083", "#9cc59a", "#b5d3a2"


def draw_tulip(c: tk.Canvas, x: float, base: float, height: float, color: str, open_: float = 1.0,
               leaves: bool = True) -> None:
    """A tulip: stem, two leaves and a cup of three petals that opens with open_ (0 closed, 1 open)."""
    top = base - height
    c.create_line(x, base, x, top + height * 0.12, fill=STEM, width=max(1, height * 0.07), capstyle="round")
    if leaves:
        for side in (-1, 1):
            c.create_polygon(x, base - height * 0.05, x + side * height * 0.2, base - height * 0.22,
                             x + side * height * 0.26, base - height * 0.55, x + side * height * 0.04, base - height * 0.3,
                             fill=LEAF, outline="", smooth=True)
    r = height * 0.2
    spread = 0.15 + 0.55 * open_
    for side in (-1, 1):  # the outer petals lean out as the flower opens
        tip = (x + side * r * (0.5 + spread * 1.2), top - r * 0.2 + r * spread * 0.6)
        c.create_polygon(x - side * r * 0.1, top + r * 1.1, x + side * r * 0.9, top + r * 0.75, tip[0], tip[1],
                         x + side * r * 0.15, top + r * 0.2, fill=blend(color, "#7a5a6a", 0.12), outline="",
                         smooth=True)
    c.create_polygon(x - r * 0.55, top + r * 1.05, x - r * 0.45, top + r * 0.1, x, top - r * 0.35,
                     x + r * 0.45, top + r * 0.1, x + r * 0.55, top + r * 1.05, fill=color, outline="", smooth=True)
    c.create_line(x - r * 0.15, top + r * 0.3, x - r * 0.2, top + r * 0.85, fill=blend(color, "#ffffff", 0.5))


class TulipField(Scene):
    """A field of tulips: over an hour of the task the buds open one by one, row after row; on pause the
    open ones close again."""

    width, height = 74, 44

    def draw(self) -> None:
        self.delete("all")
        w, h = self.w, self.h
        self.create_rectangle(0, h * 0.52, w, h, fill="#e5efd9", outline="")  # the field
        for k in range(4):  # furrows running away from us
            y = h * 0.52 + (h * 0.48) * (k + 1) / 5
            self.create_line(0, y, w, y, fill="#d6e6c6")
        rows = ((h * 0.6, 8, px(9)), (h * 0.76, 7, px(12)), (h - px(2), 6, px(16)))  # back, middle, front
        total = sum(n for _, n, _ in rows)
        bloomed = 0 if self.state == "stopped" else int(hour_progress(self.seconds) * (total + 1))
        palette = hours(self.seconds) % len(TULIP_COLORS)
        k = 0
        for base, n, size in rows:
            for i in range(n):
                x = w * (i + 0.5 + (0.25 if n % 2 == 0 else 0)) / (n + 0.5)
                order = (i * 7 + k * 3) % total  # the field fills in a scattered order, not left to right
                color = TULIP_COLORS[(palette + i + k) % len(TULIP_COLORS)]
                if order < bloomed:
                    draw_tulip(self, x, base, size, color, 0.0 if self.state == "paused" else 0.9, leaves=size > px(12))
                else:
                    draw_tulip(self, x, base, size * 0.8, BUD, 0.0, leaves=size > px(12))
            k += 1


# ------------------------------------------------------------------ Lazi tofu

TOFU_RAW, TOFU_GOLDEN = "#f3e3c3", "#e0a84a"


def draw_chili(c: tk.Canvas, x: float, y: float, length: float, angle: float, color: str = "#b5231c") -> None:
    """A dried chili pepper: a curved, tapering pod with a green cap."""
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    w = length * 0.18
    pts = [(x + nx * w, y + ny * w), (x + ux * length * 0.5 + nx * w * 0.8, y + uy * length * 0.5 + ny * w * 0.8),
           (x + ux * length + nx * w * 0.1, y + uy * length + ny * w * 0.1),
           (x + ux * length * 0.55 - nx * w * 0.7, y + uy * length * 0.55 - ny * w * 0.7), (x - nx * w, y - ny * w)]
    c.create_polygon([v for p in pts for v in p], fill=color, outline=blend(color, "#000000", 0.35), smooth=True)
    c.create_line(x, y, x - ux * length * 0.15, y - uy * length * 0.15, fill="#4f7a2e", width=max(1, w * 0.9),
                  capstyle="round")


def _rot(points, angle: float, cx: float, cy: float) -> list[float]:
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for x, y in points:
        dx, dy = x - cx, y - cy
        out += [cx + dx * ca - dy * sa, cy + dx * sa + dy * ca]
    return out


# What is in the wok: (x offset, y offset from the bottom, size, kind, how high it flies, spin), in units of the wok.
# the food in the wok: (x across the opening -1..1, depth into it 0 front..1 back, size, kind, how high it flies,
# turns in the toss); whole turns, so every piece lands the way it lay
WOK_FOOD = ((-0.5, 0.3, 0.16, "tofu", 1.0, 1), (-0.18, 0.15, 0.17, "tofu", 1.25, -1), (0.18, 0.2, 0.16, "tofu", 0.9, 2),
            (0.5, 0.35, 0.15, "tofu", 1.15, -2), (-0.3, 0.75, 0.15, "tofu", 1.4, 1), (0.08, 0.8, 0.16, "tofu", 1.6, -1),
            (-0.02, 0.45, 0.3, "chili", 1.3, 1), (0.34, 0.7, 0.26, "chili", 1.0, -2), (-0.6, 0.7, 0.1, "scallion", 1.5, 2),
            (0.3, 0.1, 0.1, "scallion", 1.7, -2))
TOSS_FRAMES = 24  # at 40 ms: a toss takes about a second


class Wok(Scene):
    """Wok hei at a night market stall: a black wok over a red-hot flame, steaming while the timer runs. Pressing PLAY (or clicking the wok) tosses it: the wok
    swings up, the tofu, chilies and scallions fly and turn in the air and land back, and the flame flares."""

    width, height = 58, 44
    frame_ms = 40

    def __init__(self, master, on_event=None):
        self.toss_frame = 0
        super().__init__(master, on_event)
        self.configure(cursor="hand2")
        self.bind("<Button-1>", lambda e: self.toss())

    def toss(self) -> None:
        start = self.toss_frame == 0
        self.toss_frame = TOSS_FRAMES
        if start and self.state != "playing":
            self._toss_loop()  # not running: animate the toss by itself

    def _toss_loop(self) -> None:
        if not self.winfo_exists() or self.toss_frame <= 0 or self.state == "playing":
            return
        self.frame += 1
        self.draw()
        self.after(self.frame_ms, self._toss_loop)

    def draw(self) -> None:
        self.delete("all")
        w, h = self.w, self.h
        u = 1 - self.toss_frame / TOSS_FRAMES if self.toss_frame else 0.0
        tossing = self.toss_frame > 0
        cx, rim, rx = w * 0.42, h * 0.5, w * 0.36
        depth = h * 0.3
        # the burner and its flame: blue while cooking, a tall orange flare in the toss, a pilot light on pause
        by = h - px(3)
        self.create_rectangle(cx - rx * 0.7, by, cx + rx * 0.7, by + px(2), fill="#3a3d44", outline="")
        if self.state != "stopped" or tossing:
            rnd = random.Random(self.frame // 2)  # the flame flickers every other frame
            n = 7
            for k in range(n):
                fx = cx - rx * 0.55 + k * rx * 1.1 / (n - 1)
                tall = px(3) if self.state == "paused" and not tossing else px(5) + rnd.uniform(0, px(3))
                if tossing:
                    tall += math.sin(math.pi * u) * px(9)
                outer = "#ff8a2a" if tossing else "#e8321e"  # red-hot, flaring orange in the toss
                inner = "#ffe08a" if tossing else "#ffb347"
                self.create_polygon(fx - px(2), by, fx, by - tall, fx + px(2), by, fill=outer, outline="", smooth=True)
                self.create_polygon(fx - px(0.8), by, fx, by - tall * 0.5, fx + px(0.8), by, fill=inner, outline="")
        if self.state == "playing" and not tossing:  # steam rising off the wok into the night air
            for k in range(3):
                x0 = cx - rx * 0.45 + k * rx * 0.45
                pts = []
                for i in range(6):
                    pts += [x0 + math.sin((i + self.frame * 0.35 + k * 2) * 0.9) * px(2), rim - px(2) - i * px(3)]
                self.create_line(pts, fill=blend(skin.T.lcd_bg, "#ffffff", 0.3), smooth=True)
        # the wok swings forward and up, tilting, and comes back. Seen from a little above: the dark inside of
        # the opening, then the food, then the front wall over it, so the food sits in the wok, not on it.
        lift = math.sin(math.pi * u) * px(6) if tossing else 0
        tilt = math.sin(2 * math.pi * u) * 14 if tossing else 0
        wy = rim - lift
        ry = depth * 0.3  # the opening, an ellipse
        steps = [math.pi * k / 16 for k in range(17)]
        front_lip = [(cx - rx * math.cos(a), wy + ry * math.sin(a)) for a in steps]  # left to right, the near edge
        bowl = [(cx + rx * math.cos(a), wy + depth * math.sin(a)) for a in steps]  # right to left, underneath
        opening = front_lip + [(cx + rx * math.cos(a), wy - ry * math.sin(a)) for a in steps]
        self.create_line(_rot([(cx + rx * 0.9, wy + px(1)), (w - px(1), wy - px(4))], tilt, cx, wy),
                         fill="#5a3b26", width=max(2, px(3.5)), capstyle="round")  # the handle
        self.create_polygon(_rot(opening, tilt, cx, wy), fill="#121216", outline="#6a6e78", width=max(1, px(1.2)))
        # the food: lying in the wok and riding with it, or flying and turning, and falling back in
        for i, (dx, back, size, kind, high, spin) in sorted(enumerate(WOK_FOOD), key=lambda f: -f[1][1]):
            v = min(1.0, max(0.0, (u - 0.03 * (i % 5)) / 0.85)) if tossing else 0.0
            arc = math.sin(math.pi * v)
            lx = cx + dx * rx * 0.8 * (1 + arc * 0.25)  # they spread a little in the air
            ly = wy + ry * (0.55 - back * 1.1)
            (x, y) = _rot([(lx, ly)], tilt, cx, wy)
            y -= arc * px(9) * high
            turn = v * 360 * spin
            sz = size * rx
            if kind == "tofu":
                sq = [(x - sz / 2, y - sz / 2), (x + sz / 2, y - sz / 2), (x + sz / 2, y + sz / 2), (x - sz / 2, y + sz / 2)]
                self.create_polygon(_rot(sq, turn, x, y), fill=TOFU_GOLDEN, outline="#8a5a22")
            elif kind == "chili":
                draw_chili(self, x - sz / 2, y, sz, turn - 15, "#c8231a")
            else:
                ring = sz / 2
                self.create_oval(x - ring, y - ring, x + ring, y + ring, outline="#6fbf4a", width=max(1, px(1.2)))
        self.create_polygon(_rot(front_lip + bowl, tilt, cx, wy), fill="#232428", outline="#0c0c0e")
        self.create_line(_rot(front_lip, tilt, cx, wy), fill="#6a6e78", width=max(1, px(1.5)))
        self.create_line(_rot([(cx - rx * 0.6, wy + depth * 0.55), (cx + rx * 0.1, wy + depth * 0.8)], tilt, cx, wy),
                         fill="#3a3c44")  # a dull shine on the steel
        if self.toss_frame:
            self.toss_frame -= 1


# ------------------------------------------------------------------ Vijača (jump rope clicker)

ROPE_LEVELS = (100, 300, 1000, 5000, 10000, 50000, 100000)  # points at which the whole skin changes color
CORDS = (("#e8dcc0", None), ("#1f9d4a", None), ("#1f9d4a", "#ffd400"), ("#ffd400", None), ("#ffd400", "#1f4fbf"),
         ("#1f4fbf", None), ("#1f4fbf", "#ffffff"), ("#ffd400", "#ffffff"))  # the capoeira cords, one per level


def rope_level(points: int) -> int:
    return sum(1 for t in ROPE_LEVELS if points >= t)


def rope_next(points: int) -> int | None:
    """The points of the next level, None at the top."""
    return next((t for t in ROPE_LEVELS if points < t), None)


def click_value(minutes_today: float, productive_share: float) -> int:
    """What one jump is worth: today's minutes of work times the productive share, at least 1 point."""
    return max(1, round(minutes_today * max(0.0, min(1.0, productive_share))))


JUMP_FRAMES = 12


class Jumper(Scene):
    """The capoeirista skips rope: every click (or tap) is one jump, worth click_value points. on_jump is
    called on each click; the cord around the waist shows the level."""

    width, height = 64, 44

    def __init__(self, master, on_event=None, on_jump=None, on_bonus=None):
        self.jump_frame = 0
        self.level = 0
        self.value = 1
        self.gain = 0  # the "+N" floating up after a jump
        self.bonus_ready = False  # a pandeiro waits top right: a click on it starts the bonus round
        self.double = False  # the bonus is on: jumps count double
        super().__init__(master, on_event)
        self.on_jump, self.on_bonus = on_jump, on_bonus
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._clicked)

    def _clicked(self, event) -> None:
        if self.bonus_ready and self.on_bonus and event.x > self.w - px(20) and event.y < px(20):
            self.on_bonus()
        else:
            self.jump()

    def jump(self) -> None:
        start = self.jump_frame == 0
        self.jump_frame = JUMP_FRAMES
        if self.on_jump:
            self.gain = self.on_jump() or self.gain
        if start:
            self._jump_loop()

    def _jump_loop(self) -> None:
        if not self.winfo_exists():
            return
        self.draw()
        if self.jump_frame > 0:
            self.jump_frame -= 1
            self.after(35, self._jump_loop)

    def _limb(self, pts, color, width) -> None:
        flat = [v for p in pts for v in p]
        self.create_line(flat, fill="#2a1a10", width=width + 2, capstyle="round", joinstyle="round")
        self.create_line(flat, fill=color, width=width, capstyle="round", joinstyle="round")

    def draw(self) -> None:
        self.delete("all")
        w, h = self.w, self.h
        floor = h - px(3)
        u = 1 - self.jump_frame / JUMP_FRAMES if self.jump_frame else 0.0
        # The rope goes up behind the back (phi 0..pi), over the head and down in front (pi..2pi), and passes under
        # the feet at u = 0.85, just as the jump is highest.
        phi = min(2 * math.pi, 2 * math.pi * u / 0.85)
        hop = px(6) * math.sin(math.pi * (u - 0.65) / 0.4) if 0.65 < u < 1.05 else 0.0
        cx = px(20)
        sk, pants = "#8a5a3c", "#f5f5f0"
        feet = floor - hop
        hip = (cx, feet - px(13))
        neck = (cx, feet - px(25))
        hands = ((cx - px(9), feet - px(14)), (cx + px(9), feet - px(14)))
        reach = (floor + px(2) - hands[0][1]) if math.cos(phi) >= 0 else (hands[0][1] - neck[1] + px(11))
        rope_y = hands[0][1] + reach * math.cos(phi) if self.jump_frame else floor + px(1)
        front = math.pi < phi < 2 * math.pi and self.jump_frame > 0  # in front of the body on its way down

        def rope() -> None:  # a parabola from hand to hand through the rope's lowest (or highest) point
            mid_y = rope_y if self.jump_frame else floor + px(1)
            pts = []
            for k in range(13):
                t = k / 6 - 1
                pts += [cx + t * (hands[1][0] - cx) * (1 + 0.25 * (1 - t * t)),
                        hands[0][1] + (mid_y - hands[0][1]) * (1 - t * t)]
            self.create_line(pts, fill="#2a1a10", width=max(2, px(2.6)), smooth=True)
            self.create_line(pts, fill="#fff3d6", width=max(1, px(1.6)), smooth=True)

        if not front:
            rope()
        self.create_oval(cx - px(8), floor - px(1), cx + px(8), floor + px(2), fill=blend(skin.T.lcd_bg, "#000000", 0.35),
                         outline="")  # the shadow stays on the ground
        bend = px(3) if hop else 0
        for side in (-1, 1):
            self._limb((hip, (cx + side * (px(3) + bend), feet - px(6)), (cx + side * px(3), feet)), pants, max(2, px(3)))
        self._limb((neck, hip), sk, max(2, px(4)))
        for hand in hands:
            self._limb((neck, ((neck[0] + hand[0]) / 2, neck[1] + px(7)), hand), sk, max(2, px(2.2)))
        c1, c2 = CORDS[min(self.level, len(CORDS) - 1)]
        self.create_line(cx - px(4), hip[1] - px(1), cx + px(4), hip[1] - px(1), fill=c1, width=max(2, px(2.5)))
        if c2:
            self.create_line(cx - px(4), hip[1] - px(1), cx + px(4), hip[1] - px(1), fill=c2, width=max(2, px(2.5)),
                             dash=(2, 2))
        self.create_line(cx + px(2), hip[1], cx + px(4), hip[1] + px(6), fill=c1, width=max(1, px(1.6)))
        self.create_oval(cx - px(3.4), neck[1] - px(8), cx + px(3.4), neck[1] - px(1), fill=sk, outline="#2a1a10")
        for hand in hands:  # the handles
            self.create_rectangle(hand[0] - px(1), hand[1] - px(2.5), hand[0] + px(1), hand[1] + px(1.5), fill="#c9a26a",
                                  outline="")
        if front:
            rope()
        font = skin.T.font("mono", 8, "bold")
        self.create_text(w - px(2), h - px(4), anchor="e", text=f"+{self.value}", fill=skin.T.lcd_dim, font=font)
        if self.double:
            self.create_text(w - px(2), h - px(15), anchor="e", text="×2", fill=skin.T.accent, font=font)
        if self.bonus_ready:  # the pandeiro calling for the bonus round
            bx, by, r = w - px(9), px(9), px(6.5)
            self.create_oval(bx - r - px(2), by - r - px(2), bx + r + px(2), by + r + px(2), fill=blend(skin.T.lcd_bg, skin.T.accent, 0.4),
                             outline="")
            self.create_oval(bx - r, by - r, bx + r, by + r, fill="#f2e6c8", outline="#a0703c", width=max(1, px(1.5)))
            for k in range(6):
                a = k * math.pi / 3
                self.create_oval(bx + math.cos(a) * r - px(1.2), by + math.sin(a) * r - px(1.2), bx + math.cos(a) * r + px(1.2),
                                 by + math.sin(a) * r + px(1.2), fill="#d9d9d9", outline="")
            self.create_text(bx, by, text="!", fill="#a0703c", font=skin.T.font("sans", 7, "bold"))
        if self.jump_frame and self.gain:  # the points just earned float up
            self.create_text(w - px(14), px(6) + px(10) * (1 - u), text=f"+{self.gain}", fill=skin.T.lcd_on, font=font)


# ------------------------------------------------------------------ Kuglanje

PIN_ORDER = (9, 7, 8, 4, 5, 6, 0, 1, 2, 3)  # the head pin falls first, the back row last
PIN_SPOTS = [(-1.5, 0), (-0.5, 0), (0.5, 0), (1.5, 0), (-1, 1), (0, 1), (1, 1), (-0.5, 2), (0.5, 2), (0, 3)]


def draw_pin(c: tk.Canvas, x: float, base: float, height: float, down: bool = False) -> None:
    """A bowling pin, standing (white with two red stripes) or knocked over (lying, greyed)."""
    w = height * 0.36
    if down:
        c.create_oval(x - height * 0.32, base - w * 0.55, x + height * 0.32, base, fill="#b9b4ac", outline="#7a756e")
        return
    c.create_oval(x - w / 2, base - height * 0.62, x + w / 2, base, fill="#fbfaf6", outline="#9a958e")
    c.create_oval(x - w * 0.3, base - height, x + w * 0.3, base - height * 0.62, fill="#fbfaf6", outline="#9a958e")
    c.create_rectangle(x - w * 0.24, base - height * 0.7, x + w * 0.24, base - height * 0.64, fill="#d6343b",
                       outline="")
    c.create_rectangle(x - w * 0.22, base - height * 0.62, x + w * 0.22, base - height * 0.57, fill="#d6343b",
                       outline="")


class Pins(Scene):
    """Ten pins on the lane; one falls every 6 minutes, and the full hour rolls a strike."""

    width, height = 54, 44

    def __init__(self, master, on_event=None, on_click=None):
        self.strike = 0
        super().__init__(master, on_event)
        if on_click:  # a click on the lane starts a game of bowling
            self.configure(cursor="hand2")
            self.bind("<Button-1>", lambda e: on_click())

    def reached(self) -> None:
        super().reached()
        self.strike = 8
        self._roll()

    def _roll(self) -> None:
        if not self.winfo_exists() or self.strike <= 0:
            return
        self.strike -= 1
        self.draw()
        self.after(60, self._roll)

    def draw(self) -> None:
        self.delete("all")
        w, h = self.w, self.h
        self.create_polygon(w * 0.3, px(2), w * 0.7, px(2), w - px(2), h - px(1), px(2), h - px(1), fill="#e3b878",
                            outline="")  # the maple lane
        for k in range(1, 6):
            t = k / 6
            self.create_line(w * 0.3 + w * 0.4 * t, px(2), px(2) + (w - px(4)) * t, h - px(1), fill="#cf9e5c")
        down = 10 if self.strike else pins_down(self.seconds)
        fallen = set(PIN_ORDER[:down])
        size = px(10)
        for i, (dx, row) in enumerate(PIN_SPOTS):
            x = w / 2 + dx * px(7.5)
            base = px(13) + row * px(4.5)
            draw_pin(self, x, base, size, i in fallen)
        by = h - px(7) - (h * 0.6) * (1 - self.strike / 8) if self.strike else h - px(7)
        r = px(5)
        self.create_oval(w / 2 - r, by - r, w / 2 + r, by + r, fill="#3b1f5e", outline="#1d0f30")
        self.create_oval(w / 2 - r * 0.5, by - r * 0.7, w / 2 + r * 0.1, by - r * 0.25, fill="#6a4a9a", outline="")


# ------------------------------------------------------------------ Korporealnost

# The figure's joints in a 36 x 44 box (side view, facing the wall on the left): head, neck, hip, knee,
# foot, elbow, hand. Crouched with the head against the wall and the hands on it, kneeling, rising, standing.
POSES = (
    ((9, 24), (14, 25), (22, 36), (11, 31), (17, 41), (17, 19), (10, 20)),
    ((13, 13), (15, 18), (18, 28), (12, 40), (24, 41), (13, 24), (12, 30)),
    ((15, 7), (16, 12), (18, 24), (17, 32), (18, 41), (17, 18), (17, 24)),
    ((18, 6), (18, 11), (18, 24), (18, 33), (18, 41), (18, 17), (18, 23)),
)
SKIN, SKIN_SHADE, HAIR, SHORTS = "#e8c1a0", "#c99a7c", "#2a2421", "#b9b6b0"


def pose(t: float) -> list[tuple[float, float]]:
    """The joints for how far the figure has risen (0..1), between the key poses."""
    t = max(0.0, min(1.0, t)) * (len(POSES) - 1)
    i = min(int(t), len(POSES) - 2)
    f = t - i
    return [(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f) for a, b in zip(POSES[i], POSES[i + 1])]


def draw_figure(c: tk.Canvas, x0: float, y0: float, w: float, h: float, t: float) -> None:
    """The figure at the wall, in grey shorts, as far risen as t."""
    sx, sy = w / 36, h / 44
    head, neck, hip, knee, foot, elbow, hand = [(x0 + x * sx, y0 + y * sy) for x, y in pose(t)]
    c.create_oval(foot[0] - 6 * sx, y0 + 41.5 * sy - sy, foot[0] + 6 * sx, y0 + 43 * sy,
                  fill=blend(skin.T.lcd_bg, "#000000", 0.12), outline="")  # its shadow on the floor
    lw = max(2, 3.2 * sx)
    c.create_line(*hip, *knee, *foot, fill=SKIN_SHADE, width=lw, capstyle="round", joinstyle="round")
    c.create_line(*neck, *hip, fill=SKIN, width=max(3, 5.4 * sx), capstyle="round")
    mid = ((hip[0] * 2 + knee[0]) / 3, (hip[1] * 2 + knee[1]) / 3)
    c.create_line(*hip, *mid, fill=SHORTS, width=max(3, 4.6 * sx), capstyle="round")
    c.create_line(*neck, *elbow, *hand, fill=SKIN_SHADE, width=max(1, 2.2 * sx), capstyle="round", joinstyle="round")
    r = 3.4 * sx
    c.create_oval(head[0] - r, head[1] - r, head[0] + r, head[1] + r, fill=SKIN, outline=SKIN_SHADE)
    c.create_arc(head[0] - r, head[1] - r, head[0] + r, head[1] + r, start=20, extent=200, style="chord", fill=HAIR,
                 outline="")


class Figure(Scene):
    """Crouched against the white wall when the task starts, standing after an hour of it; `posture`, when
    the player sets it, also lets him sink on pause and tire (see posture())."""

    width, height = 36, 44
    posture: float | None = None

    def draw(self) -> None:
        self.delete("all")
        w, h = self.w, self.h
        self.create_rectangle(0, 0, px(4), h, fill=blend(skin.T.lcd_bg, "#000000", 0.05), outline="")  # the wall
        self.create_line(0, h - px(2), w, h - px(2), fill=blend(skin.T.lcd_bg, "#000000", 0.18))
        t = self.posture if self.posture is not None else rise(self.seconds) if self.state != "stopped" else 0.0
        draw_figure(self, 0, 0, w, h, t)


SCENES = {"sushi": SushiBelt, "tulip": TulipField, "wok": Wok, "jumper": Jumper, "pins": Pins,
          "figure": Figure}
