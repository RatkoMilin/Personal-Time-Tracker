"""Skins: themes plus the drawn widgets that follow them (panels, buttons, LCD digits, analog dial).

Widgets read the active theme `T` when they are built; switching skins rebuilds the window.
"""

from __future__ import annotations

import math
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

WIN = sys.platform == "win32"


@dataclass(frozen=True)
class Theme:
    key: str
    name: str
    # Window body and text
    body: str
    body_light: str
    body_dark: str
    text: str
    accent: str
    # Display wells (LCD, fields, list)
    lcd_bg: str
    lcd_on: str
    lcd_off: str
    lcd_dim: str
    lcd_text: str
    # Buttons
    btn_face: str
    btn_light: str
    btn_dark: str
    btn_glyph: str
    sel_bg: str
    sel_fg: str
    # Fonts: (Windows family, fallback family)
    mono: tuple[str, str]
    sans: tuple[str, str]
    label_size: int = 8
    label_weight: str = "bold"
    upper: bool = True
    # Shapes: "bevel" (classic 3D), "round" (soft corners), "chamfer" (cut corners)
    shape: str = "bevel"
    radius: int = 0
    panel_outline: str = ""
    title_style: str = "stripes"
    # Display: seven "segments" or an "analog" dial; segment style "hex", "round" or "sharp"
    display: str = "segments"
    segments: str = "hex"
    marquee: bool = True
    blink: bool = True
    dial_face: str = ""
    dial_hand: str = ""
    dial_second: str = ""

    def font(self, kind: str = "sans", size: int = 10, weight: str = "normal") -> tuple:
        families = self.mono if kind == "mono" else self.sans
        return (families[0] if WIN else families[1], size, weight)

    def label_font(self) -> tuple:
        return self.font("sans", self.label_size, self.label_weight)

    def tx(self, text: str) -> str:
        return text.upper() if self.upper else text


THEMES: dict[str, Theme] = {t.key: t for t in (
    Theme(
        key="matrix", name="Matrix (digitalni)",
        body="#2b2b3a", body_light="#55556b", body_dark="#121219", text="#d8d8e4", accent="#c9a94b",
        lcd_bg="#000000", lcd_on="#00e800", lcd_off="#0a260a", lcd_dim="#1c8a1c", lcd_text="#00e800",
        btn_face="#b4b4c2", btn_light="#ececf4", btn_dark="#56566a", btn_glyph="#1c1c26",
        sel_bg="#0000c6", sel_fg="#ffffff",
        mono=("Consolas", "DejaVu Sans Mono"), sans=("Tahoma", "DejaVu Sans"),
    ),
    Theme(
        key="pastel", name="Pastel (roze-plavi)",
        body="#f7dbe7", body_light="#fff0f6", body_dark="#e6b8cb", text="#6b5b8c", accent="#8fb8ec",
        lcd_bg="#e6f1ff", lcd_on="#e0679b", lcd_off="#d3e3f7", lcd_dim="#9bb3d6", lcd_text="#5e6fa3",
        btn_face="#bfd9f7", btn_light="#e8f2ff", btn_dark="#95b6e0", btn_glyph="#5e6fa3",
        sel_bg="#f2a3c3", sel_fg="#ffffff",
        mono=("Consolas", "DejaVu Sans Mono"), sans=("Segoe UI", "DejaVu Sans"),
        label_size=9, label_weight="normal", upper=False,
        shape="round", radius=12, panel_outline="#e6b8cb", title_style="dots", segments="round",
    ),
    Theme(
        key="wood", name="Drvo (analogni)",
        body="#4a2f1d", body_light="#6e4a30", body_dark="#2e1c10", text="#efe3c8", accent="#c9a15f",
        lcd_bg="#16392a", lcd_on="#efe3c8", lcd_off="#1f4634", lcd_dim="#8fae98", lcd_text="#e6dcc0",
        btn_face="#d8c7a0", btn_light="#efe3c8", btn_dark="#9c8456", btn_glyph="#2e1c10",
        sel_bg="#2f6a4c", sel_fg="#ffffff",
        mono=("Courier New", "DejaVu Sans Mono"), sans=("Georgia", "DejaVu Serif"),
        label_size=9, label_weight="italic", upper=False,
        shape="round", radius=5, panel_outline="#c9a15f", title_style="grain",
        display="analog", marquee=False, blink=False,
        dial_face="#efe3c8", dial_hand="#16392a", dial_second="#a63d2a",
    ),
    Theme(
        key="cyber", name="Sajber (sivi)",
        body="#23262b", body_light="#3a3f47", body_dark="#0f1114", text="#aeb6c2", accent="#00d9ff",
        lcd_bg="#0c0e11", lcd_on="#d7e1ec", lcd_off="#181c22", lcd_dim="#5f6b7a", lcd_text="#a9b8ca",
        btn_face="#2d3239", btn_light="#00d9ff", btn_dark="#0f1114", btn_glyph="#d7e1ec",
        sel_bg="#00d9ff", sel_fg="#0c0e11",
        mono=("Consolas", "DejaVu Sans Mono"), sans=("Bahnschrift", "DejaVu Sans"),
        shape="chamfer", panel_outline="#00d9ff", title_style="notch", segments="sharp",
    ),
)}

T: Theme = THEMES["matrix"]

# Pixel scale for canvas drawings, so they grow with fonts on high-DPI screens.
S = 1.0


def px(v: float) -> int:
    return int(round(v * S))


def use(root: tk.Tk, key: str) -> Theme:
    """Activate a theme and restyle the ttk/option database parts that widgets pick up when created."""
    global T, S
    T = THEMES.get(key, THEMES["matrix"])
    S = max(1.0, root.winfo_fpixels("1i") / 96.0)
    root.configure(bg=T.body)
    style = ttk.Style(root)
    style.theme_use("clam")  # the only built-in theme that honors custom colors everywhere
    style.configure("Skin.TCombobox", fieldbackground=T.lcd_bg, background=T.btn_face, foreground=T.lcd_text,
                    arrowcolor=T.btn_glyph, bordercolor=T.lcd_bg, lightcolor=T.lcd_bg, darkcolor=T.lcd_bg,
                    selectbackground=T.lcd_bg, selectforeground=T.lcd_text, insertcolor=T.lcd_text, padding=1)
    style.map("Skin.TCombobox", fieldbackground=[("readonly", T.lcd_bg)], foreground=[("readonly", T.lcd_text)],
              selectbackground=[("focus", T.lcd_bg)], selectforeground=[("focus", T.lcd_text)],
              background=[("pressed", T.btn_dark), ("active", T.btn_light)])
    for pattern, value in (("*TCombobox*Listbox.background", T.lcd_bg),
                           ("*TCombobox*Listbox.foreground", T.lcd_text),
                           ("*TCombobox*Listbox.selectBackground", T.sel_bg),
                           ("*TCombobox*Listbox.selectForeground", T.sel_fg),
                           ("*TCombobox*Listbox.font", T.font("mono", 10)),
                           ("*Menu.background", T.body), ("*Menu.foreground", T.text),
                           ("*Menu.activeBackground", T.sel_bg), ("*Menu.activeForeground", T.sel_fg),
                           ("*Menu.selectColor", T.accent)):
        root.option_add(pattern, value, "interactive")
    return T


# ------------------------------------------------------------------ shapes

def round_rect(c: tk.Canvas, x1, y1, x2, y2, r, **kw) -> int:
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    if r <= 0:
        return c.create_rectangle(x1, y1, x2, y2, **kw)
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
           x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(pts, smooth=True, **kw)


def chamfer_rect(c: tk.Canvas, x1, y1, x2, y2, cut, **kw) -> int:
    pts = [x1 + cut, y1, x2, y1, x2, y2 - cut, x2 - cut, y2, x1, y2, x1, y1 + cut]
    return c.create_polygon(pts, **kw)


class Panel(tk.Frame):
    """A display well in the theme's shape; put widgets into `.inner`.

    The shape is drawn on a canvas placed behind the inner frame, so normal
    geometry management sizes the panel from its content.
    """

    def __init__(self, master, pad: float = 4):
        super().__init__(master, bg=master["bg"])
        pad = px(pad) + (px(T.radius / 3) if T.shape == "round" else px(2))
        self.canvas = tk.Canvas(self, bg=master["bg"], highlightthickness=0, bd=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.inner = tk.Frame(self, bg=T.lcd_bg)  # created after the canvas, so it stacks above it
        self.inner.pack(fill="both", expand=True, padx=pad, pady=pad)
        self.canvas.bind("<Configure>", self._redraw)

    def _redraw(self, _event=None):
        c = self.canvas
        w, h = c.winfo_width(), c.winfo_height()
        c.delete("all")
        if T.shape == "round":
            round_rect(c, 0, 0, w - 1, h - 1, px(T.radius), fill=T.lcd_bg, outline=T.panel_outline)
        elif T.shape == "chamfer":
            chamfer_rect(c, 0, 0, w - 1, h - 1, px(7), fill=T.lcd_bg, outline=T.panel_outline)
        else:
            c.create_rectangle(0, 0, w - 1, h - 1, fill=T.lcd_bg, width=0)
            c.create_line(0, h - 1, 0, 0, w - 1, 0, fill=T.body_dark)
            c.create_line(1, h - 1, w - 1, h - 1, w - 1, 1, fill=T.body_light)


def field(master, textvariable: tk.StringVar, width: int) -> tuple[Panel, tk.Entry]:
    panel = Panel(master, pad=1)
    entry = tk.Entry(panel.inner, textvariable=textvariable, width=width, bg=T.lcd_bg, fg=T.lcd_text,
                     insertbackground=T.lcd_text, selectbackground=T.sel_bg, selectforeground=T.sel_fg,
                     disabledbackground=T.lcd_bg, relief="flat", bd=0, highlightthickness=0,
                     font=T.font("mono", 10))
    entry.pack(fill="x", padx=px(2), pady=px(2))
    return panel, entry


def combo(master, textvariable: tk.StringVar, width: int) -> tuple[Panel, ttk.Combobox]:
    panel = Panel(master, pad=1)
    cb = ttk.Combobox(panel.inner, textvariable=textvariable, style="Skin.TCombobox", width=width,
                      font=T.font("mono", 10))
    cb.pack(fill="x")
    return panel, cb


def label(master, text: str = "", **kw) -> tk.Label:
    kw.setdefault("font", T.label_font())
    kw.setdefault("fg", T.text)
    return tk.Label(master, text=T.tx(text), bg=master["bg"], **kw)


# ------------------------------------------------------------ seven segment

#   aaa
#  f   b
#   ggg
#  e   c
#   ddd
DIGITS = {
    "0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgedc", "7": "abc",
    "8": "abcdefg", "9": "abcdfg", "-": "g", " ": "",
}


class SevenSegment(tk.Canvas):
    """LCD digits with dim 'ghost' segments; the theme picks hexagonal, rounded or sharp italic segments."""

    def __init__(self, master, pattern: str = "88:88:88", digit_w: float = 20, digit_h: float = 36,
                 thick: float = 4.5):
        self.style = T.segments
        if self.style == "sharp":
            thick = 3.5
        self.dw, self.dh, self.t = px(digit_w), px(digit_h), max(2.0, thick * S)
        self.skew = 0.2 if self.style == "sharp" else 0.0
        self.gap = px(5)
        self.colon_w = px(9)
        self.pattern = pattern
        width = sum(self.colon_w if ch == ":" else self.dw + self.gap for ch in pattern) + self.skew * self.dh
        super().__init__(master, width=width, height=self.dh + px(2), bg=T.lcd_bg, highlightthickness=0)
        self.cells: list = []
        x = 0
        for ch in pattern:
            if ch == ":":
                self.cells.append(self._colon(x))
                x += self.colon_w
            else:
                self.cells.append(self._digit(x))
                x += self.dw + self.gap
        self.set("  :  :  ")

    def _sk(self, pts: list[float]) -> list[float]:
        """Italic slant for the sharp style: shift x by the distance from the baseline."""
        if not self.skew:
            return pts
        out = []
        for i in range(0, len(pts), 2):
            out += [pts[i] + (self.dh - pts[i + 1]) * self.skew, pts[i + 1]]
        return out

    def _hseg(self, x, y, length):
        t2 = self.t / 2
        return [x, y, x + t2, y - t2, x + length - t2, y - t2, x + length, y, x + length - t2, y + t2, x + t2, y + t2]

    def _vseg(self, x, y, length):
        t2 = self.t / 2
        return [x, y, x + t2, y + t2, x + t2, y + length - t2, x, y + length, x - t2, y + length - t2, x - t2, y + t2]

    def _digit(self, x0) -> dict[str, int]:
        w, h, t = self.dw, self.dh, self.t
        g = 1.2 * S
        y0 = px(1)
        mid = y0 + h / 2
        top, bot = y0 + t / 2, y0 + h - t / 2
        left, right = x0 + t / 2, x0 + w - t / 2
        lines = {  # center line of each segment
            "a": (left + g, top, right - g, top), "g": (left + g, mid, right - g, mid),
            "d": (left + g, bot, right - g, bot), "f": (left, top + g, left, mid - g),
            "b": (right, top + g, right, mid - g), "e": (left, mid + g, left, bot - g),
            "c": (right, mid + g, right, bot - g),
        }
        items = {}
        for seg, (x1, y1, x2, y2) in lines.items():
            if self.style == "round":
                inset = t / 2
                if y1 == y2:
                    x1, x2 = x1 + inset, x2 - inset
                else:
                    y1, y2 = y1 + inset, y2 - inset
                items[seg] = self.create_line(x1, y1, x2, y2, width=t, capstyle="round", fill=T.lcd_off)
            else:
                poly = self._hseg(x1, y1, x2 - x1) if y1 == y2 else self._vseg(x1, y1, y2 - y1)
                items[seg] = self.create_polygon(self._sk(poly), fill=T.lcd_off, outline="")
        return items

    def _colon(self, x0) -> list[int]:
        s = self.t
        cx = x0 + self.colon_w / 2 - self.gap / 2
        items = []
        for y in (px(1) + self.dh * 0.32, px(1) + self.dh * 0.7):
            if self.style == "round":
                items.append(self.create_oval(cx - s / 2, y - s / 2, cx + s / 2, y + s / 2, fill=T.lcd_off,
                                              width=0))
            else:
                box = [cx - s / 2, y - s / 2, cx + s / 2, y - s / 2, cx + s / 2, y + s / 2, cx - s / 2, y + s / 2]
                items.append(self.create_polygon(self._sk(box), fill=T.lcd_off, outline=""))
        return items

    def set(self, text: str, on: str | None = None) -> None:
        on = on or T.lcd_on
        for cell, ch in zip(self.cells, text.rjust(len(self.pattern))):
            if isinstance(cell, list):
                for item in cell:
                    self.itemconfigure(item, fill=on if ch == ":" else T.lcd_off)
            else:
                lit = DIGITS.get(ch, "")
                for seg, item in cell.items():
                    self.itemconfigure(item, fill=on if seg in lit else T.lcd_off)


class AnalogDial(tk.Canvas):
    """Stopwatch dial for the analog skin: hour, minute and second hands show the elapsed time."""

    def __init__(self, master, size: float = 76):
        s = px(size)
        super().__init__(master, width=s, height=s, bg=T.lcd_bg, highlightthickness=0)
        self.c = s / 2
        r = s / 2 - px(2)
        self.create_oval(self.c - r, self.c - r, self.c + r, self.c + r, fill=T.accent, outline="")
        r -= px(3)
        self.r = r
        self.create_oval(self.c - r, self.c - r, self.c + r, self.c + r, fill=T.dial_face, outline="")
        for i in range(60):
            a = math.radians(i * 6)
            outer, inner = r - px(2), r - (px(8) if i % 5 == 0 else px(4))
            self.create_line(self.c + inner * math.sin(a), self.c - inner * math.cos(a),
                             self.c + outer * math.sin(a), self.c - outer * math.cos(a),
                             fill=T.dial_hand, width=max(1, px(2)) if i % 5 == 0 else 1)
        self.hour = self.create_line(0, 0, 0, 0, fill=T.dial_hand, width=max(2, px(4)), capstyle="round")
        self.minute = self.create_line(0, 0, 0, 0, fill=T.dial_hand, width=max(2, px(3)), capstyle="round")
        self.second = self.create_line(0, 0, 0, 0, fill=T.dial_second, width=max(1, px(1.5)))
        d = px(3)
        self.create_oval(self.c - d, self.c - d, self.c + d, self.c + d, fill=T.dial_second, outline="")
        self.set_seconds(0)

    def _hand(self, item, fraction: float, length: float) -> None:
        a = 2 * math.pi * fraction
        self.coords(item, self.c, self.c, self.c + length * math.sin(a), self.c - length * math.cos(a))

    def set_seconds(self, secs: float) -> None:
        self._hand(self.hour, (secs / 43200) % 1, self.r * 0.5)
        self._hand(self.minute, (secs / 3600) % 1, self.r * 0.78)
        self._hand(self.second, (secs / 60) % 1, self.r * 0.88)


class Marquee(tk.Canvas):
    """Scrolling song-title style text."""

    def __init__(self, master, chars: int = 30):
        self.chars = chars
        self.font = T.font("mono", 10)
        probe = tk.Label(master, text="M" * chars, font=self.font)
        width = probe.winfo_reqwidth()
        probe.destroy()
        super().__init__(master, width=width, height=px(18), bg=T.lcd_bg, highlightthickness=0)
        self.item = self.create_text(0, px(9), anchor="w", text="", fill=T.lcd_on, font=self.font)
        self.text = ""
        self.offset = 0
        self._step()

    def set_text(self, text: str) -> None:
        if text != self.text:
            self.text = text
            self.offset = 0
            self._render()

    def _render(self) -> None:
        if len(self.text) <= self.chars:
            shown = self.text
        else:
            loop = self.text + "  ***  "
            shown = (loop * 2)[self.offset % len(loop):][: self.chars]
        self.itemconfigure(self.item, text=shown)

    def _step(self) -> None:
        if not self.winfo_exists():  # destroyed by a skin switch
            return
        self.offset += 1
        self._render()
        self.after(250, self._step)


# ------------------------------------------------------------------ buttons

class SkinButton(tk.Canvas):
    """Button drawn in the theme's shape, with a glyph (play/pause/stop/eject/prev/next) or a text label."""

    def __init__(self, master, command, glyph: str | None = None, text: str | None = None,
                 width: float = 26, height: float = 20, tooltip: str | None = None):
        font = T.font("sans", 8 if T.upper else 9, "bold" if T.upper else "normal")
        text = T.tx(text) if text else None
        w, h = px(width), px(height)
        if T.shape == "round":
            w, h = w + px(4), h + px(2)
        if text:
            probe = tk.Label(master, text=text, font=font)
            w = max(w, probe.winfo_reqwidth() + px(12))
            probe.destroy()
        super().__init__(master, width=w, height=h, bg=master["bg"], highlightthickness=0, cursor="hand2")
        self.command = command
        self.w, self.h = w, h
        self._draw_face(pressed=False)
        self.glyph_items = self._glyph(glyph) if glyph else [
            self.create_text(w / 2, h / 2, text=text, fill=T.btn_glyph, font=font)]
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.tip = Tooltip(self, tooltip) if tooltip else None

    def _draw_face(self, pressed: bool) -> None:
        self.delete("face")
        w, h = self.w, self.h
        if T.shape == "round":
            round_rect(self, 1, 1, w - 2, h - 2, px(T.radius) * 0.8, fill=T.btn_dark if pressed else T.btn_face,
                       outline=T.btn_dark, tags="face")
        elif T.shape == "chamfer":
            chamfer_rect(self, 0, 0, w - 1, h - 1, px(5), fill=T.btn_light if pressed else T.btn_face,
                         outline=T.btn_light, tags="face")
        else:
            self.create_rectangle(0, 0, w - 1, h - 1, fill=T.btn_face, width=0, tags="face")
            self.create_line(0, h - 1, 0, 0, w - 1, 0, fill=T.btn_dark if pressed else T.btn_light, tags="face")
            self.create_line(1, h - 1, w - 1, h - 1, w - 1, 0, fill=T.btn_light if pressed else T.btn_dark,
                             tags="face")
        self.tag_lower("face")

    def _glyph(self, glyph: str) -> list[int]:
        cx, cy = self.w / 2, self.h / 2
        s = min(self.w, self.h) * 0.28
        fill = T.btn_glyph
        if glyph == "play":
            return [self.create_polygon(cx - s * 0.8, cy - s, cx - s * 0.8, cy + s, cx + s, cy, fill=fill)]
        if glyph == "pause":
            bw = s * 0.55
            return [self.create_rectangle(cx - s * 0.9, cy - s, cx - s * 0.9 + bw, cy + s, fill=fill, width=0),
                    self.create_rectangle(cx + s * 0.9 - bw, cy - s, cx + s * 0.9, cy + s, fill=fill, width=0)]
        if glyph == "stop":
            return [self.create_rectangle(cx - s * 0.85, cy - s * 0.85, cx + s * 0.85, cy + s * 0.85, fill=fill,
                                          width=0)]
        if glyph == "eject":
            return [self.create_polygon(cx - s, cy + s * 0.2, cx + s, cy + s * 0.2, cx, cy - s, fill=fill),
                    self.create_rectangle(cx - s, cy + s * 0.5, cx + s, cy + s, fill=fill, width=0)]
        if glyph == "prev":
            return [self.create_polygon(cx + s * 0.6, cy - s * 0.8, cx + s * 0.6, cy + s * 0.8, cx - s * 0.6, cy,
                                        fill=fill)]
        if glyph == "next":
            return [self.create_polygon(cx - s * 0.6, cy - s * 0.8, cx - s * 0.6, cy + s * 0.8, cx + s * 0.6, cy,
                                        fill=fill)]
        raise ValueError(glyph)

    def _set_glyph_color(self, color: str) -> None:
        for item in self.glyph_items:
            self.itemconfigure(item, fill=color)

    def _press(self, _event):
        self._draw_face(pressed=True)
        if T.shape == "chamfer":
            self._set_glyph_color(T.lcd_bg)
        elif T.shape == "round":
            self._set_glyph_color(T.btn_light)
        for item in self.glyph_items:
            self.move(item, 1, 1)

    def _release(self, event):
        self._draw_face(pressed=False)
        self._set_glyph_color(T.btn_glyph)
        for item in self.glyph_items:
            self.move(item, -1, -1)
        if 0 <= event.x < self.w and 0 <= event.y < self.h:
            self.command()


class TitleBar(tk.Canvas):
    """Title strip styled by the theme; with on_menu it gets a small menu button on the left."""

    def __init__(self, master, title: str, on_menu=None):
        super().__init__(master, height=px(18), bg=T.body, highlightthickness=0)
        self.title = title
        self.on_menu = on_menu
        self.bind("<Configure>", lambda e: self.draw())

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), px(18)
        style = T.title_style
        if style == "grain":  # wood grain
            for i, y in enumerate((3, 6, 10, 13, 16)):
                pts = []
                for x in range(0, w + 20, 20):
                    pts += [x, px(y) + math.sin((x + i * 37) / 23) * px(1.2)]
                self.create_line(pts, fill=T.body_light, smooth=True)
        font = T.font("sans", 8 if T.upper else 9, "bold" if T.upper else "normal")
        text = self.create_text(w / 2, h / 2, text=T.tx(self.title), fill=T.text, font=font)
        x0, y0, x1, y1 = self.bbox(text)
        left = px(22) if self.on_menu else px(6)
        if style == "stripes":
            for y in (px(6), px(9), px(12)):
                self.create_line(left, y, x0 - px(8), y, fill=T.accent)
                self.create_line(x1 + px(8), y, w - px(6), y, fill=T.accent)
        elif style == "dots":
            for i, color in enumerate((T.lcd_on, T.accent, T.lcd_on)):
                r = px(2.5)
                for x in (x0 - px(14) - i * px(9), x1 + px(14) + i * px(9)):
                    self.create_oval(x - r, h / 2 - r, x + r, h / 2 + r, fill=color, outline="")
        elif style == "grain":
            plaque = round_rect(self, x0 - px(10), y0 - px(1), x1 + px(10), y1 + px(1), px(4), fill=T.body_dark,
                                outline=T.accent)
            self.tag_lower(plaque, text)
        elif style == "notch":
            y = h - px(3)
            self.create_line(left, y, x0 - px(12), y, x0 - px(6), px(3), x1 + px(6), px(3), x1 + px(12), y,
                             w - px(6), y, fill=T.accent)
        if self.on_menu:
            r = px(6)
            cx, cy = px(11), h / 2
            if T.shape == "round":
                box = self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=T.btn_face, outline=T.btn_dark)
            elif T.shape == "chamfer":
                box = self.create_polygon(cx, cy - r, cx + r, cy, cx, cy + r, cx - r, cy, fill=T.btn_face,
                                          outline=T.accent)
            else:
                box = self.create_rectangle(cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1, fill=T.btn_face,
                                            outline=T.btn_dark)
            bar = self.create_line(cx - r / 2, cy, cx + r / 2, cy, fill=T.btn_glyph, width=max(1, px(2)))
            for item in (box, bar):
                self.tag_bind(item, "<Button-1>", lambda e: self.on_menu(e))


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str):
        self.widget, self.text, self.tip, self._job = widget, text, None, None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event):
        self._job = self.widget.after(500, self._show)

    def _show(self):
        self._job = None
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        tk.Label(self.tip, text=self.text, bg="#ffffe1", fg="black", relief="solid", bd=1,
                 font=T.font("sans", 8), padx=4, pady=1).pack()
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip.wm_geometry(f"+{x}+{y}")

    def _hide(self, _event=None):
        if self._job:
            self.widget.after_cancel(self._job)
            self._job = None
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


def resource_path(name: str) -> Path:
    """Bundled assets both from source and from a PyInstaller build."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent))
    return base / "assets" / name


def set_window_icon(win: tk.Misc) -> None:
    ico, png = resource_path("icon.ico"), resource_path("icon.png")
    try:
        if WIN and ico.exists():
            win.iconbitmap(default=str(ico))
        elif png.exists():
            img = tk.PhotoImage(file=str(png))
            win.iconphoto(True, img)
            win._icon_ref = img
    except tk.TclError:
        pass
