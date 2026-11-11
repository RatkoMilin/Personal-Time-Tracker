"""Vijača's bonus round: the mestre plays a phrase on four instruments, you play it back.

Every 25 jumps a pandeiro shows up next to the jumper; clicking it opens the roda. The mestre plays a
phrase (berimbau, atabaque, pandeiro, agogô), you repeat it by clicking the instruments, and each phrase
repeated right grows by one note and earns two minutes of double points for the jumps (ten at most).
A wrong note ends the round; nothing is lost.
"""

from __future__ import annotations

import random
import time
import tkinter as tk

from . import skin
from .skin import blend, px

BONUS_EVERY = 25  # jumps between two bonus rounds
MINUTES_PER_PHRASE = 2
MAX_MINUTES = 10
START_LENGTH = 3
TOQUE_MS = (340, 340, 680)  # the mestre's swing between notes: short, short, long, as a berimbau toque
PADS = (("Berimbau", "#ffd400"), ("Atabaque", "#1f9d4a"), ("Pandeiro", "#1f4fbf"), ("Agogô", "#f2f2f2"))


class SimonGame:
    """The rules, without any drawing: phrase() is what the mestre plays, press() is your answer."""

    def __init__(self, rnd: random.Random | None = None):
        self.rnd = rnd or random.Random()
        self.sequence = [self.rnd.randrange(4) for _ in range(START_LENGTH)]
        self.pos = 0
        self.phrases = 0  # phrases repeated right
        self.over = False

    def press(self, pad: int) -> str:
        """'ok' (keep going), 'phrase' (the whole phrase right: a longer one follows) or 'wrong'."""
        if self.over:
            return "wrong"
        if pad != self.sequence[self.pos]:
            self.over = True
            return "wrong"
        self.pos += 1
        if self.pos < len(self.sequence):
            return "ok"
        self.phrases += 1
        self.pos = 0
        self.sequence.append(self.rnd.randrange(4))
        if self.minutes() >= MAX_MINUTES:
            self.over = True
        return "phrase"

    def minutes(self) -> int:
        return min(MAX_MINUTES, self.phrases * MINUTES_PER_PHRASE)


class SimonRound(tk.Toplevel):
    """The roda: four instrument pads. on_done(minutes) gets the double-points minutes won."""

    def __init__(self, master, on_sound=None, on_done=None, on_phrase=None):
        super().__init__(master, bg=skin.T.body)
        self.title("Roda: bonus")
        self.resizable(False, False)
        self.on_sound, self.on_done = on_sound, on_done
        self.on_phrase = on_phrase  # plays the whole phrase as one sound; True if it did
        self.game = SimonGame()
        self.lit: int | None = None
        self.listening = False
        self.size = px(220)
        self.c = tk.Canvas(self, width=self.size, height=self.size + px(50), bg=skin.T.lcd_bg, highlightthickness=0,
                           cursor="hand2")
        self.c.pack(padx=px(6), pady=px(6))
        self.c.bind("<Button-1>", self._click)
        self.message = "Slušaj mestrea..."
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self.finish)
        self.draw()
        self.after(700, self.play_phrase)

    def _pad_box(self, i: int) -> tuple[float, float, float, float]:
        half = self.size / 2
        x0, y0 = (i % 2) * half, (i // 2) * half
        g = px(6)
        return x0 + g, y0 + g, x0 + half - g, y0 + half - g

    def play_phrase(self) -> None:
        """The mestre plays the phrase in the toque's swing (short, short, long), then it is your turn."""
        self.listening = False
        self.message = "Slušaj mestrea..."

        seq = list(self.game.sequence)
        at = [sum(TOQUE_MS[j % len(TOQUE_MS)] for j in range(k)) for k in range(len(seq))]
        # the laptop plays one sound at a time: one sound for the whole phrase keeps every note whole and on time
        whole = bool(self.on_phrase and self.on_phrase([(t / 1000, f"pad{p}") for t, p in zip(at, seq)]))

        def note(k):
            if self.winfo_exists():
                self._flash(seq[k], sound=not whole)

        def your_turn():
            if self.winfo_exists():
                self.lit = None
                self.listening = True
                self.message = "Tvoj red: ponovi"
                self.draw()

        for k, t in enumerate(at):
            self.after(t, note, k)
        self.after(at[-1] + 450, your_turn)

    def _flash(self, pad: int, sound: bool = True) -> None:
        self.lit = pad
        if sound and self.on_sound:
            self.on_sound(f"pad{pad}")
        self.draw()
        self.after(260, self._unflash, pad)

    def _unflash(self, pad: int) -> None:
        if self.winfo_exists() and self.lit == pad:
            self.lit = None
            self.draw()

    def _click(self, event) -> None:
        if self.game.over:
            self.finish()
            return
        if not self.listening:
            return
        pad = next((i for i in range(4) if self._pad_box(i)[0] <= event.x <= self._pad_box(i)[2]
                    and self._pad_box(i)[1] <= event.y <= self._pad_box(i)[3]), None)
        if pad is None:
            return
        self._flash(pad)
        result = self.game.press(pad)
        if result == "phrase" and not self.game.over:
            self.message = f"Tačno! ×2 još {self.game.minutes()} min"
            self.listening = False
            self.draw()
            self.after(900, self.play_phrase)
        elif self.game.over:
            won = self.game.minutes()
            self.message = f"Bonus: ×2 poena {won} min" if won else "Promašaj. Sledeći put!"
            if self.on_sound:
                self.on_sound("flip" if won else "stop")
            self.listening = False
            self.draw()

    def finish(self) -> None:
        if self.on_done:
            self.on_done(self.game.minutes())
            self.on_done = None
        self.destroy()

    def draw(self) -> None:
        c = self.c
        c.delete("all")
        for i, (name, color) in enumerate(PADS):
            x0, y0, x1, y1 = self._pad_box(i)
            lit = self.lit == i
            skin.round_rect(c, x0, y0, x1, y1, px(14), fill=color if lit else blend(skin.T.lcd_bg, color, 0.35),
                            outline=color, width=max(1, px(2)))
            c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=name,
                          fill="#111111" if lit else blend(color, "#ffffff", 0.3), font=skin.T.font("sans", 10, "bold"))
        y = self.size + px(16)
        c.create_text(self.size / 2, y, text=self.message, fill=skin.T.lcd_on, font=skin.T.font("sans", 10, "bold"))
        hint = "klik: zatvori" if self.game.over else f"niz od {len(self.game.sequence)} tonova"
        c.create_text(self.size / 2, y + px(20), text=hint, fill=skin.T.lcd_dim, font=skin.T.font("sans", 8))


def bonus_active(until: float, now: float | None = None) -> bool:
    return (time.time() if now is None else now) < until
