"""Kuglanje: a small game of ten-pin bowling, played in its own window (a click on the lane opens it).

Aim with a swinging arrow (click to stop it), then power with a filling bar (click again), and the ball
rolls. Ten frames with the real scoring (strike, spare, bonus balls in the tenth); the game in progress
and the best score are kept in the settings, and the score sheet is shown beside the title.
"""

from __future__ import annotations

import math
import random
import tkinter as tk

from . import skin
from .scenes import PIN_SPOTS
from .skin import blend, px

ALL_PINS = frozenset(range(10))


# ------------------------------------------------------------------ scoring

def frames(rolls: list[int]) -> list[list[int]]:
    """The rolls grouped into frames (the tenth can hold three)."""
    out: list[list[int]] = []
    i = 0
    while i < len(rolls):
        if len(out) == 9:
            out.append(rolls[i:i + 3])
            break
        if rolls[i] == 10:
            out.append([10])
            i += 1
        else:
            out.append(rolls[i:i + 2])
            i += 2
    return out


def game_over(rolls: list[int]) -> bool:
    fs = frames(rolls)
    if len(fs) < 10:
        return False
    last = fs[9]
    if len(last) == 3:
        return True
    return len(last) == 2 and sum(last) < 10


def frame_open(rolls: list[int]) -> bool:
    """Is the next roll the second (or third) ball of a frame, at the pins still standing?"""
    fs = frames(rolls)
    if not fs or game_over(rolls):
        return False
    last = fs[-1]
    if len(fs) < 10:
        return len(last) == 1 and last[0] < 10
    if len(last) == 1:
        return last[0] < 10
    if len(last) == 2:
        return last[0] == 10 and last[1] < 10  # a strike, then a ball at what is left of the fresh rack
    return False


def standing_count(rolls: list[int]) -> int:
    """How many pins the next ball faces."""
    if not frame_open(rolls):
        return 10
    fs = frames(rolls)
    return 10 - fs[-1][-1]


def marks(rolls: list[int]) -> list[str]:
    """What the score sheet shows for each frame: X for a strike, n/ for a spare, - for a miss."""
    out = []
    for f in frames(rolls):
        text, left = "", 10  # left: the pins the ball faced
        for r in f:
            if left == 10 and r == 10:
                text += "X"
            elif left < 10 and r == left:
                text += "/"
                left = 10
            else:
                text += "-" if r == 0 else str(r)
                left = left - r if left == 10 else 10
        out.append(text)
    return out


def scores(rolls: list[int]) -> list[int | None]:
    """The running total after each frame, None while its bonus balls are still to come."""
    out: list[int | None] = []
    total, i = 0, 0
    for k in range(10):
        if i >= len(rolls):
            break
        if k == 9:
            f = rolls[i:i + 3]
            done = game_over(rolls)
            total += sum(f)
            out.append(total if done else None)
            break
        if rolls[i] == 10:
            bonus = rolls[i + 1:i + 3]
            if len(bonus) < 2:
                out.append(None)
                break
            total += 10 + sum(bonus)
            i += 1
        else:
            pair = rolls[i:i + 2]
            if len(pair) < 2:
                out.append(None)
                break
            if sum(pair) == 10:
                bonus = rolls[i + 2:i + 3]
                if not bonus:
                    out.append(None)
                    break
                total += 10 + bonus[0]
            else:
                total += sum(pair)
            i += 2
        out.append(total)
    return out


def total(rolls: list[int]) -> int:
    done = [s for s in scores(rolls) if s is not None]
    return done[-1] if done else 0


# ------------------------------------------------------------------ the throw

SPREAD = 1.2  # how far across the lane (in half lane widths) the steepest angle carries the ball by the pins
GUTTER_X = 1.12  # the middle of a gutter, in half lane widths
MAX_HOOK = 0.18  # the spin: how far the ball curls off its line by the pins, at most


def ball_x(spot: float, angle: float, y: float, hook: float = 0.0) -> float:
    """Where the ball is across the lane (-1 left edge .. 1 right edge) after y (0..1) of the way to the pins,
    rolled from spot at angle (-1..1) with hook (its spin curls it a little, more and more towards the pins).
    Once it rolls past an edge it drops into that gutter and stays in it, whatever the spin."""
    steps = max(1, int(y * 40))
    for k in range(1, steps + 1):
        x = spot + angle * SPREAD * (y * k / steps) + hook * (y * k / steps) ** 2
        if abs(x) > 1:
            return math.copysign(GUTTER_X, x)
    return spot + angle * SPREAD * y + hook * y * y


def pin_aim(spot: float, angle: float, hook: float = 0.0) -> float:
    """Where the ball meets the pins; ±GUTTER_X if it fell off the side on the way."""
    return ball_x(spot, angle, 1.0, hook)


def throw(aim: float, power: float, standing: set[int], rnd: random.Random) -> set[int]:
    """Which of the standing pins fall. aim: -1 (left gutter) .. 1 (right gutter), 0 the middle;
    power 0..1. The ball knocks the pins on its line, and falling pins take down the ones behind them,
    more often the harder the ball."""
    if abs(aim) > 0.95 or not standing:
        return set()  # the gutter
    x = aim * 2.5  # in pin spacings
    if standing == ALL_PINS and 0.08 < abs(aim) < 0.3 and power > 0.6 and rnd.random() < 0.25 + 0.35 * power:
        return set(standing)  # the pocket: a strike
    hit = {i for i in standing if abs(PIN_SPOTS[i][0] - x) < 0.55 + 0.3 * power}
    chain = 0.35 + 0.5 * power
    for row in (3, 2, 1, 0):  # from the head pin back, falling pins knock their neighbours
        for i in [j for j in hit if PIN_SPOTS[j][1] == row]:
            for j in standing - hit:
                dx = abs(PIN_SPOTS[j][0] - PIN_SPOTS[i][0])
                behind = PIN_SPOTS[j][1] == row - 1 and dx <= 0.5
                beside = PIN_SPOTS[j][1] == row and dx <= 1.0
                if (behind and rnd.random() < chain) or (beside and rnd.random() < chain * 0.35):
                    hit.add(j)
    return hit


PIN_PROFILE = ((0.0, -1.0), (0.13, -0.98), (0.17, -0.88), (0.12, -0.72), (0.1, -0.64), (0.2, -0.5), (0.26, -0.3),
               (0.22, -0.08), (0.14, 0.0))  # the right half of a pin, from the top down, in pin heights


def draw_pin_tilted(c: tk.Canvas, x: float, base: float, height: float, angle: float) -> None:
    """A pin standing on (x, base), leaning by angle degrees (90: lying on its right side); it greys as it lies."""
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)

    def at(u, v):  # u across, v up the pin (negative up), both in pin heights
        return x + (u * ca - v * sa) * height, base + (u * sa + v * ca) * height

    side = [at(u, v) for u, v in PIN_PROFILE]
    outline = side + [at(-u, v) for u, v in reversed(PIN_PROFILE)]
    lie = min(1.0, abs(angle) / 90)
    c.create_polygon([q for pt in outline for q in pt], smooth=True, fill=blend("#fbfaf6", "#cfc9bf", lie),
                     outline="#9a958e")
    for v0, v1, half in ((-0.7, -0.665, 0.11), (-0.635, -0.6, 0.13)):  # the two red stripes
        band = [at(-half, v0), at(half, v0), at(half, v1), at(-half, v1)]
        c.create_polygon([q for pt in band for q in pt], fill="#d6343b", outline="")


# ------------------------------------------------------------------ the game window

class BowlingGame(tk.Toplevel):
    """The lane: slide the ball to a spot, swing the arrow for the direction, then the power bar. The ball
    rolls with a little random spin and the pins topple one after another. settings keeps the game; on_sound
    plays the skin's sounds; on_change tells the player the score sheet changed."""

    FRAME_MS = 16

    SPOT, AIM, POWER, ROLL, RESULT, DONE = "spot", "aim", "power", "roll", "result", "done"

    def __init__(self, master, settings, on_sound=None, on_change=None):
        super().__init__(master, bg=skin.T.body)
        self.title("Kuglanje")
        self.resizable(False, False)
        self.settings, self.on_sound, self.on_change = settings, on_sound, on_change
        self.rolls: list[int] = [r for r in settings["bowling_rolls"] if isinstance(r, int)]
        self.standing = set(ALL_PINS)
        if frame_open(self.rolls):  # a frame half played: the pins left standing
            saved = {i for i in settings["bowling_pins"] if i in ALL_PINS}
            n = standing_count(self.rolls)
            self.standing = saved if len(saved) == n else set(range(n))
        self.rnd = random.Random()
        self.w, self.h = px(240), px(380)
        self.c = tk.Canvas(self, width=self.w, height=self.h, bg="#0a0a0a", highlightthickness=0, cursor="hand2")
        self.c.pack(padx=px(6), pady=px(6))
        self.c.bind("<Button-1>", self.click)
        self.bind("<space>", self.click)
        self.state_ = self.DONE if game_over(self.rolls) else self.SPOT
        self.t = 0
        self.spot = self.aim = self.power = 0.0
        self.ball_y = 0.0
        self.hook = self.spin = self.turn = 0.0
        self.message = ""
        self.knocked: set[int] = set()
        self.falls: dict[int, tuple[int, int, float]] = {}  # knocked pin -> (delay in frames, side, slide)
        self.shown = ""  # the message, shown once the pins are down
        self.transient(master)
        self._step()

    # -------------------------------------------------------------- game logic

    def click(self, _event=None):
        if self.state_ == self.SPOT:
            self.state_, self.t = self.AIM, 0
        elif self.state_ == self.AIM:
            self.state_, self.t = self.POWER, 0
        elif self.state_ == self.POWER:
            self.state_, self.ball_y = self.ROLL, 0.0
            self.hook = self.rnd.uniform(-MAX_HOOK, MAX_HOOK)  # a bit of random spin
            self.spin = math.copysign(self.rnd.uniform(0.15, 0.35), self.hook)
            if self.on_sound:
                self.on_sound("roll")
        elif self.state_ == self.DONE:
            self.rolls, self.standing, self.message = [], set(ALL_PINS), ""
            self.state_ = self.SPOT
            self._save()

    def _finish_roll(self) -> None:
        aim = pin_aim(self.spot, self.aim, self.hook)
        self.knocked = throw(aim, self.power, self.standing, self.rnd)
        self.falls = {}
        for i in self.knocked:  # the pins nearest the ball go first, the rest follow, falling away from it
            dx, row = PIN_SPOTS[i]
            side = 1 if dx > aim * 2.5 + self.rnd.uniform(-0.4, 0.4) else -1  # in pin spacings
            self.falls[i] = ((3 - row) * 5 + self.rnd.randint(0, 5), side, self.rnd.uniform(0.3, 1.0))
        fresh = not frame_open(self.rolls)
        self.rolls.append(len(self.knocked))
        self.standing -= self.knocked
        if fresh and len(self.knocked) == 10:
            self.message = "STRIKE!"
        elif not fresh and not self.standing:
            self.message = "SPARE!"
        elif abs(aim) > 0.95:
            self.message = "Kanal!"
        elif not self.knocked:
            self.message = "Promašaj"
        else:
            self.message = str(len(self.knocked))
        if self.on_sound:
            self.on_sound("flip" if self.message in ("STRIKE!", "SPARE!") else "stop" if self.knocked else "pause")
        if not frame_open(self.rolls):
            self.standing = set(ALL_PINS)  # a fresh rack for the next frame
        if game_over(self.rolls):
            score = total(self.rolls)
            if score > self.settings["bowling_best"]:
                self.settings.update({"bowling_best": score})
                self.message = f"Rekord! {score}"
            else:
                self.message = f"Kraj: {score}"
        self.state_, self.t = self.RESULT, 0
        self._save()

    def _save(self) -> None:
        self.settings.update({"bowling_rolls": list(self.rolls), "bowling_pins": sorted(self.standing)})
        if self.on_change:
            self.on_change()

    # -------------------------------------------------------------- animation

    def _step(self) -> None:
        if not self.winfo_exists():
            return
        self.t += 1
        if self.state_ == self.SPOT:
            self.spot = math.sin(self.t * 0.035) * 0.85
        elif self.state_ == self.AIM:
            self.aim = math.sin(self.t * 0.055)
        elif self.state_ == self.POWER:
            self.power = (1 - math.cos(self.t * 0.065)) / 2
        elif self.state_ == self.ROLL:
            self.ball_y += 0.014 + 0.016 * self.power
            self.turn += self.spin
            if self.ball_y >= 1:
                self._finish_roll()
        elif self.state_ == self.RESULT:
            self.ball_y += 0.014 + 0.016 * self.power  # on through the pins and off the end of the lane
            self.turn += self.spin
            if self.t > 95:
                self.state_ = self.DONE if game_over(self.rolls) else self.SPOT
                self.knocked, self.falls = set(), {}
                if self.state_ == self.SPOT:
                    self.message = ""
        self.draw()
        self.after(self.FRAME_MS, self._step)

    def _fall(self, i: int) -> float:
        """How far knocked pin i has toppled, 0 standing .. 1 lying."""
        if self.state_ != self.RESULT or i not in self.falls:
            return 1.0 if i in self.knocked else 0.0
        p = max(0.0, min(1.0, (self.t - self.falls[i][0]) / 14))
        return 1 - (1 - p) ** 2  # it starts slow and drops

    def draw(self) -> None:
        c = self.c
        c.delete("all")
        w, h = self.w, self.h
        top, bottom = px(70), h - px(16)
        lx0, lx1 = w * 0.18, w * 0.82
        half, run = (lx1 - lx0) / 2, bottom - top - px(60)
        c.create_rectangle(lx0 - px(14), top, lx1 + px(14), bottom, fill="#2a2a30", outline="")  # the gutters
        c.create_rectangle(lx0, top, lx1, bottom, fill="#e3b878", outline="")
        for k in range(1, 12):
            x = lx0 + (lx1 - lx0) * k / 12
            c.create_line(x, top, x, bottom, fill="#d9ab68")
        for k in range(7):  # the aiming arrows
            x = lx0 + (lx1 - lx0) * (k + 1) / 8
            y = bottom - px(70) - abs(k - 3) * px(6)
            c.create_polygon(x - px(3), y, x + px(3), y, x, y - px(9), fill="#7a4a20", outline="")
        self._sheet(c, w)
        # the ball, under the pins once it reaches them
        rolling = self.state_ in (self.ROLL, self.RESULT)
        y = self.ball_y if rolling else 0.0
        across = ball_x(self.spot, 0.0 if self.state_ == self.SPOT else self.aim, y, self.hook if rolling else 0.0)
        bx, by = w / 2 + across * half, bottom - px(14) - run * y
        r = px(8) if abs(across) > 1 else px(11)  # down in the gutter
        if self.state_ != self.DONE and by > top + r:
            self._ball(c, bx, by, r)
        size = px(26)
        for i, (dx, row) in enumerate(PIN_SPOTS):
            if i in self.standing or i in self.knocked:
                f = self._fall(i)
                side, slide = (self.falls[i][1], self.falls[i][2]) if i in self.falls else (1, 0.5)
                draw_pin_tilted(c, w / 2 + dx * px(30) + side * f * slide * px(8), top + px(28) + row * px(16),
                                size, side * f * 90)
        if self.state_ == self.SPOT:  # sliding left and right along the foul line
            for d in (-1, 1):
                c.create_polygon(bx + d * (r + px(4)), by - px(5), bx + d * (r + px(4)), by + px(5),
                                 bx + d * (r + px(11)), by, fill="#ff4f9a", outline="")
        if self.state_ in (self.AIM, self.POWER):  # the arrow swings left and right: the ball follows its line
            dx, dy = self.aim * SPREAD * half, -run
            n = math.hypot(dx, dy)
            c.create_line(bx + dx / n * (r + px(4)), by + dy / n * (r + px(4)), bx + dx / n * px(58),
                          by + dy / n * px(58), fill="#ff4f9a", width=max(2, px(3)), arrow="last",
                          arrowshape=(px(10), px(12), px(5)))
        if self.state_ == self.POWER:
            px0 = lx1 + px(14)
            c.create_rectangle(px0, bottom - px(110), px0 + px(9), bottom, outline="#2ad1c9")
            c.create_rectangle(px0 + 1, bottom - px(110) * self.power, px0 + px(9) - 1, bottom - 1,
                               fill=blend("#2ad1c9", "#ff4f9a", self.power), outline="")
        font = skin.T.font("sans", 14, "bold")
        hint = {self.SPOT: "klik: mesto", self.AIM: "klik: smer", self.POWER: "klik: snaga",
                self.DONE: "klik: nova igra"}.get(self.state_, "")
        if self.message and (self.state_ != self.RESULT or self.t > 30):
            c.create_text(w / 2, top + px(150), text=self.message, fill="#ffb000", font=font)
        if hint:
            c.create_text(w / 2, h - px(6), text=hint, fill="#8a8aa0", font=skin.T.font("sans", 8))

    def _ball(self, c: tk.Canvas, x: float, y: float, r: float) -> None:
        """The ball, its finger holes turning with the spin."""
        c.create_oval(x - r, y - r, x + r, y + r, fill="#3b1f5e", outline="#1d0f30")
        c.create_oval(x - r * 0.55, y - r * 0.7, x + r * 0.05, y - r * 0.25, fill="#6a4a9a", outline="")
        for fa, fd in ((-0.5, 0.42), (0.0, 0.5), (0.55, 0.4)):
            a = self.turn + fa
            hx, hy = x + math.cos(a) * fd * r, y + math.sin(a) * fd * r
            c.create_oval(hx - r * 0.15, hy - r * 0.15, hx + r * 0.15, hy + r * 0.15, fill="#0d0618", outline="")

    def _sheet(self, c: tk.Canvas, w: int) -> None:
        """The score sheet at the top: ten frames with their marks and running totals, the best score."""
        fw = (w - px(8)) / 10
        y0 = px(6)
        ms, ss = marks(self.rolls), scores(self.rolls)
        font = skin.T.font("mono", 7, "bold")
        for k in range(10):
            x = px(4) + k * fw
            c.create_rectangle(x, y0, x + fw, y0 + px(34), outline="#2ad1c9")
            c.create_rectangle(x + fw * 0.5, y0, x + fw, y0 + px(12), outline="#2ad1c9")
            if k < len(ms):
                c.create_text(x + fw * 0.5, y0 + px(6), text=ms[k], fill="#ff4f9a", font=font)
            if k < len(ss) and ss[k] is not None:
                c.create_text(x + fw / 2, y0 + px(24), text=str(ss[k]), fill="#ffe2a8", font=font)
        c.create_text(w / 2, y0 + px(48), text=f"ukupno {total(self.rolls)}   ·   rekord {self.settings['bowling_best']}",
                      fill="#8a8aa0", font=skin.T.font("mono", 8))
