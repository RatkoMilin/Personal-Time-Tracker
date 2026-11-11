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
from .scenes import PIN_SPOTS, draw_pin
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

def throw(aim: float, power: float, standing: set[int], rnd: random.Random) -> set[int]:
    """Which of the standing pins fall. aim: -1 (left gutter) .. 1 (right gutter), 0 the middle;
    power 0..1. The ball knocks the pins on its line, and falling pins take down the ones behind them,
    more often the harder the ball."""
    if abs(aim) > 0.95 or not standing:
        return set()  # the gutter
    x = aim * 2.0  # in pin spacings
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


# ------------------------------------------------------------------ the game window

class BowlingGame(tk.Toplevel):
    """The lane, the aiming arrow and the power bar. get/put store the game in the settings; on_sound
    plays the skin's sounds; on_change tells the player the score sheet changed."""

    AIM, POWER, ROLL, RESULT, DONE = "aim", "power", "roll", "result", "done"

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
        self.state_ = self.DONE if game_over(self.rolls) else self.AIM
        self.t = 0
        self.aim = self.power = 0.0
        self.ball_y = 0.0
        self.message = ""
        self.knocked: set[int] = set()
        self.transient(master)
        self._step()

    # -------------------------------------------------------------- game logic

    def click(self, _event=None):
        if self.state_ == self.AIM:
            self.state_, self.t = self.POWER, 0
        elif self.state_ == self.POWER:
            self.state_, self.ball_y = self.ROLL, 0.0
            if self.on_sound:
                self.on_sound("roll")
        elif self.state_ == self.DONE:
            self.rolls, self.standing, self.message = [], set(ALL_PINS), ""
            self.state_ = self.AIM
            self._save()

    def _finish_roll(self) -> None:
        self.knocked = throw(self.aim, self.power, self.standing, self.rnd)
        fresh = not frame_open(self.rolls)
        self.rolls.append(len(self.knocked))
        self.standing -= self.knocked
        if fresh and len(self.knocked) == 10:
            self.message = "STRIKE!"
        elif not fresh and not self.standing:
            self.message = "SPARE!"
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
        if self.state_ == self.AIM:
            self.aim = math.sin(self.t * 0.09) * 0.98
        elif self.state_ == self.POWER:
            self.power = (1 - math.cos(self.t * 0.12)) / 2
        elif self.state_ == self.ROLL:
            self.ball_y += 0.035 + 0.035 * self.power
            if self.ball_y >= 1:
                self._finish_roll()
        elif self.state_ == self.RESULT and self.t > 28:
            self.state_ = self.DONE if game_over(self.rolls) else self.AIM
            self.knocked = set()
            if self.state_ == self.AIM:
                self.message = ""
        self.draw()
        self.after(30, self._step)

    def draw(self) -> None:
        c = self.c
        c.delete("all")
        w, h = self.w, self.h
        top, bottom = px(70), h - px(16)
        lx0, lx1 = w * 0.18, w * 0.82
        c.create_rectangle(lx0 - px(10), top, lx1 + px(10), bottom, fill="#2a2a30", outline="")  # the gutters
        c.create_rectangle(lx0, top, lx1, bottom, fill="#e3b878", outline="")
        for k in range(1, 12):
            x = lx0 + (lx1 - lx0) * k / 12
            c.create_line(x, top, x, bottom, fill="#d9ab68")
        for k in range(7):  # the aiming arrows
            x = lx0 + (lx1 - lx0) * (k + 1) / 8
            y = bottom - px(70) - abs(k - 3) * px(6)
            c.create_polygon(x - px(3), y, x + px(3), y, x, y - px(9), fill="#7a4a20", outline="")
        self._sheet(c, w)
        size = px(26)
        for i, (dx, row) in enumerate(PIN_SPOTS):
            x = w / 2 + dx * px(22)
            base = top + px(28) + row * px(16)
            if i in self.standing or i in self.knocked:
                draw_pin(c, x, base, size, down=i in self.knocked)
        ball_x = w / 2 + self.aim * (lx1 - lx0) / 2
        if self.state_ == self.ROLL:
            by = bottom - px(14) - (bottom - top - px(60)) * self.ball_y
        else:
            by = bottom - px(14)
        r = px(11)
        if self.state_ in (self.AIM, self.POWER, self.ROLL):
            c.create_oval(ball_x - r, by - r, ball_x + r, by + r, fill="#3b1f5e", outline="#1d0f30")
            c.create_oval(ball_x - r * 0.55, by - r * 0.7, ball_x + r * 0.05, by - r * 0.25, fill="#6a4a9a", outline="")
            for fx, fy in ((0.25, -0.2), (0.45, 0.0), (0.2, 0.15)):
                c.create_oval(ball_x + fx * r - px(1.6), by + fy * r - px(1.6), ball_x + fx * r + px(1.6),
                              by + fy * r + px(1.6), fill="#0d0618", outline="")
        if self.state_ == self.AIM:
            c.create_line(ball_x, by - r - px(4), ball_x, by - r - px(40), fill="#ff4f9a", width=max(2, px(3)),
                          arrow="last", arrowshape=(px(10), px(12), px(5)))
        if self.state_ == self.POWER:
            bx = lx1 + px(14)
            c.create_rectangle(bx, bottom - px(110), bx + px(9), bottom, outline="#2ad1c9")
            fill_top = bottom - px(110) * self.power
            c.create_rectangle(bx + 1, fill_top, bx + px(9) - 1, bottom - 1,
                               fill=blend("#2ad1c9", "#ff4f9a", self.power), outline="")
        font = skin.T.font("sans", 14, "bold")
        hint = {self.AIM: "klik: smer", self.POWER: "klik: snaga", self.DONE: "klik: nova igra"}.get(self.state_, "")
        if self.message:
            c.create_text(w / 2, top + px(150), text=self.message, fill="#ffb000", font=font)
        if hint:
            c.create_text(w / 2, h - px(6), text=hint, fill="#8a8aa0", font=skin.T.font("sans", 8))

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
