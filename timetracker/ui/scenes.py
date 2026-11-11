"""Seven skins with a little scene next to the clock that follows the task's time.

Suši: a conveyor belt runs while you work, and a plate lands on the stack every 10 minutes.
Lale: a tulip grows from the bulb over an hour of the task and closes its petals on pause; every
  full hour a tulip is planted beside the title.
Lazi tofu: a tofu cube drops into the wok every 5 minutes and slowly turns golden; at the full hour
  the wok is tossed and a plate is served beside the title.
Kapoera: a capoeirista sways in the ginga while the timer runs; every 30 minutes earns the next cord.
Kuglanje: a pin falls every 6 minutes; at the full hour the ball rolls a strike, marked on the
  score sheet beside the title.
Prozor: dusk through the holes of a roller blind; over 90 minutes the light goes from gold to orange,
  pink, violet and night, and on pause the blind is let down.
Korporealnost: a figure crouches against the gallery wall and slowly rises over an hour of the task.

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
CUBE = 5 * 60  # Lazi tofu
GRADE = 30 * 60  # Kapoera
PIN = 6 * 60  # Kuglanje
DUSK = 90 * 60  # Prozor: one sunset
HOUR = 3600


def plates(seconds: float) -> int:
    return int(max(0.0, seconds) // PLATE)


def hours(seconds: float) -> int:
    return int(max(0.0, seconds) // HOUR)


def hour_progress(seconds: float) -> float:
    return (max(0.0, seconds) % HOUR) / HOUR


def cubes(seconds: float) -> int:
    """Tofu cubes in the wok: one per 5 minutes, served (and the wok empty again) every hour."""
    return int((max(0.0, seconds) % HOUR) // CUBE)


def grade(seconds: float) -> int:
    return int(max(0.0, seconds) // GRADE)


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

TULIP_COLORS = ("#e0424f", "#f59ab5", "#f5c542", "#9b5fc0", "#f08a2e")


def draw_tulip(c: tk.Canvas, x: float, base: float, height: float, color: str, open_: float = 1.0,
               leaves: bool = True) -> None:
    """A tulip: stem, two leaves and a cup of three petals that opens with open_ (0 closed, 1 open)."""
    top = base - height
    c.create_line(x, base, x, top + height * 0.12, fill="#4f9a45", width=max(1, height * 0.07), capstyle="round")
    if leaves:
        for side in (-1, 1):
            c.create_polygon(x, base - height * 0.05, x + side * height * 0.2, base - height * 0.22,
                             x + side * height * 0.26, base - height * 0.55, x + side * height * 0.04, base - height * 0.3,
                             fill="#5fae4f", outline="", smooth=True)
    r = height * 0.2
    spread = 0.15 + 0.55 * open_
    for side in (-1, 1):  # the outer petals lean out as the flower opens
        tip = (x + side * r * (0.5 + spread * 1.2), top - r * 0.2 + r * spread * 0.6)
        c.create_polygon(x - side * r * 0.1, top + r * 1.1, x + side * r * 0.9, top + r * 0.75, tip[0], tip[1],
                         x + side * r * 0.15, top + r * 0.2, fill=blend(color, "#000000", 0.12), outline="",
                         smooth=True)
    c.create_polygon(x - r * 0.55, top + r * 1.05, x - r * 0.45, top + r * 0.1, x, top - r * 0.35,
                     x + r * 0.45, top + r * 0.1, x + r * 0.55, top + r * 1.05, fill=color, outline="", smooth=True)
    c.create_line(x - r * 0.15, top + r * 0.3, x - r * 0.2, top + r * 0.85, fill=blend(color, "#ffffff", 0.5))


class Tulip(Scene):
    """Grows from a bulb over an hour of the task; the petals close while the timer is paused."""

    width, height = 32, 44

    def draw(self) -> None:
        self.delete("all")
        w, h = self.w, self.h
        base = h - px(6)
        self.create_oval(px(2), base - px(3), w - px(2), h - px(1), fill="#7a5236", outline="")  # soil
        if self.state == "stopped" and self.seconds <= 0:
            self.create_oval(w / 2 - px(4), base - px(5), w / 2 + px(4), base + px(2), fill="#c9a77c",
                             outline="#8a6a4a")  # the bulb, waiting
            return
        p = hour_progress(self.seconds)
        color = TULIP_COLORS[hours(self.seconds) % len(TULIP_COLORS)]
        if p < 0.08:  # a sprout pushing out of the bulb
            self.create_oval(w / 2 - px(4), base - px(5), w / 2 + px(4), base + px(2), fill="#c9a77c", outline="")
            self.create_line(w / 2, base - px(4), w / 2, base - px(4) - px(10) * p / 0.08, fill="#5fae4f",
                             width=max(1, px(2)), capstyle="round")
            return
        height = (h - px(10)) * (0.35 + 0.65 * min(1.0, p / 0.6))
        bud = min(1.0, max(0.0, (p - 0.3) / 0.3))  # green bud turning into the flower's color
        open_ = 0.0 if self.state == "paused" else max(0.0, (p - 0.6) / 0.4)
        draw_tulip(self, w / 2, base, height, blend("#7fbf5a", color, bud), open_)


# ------------------------------------------------------------------ Lazi tofu

TOFU_RAW, TOFU_GOLDEN = "#f3e3c3", "#c98a3a"


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


class Wok(Scene):
    """A tofu cube drops in every 5 minutes and browns; at the full hour the wok is tossed."""

    width, height = 58, 44
    frame_ms = 150

    def __init__(self, master, on_event=None):
        self.toss = 0
        super().__init__(master, on_event)

    def milestone(self, seconds: float) -> int:
        return hours(seconds)

    def reached(self) -> None:
        super().reached()
        self.toss = 10  # frames of the toss

    def draw(self) -> None:
        self.delete("all")
        w, h = self.w, self.h
        cx, rim = w * 0.42, h * 0.45
        rx, depth = w * 0.38, h * 0.42
        if self.state == "playing":  # steam rising off the wok
            for k in range(3):
                x0 = cx - rx * 0.5 + k * rx * 0.5
                pts = []
                for i in range(6):
                    y = rim - px(3) - i * px(2.6)
                    pts += [x0 + math.sin((i + self.frame + k * 2) * 0.9) * px(2), y]
                self.create_line(pts, fill=blend(skin.T.lcd_bg, "#ffffff", 0.35), smooth=True)
        self.create_line(cx + rx * 0.95, rim + px(2), w - px(2), rim - px(3), fill="#5a3b26", width=max(2, px(3.5)),
                         capstyle="round")  # the handle
        self.create_arc(cx - rx, rim - depth, cx + rx, rim + depth, start=180, extent=180, style="chord",
                        fill="#2a2a2e", outline="#111114")
        self.create_line(cx - rx, rim, cx + rx, rim, fill="#4a4a50", width=max(1, px(1.5)))
        n = 0 if self.toss else cubes(self.seconds)
        secs_in_hour = max(0.0, self.seconds) % HOUR
        rnd = random.Random(4)
        jump = math.sin(math.pi * self.toss / 10) * px(10) if self.toss else 0
        size = px(5.5)
        for k in range(n if not self.toss else 8):
            row, col = divmod(k, 4)
            x = cx - rx * 0.55 + col * size * 1.15 + row * size * 0.5 + rnd.uniform(-1, 1)
            y = rim + px(1) - row * size * 0.8 - jump * rnd.uniform(0.7, 1.2)
            age = secs_in_hour - k * CUBE if not self.toss else HOUR
            color = blend(TOFU_RAW, TOFU_GOLDEN, min(1.0, age / (3 * CUBE)))
            self.create_rectangle(x, y - size, x + size, y, fill=color, outline=blend(color, "#000000", 0.25))
        if n >= 2 or self.toss:  # a few chilies and scallions in with the tofu
            draw_chili(self, cx - rx * 0.6, rim - px(4) - jump, px(9), -20)
            draw_chili(self, cx + rx * 0.25, rim - px(5) - jump, px(8), 200)
            for x in (cx - rx * 0.1, cx + rx * 0.45):
                self.create_rectangle(x, rim - px(3) - jump, x + px(4), rim - px(1) - jump, fill="#5fae3e", outline="")
        if self.toss:
            self.toss -= 1


# ------------------------------------------------------------------ Kapoera

CORDS = (("#e8dcc0", None), ("#1f9d4a", None), ("#1f9d4a", "#ffd400"), ("#ffd400", None), ("#ffd400", "#1f4fbf"),
         ("#1f4fbf", None), ("#1f9d4a", "#1f4fbf"), ("#ffd400", "#ffffff"), ("#1f4fbf", "#ffffff"))


def cord_colors(seconds: float) -> tuple[str, str | None]:
    return CORDS[min(grade(seconds), len(CORDS) - 1)]


class Roda(Scene):
    """A capoeirista in the ginga (swaying while the timer runs) and the cord earned so far."""

    width, height = 60, 44
    frame_ms = 430  # the berimbau's beat

    def milestone(self, seconds: float) -> int:
        return grade(seconds)

    def _limb(self, pts, color, width) -> None:
        flat = [v for p in pts for v in p]
        self.create_line(flat, fill="#2a1a10", width=width + 2, capstyle="round", joinstyle="round")
        self.create_line(flat, fill=color, width=width, capstyle="round", joinstyle="round")

    def draw(self) -> None:
        self.delete("all")
        w, h = self.w, self.h
        floor = h - px(3)
        moving = self.state == "playing"
        side = -1 if moving and self.frame % 2 else 1  # the ginga: step back left, step back right
        cx = px(15)
        sk, pants = "#8a5a3c", "#f5f5f0"
        hip = (cx, floor - px(17))
        neck = (cx + side * px(2), floor - px(29))
        if moving:
            legs = [((hip[0], hip[1]), (cx - side * px(6), floor - px(8)), (cx - side * px(11), floor)),
                    ((hip[0], hip[1]), (cx + side * px(5), floor - px(9)), (cx + side * px(6), floor))]
            arms = [(neck, (cx + side * px(7), neck[1] + px(1)), (cx + side * px(6), neck[1] - px(5))),
                    (neck, (cx - side * px(6), neck[1] + px(6)), (cx - side * px(9), neck[1] + px(10)))]
        else:
            legs = [(hip, (cx - px(3), floor - px(8)), (cx - px(4), floor)), (hip, (cx + px(3), floor - px(8)),
                                                                             (cx + px(4), floor))]
            arms = [(neck, (cx - px(4), neck[1] + px(7)), (cx - px(4), neck[1] + px(13))),
                    (neck, (cx + px(4), neck[1] + px(7)), (cx + px(4), neck[1] + px(13)))]
        for leg in legs:
            self._limb(leg, pants, max(2, px(3)))
        self._limb((neck, hip), sk, max(2, px(3.5)))
        for arm in arms:
            self._limb(arm, sk, max(2, px(2.2)))
        hx, hy = neck[0] + side * px(1), neck[1] - px(4)
        self.create_oval(hx - px(3.2), hy - px(3.2), hx + px(3.2), hy + px(3.2), fill=sk, outline="#2a1a10")
        # the cord: tied in a knot, two ends hanging
        c1, c2 = cord_colors(self.seconds if self.state != "stopped" else 0)
        kx, ky = w - px(16), h * 0.42
        loop = [(kx - px(11), ky - px(8)), (kx - px(13), ky + px(2)), (kx - px(4), ky + px(6)), (kx, ky),
                (kx + px(4), ky + px(6)), (kx + px(12), ky + px(2)), (kx + px(10), ky - px(8)), (kx, ky - px(11)),
                (kx - px(11), ky - px(8))]
        ends = [[(kx, ky), (kx - px(4), ky + px(10)), (kx - px(6), ky + px(18))],
                [(kx, ky), (kx + px(3), ky + px(11)), (kx + px(3), ky + px(19))]]
        for pts in (loop, *ends):
            flat = [v for p in pts for v in p]
            self.create_line(flat, fill="#2a1a10", width=max(3, px(4.5)), smooth=True, capstyle="round")
            self.create_line(flat, fill=c1, width=max(2, px(3)), smooth=True, capstyle="round")
            if c2:  # a two-colored cord: the second color twisted in
                self.create_line(flat, fill=c2, width=max(2, px(3)), smooth=True, capstyle="round", dash=(3, 3))
        self.create_oval(kx - px(2.5), ky - px(2.5), kx + px(2.5), ky + px(2.5), fill=c1, outline="#2a1a10")


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

    def __init__(self, master, on_event=None):
        self.strike = 0
        super().__init__(master, on_event)

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


# ------------------------------------------------------------------ Prozor

class Blind(Scene):
    """A window with a roller blind; light shines through its holes, gold to night over 90 minutes."""

    width, height = 44, 44

    def milestone(self, seconds: float) -> int:
        return int(max(0.0, seconds) // DUSK) * 5 + dusk_phase(seconds)

    def draw(self) -> None:
        self.delete("all")
        w, h = self.w, self.h
        light = light_color(self.seconds)
        dim = self.state != "playing"  # paused or stopped: the blind is let down, little light gets in
        self.create_rectangle(px(2), px(2), w - px(2), h - px(2), fill="#3a2f2a", outline="#1c1512")
        slat = "#5a4a40"
        self.create_rectangle(px(4), px(4), w - px(4), h - px(4), fill=slat, outline="")
        rows = 7
        for r in range(rows):
            y = px(5) + r * (h - px(10)) / rows
            self.create_line(px(4), y, w - px(4), y, fill="#3e322b")
            for c in range(6):
                x = px(7) + c * (w - px(14)) / 5
                glow = blend(slat, light, 0.25 if dim else 1.0)
                self.create_rectangle(x - px(1.2), y + px(1.4), x + px(1.2), y + px(3), fill=glow, outline="")
        if not dim:  # a soft glow of the light on the sill
            self.create_line(px(4), h - px(4), w - px(4), h - px(4), fill=blend(slat, light, 0.6), width=max(1, px(2)))


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
    """Crouched against the white wall when the task starts, standing after an hour of it."""

    width, height = 36, 44

    def draw(self) -> None:
        self.delete("all")
        w, h = self.w, self.h
        self.create_rectangle(0, 0, px(4), h, fill=blend(skin.T.lcd_bg, "#000000", 0.05), outline="")  # the wall
        self.create_line(0, h - px(2), w, h - px(2), fill=blend(skin.T.lcd_bg, "#000000", 0.18))
        draw_figure(self, 0, 0, w, h, rise(self.seconds) if self.state != "stopped" else 0.0)


SCENES = {"sushi": SushiBelt, "tulip": Tulip, "wok": Wok, "roda": Roda, "pins": Pins, "blind": Blind,
          "figure": Figure}
