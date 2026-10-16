"""The 2000s skins: the gadgets next to the clock and the things that grow around the playlist.

Kinetik: a speedometer. The needle climbs with the task's time (top speed after 90 minutes), every
  15 minutes is a lap, and on pause the bike slows down instead of stopping dead.
Blades: a ring of light around an orb. One quarter lights up per 15 minutes; a full ring is an hour
  and pops up an "Achievement unlocked" toast.
Kristalne kule: a crystal tower for every task of the day, as tall as the time spent on it.
Atmos: 16 pads of a drum machine, one lights up every 5 minutes; a full phrase (80 minutes) grows
  leaves around the playlist.
Grafiti: a new tag on the wall around the playlist for every full hour worked today.
"""

from __future__ import annotations

import math
import random
import tkinter as tk

from . import skin
from .skin import blend, px

LAP = 15 * 60  # Kinetik: seconds per lap
TOP_SPEED_AT = 90 * 60  # Kinetik: the needle reaches the top after this much of the task
QUARTER = 15 * 60  # Blades: one quarter of the ring
PAD = 5 * 60  # Atmos: one pad of the sequencer
PHRASE = 16 * PAD  # Atmos: all 16 pads (80 minutes)
TOWER_FULL = 3 * 3600  # Kristalne kule: a tower is full height at three hours
MAX_TOWERS = 8
MAX_TAGS = 9


def laps_done(seconds: float) -> int:
    return int(max(0.0, seconds) // LAP)


def speed_target(seconds: float, playing: bool) -> float:
    """Where the Kinetik needle is heading (0..1): idle revs at the start, top speed after 90 minutes."""
    if not playing:
        return 0.0
    return 0.15 + 0.85 * min(1.0, max(0.0, seconds) / TOP_SPEED_AT)


def quarters_lit(seconds: float) -> int:
    return int((max(0.0, seconds) % 3600) // QUARTER)


def hours_done(seconds: float) -> int:
    return int(max(0.0, seconds) // 3600)


def pads_lit(seconds: float) -> int:
    return int((max(0.0, seconds) % PHRASE) // PAD)


def phrases_done(seconds: float) -> int:
    return int(max(0.0, seconds) // PHRASE)


def tower_height(seconds: float) -> float:
    return min(1.0, max(0.0, seconds) / TOWER_FULL)


def tags_for(day_seconds: float) -> int:
    """Grafiti: one tag per full hour worked today."""
    return min(MAX_TAGS, int(max(0.0, day_seconds) // 3600))


class _Gadget(tk.Canvas):
    def __init__(self, master, width: float, height: float):
        self.w, self.h = px(width), px(height)
        super().__init__(master, width=self.w, height=self.h, bg=skin.T.lcd_bg, highlightthickness=0)


# ------------------------------------------------------------------ Kinetik

CYAN, MAGENTA = "#2ff3ff", "#ff2fb3"


class Speedometer(_Gadget):
    """set(seconds, state) on every tick; on_lap is called when a lap (15 minutes) is done."""

    def __init__(self, master, on_lap=None, width: float = 58, height: float = 44):
        super().__init__(master, width, height)
        self.on_lap = on_lap
        self.seconds, self.state = 0.0, "stopped"
        self.laps: int | None = None
        self.speed = 0.0
        self.draw()

    def set(self, seconds: float, state: str) -> None:
        now = laps_done(seconds)
        if self.laps is not None and state == "playing" and now > self.laps and self.on_lap:
            self.on_lap()
        self.seconds, self.state, self.laps = seconds, state, now
        target = speed_target(seconds, state == "playing")
        # Speeding up is quick, slowing down takes a few seconds (the bike rolls out on pause).
        self.speed += (target - self.speed) * (0.55 if target > self.speed else 0.22)
        if abs(target - self.speed) < 0.003:
            self.speed = target
        self.draw()

    def draw(self) -> None:
        self.delete("all")
        w, h = self.w, self.h
        cx, cy, r = w / 2, h * 0.6, min(w / 2, h * 0.6) - px(2)
        box = (cx - r, cy - r, cx + r, cy + r)
        self.create_arc(*box, start=-30, extent=240, style="arc", outline="#1c2340", width=max(2, px(4)))
        lit, steps = self.speed, 24
        for k in range(steps):  # the lit part of the scale, cyan to magenta
            if (k + 1) / steps > lit + 1e-9:
                break
            self.create_arc(*box, start=210 - 240 * (k + 1) / steps, extent=240 / steps + 0.6, style="arc",
                            outline=blend(CYAN, MAGENTA, k / (steps - 1)), width=max(2, px(4)))
        for k in range(9):  # ticks
            a = math.radians(210 - 240 * k / 8)
            r0 = r - px(5 if k % 2 == 0 else 3)
            self.create_line(cx + math.cos(a) * r0, cy - math.sin(a) * r0, cx + math.cos(a) * (r - px(1)),
                             cy - math.sin(a) * (r - px(1)), fill="#8fa0c8")
        a = math.radians(210 - 240 * self.speed)
        self.create_line(cx, cy, cx + math.cos(a) * (r - px(4)), cy - math.sin(a) * (r - px(4)), fill="#ffffff",
                         width=max(1, px(1.6)), capstyle="round")
        self.create_oval(cx - px(2.5), cy - px(2.5), cx + px(2.5), cy + px(2.5), fill=MAGENTA, outline="")
        font = skin.T.font("mono", 7, "bold")
        self.create_text(cx, h - px(5), text=f"{round(self.speed * 320)}", fill=CYAN, font=font)
        if self.state != "stopped":
            self.create_text(px(2), px(1), anchor="nw", text=f"L{laps_done(self.seconds) + 1}", fill=MAGENTA,
                             font=font)


# ------------------------------------------------------------------ Blades

GREEN, GREEN_DARK, RING_OFF = "#7ed321", "#3f7a0e", "#c9d1d8"


class RingOfLight(_Gadget):
    """Four quarters around an orb; on_hour is called when the ring fills up (a full hour)."""

    def __init__(self, master, on_hour=None, width: float = 44, height: float = 44):
        super().__init__(master, width, height)
        self.on_hour = on_hour
        self.seconds, self.running = 0.0, False
        self.hours: int | None = None
        self.pulse = False
        self.draw()

    def set(self, seconds: float, running: bool) -> None:
        now = hours_done(seconds)
        if self.hours is not None and running and now > self.hours and self.on_hour:
            self.on_hour(now)
        self.seconds, self.running, self.hours = seconds, running, now
        self.pulse = not self.pulse
        self.draw()

    def draw(self) -> None:
        self.delete("all")
        w, h = self.w, self.h
        cx, cy, r = w / 2, h / 2, min(w, h) / 2 - px(3)
        box = (cx - r, cy - r, cx + r, cy + r)
        lit = quarters_lit(self.seconds)
        for k, start in enumerate((90, 0, 270, 180)):  # clockwise from the top left, like the controller
            if k < lit:
                color = GREEN
                self.create_arc(*box, start=start + 6, extent=78, style="arc", outline=blend(skin.T.lcd_bg, GREEN, 0.35),
                                width=max(3, px(7)))
            elif k == lit and self.running and self.pulse:
                color = blend(RING_OFF, GREEN, 0.5)  # the next quarter blinks while the timer runs
            else:
                color = RING_OFF
            self.create_arc(*box, start=start + 6, extent=78, style="arc", outline=color, width=max(2, px(4)))
        orb = r - px(6)
        on = self.running or self.seconds > 0
        face, edge = (GREEN, GREEN_DARK) if on else ("#b6bec5", "#8a939b")
        self.create_oval(cx - orb, cy - orb, cx + orb, cy + orb, fill=face, outline=edge)
        self.create_oval(cx - orb * 0.7, cy - orb * 0.85, cx + orb * 0.7, cy - orb * 0.05,
                         fill=blend(face, "#ffffff", 0.55), outline="")  # glossy highlight
        if hours_done(self.seconds):
            self.create_text(cx, cy + orb * 0.25, text=str(hours_done(self.seconds)), fill="#ffffff",
                             font=skin.T.font("sans", 8, "bold"))


def achievement(master: tk.Misc, text: str, duration_ms: int = 3800) -> tk.Toplevel | None:
    """Blades: an "Achievement unlocked" toast at the bottom of the window, gone after a few seconds."""
    try:
        if not master.winfo_viewable():
            return None
        top = tk.Toplevel(master)
    except tk.TclError:
        return None
    top.overrideredirect(True)
    try:
        top.attributes("-topmost", True)
    except tk.TclError:
        pass
    w, h = px(250), px(50)
    c = tk.Canvas(top, width=w, height=h, bg="#101214", highlightthickness=0, bd=0)
    c.pack()
    skin.round_rect(c, 1, 1, w - 2, h - 2, px(12), fill="#2a2f33", outline="#5a6168")
    r = px(15)
    cx, cy = px(8) + r, h / 2
    c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=GREEN, outline=GREEN_DARK)
    c.create_oval(cx - r * 0.7, cy - r * 0.85, cx + r * 0.7, cy - r * 0.05, fill="#c4f08a", outline="")
    # a little trophy on the orb
    c.create_polygon(cx - px(6), cy - px(5), cx + px(6), cy - px(5), cx + px(4), cy + px(2), cx - px(4), cy + px(2),
                     fill="#ffffff", outline="")
    c.create_rectangle(cx - px(1.2), cy + px(2), cx + px(1.2), cy + px(6), fill="#ffffff", outline="")
    c.create_rectangle(cx - px(4), cy + px(6), cx + px(4), cy + px(8), fill="#ffffff", outline="")
    x = cx + r + px(10)
    c.create_text(x, cy - px(8), anchor="w", text="Achievement unlocked", fill="#ffffff",
                  font=skin.T.font("sans", 9, "bold"))
    c.create_text(x, cy + px(9), anchor="w", text=text, fill="#cfd6dc", font=skin.T.font("sans", 9))
    master.update_idletasks()
    x0 = master.winfo_rootx() + (master.winfo_width() - w) // 2
    y0 = master.winfo_rooty() + master.winfo_height() - h - px(14)
    top.geometry(f"{w}x{h}+{x0}+{y0}")
    top.after(duration_ms, top.destroy)
    return top


# ------------------------------------------------------------------ Kristalne kule

TOWER_DEEP, TOWER_LIGHT, TOWER_GLOW = "#1b2a6b", "#6f9bff", "#cfe0ff"


class Towers(_Gadget):
    """set(seconds per task, index of the running task or None); on_level when the running tower grows an hour."""

    def __init__(self, master, on_level=None, width: float = 66, height: float = 44):
        super().__init__(master, width, height)
        self.on_level = on_level
        self.groups: list[float] = []
        self.active: int | None = None
        self.levels: int | None = None
        self.twinkle = False
        self.draw()

    def set(self, groups: list[float], active: int | None) -> None:
        level = hours_done(groups[active]) if active is not None and active < len(groups) else None
        if self.levels is not None and level is not None and level > self.levels and self.on_level:
            self.on_level()
        self.groups, self.active, self.levels = list(groups), active, level
        self.twinkle = not self.twinkle
        self.draw()

    def draw(self) -> None:
        self.delete("all")
        w, h = self.w, self.h
        for k in range(4):  # a faint blue horizon in the fog
            y = h - px(3) - k * px(3)
            self.create_line(0, y, w, y, fill=blend(skin.T.lcd_bg, "#22346e", 0.6 - k * 0.14))
        first = max(0, len(self.groups) - MAX_TOWERS)
        shown = self.groups[first:]
        if not shown:
            return
        step = w / MAX_TOWERS
        tw = step * 0.62
        base = h - px(3)
        room = h - px(9)
        for i, secs in enumerate(shown):
            x = step * (i + 0.5) + (MAX_TOWERS - len(shown)) * step / 2
            top = base - max(px(3), tower_height(secs) * room)
            active = self.active is not None and first + i == self.active
            body = TOWER_LIGHT if active else blend(TOWER_DEEP, TOWER_LIGHT, 0.25 + 0.5 * tower_height(secs))
            if active:  # a soft glow around the running tower
                g = px(2)
                self.create_rectangle(x - tw / 2 - g, top - g, x + tw / 2 + g, base, fill=blend(skin.T.lcd_bg, TOWER_LIGHT, 0.3),
                                      outline="")
            self.create_rectangle(x - tw / 2, top, x + tw / 2, base, fill=body, outline="")
            self.create_rectangle(x - tw / 2, top, x - tw / 6, base, fill=blend(body, "#ffffff", 0.3), outline="")
            self.create_polygon(x - tw / 2, top, x, top - tw * 0.45, x + tw / 2, top, fill=blend(body, TOWER_GLOW, 0.6),
                                outline="")  # the crystal's point
            if active and self.twinkle:
                s = px(2)
                self.create_line(x - s, top - tw * 0.45 - px(2), x + s, top - tw * 0.45 - px(2), fill=TOWER_GLOW)
                self.create_line(x, top - tw * 0.45 - px(2) - s, x, top - tw * 0.45 - px(2) + s, fill=TOWER_GLOW)


# ------------------------------------------------------------------ Atmos

PAD_ON, PAD_ON2, PAD_OFF = "#36d6b0", "#b6ff5a", "#163a33"


class Pads(_Gadget):
    """A 4x4 drum machine: one pad per 5 minutes; on_phrase when all 16 are lit (80 minutes)."""

    def __init__(self, master, on_phrase=None, width: float = 44, height: float = 44):
        super().__init__(master, width, height)
        self.on_phrase = on_phrase
        self.seconds, self.running = 0.0, False
        self.phrases: int | None = None
        self.step = 0
        self._playing = False
        self.draw()

    def set(self, seconds: float, running: bool) -> None:
        now = phrases_done(seconds)
        if self.phrases is not None and running and now > self.phrases and self.on_phrase:
            self.on_phrase()
        self.seconds, self.running, self.phrases = seconds, running, now
        if running and not self._playing:
            self._playing = True
            self._beat()
        self.draw()

    def _beat(self) -> None:
        """The playhead runs over the pads in eighth notes at 174 BPM while the timer runs."""
        if not self.winfo_exists():
            return
        if not self.running:
            self._playing = False
            self.draw()
            return
        self.step = (self.step + 1) % 16
        self.draw()
        self.after(172, self._beat)

    def draw(self) -> None:
        self.delete("all")
        w, h = self.w, self.h
        gap = px(2)
        size = (min(w, h) - gap * 5) / 4
        x0 = (w - (size * 4 + gap * 3)) / 2
        y0 = (h - (size * 4 + gap * 3)) / 2
        lit = pads_lit(self.seconds)
        for i in range(16):
            row, col = divmod(i, 4)
            x, y = x0 + col * (size + gap), y0 + row * (size + gap)
            on = i < lit
            color = blend(PAD_ON, PAD_ON2, i / 15) if on else PAD_OFF
            if self.running and i == self.step:
                color = blend(color, "#ffffff", 0.45)
            skin.round_rect(self, x, y, x + size, y + size, px(2), fill=color, outline="")


# ------------------------------------------------------------------ painted around the playlist

TAG_COLORS = ("#ff3aa0", "#b6ff2e", "#3ad1ff", "#ff8a1f", "#a259ff", "#ffe600")


def draw_tag(c: tk.Canvas, x: float, y: float, size: float, seed: int) -> None:
    """A graffiti tag: a fat squiggle in a loud color with a black outline, an arrow at its end, a star or
    a crown on top and one paint drip."""
    rnd = random.Random(seed)
    color = TAG_COLORS[seed % len(TAG_COLORS)]
    pts = [(x - size * 0.6, y + size * 0.15)]
    for k in range(1, 5):
        pts.append((x - size * 0.6 + size * 0.3 * k, y + (-1) ** k * size * rnd.uniform(0.18, 0.32)))
    (ax, ay), (bx, by) = pts[-2], pts[-1]
    d = math.hypot(bx - ax, by - ay) or 1
    ux, uy = (bx - ax) / d, (by - ay) / d
    head = [bx + ux * size * 0.3, by + uy * size * 0.3, bx - uy * size * 0.22, by + ux * size * 0.22,
            bx + uy * size * 0.22, by - ux * size * 0.22]
    thick = max(3, size * 0.2)
    flat = [v for pt in pts for v in pt]
    drip_x = pts[1][0]
    c.create_line(drip_x, pts[1][1], drip_x, pts[1][1] + size * 0.45, fill="#111111", width=px(2) + 2, capstyle="round")
    c.create_line(drip_x, pts[1][1], drip_x, pts[1][1] + size * 0.45, fill=color, width=px(2), capstyle="round")
    c.create_line(flat, fill="#111111", width=thick + px(3), smooth=True, capstyle="round", joinstyle="round")
    c.create_polygon(head, fill=color, outline="#111111", width=max(1, px(1.5)))
    c.create_line(flat, fill=color, width=thick, smooth=True, capstyle="round", joinstyle="round")
    c.create_line([v for pt in pts[:3] for v in (pt[0], pt[1] - thick * 0.25)], fill="#ffffff",
                  width=max(1, px(1)), smooth=True)
    if seed % 2:  # a star
        r = size * 0.2
        cx, cy = x - size * 0.55, y - size * 0.35
        star = []
        for k in range(10):
            a = -math.pi / 2 + k * math.pi / 5
            rr = r if k % 2 == 0 else r * 0.45
            star += [cx + math.cos(a) * rr, cy + math.sin(a) * rr]
        c.create_polygon(star, fill="#ffffff", outline="#111111", width=1)
    else:  # a crown
        cx, cy, s = x - size * 0.5, y - size * 0.4, size * 0.13
        c.create_polygon(cx - s * 1.5, cy + s, cx - s * 1.5, cy - s * 0.5, cx - s * 0.6, cy + s * 0.2, cx, cy - s,
                         cx + s * 0.6, cy + s * 0.2, cx + s * 1.5, cy - s * 0.5, cx + s * 1.5, cy + s, fill="#ffe600",
                         outline="#111111", width=1)


def draw_vine(c: tk.Canvas, x: float, y: float, size: float, seed: int) -> None:
    """A jungle cluster: three big leaves and a curl of vine."""
    rnd = random.Random(seed)
    greens = ("#2f8f5b", "#3fae6c", "#1f6e4a", "#5ccf8a")
    c.create_line(x, y, x + size * 0.3, y - size * 0.35, x - size * 0.1, y - size * 0.6, fill="#2a5a3a",
                  width=max(1, px(1.2)), smooth=True)
    for k in range(3):
        angle = rnd.uniform(-160, -20) + k * 40
        a = math.radians(angle)
        skin.draw_leaf(c, x + math.cos(a) * size * 0.3, y + math.sin(a) * size * 0.3, size * rnd.uniform(0.85, 1.1),
                       angle, greens[(seed + k) % len(greens)])
