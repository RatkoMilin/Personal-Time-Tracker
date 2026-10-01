"""Skins: themes plus the drawn widgets that follow them (panels, buttons, LCD digits, analog dial).

Widgets read the active theme `T` when they are built; switching skins rebuilds the window.
"""

from __future__ import annotations

import math
import random
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
    # Extras: button shape "paw" or "circle" (default follows `shape`), a pattern around the playlist
    # ("spots" or "leaves"), decorations next to the clock ("oranges").
    button: str = ""
    pl_pattern: str = ""
    clock_deco: str = ""
    leaf: str = "#3f8f2f"
    # Productivity meter look: "" (bar), "sword" (katana glows neon), "flowers" (branch blossoms, flowers can be
    # turned into walnuts), "lanterns" (lit paper lanterns), "cat" (bar with a cat at 80%+), "mondrian", "glow".
    meter: str = ""
    meter_fill: str = ""
    # Per-panel colors (default: the LCD colors) and a thick black frame width ("block" shape).
    list_bg: str = ""
    list_fg: str = ""
    list_run: str = ""  # the running entry in the list (default: lcd_on)
    task_bg: str = ""
    task_fg: str = ""
    border: int = 0
    # Effects: digits scramble on play/pause, confetti on play; lamp themes switch palettes while playing.
    scramble: bool = False
    confetti: bool = False
    lit_variant: str = ""
    dark_variant: str = ""
    hidden: bool = False  # not offered in the skin menu (e.g. the lit half of a lamp theme)
    # Layout extras: a decorated strip down the right side ("dandelion"), the playlist section's own
    # background, a list without a box (only its text), nested panel outlines for a layered look, and a
    # glow color around canvas-drawn text.
    side: str = ""
    pl_body: str = ""
    pl_plain: bool = False
    layers: tuple = ()
    glow: str = ""
    play_fx: str = ""  # "bullet": the play button takes a shot when pressed (the hole fades away)

    def font(self, kind: str = "sans", size: int = 10, weight: str = "normal") -> tuple:
        families = self.mono if kind == "mono" else self.sans
        return (families[0] if WIN else families[1], size, weight)

    def label_font(self) -> tuple:
        return self.font("sans", self.label_size, self.label_weight)

    def tx(self, text: str) -> str:
        return text.upper() if self.upper else text


THEMES: dict[str, Theme] = {t.key: t for t in (
    Theme(
        key="matrix", name="Matrix",
        body="#2b2b3a", body_light="#55556b", body_dark="#121219", text="#d8d8e4", accent="#c9a94b",
        lcd_bg="#000000", lcd_on="#00e800", lcd_off="#0a260a", lcd_dim="#1c8a1c", lcd_text="#00e800",
        btn_face="#b4b4c2", btn_light="#ececf4", btn_dark="#56566a", btn_glyph="#1c1c26",
        sel_bg="#0000c6", sel_fg="#ffffff",
        mono=("Consolas", "DejaVu Sans Mono"), sans=("Tahoma", "DejaVu Sans"), scramble=True,
    ),
    Theme(
        key="pastel", name="Pastel",
        body="#f7dbe7", body_light="#fff0f6", body_dark="#e6b8cb", text="#6b5b8c", accent="#8fb8ec",
        lcd_bg="#e6f1ff", lcd_on="#e0679b", lcd_off="#d3e3f7", lcd_dim="#9bb3d6", lcd_text="#5e6fa3",
        btn_face="#bfd9f7", btn_light="#e8f2ff", btn_dark="#95b6e0", btn_glyph="#5e6fa3",
        sel_bg="#f2a3c3", sel_fg="#ffffff",
        mono=("Consolas", "DejaVu Sans Mono"), sans=("Segoe UI", "DejaVu Sans"),
        label_size=9, label_weight="normal", upper=False,
        shape="round", radius=12, panel_outline="#e6b8cb", title_style="dots", segments="round",
        pl_pattern="bubbles",
    ),
    Theme(
        key="wood", name="Orah",
        body="#5b3b27", body_light="#80583a", body_dark="#341f12", text="#f0e2c8", accent="#c9a15f",
        lcd_bg="#16392a", lcd_on="#efe3c8", lcd_off="#1f4634", lcd_dim="#8fae98", lcd_text="#e6dcc0",
        btn_face="#d8c7a0", btn_light="#efe3c8", btn_dark="#9c8456", btn_glyph="#341f12",
        sel_bg="#2f6a4c", sel_fg="#ffffff",
        mono=("Courier New", "DejaVu Sans Mono"), sans=("Georgia", "DejaVu Serif"),
        label_size=9, label_weight="italic", upper=False,
        shape="round", radius=5, panel_outline="#c9a15f", title_style="grain",
        display="analog", marquee=False, blink=False, meter="flowers",
        dial_face="#efe3c8", dial_hand="#16392a", dial_second="#a63d2a",
    ),
    Theme(
        key="cyber", name="Samuraj",
        body="#3b434a", body_light="#a9b3ba", body_dark="#1b2024", text="#d5dde2", accent="#5fd8ff",
        lcd_bg="#0b1014", lcd_on="#8fe9ff", lcd_off="#132028", lcd_dim="#5b6b75", lcd_text="#c9d4da",
        btn_face="#8e9aa3", btn_light="#d6dee3", btn_dark="#4b555c", btn_glyph="#0b1014",
        sel_bg="#5fd8ff", sel_fg="#0b1014",
        mono=("Consolas", "DejaVu Sans Mono"), sans=("Bahnschrift", "DejaVu Sans"),
        shape="chamfer", panel_outline="#5fd8ff", title_style="notch", segments="sharp", meter="sword",
    ),
    Theme(
        key="cat", name="Mačkasti",
        body="#f4ecdf", body_light="#fffaf2", body_dark="#cfc4b2", text="#3b3a3e", accent="#6e6b72",
        lcd_bg="#3b3a3e", lcd_on="#f8f1e4", lcd_off="#47464b", lcd_dim="#a8a299", lcd_text="#f1e9da",
        btn_face="#3b3a3e", btn_light="#5a5960", btn_dark="#1f1e22", btn_glyph="#f8f1e4",
        sel_bg="#f1e9da", sel_fg="#3b3a3e",
        mono=("Consolas", "DejaVu Sans Mono"), sans=("Segoe UI", "DejaVu Sans"),
        label_size=9, label_weight="bold", upper=False,
        shape="round", radius=12, panel_outline="#1f1e22", title_style="ears", segments="round",
        button="paw", pl_pattern="spots", meter="cat", meter_fill="#3b3a3e",
    ),
    Theme(
        key="setsuna", name="Setsuna",
        body="#ffffff", body_light="#ffffff", body_dark="#e6e6e6", text="#111111", accent="#E94C53",
        lcd_bg="#111111", lcd_on="#DB4C01", lcd_off="#2b1b12", lcd_dim="#8e5a3c", lcd_text="#ffffff",
        btn_face="#DB4C01", btn_light="#f07a3e", btn_dark="#E94C53", btn_glyph="#ffffff",
        sel_bg="#E94C53", sel_fg="#ffffff",
        mono=("Consolas", "DejaVu Sans Mono"), sans=("Segoe UI", "DejaVu Sans"),
        label_size=9, label_weight="bold", upper=False,
        shape="round", radius=14, panel_outline="#111111", title_style="oranges", segments="round",
        button="circle", pl_pattern="leaves", clock_deco="oranges", meter="lanterns", confetti=True,
    ),
    Theme(
        key="mondrian", name="Mondrian",
        body="#ffffff", body_light="#ffffff", body_dark="#111111", text="#111111", accent="#dd0100",
        lcd_bg="#ffffff", lcd_on="#111111", lcd_off="#ececec", lcd_dim="#9a9a9a", lcd_text="#111111",
        btn_face="#ffffff", btn_light="#ffffff", btn_dark="#111111", btn_glyph="#111111",
        sel_bg="#fac901", sel_fg="#111111",
        mono=("Consolas", "DejaVu Sans Mono"), sans=("Arial", "DejaVu Sans"),
        label_size=8, label_weight="bold", upper=True,
        shape="block", border=4, title_style="mondrian", button="block", meter="mondrian", meter_fill="#fac901",
        list_bg="#dd0100", list_fg="#ffffff", list_run="#fac901", task_bg="#225095", task_fg="#ffffff",
    ),
    Theme(
        key="egg", name="Jaje",
        body="#3a3a3a", body_light="#4c4c4c", body_dark="#222222", text="#9a9a9a", accent="#6a6a6a",
        lcd_bg="#2b2b2b", lcd_on="#8a8a8a", lcd_off="#333333", lcd_dim="#5a5a5a", lcd_text="#9a9a9a",
        btn_face="#4a4a4a", btn_light="#5a5a5a", btn_dark="#2a2a2a", btn_glyph="#a0a0a0",
        sel_bg="#555555", sel_fg="#dddddd",
        mono=("Consolas", "DejaVu Sans Mono"), sans=("Segoe UI", "DejaVu Sans"),
        label_size=9, label_weight="normal", upper=False,
        shape="round", radius=20, panel_outline="#222222", title_style="egg", segments="round", button="circle",
        meter="glow", meter_fill="#6a6a6a", lit_variant="egg_lit",
    ),
    Theme(
        key="egg_lit", name="Jaje", hidden=True,
        body="#fbf6ea", body_light="#ffffff", body_dark="#e6d9bb", text="#6b5a3a", accent="#f3c76b",
        lcd_bg="#fffaf0", lcd_on="#c98a1a", lcd_off="#f3ead6", lcd_dim="#d6c49a", lcd_text="#6b5a3a",
        btn_face="#f4ead4", btn_light="#ffffff", btn_dark="#e2cfa4", btn_glyph="#8a6a2a",
        sel_bg="#f3c76b", sel_fg="#3a2a0a",
        mono=("Consolas", "DejaVu Sans Mono"), sans=("Segoe UI", "DejaVu Sans"),
        label_size=9, label_weight="normal", upper=False,
        shape="round", radius=20, panel_outline="#e6d9bb", title_style="egg", segments="round", button="circle",
        meter="glow", meter_fill="#ffd36b", dark_variant="egg",
    ),
    Theme(
        key="dandelion", name="Maslačak",
        body="#fdfbf9", body_light="#ffffff", body_dark="#ead7dd", text="#55664a", accent="#e3a3b6",
        lcd_bg="#ffffff", lcd_on="#5f8f44", lcd_off="#f2eeee", lcd_dim="#b5c4a8", lcd_text="#55664a",
        btn_face="#fffaf0", btn_light="#ffffff", btn_dark="#f2d36b", btn_glyph="#5f8f44",
        sel_bg="#f6cfda", sel_fg="#3e4a36",
        mono=("Consolas", "DejaVu Sans Mono"), sans=("Segoe UI", "DejaVu Sans"),
        label_size=9, label_weight="normal", upper=False,
        shape="round", radius=14, panel_outline="#efd5dd", title_style="dandelion", segments="round",
        button="dandelion", meter="bw", side="dandelion", pl_body="#f9e7ed", pl_plain=True,
        list_bg="#f9e7ed", list_fg="#4f5b45",
    ),
    Theme(
        key="coffee", name="My Passion",
        # almost black coffee: the darkest browns of the palette, the lighter ones only for edges
        body="#171211", body_light="#2a211e", body_dark="#090706", text="#d9cbc5", accent="#a48980",
        lcd_bg="#0e0b0a", lcd_on="#e3f2f7", lcd_off="#1c1614", lcd_dim="#6d564e", lcd_text="#d4e7ee",
        btn_face="#2f2522", btn_light="#42342f", btn_dark="#130e0d", btn_glyph="#e3f2f7",
        sel_bg="#4c3b36", sel_fg="#ffffff",
        mono=("Consolas", "DejaVu Sans Mono"), sans=("Segoe UI", "DejaVu Sans"),
        label_size=9, label_weight="bold", upper=False,
        shape="round", radius=9, panel_outline="#4c3b36", title_style="coffee", segments="ice", meter="coffee",
        layers=("#2f2522", "#211a17", "#130e0d"), glow="#5f7f89", play_fx="bullet",
    ),
)}

MONDRIAN_RED, MONDRIAN_BLUE, MONDRIAN_YELLOW = "#dd0100", "#225095", "#fac901"
ICE_EDGE = "#9fc6d4"  # the bluish rim of an ice cube


def block_colors(role: str | None) -> tuple[str, str]:
    """(fill, glyph) of a Mondrian button by its role."""
    return {"play": (MONDRIAN_BLUE, "#ffffff"), "pause": (MONDRIAN_YELLOW, "#111111"),
            "stop": (MONDRIAN_RED, "#ffffff")}.get(role or "", ("#ffffff", "#111111"))

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


def draw_orange(c: tk.Canvas, cx: float, cy: float, r: float) -> None:
    """A small orange fruit with a highlight and a green leaf."""
    c.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#DB4C01", outline="#a83a00")
    c.create_oval(cx - r * 0.55, cy - r * 0.6, cx - r * 0.1, cy - r * 0.25, fill="#f39a60", outline="")
    c.create_line(cx, cy - r, cx + r * 0.1, cy - r * 1.25, fill="#5b3a1e", width=max(1, r / 6))
    draw_leaf(c, cx + r * 0.55, cy - r * 1.1, r * 0.9, -25)


def draw_orange_piece(c: tk.Canvas, cx: float, cy: float, r: float, kind: str) -> None:
    """A whole orange ("w"), a half ("h") or a quarter ("q") showing its juicy cut face."""
    if kind == "w":
        draw_orange(c, cx, cy, r)
        return
    start, extent = (0, 180) if kind == "h" else (45, 90)
    top = cy + (r * 0.45 if kind == "h" else r * 0.35)  # sit the cut piece on the same baseline
    box = (cx - r, top - r, cx + r, top + r)
    c.create_arc(*box, start=start, extent=extent, style="pieslice", fill="#DB4C01", outline="")
    inner = (cx - r * 0.82, top - r * 0.82, cx + r * 0.82, top + r * 0.82)
    c.create_arc(*inner, start=start, extent=extent, style="pieslice", fill="#f7a35c", outline="")
    for k in range(1, 6 if kind == "h" else 3):
        a = math.radians(start + extent * k / (6 if kind == "h" else 3))
        c.create_line(cx, top, cx + math.cos(a) * r * 0.8, top - math.sin(a) * r * 0.8, fill="#fbd3a8", width=1)


def draw_egg(c: tk.Canvas, cx: float, cy: float, h: float, lit: bool) -> None:
    """Egg-shaped lamp; glowing warm when lit."""
    w = h * 0.78
    if lit:
        for k, color in enumerate(("#fff3d6", "#ffe8b0", "#ffd98a")):
            g = (3 - k) * h * 0.12
            c.create_oval(cx - w / 2 - g, cy - h / 2 - g, cx + w / 2 + g, cy + h / 2 + g, fill=color, outline="")
        c.create_oval(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, fill="#fffaf0", outline="#f3c76b")
    else:
        c.create_oval(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, fill="#5a5a5a", outline="#2a2a2a")
        c.create_oval(cx - w * 0.25, cy - h * 0.32, cx - w * 0.05, cy - h * 0.12, fill="#6a6a6a", outline="")


def draw_iced_americano(c: tk.Canvas, cx: float, cy: float, h: float) -> None:
    """A tall glass of iced americano: dark coffee, a few ice cubes and a straw."""
    top_w, bot_w = h * 0.62, h * 0.46
    y0, y1 = cy - h / 2, cy + h / 2
    c.create_line(cx + top_w * 0.15, y0 - h * 0.12, cx + top_w * 0.05, y1 - h * 0.25, fill="#d9cbc5", width=2)
    c.create_polygon(cx - top_w / 2 + 1, y0 + h * 0.2, cx + top_w / 2 - 1, y0 + h * 0.2, cx + bot_w / 2 - 1, y1 - 1,
                     cx - bot_w / 2 + 1, y1 - 1, fill="#130e0d", outline="")
    for dx, dy in ((-0.14, 0.32), (0.12, 0.42), (-0.05, 0.58)):
        s = h * 0.17
        x, y = cx + dx * h, y0 + dy * h
        c.create_rectangle(x - s / 2, y - s / 2, x + s / 2, y + s / 2, fill="#a9c9d3", outline=ICE_EDGE)
        c.create_line(x - s / 2 + 1, y - s / 2 + 1, x + s / 4, y - s / 2 + 1, fill="#eef8fb")
    c.create_polygon(cx - top_w / 2, y0, cx + top_w / 2, y0, cx + bot_w / 2, y1, cx - bot_w / 2, y1,
                     fill="", outline="#d4e7ee")
    c.create_line(cx - top_w / 2 + 2, y0 + 2, cx - bot_w / 2 + 2, y1 - 3, fill="#f4fbfd")


def draw_leaf(c: tk.Canvas, x: float, y: float, size: float, angle: float, color: str = "#3f8f2f") -> None:
    """A pointed leaf centered at (x, y), rotated by angle degrees, with a lighter middle vein."""
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)

    def rot(px_, py_):
        return x + px_ * ca - py_ * sa, y + px_ * sa + py_ * ca

    half, width = size / 2, size * 0.22
    outline = [rot(-half, 0), rot(-half * 0.3, -width), rot(half * 0.4, -width * 0.8), rot(half, 0),
               rot(half * 0.4, width * 0.8), rot(-half * 0.3, width)]
    c.create_polygon([v for pt in outline for v in pt], fill=color, outline="", smooth=True)
    c.create_line(*rot(-half * 0.8, 0), *rot(half * 0.8, 0), fill="#7cc46a", width=1)


def draw_paw(c: tk.Canvas, x0: float, y0: float, x1: float, y1: float, **kw) -> list[int]:
    """Cat paw: a big pad in the lower part and four toe beans above it."""
    w, h = x1 - x0, y1 - y0
    if w > h * 1.3:  # wide paw for a text label: a long pad, toes stay round
        items = [round_rect(c, x0, y0 + h * 0.38, x1, y1, (h * 0.62) / 2, **kw)]
        tw = th = h * 0.3
    else:
        items = [c.create_oval(x0 + w * 0.1, y0 + h * 0.38, x1 - w * 0.1, y1, **kw)]
        tw, th = w * 0.18, h * 0.32
    for fx, fy in ((0.14, 0.22), (0.38, 0.0), (0.62, 0.0), (0.86, 0.22)):
        cx, top = x0 + w * fx, y0 + h * fy
        items.append(c.create_oval(cx - tw / 2, top, cx + tw / 2, top + th, **kw))
    return items


class Panel(tk.Frame):
    """A display well in the theme's shape; put widgets into `.inner`.

    The shape is drawn on a canvas placed behind the inner frame, so normal
    geometry management sizes the panel from its content. With pattern
    ("spots" or "leaves") a wider margin around the content is decorated.
    """

    def __init__(self, master, pad: float = 4, pattern: str = "", bg: str | None = None, plain: bool = False):
        super().__init__(master, bg=master["bg"])
        self.pattern = pattern
        self.plain = plain  # no box at all: only the content shows
        self.bg = bg or T.lcd_bg
        pad = (px(pad) + (px(T.radius / 3) if T.shape == "round" else px(2)) + (px(9) if pattern else 0)
               + (px(T.border) if T.shape == "block" else 0) + px(2) * len(T.layers))
        if plain:
            pad = px(2)
        self.canvas = tk.Canvas(self, bg=master["bg"], highlightthickness=0, bd=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.inner = tk.Frame(self, bg=self.bg)  # created after the canvas, so it stacks above it
        self.inner.pack(fill="both", expand=True, padx=pad, pady=pad)
        self.canvas.bind("<Configure>", self._redraw)

    def _redraw(self, _event=None):
        c = self.canvas
        w, h = c.winfo_width(), c.winfo_height()
        c.delete("all")
        if self.plain:
            c.configure(bg=self.bg)
            return
        if T.layers:  # nested outlines, each a shade darker, for a layered (iced coffee) look
            g = px(2)
            round_rect(c, 0, 0, w - 1, h - 1, px(T.radius), fill=T.layers[0], outline=T.panel_outline)
            for k, color in enumerate(T.layers[1:], start=1):
                round_rect(c, g * k, g * k, w - 1 - g * k, h - 1 - g * k, px(T.radius) - g * k / 2, fill=color,
                           outline="")
            k = len(T.layers)
            round_rect(c, g * k, g * k, w - 1 - g * k, h - 1 - g * k, px(T.radius) - g * k / 2, fill=self.bg,
                       outline="")
        elif T.shape == "round":
            round_rect(c, 0, 0, w - 1, h - 1, px(T.radius), fill=self.bg, outline=T.panel_outline)
        elif T.shape == "chamfer":
            chamfer_rect(c, 0, 0, w - 1, h - 1, px(7), fill=self.bg, outline=T.panel_outline)
        elif T.shape == "block":  # Mondrian: a flat color field inside a thick black line
            b = px(T.border)
            c.create_rectangle(b / 2, b / 2, w - b / 2, h - b / 2, fill=self.bg, outline="#111111", width=b)
        else:
            c.create_rectangle(0, 0, w - 1, h - 1, fill=self.bg, width=0)
            c.create_line(0, h - 1, 0, 0, w - 1, 0, fill=T.body_dark)
            c.create_line(1, h - 1, w - 1, h - 1, w - 1, 1, fill=T.body_light)
        if self.pattern and w > 40 and h > 40:
            self._draw_pattern(c, w, h)

    def _draw_pattern(self, c: tk.Canvas, w: int, h: int) -> None:
        # Deterministic, so the pattern does not jump around when the window redraws.
        rnd = random.Random(w * 7919 + h)
        m = px(10)  # the decorated margin (the inner frame covers the middle)
        spots = []
        for _ in range(int((w + h) / px(14))):
            edge = rnd.random() * 2 * (w + h)
            if edge < w:
                x, y = edge, rnd.uniform(m * 0.2, m)
            elif edge < w + h:
                x, y = w - rnd.uniform(m * 0.2, m), edge - w
            elif edge < 2 * w + h:
                x, y = edge - w - h, h - rnd.uniform(m * 0.2, m)
            else:
                x, y = rnd.uniform(m * 0.2, m), edge - 2 * w - h
            spots.append((x, y))
        if self.pattern == "spots":
            for x, y in spots:
                r = rnd.uniform(px(2), px(5))
                color = rnd.choice(("#5c5a61", "#2a292d", "#e9e0d0"))
                c.create_oval(x - r * 1.2, y - r, x + r * 1.2, y + r, fill=color, outline="")
        elif self.pattern == "leaves":
            for x, y in spots[::2]:
                draw_leaf(c, x, y, rnd.uniform(px(9), px(14)), rnd.uniform(0, 360), T.leaf)
        elif self.pattern == "bubbles":  # barely visible
            for x, y in spots[::3]:
                r = rnd.uniform(px(2), px(4))
                c.create_oval(x - r, y - r, x + r, y + r, outline=T.body_light, width=1)

    def bubble_burst(self, duration_ms: int = 2600) -> None:
        """Bubbles rising along the edges (pastel skin, when the playlist opens, where no overlay is possible)."""
        c = self.canvas
        w, h = c.winfo_width(), c.winfo_height()
        if w < 40 or h < 40:
            return
        rnd = random.Random()
        m = px(10)
        bubbles = []
        for _ in range(24):
            x = rnd.choice((rnd.uniform(m * 0.2, m * 0.8), w - rnd.uniform(m * 0.2, m * 0.8),
                            rnd.uniform(m, w - m)))
            r = rnd.uniform(px(3), px(6))
            y = h + rnd.uniform(0, h * 0.6)
            color = rnd.choice((T.accent, T.lcd_on, T.btn_dark))
            item = c.create_oval(x - r, y - r, x + r, y + r, outline=color, width=2, tags="burst")
            shine = c.create_oval(x - r * 0.5, y - r * 0.6, x - r * 0.1, y - r * 0.2, fill="#ffffff", outline="",
                                  tags="burst")
            bubbles.append(((item, shine), rnd.uniform(1.5, 3.5) * S, rnd.uniform(0, 6.28)))
        steps = max(1, duration_ms // 40)

        def step(i=0):
            if not c.winfo_exists():
                return
            if i >= steps:
                c.delete("burst")
                return
            for items, speed, phase in bubbles:
                for item in items:
                    c.move(item, math.sin(i / 5 + phase) * 0.6, -speed)
            c.after(40, step, i + 1)

        step()


# ------------------------------------------------------------ overlays

TRANSPARENT_KEY = "#010203"  # color keyed out of overlay windows


def overlay(widget: tk.Misc, frames: int, draw, interval: int = 33) -> tk.Toplevel | None:
    """Run a short animation in a borderless see-through window laid over `widget`.

    Only Windows has color-keyed windows (and there clicks go through the transparent part); elsewhere
    nothing is shown and None is returned. draw(canvas, frame, width, height) paints one frame.
    """
    try:
        widget.update_idletasks()
        w, h = widget.winfo_width(), widget.winfo_height()
        if not widget.winfo_viewable() or w < 20 or h < 20:
            return None
        top = tk.Toplevel(widget)
    except tk.TclError:
        return None
    top.withdraw()
    top.overrideredirect(True)
    try:
        top.attributes("-transparentcolor", TRANSPARENT_KEY)
    except tk.TclError:
        top.destroy()
        return None
    top.attributes("-topmost", True)
    try:
        top.attributes("-disabled", True)  # never takes input
    except tk.TclError:
        pass
    top.geometry(f"{w}x{h}+{widget.winfo_rootx()}+{widget.winfo_rooty()}")
    c = tk.Canvas(top, width=w, height=h, bg=TRANSPARENT_KEY, highlightthickness=0, bd=0)
    c.pack()
    focus = widget.focus_get()
    top.deiconify()
    if focus is not None:  # showing a window activates it: give the focus back (e.g. to the task field)
        focus.focus_force()

    def step(i=0):
        if not top.winfo_exists():
            return
        if i >= frames:
            top.destroy()
            return
        c.delete("all")
        draw(c, i, w, h)
        top.after(interval, step, i + 1)

    step()
    return top


def confetti_painter(colors: tuple[str, ...], count: int = 80, seed: int | None = None):
    """Paper confetti falling, fluttering and spinning over the whole window."""
    rnd = random.Random(seed)
    pieces = [dict(x=rnd.uniform(0, 1), y=rnd.uniform(-0.5, 0.0), vy=rnd.uniform(0.012, 0.024),
                   drift=rnd.uniform(4, 14), phase=rnd.uniform(0, 6.28), spin=rnd.uniform(-0.3, 0.3),
                   size=rnd.uniform(3, 6), color=rnd.choice(colors), round=rnd.random() < 0.25)
              for _ in range(count)]

    def draw(c: tk.Canvas, i: int, w: int, h: int) -> None:
        for p in pieces:
            y = (p["y"] + p["vy"] * i + 0.00012 * i * i) * h
            if y < -px(10) or y > h + px(10):
                continue
            x = p["x"] * w + math.sin(i * 0.15 + p["phase"]) * px(p["drift"])
            s = px(p["size"])
            if p["round"]:
                c.create_oval(x - s / 2, y - s / 2, x + s / 2, y + s / 2, fill=p["color"], outline="")
                continue
            a = p["phase"] + p["spin"] * i
            flip = abs(math.cos(i * 0.2 + p["phase"]))  # turning over: the strip looks thinner
            dx, dy = math.cos(a) * s, math.sin(a) * s
            ex, ey = -math.sin(a) * s * 0.45 * flip, math.cos(a) * s * 0.45 * flip
            c.create_polygon(x - dx - ex, y - dy - ey, x + dx - ex, y + dy - ey, x + dx + ex, y + dy + ey,
                             x - dx + ex, y - dy + ey, fill=p["color"], outline="")

    return draw


def bubble_painter(colors: tuple[str, ...], count: int = 26, frames: int = 75, seed: int | None = None):
    """Soap bubbles rising from the bottom with a wobble, each popping near its own height."""
    rnd = random.Random(seed)
    bubbles = [dict(x=rnd.uniform(0.05, 0.95), r=rnd.uniform(4, 12), start=rnd.randint(0, frames // 3),
                    speed=rnd.uniform(0.012, 0.022), pop=rnd.uniform(0.05, 0.6), phase=rnd.uniform(0, 6.28),
                    color=rnd.choice(colors)) for _ in range(count)]

    def draw(c: tk.Canvas, i: int, w: int, h: int) -> None:
        for b in bubbles:
            t = i - b["start"]
            if t < 0:
                continue
            r = px(b["r"])
            y = h + r - t * b["speed"] * h
            x = b["x"] * w + math.sin(t / 5 + b["phase"]) * px(3)
            if y < b["pop"] * h:  # popped: a few short lines for a moment, then gone
                if y > b["pop"] * h - b["speed"] * h * 3:
                    for k in range(6):
                        a = k * math.pi / 3
                        c.create_line(x + math.cos(a) * r * 0.8, y + math.sin(a) * r * 0.8,
                                      x + math.cos(a) * r * 1.3, y + math.sin(a) * r * 1.3, fill=b["color"],
                                      width=2)
                continue
            c.create_oval(x - r, y - r, x + r, y + r, outline=b["color"], width=2)
            c.create_arc(x - r * 0.7, y - r * 0.7, x + r * 0.7, y + r * 0.7, start=100, extent=70, style="arc",
                         outline="#ffffff", width=2)

    return draw


def confetti(widget: tk.Misc) -> tk.Toplevel | None:
    """Setsuna: confetti over the whole app (the playlist included) when the timer starts."""
    return overlay(widget, 60, confetti_painter(("#DB4C01", "#E94C53", "#111111", "#f7a35c", "#3f8f2f", "#ffd27a")))


def bubbles(widget: tk.Misc) -> tk.Toplevel | None:
    """Pastel: bubbles floating up over the playlist when it opens."""
    return overlay(widget, 75, bubble_painter((T.accent, T.lcd_on, "#b59ce0", "#7cc7e8")))


def orange_pieces(seconds: float, limit: int = 20) -> list[str]:
    """Setsuna title: a quarter orange after 15 running minutes, a half after 30, a whole one per hour."""
    minutes = int(max(0.0, seconds) // 60)
    pieces = ["w"] * (minutes // 60)
    rest = minutes % 60
    if rest >= 30:
        pieces.append("h")
    if rest % 30 >= 15:
        pieces.append("q")
    return pieces[:limit]


def field(master, textvariable: tk.StringVar, width: int, bg: str | None = None,
          fg: str | None = None) -> tuple[Panel, tk.Entry]:
    bg, fg = bg or T.lcd_bg, fg or T.lcd_text
    panel = Panel(master, pad=1, bg=bg)
    entry = tk.Entry(panel.inner, textvariable=textvariable, width=width, bg=bg, fg=fg,
                     insertbackground=fg, selectbackground=T.sel_bg, selectforeground=T.sel_fg,
                     disabledbackground=bg, relief="flat", bd=0, highlightthickness=0,
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
        elif self.style == "ice":  # chunky cubes of ice
            thick = 5.5
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
                if self.style == "ice":  # square-ended blocks, so lit segments look like ice cubes
                    t2 = t / 2 - 0.5
                    poly = ([x1 + 1, y1 - t2, x2 - 1, y1 - t2, x2 - 1, y1 + t2, x1 + 1, y1 + t2] if y1 == y2 else
                            [x1 - t2, y1 + 1, x1 + t2, y1 + 1, x1 + t2, y2 - 1, x1 - t2, y2 - 1])
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
                    if self.style == "ice":
                        self.itemconfigure(item, fill=on if seg in lit else T.lcd_off,
                                           outline=ICE_EDGE if seg in lit else "")
                    else:
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
        self.glows = [self.create_text(dx, px(9) + dy, anchor="w", text="", fill=blend(T.lcd_bg, T.glow, 0.7),
                                       font=self.font) for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
                      ] if T.glow else []
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
        for item in (*self.glows, self.item):
            self.itemconfigure(item, text=shown)

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
        self.kind = T.button or T.shape
        if self.kind == "round":
            w, h = w + px(4), h + px(2)
        if text:
            probe = tk.Label(master, text=text, font=font)
            w = max(w, probe.winfo_reqwidth() + px(12))
            probe.destroy()
        if self.kind == "paw" and h >= px(18):
            w, h = max(w + px(8), int(h * 1.6)), int(h * 1.6)
        elif self.kind == "paw":
            self.kind = "circle"  # too small for toes: a round bean
        if self.kind == "dandelion":  # a round flower: room for the ring of petals
            if text:
                h = h + px(4)
                w = max(w + px(6), h)
            else:
                w = h = max(w, h) + px(10)
        if self.kind == "circle":
            if text:
                h = h + px(4)
                w = max(w + px(6), h)
            else:
                w = h = max(w, h) + px(6)
        if self.kind == "block":
            w, h = w + px(6), h + px(6)
        # The glyph sits on the paw's big pad, lower than the middle.
        self.glyph_cy = h * 0.68 if self.kind == "paw" else h / 2
        self.fill, self.glyph_color = (block_colors(glyph) if self.kind == "block" else (T.btn_face, T.btn_glyph))
        super().__init__(master, width=w, height=h, bg=master["bg"], highlightthickness=0, cursor="hand2")
        self.command = command
        self.w, self.h = w, h
        self._draw_face(pressed=False)
        self.glyph_items = self._glyph(glyph) if glyph else [
            self.create_text(w / 2, self.glyph_cy, text=text, fill=self.glyph_color, font=font)]
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.tip = Tooltip(self, tooltip) if tooltip else None

    def _draw_face(self, pressed: bool) -> None:
        self.delete("face")
        w, h = self.w, self.h
        fill = T.btn_dark if pressed else T.btn_face
        if self.kind == "block":  # Mondrian: primary color field in a thick black frame, black when pressed
            b = max(2, px(T.border - 1))
            self.create_rectangle(b / 2, b / 2, w - b / 2, h - b / 2, fill="#111111" if pressed else self.fill,
                                  outline="#111111", width=b, tags="face")
        elif self.kind == "paw":
            draw_paw(self, 1, 1, w - 2, h - 2, fill=fill, outline="", tags="face")
        elif self.kind == "dandelion":  # subtle: a pale face inside a ring of tiny yellow petals
            if w == h:
                cx, cy, r = w / 2, h / 2, w / 2 - 1
                petal = blend(T.btn_face, T.btn_dark, 0.75)
                for k in range(24):
                    a = k * 2 * math.pi / 24
                    ca, sa = math.cos(a), math.sin(a)
                    self.create_polygon(cx + ca * r * 0.66 - sa * r * 0.08, cy + sa * r * 0.66 + ca * r * 0.08,
                                        cx + ca * r, cy + sa * r,
                                        cx + ca * r * 0.66 + sa * r * 0.08, cy + sa * r * 0.66 - ca * r * 0.08,
                                        fill=petal, outline="", tags="face")
                rr = r * 0.74
                self.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, fill=T.btn_dark if pressed else T.btn_face,
                                 outline=T.btn_dark, tags="face")
            else:
                round_rect(self, 1, 1, w - 2, h - 2, (h - 3) / 2, fill=T.btn_dark if pressed else T.btn_face,
                           outline=T.btn_dark, tags="face")
        elif self.kind == "circle":
            if w == h:
                self.create_oval(1, 1, w - 2, h - 2, fill=fill, outline="", tags="face")
            else:
                round_rect(self, 1, 1, w - 2, h - 2, (h - 3) / 2, fill=fill, outline="", tags="face")
        elif self.kind == "round":
            round_rect(self, 1, 1, w - 2, h - 2, px(T.radius) * 0.8, fill=fill, outline=T.btn_dark, tags="face")
        elif self.kind == "chamfer":  # armor plate: silver with a light top edge, neon when pressed
            chamfer_rect(self, 0, 0, w - 1, h - 1, px(5), fill=T.accent if pressed else T.btn_face,
                         outline=T.btn_dark, tags="face")
            if not pressed:
                self.create_line(px(5), 1, w - 2, 1, fill=T.btn_light, tags="face")
        else:
            self.create_rectangle(0, 0, w - 1, h - 1, fill=T.btn_face, width=0, tags="face")
            self.create_line(0, h - 1, 0, 0, w - 1, 0, fill=T.btn_dark if pressed else T.btn_light, tags="face")
            self.create_line(1, h - 1, w - 1, h - 1, w - 1, 0, fill=T.btn_light if pressed else T.btn_dark,
                             tags="face")
        self.tag_lower("face")

    def _glyph(self, glyph: str) -> list[int]:
        cx, cy = self.w / 2, self.glyph_cy
        s = min(self.w, self.h) * (0.2 if self.kind == "paw" else 0.28)
        fill = self.glyph_color
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

    def bullet_hole(self, duration_ms: int = 1800) -> None:
        """A bullet hole punched into the button: dark hole, torn rim, cracks and a puff of smoke.

        After a moment it fades back into the button face and is gone.
        """
        self.delete("hole")
        rnd = random.Random()
        cx = self.w / 2 + rnd.uniform(-0.15, 0.15) * self.w
        cy = self.glyph_cy + rnd.uniform(-0.15, 0.15) * self.h
        r = max(2.5, min(self.w, self.h) * 0.13)
        face, bg = self.fill if self.kind == "block" else T.btn_face, self["bg"]
        parts: list[tuple[int, str, str]] = []  # (item, color, option) to fade

        def jagged(radius: float, n: int = 11) -> list[float]:
            pts = []
            for k in range(n):
                a = k * 2 * math.pi / n
                rr = radius * rnd.uniform(0.8, 1.15)
                pts += [cx + math.cos(a) * rr, cy + math.sin(a) * rr]
            return pts

        soot = blend(face, "#000000", 0.45)
        parts.append((self.create_oval(cx - r * 2, cy - r * 2, cx + r * 2, cy + r * 2, fill=soot, outline="",
                                       tags="hole"), soot, "fill"))
        for _ in range(7):  # cracks running out from the hole
            a, length = rnd.uniform(0, 2 * math.pi), r * rnd.uniform(2.2, 3.4)
            bend = rnd.uniform(-0.35, 0.35)
            pts = [cx + math.cos(a) * r, cy + math.sin(a) * r,
                   cx + math.cos(a + bend) * length * 0.6, cy + math.sin(a + bend) * length * 0.6,
                   cx + math.cos(a) * length, cy + math.sin(a) * length]
            parts.append((self.create_line(*pts, fill="#a08f88", width=1, tags="hole"), "#a08f88", "fill"))
        parts.append((self.create_polygon(jagged(r * 1.3), fill="#6d564e", outline="", tags="hole"), "#6d564e",
                      "fill"))
        parts.append((self.create_polygon(jagged(r * 0.85, 9), fill="#050403", outline="", tags="hole"), "#050403",
                      "fill"))
        parts.append((self.create_line(cx - r * 1.1, cy - r * 0.4, cx - r * 0.5, cy - r * 1.1, fill="#d9cbc5",
                                       tags="hole"), "#d9cbc5", "fill"))
        smoke = [(self.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill="#c8bdb8", outline="", tags="hole"),
                  rnd.uniform(-0.4, 0.4)) for _ in range(3)]
        frames = max(1, duration_ms // 40)

        def step(i=0):
            if not self.winfo_exists():
                return
            if i >= frames:
                self.delete("hole")
                return
            t = i / frames
            for k, (item, drift) in enumerate(smoke):  # the puff drifts up, grows and thins out
                if t < 0.45:
                    x0, y0, x1, y1 = self.coords(item)
                    g = 0.35 + k * 0.1
                    self.coords(item, x0 - g + drift, y0 - g - 0.9, x1 + g + drift, y1 + g - 0.9)
                    self.itemconfigure(item, fill=blend("#c8bdb8", bg, t / 0.45))
                else:
                    self.itemconfigure(item, state="hidden")
            if t > 0.5:  # the hole closes up: its colors melt into the button face
                for item, color, option in parts:
                    self.itemconfigure(item, **{option: blend(color, face, (t - 0.5) / 0.5)})
            self.after(40, step, i + 1)

        step()

    def _set_glyph_color(self, color: str) -> None:
        for item in self.glyph_items:
            self.itemconfigure(item, fill=color)

    def _press(self, _event):
        self._draw_face(pressed=True)
        if self.kind == "chamfer":
            self._set_glyph_color(T.lcd_bg)
        elif self.kind == "round":
            self._set_glyph_color(T.btn_light)
        elif self.kind == "block":
            self._set_glyph_color("#ffffff")
        for item in self.glyph_items:
            self.move(item, 1, 1)

    def _release(self, event):
        self._draw_face(pressed=False)
        self._set_glyph_color(self.glyph_color)
        for item in self.glyph_items:
            self.move(item, -1, -1)
        if 0 <= event.x < self.w and 0 <= event.y < self.h:
            self.command()


def blend(c1: str, c2: str, t: float) -> str:
    """Color between c1 (t=0) and c2 (t=1); Tk has no alpha, so glows are drawn as blended rings."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


class ProductivityMeter(tk.Canvas):
    """One-line productivity meter. Clicking it calls on_click.

    Styles (theme `meter`): "" text and a three-part bar; "sword" a katana whose blade glows neon blue
    for the productive share; "flowers" a branch that blossoms for the productive share, and a click on
    a flower turns it into a walnut for the rest of the day (on_walnut stores it); "lanterns" a string of
    paper lanterns that light up; "cat" a bar with a fat white cat lying on it at 80%+ (click: tail wag,
    blink or paw swat, in random order); "mondrian" color fields in thick black lines; "glow" a lamp bar
    whose light grows with the share.
    """

    CAT_AT = 0.8

    def __init__(self, master, on_click, walnuts=(), on_walnut=None):
        self.h = {"cat": px(62), "lanterns": px(34), "glow": px(32), "flowers": px(32)}.get(T.meter, px(28) if T.meter else px(18))
        super().__init__(master, height=self.h, bg=master["bg"], highlightthickness=0, cursor="hand2")
        self.bg = master["bg"]
        self.shares: tuple[float, float, float] | None = None
        self.walnuts: set[int] = set(walnuts)
        self.on_click, self.on_walnut = on_click, on_walnut
        self.cat_pose = {"tail": 0.0, "face": False, "eyes": 1.0, "paw": 0.0}
        self.cat_box: tuple[float, float, float, float] | None = None
        self.cat_queue: list[str] = []
        self.animating = False
        self.walnut_ok = True  # flowers turn into walnuts only on today's meter
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Button-1>", self._clicked)

    def set(self, productive: float, neutral: float, distracting: float, total: float) -> None:
        shares = (productive / total, neutral / total, distracting / total) if total else None
        if shares != self.shares:
            self.shares = shares
            self.draw()

    # ------------------------------------------------------------ clicks

    def _clicked(self, event) -> None:
        for item in reversed(self.find_overlapping(event.x - 1, event.y - 1, event.x + 1, event.y + 1)):
            for tag in self.gettags(item):
                if tag.startswith("flower") and tag[6:].isdigit() and self.walnut_ok:
                    self.make_walnut(int(tag[6:]))
                    return
        box = self.cat_box
        if box and box[0] <= event.x <= box[2] and box[1] <= event.y <= box[3]:
            self.animate_cat()
            return
        self.on_click()

    def make_walnut(self, index: int) -> None:
        if index in self.walnuts:
            return
        self.walnuts.add(index)
        self.draw()
        if self.on_walnut:
            self.on_walnut(sorted(self.walnuts))

    # ------------------------------------------------------------ drawing

    def draw(self) -> None:
        self.delete("all")
        self.cat_box = None
        w, h = self.winfo_width(), self.h
        font = T.font("mono", 9, "bold" if T.upper else "normal")
        prod, neutral, dist = self.shares or (0.0, 0.0, 0.0)
        label = (T.tx(f"Produktivno {prod:.0%}") if T.meter else T.tx(f"Produktivno {prod:.0%} · ometanje {dist:.0%}")
                 ) if self.shares else T.tx("Produktivnost: još nema podataka" if not T.meter else "Bez podataka")
        text_y = px(40) if T.meter == "cat" else h / 2  # the cat sits on the bar, its tail hangs below
        text = self.create_text(0, text_y, anchor="w", fill=T.text, font=font, text=label)
        x0, x1 = self.bbox(text)[2] + px(10), w - px(2)
        if x1 - x0 < px(40) or (not self.shares and not T.meter):
            return
        style = T.meter
        if style == "sword":
            self._sword(x0, x1, h / 2, prod)
        elif style == "flowers":
            self._branch(x0, x1, h / 2, prod)
        elif style == "lanterns":
            self._lanterns(x0, x1, prod)
        elif style == "mondrian":
            self._mondrian(x0, x1, h / 2, prod, dist)
        elif style == "glow":
            self._glow(x0, x1, h / 2, prod)
        elif style == "bw":
            self._bw(x0, x1, h / 2, prod)
        elif style == "coffee":
            self._coffee(x0, x1, h / 2, prod)
        else:
            cy = text_y
            self._bar(x0, x1, cy, prod, neutral, dist)
            if style == "cat" and prod >= self.CAT_AT:
                self._cat(x0 + (x1 - x0) * 0.6, cy - px(4))

    def _bar(self, x0, x1, cy, prod, neutral, dist) -> None:
        y0, y1 = cy - px(4), cy + px(4)
        self.create_rectangle(x0, y0, x1, y1, fill=T.lcd_bg, outline=T.body_dark)
        x = x0
        for share, color in ((prod, T.meter_fill or T.lcd_on), (neutral, T.lcd_dim), (dist, T.accent)):
            seg = (x1 - x0) * share
            if seg >= 1:
                self.create_rectangle(x, y0, x + seg, y1, fill=color, width=0)
            x += seg

    def _sword(self, x0: float, x1: float, cy: float, prod: float) -> None:
        """Katana: kashira, wrapped tsuka, oval tsuba, habaki and a curved blade with a kissaki point."""
        length = x1 - x0
        grip_end = x0 + length * 0.22
        cy += px(2)
        # Tsuka: dark wrap with silver diamonds (same as the samurai's armor), kashira cap at the end.
        self.create_polygon(x0 + px(3), cy - px(3), grip_end, cy - px(3.4), grip_end, cy + px(3.4),
                            x0 + px(3), cy + px(3), fill="#1d2226", outline="#4b555c")
        x = x0 + px(5)
        while x + px(5) < grip_end - px(1):
            self.create_polygon(x, cy, x + px(2.5), cy - px(2.6), x + px(5), cy, x + px(2.5), cy + px(2.6),
                                fill="#8e9aa3", outline="")
            x += px(6)
        self.create_rectangle(x0, cy - px(3.6), x0 + px(3), cy + px(3.6), fill="#c99a6e", outline="#5a4128")
        # Tsuba (oval guard) and habaki (the collar at the blade's root).
        self.create_oval(grip_end, cy - px(8), grip_end + px(4), cy + px(8), fill="#2a2f33", outline="#c99a6e")
        b0, b1 = grip_end + px(4), x1
        self.create_polygon(b0, cy - px(4), b0 + px(5), cy - px(4.3), b0 + px(5), cy + px(3.6), b0, cy + px(3.6),
                            fill="#d9b25a", outline="#8a6a2a")
        b0 += px(5)
        n = 60
        half = px(3.8)
        point = 1 - min(0.12, px(16) / max(1.0, b1 - b0))  # where the kissaki (point) begins

        def spine(t: float) -> float:  # sori: the blade curves up towards the point
            return cy - px(5) * t * t

        def back(t: float) -> tuple[float, float]:
            y = spine(t) - half
            if t > point:  # the back runs almost straight into the point
                y += half * 0.6 * ((t - point) / (1 - point)) ** 2
            return b0 + (b1 - b0) * t, y

        def edge(t: float) -> tuple[float, float]:
            y = spine(t) + half
            if t > point:  # the cutting edge sweeps up in a curve to meet the back
                u = (t - point) / (1 - point)
                y -= half * 1.6 * (1 - math.cos(u * math.pi / 2)) ** 0.8
            return b0 + (b1 - b0) * t, y

        def outline(t_end: float) -> list[float]:
            ts = [t_end * i / n for i in range(n + 1)]
            pts = [back(t) for t in ts] + [edge(t) for t in reversed(ts)]
            return [v for p in pts for v in p]

        t = min(1.0, prod) if prod > 0.005 else 0.0
        if t:  # glow halo around the neon part: wide soft lines blending into the background
            mid = [((back(i * t / n)[0]), (back(i * t / n)[1] + edge(i * t / n)[1]) / 2) for i in range(n + 1)]
            for width, k in ((16, 0.18), (12, 0.32), (9, 0.5)):
                self.create_line(mid, fill=blend(self.bg, "#5fd8ff", k), width=px(width), capstyle="round",
                                 joinstyle="round", smooth=True)
        self.create_polygon(outline(1.0), fill="#c3ccd2", outline="#6f7b83")  # plain silver
        if t:
            self.create_polygon(outline(t), fill="#3cc6f5", outline="#9eeaff")
            # hamon: the wavy temper line, bright white-blue
            ham = [(back(i * t / n)[0], edge(i * t / n)[1] - px(1.6) - math.sin(i * 1.3) * px(0.6))
                   for i in range(n + 1)]
            self.create_line(ham, fill="#e9fbff", width=max(1, px(1)), smooth=True)
        else:
            ham = [(edge(i / n)[0], edge(i / n)[1] - px(1.6) - math.sin(i * 1.3) * px(0.6)) for i in range(n)]
            self.create_line(ham, fill="#eef2f4", width=1, smooth=True)
        # Yokote: the line where the point begins.
        yx = b0 + (b1 - b0) * point
        self.create_line(yx, back(point)[1] + 1, yx, edge(point)[1] - 1, fill="#6f7b83")

    def _branch(self, x0: float, x1: float, cy: float, prod: float) -> None:
        bark, twig = "#2e1c10", "#3d2616"
        pts = []
        for i in range(31):
            x = x0 + (x1 - x0) * i / 30
            pts.append((x, cy + px(2) + math.sin(i / 3.2) * px(1.5)))
        self.create_line(pts, fill=bark, width=max(2, px(3)), smooth=True, capstyle="round")
        bloom_until = x0 + (x1 - x0) * prod
        x, up, index = x0 + px(8), True, 0
        while x < x1 - px(4):
            base_y = cy + px(2) + math.sin((x - x0) / (x1 - x0) * 30 / 3.2) * px(1.5)
            tip = (x + px(5), base_y - px(8) if up else base_y + px(7))
            self.create_line(x, base_y, *tip, fill=twig, width=max(1, px(1.5)), capstyle="round")
            if index in self.walnuts:
                self._walnut(*tip)
            elif x <= bloom_until:  # a blossom on productive twigs, bare twig otherwise
                tag = f"flower{index}"
                r = px(2.6)
                for k in range(5):
                    a = k * 2 * math.pi / 5 + 0.3
                    px_, py_ = tip[0] + math.cos(a) * r, tip[1] + math.sin(a) * r
                    self.create_oval(px_ - r * 0.75, py_ - r * 0.75, px_ + r * 0.75, py_ + r * 0.75,
                                     fill="#f7d3df", outline="#d99ab0", tags=tag)
                self.create_oval(tip[0] - r * 0.5, tip[1] - r * 0.5, tip[0] + r * 0.5, tip[1] + r * 0.5,
                                 fill="#e8b923", outline="", tags=tag)
            x += px(11)
            up = not up
            index += 1

    def _walnut(self, cx: float, cy: float) -> None:
        """A walnut in its shell: brown, wrinkled, with the seam down the middle."""
        rx, ry = px(4), px(4.6)
        self.create_oval(cx - rx, cy - ry, cx + rx, cy + ry, fill="#a8763e", outline="#5a3a1a")
        self.create_line(cx, cy - ry, cx, cy + ry, fill="#5a3a1a")
        for dy in (-0.45, 0.0, 0.45):
            y = cy + ry * dy
            self.create_line(cx - rx * 0.7, y, cx - rx * 0.25, y - px(1), fill="#6e4a24")
            self.create_line(cx + rx * 0.25, y + px(1), cx + rx * 0.7, y, fill="#6e4a24")

    def _lanterns(self, x0: float, x1: float, prod: float) -> None:
        """Paper lanterns (chochin) on a sagging string; productive ones are lit and glow."""
        top = px(5)
        sag = px(5)
        self.create_line([(x0 + (x1 - x0) * i / 20, top + sag * math.sin(math.pi * i / 20)) for i in range(21)],
                         fill="#111111", width=1, smooth=True)
        lw, lh = px(13), px(18)
        count = max(1, int((x1 - x0) // (lw + px(7))))
        step = (x1 - x0) / count
        lit_n = round(count * prod)
        for i in range(count):
            cx = x0 + step * (i + 0.5)
            sy = top + sag * math.sin(math.pi * (cx - x0) / (x1 - x0))
            cy = sy + px(3) + lh / 2
            lit = i < lit_n
            self.create_line(cx, sy, cx, cy - lh / 2, fill="#111111")
            if lit:
                for k, g in ((0.25, px(6)), (0.45, px(4)), (0.7, px(2))):
                    self.create_oval(cx - lw / 2 - g, cy - lh / 2 - g, cx + lw / 2 + g, cy + lh / 2 + g,
                                     fill=blend(self.bg, "#ffb35c", k), outline="")
            paper, rib = ("#E94C53", "#a8282f") if lit else ("#f1ece4", "#c9c2b6")
            self.create_oval(cx - lw / 2, cy - lh / 2, cx + lw / 2, cy + lh / 2, fill=paper, outline=rib)
            for f in (-0.28, 0.0, 0.28):
                half = lw / 2 * math.sqrt(1 - (2 * f) ** 2)
                self.create_line(cx - half, cy + lh * f, cx + half, cy + lh * f, fill=rib)
            if lit:
                self.create_oval(cx - lw * 0.18, cy - lh * 0.2, cx + lw * 0.18, cy + lh * 0.2, fill="#ffd27a",
                                 outline="")
            for y in (cy - lh / 2, cy + lh / 2 - px(2)):
                self.create_rectangle(cx - lw * 0.28, y, cx + lw * 0.28, y + px(2), fill="#111111", outline="")

    def _mondrian(self, x0: float, x1: float, cy: float, prod: float, dist: float) -> None:
        """Yellow for productive, red for distracting, white for the rest, between thick black lines."""
        b = px(3)
        y0, y1 = cy - px(8), cy + px(8)
        self.create_rectangle(x0, y0, x1, y1, fill="#ffffff", outline="")
        xp = x0 + (x1 - x0) * prod
        xd = x1 - (x1 - x0) * dist
        if xp - x0 >= 1:
            self.create_rectangle(x0, y0, xp, y1, fill=MONDRIAN_YELLOW, outline="")
        if x1 - xd >= 1:
            self.create_rectangle(xd, y0, x1, y1, fill=MONDRIAN_RED, outline="")
        for x in (xp, xd):
            if x0 + 1 < x < x1 - 1:
                self.create_line(x, y0, x, y1, fill="#111111", width=b)
        self.create_rectangle(x0 + b / 2, y0 + b / 2, x1 - b / 2, y1 - b / 2, outline="#111111", width=b)

    def _glow(self, x0: float, x1: float, cy: float, prod: float) -> None:
        """Lamp bar: the filled part shines, and the halo around it grows as it fills."""
        r = px(4)
        lit = bool(T.dark_variant)
        fill = T.meter_fill or T.lcd_on
        xp = x0 + (x1 - x0) * prod
        if lit and xp - x0 > r:
            spread = px(4) + px(8) * prod
            for k in (0.22, 0.45, 0.75):
                g = spread * (1 - k)
                round_rect(self, x0 - g, cy - r - g, xp + g, cy + r + g, r + g, fill=blend(self.bg, fill, k),
                           outline="")
        round_rect(self, x0, cy - r, x1, cy + r, r, fill=T.lcd_off, outline=T.body_dark)
        if xp - x0 > r:
            round_rect(self, x0, cy - r, xp, cy + r, r, fill=fill, outline="")
            if lit:
                round_rect(self, x0 + px(2), cy - r * 0.35, xp - px(2), cy + r * 0.2, r * 0.3, fill="#fffbe8",
                           outline="")

    def _bw(self, x0: float, x1: float, cy: float, prod: float) -> None:
        """Plain black and white, rounded."""
        r = px(5)
        round_rect(self, x0, cy - r, x1, cy + r, r, fill="#ffffff", outline="#111111")
        xp = x0 + (x1 - x0) * prod
        if xp - x0 > r:
            round_rect(self, x0, cy - r, xp, cy + r, r, fill="#111111", outline="")

    COFFEE_TEXT = "How is possible?"

    def _coffee(self, x0: float, x1: float, cy: float, prod: float) -> None:
        """A glass of coffee lying down; at 80%+ the words show through the ice."""
        r = px(8)
        round_rect(self, x0, cy - r, x1, cy + r, r, fill="#0e0b0a", outline="#4c3b36")
        xp = x0 + (x1 - x0) * prod
        if xp - x0 > r:
            steps = 6  # layered espresso: darker at the bottom, crema on top
            for k in range(steps):
                y0 = cy - r + 2 * r * k / steps
                color = blend("#634e47", "#1c1614", k / (steps - 1))
                self.create_rectangle(x0 + r * 0.6, y0, xp - r * 0.6, y0 + 2 * r / steps + 1, fill=color,
                                      outline="")
            round_rect(self, x0, cy - r, xp, cy + r, r, fill="", outline="#4c3b36")
            for k, fx in enumerate((0.2, 0.45, 0.7) if prod < self.CAT_AT else ()):  # ice cubes floating in it
                x = x0 + (xp - x0) * fx
                if x + px(5) < xp - r * 0.6:
                    s = px(6)
                    self.create_rectangle(x, cy - s / 2 - px(1) * (k % 2), x + s, cy + s / 2 - px(1) * (k % 2),
                                          fill="", outline=ICE_EDGE)
        if prod >= self.CAT_AT:
            font = T.font("sans", 9, "bold")
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                self.create_text((x0 + x1) / 2 + dx, cy + dy, text=self.COFFEE_TEXT, font=font,
                                 fill=blend("#1c1614", T.glow or "#ffffff", 0.9))
            self.create_text((x0 + x1) / 2, cy, text=self.COFFEE_TEXT, font=font, fill="#f2fafc")

    # ------------------------------------------------------------ the cat

    def _cat(self, cx: float, base: float) -> None:
        """Fat white cat loafing on the bar in profile, facing left with its small head turned away
        (only the back of the head shows); the tail hangs down over the bar.

        cx is the middle of the body, base the bar's top edge.
        """
        p = self.cat_pose
        white, line, spot = "#ffffff", "#77737c", "#b3afb7"
        bw, bh = px(54), px(25)
        bx0, bx1 = cx - bw / 2, cx + bw / 2
        lw = max(1, px(1))
        # Tail (behind the body): from the rump over the bar's far edge, hanging below it.
        swing = p["tail"]
        tail = [(bx1 - px(8), base - px(6)), (bx1 + px(2), base - px(1)), (bx1 + px(4) + swing * px(3), base + px(9)),
                (bx1 + px(2) + swing * px(9), base + px(21))]
        self.create_line(tail, fill=line, width=px(7), smooth=True, capstyle="round", tags="cat")
        self.create_line(tail, fill=white, width=px(7) - 2 * lw, smooth=True, capstyle="round", tags="cat")
        tip = tail[-1]
        self.create_oval(tip[0] - px(2.5), tip[1] - px(2.5), tip[0] + px(2.5), tip[1] + px(2.5), fill=spot,
                         outline="", tags="cat")
        # Body: a loaf, flat at the bottom, highest over the back.
        body = [(bx0 + bw * 0.12, base), (bx0 + bw * 0.02, base - bh * 0.3), (bx0 + bw * 0.06, base - bh * 0.8),
                (bx0 + bw * 0.3, base - bh * 0.98), (bx0 + bw * 0.62, base - bh * 1.04), (bx1 - bw * 0.06, base - bh * 0.8),
                (bx1, base - bh * 0.32), (bx1 - bw * 0.06, base), (bx0 + bw * 0.5, base + px(1))]
        self.create_polygon([v for pt in body for v in pt], smooth=True, fill=white, outline=line, width=lw,
                            tags="cat")
        rnd = random.Random(7)
        for sx, sy, sr in ((0.45, 0.74, 3.2), (0.56, 0.62, 1.6), (0.76, 0.82, 2.4), (0.3, 0.4, 1.4), (0.84, 0.5, 1.5),
                           (0.62, 0.86, 1.3), (0.2, 0.7, 1.1)):
            x, y, r = bx0 + bw * sx, base - bh * sy, px(sr)
            self.create_oval(x - r * 1.5, y - r, x + r * 1.5, y + r * rnd.uniform(0.8, 1.1), fill=spot, outline="",
                             tags="cat")
        # Haunch: the folded back leg.
        self.create_arc(bx1 - bw * 0.38, base - bh * 0.62, bx1 - bw * 0.04, base + bh * 0.3, start=30, extent=120,
                        style="arc", outline=line, width=lw, tags="cat")
        # Front paw: tucked under the chest, or reaching out for a swat.
        reach = p["paw"]
        px0, py0 = bx0 + bw * 0.1, base - px(2)
        tip_x, tip_y = px0 - px(3) - reach * px(12), py0 - reach * px(9)
        self.create_line(px0 + px(4), py0, tip_x, tip_y, fill=line, width=px(5), capstyle="round", tags="cat")
        self.create_line(px0 + px(4), py0, tip_x, tip_y, fill=white, width=px(5) - 2 * lw, capstyle="round",
                         tags="cat")
        # Head: small, at the front of the loaf, ears up.
        hr = px(8)
        hx, hy = bx0 + bw * 0.1, base - bh * 0.92
        for ex, tilt in ((-0.6, -1), (0.35, 1)):
            ear_x = hx + hr * ex
            self.create_polygon(ear_x - px(3.5), hy - hr * 0.55, ear_x + tilt * px(0.8), hy - hr - px(5),
                                ear_x + px(3.5), hy - hr * 0.5, fill=white, outline=line, width=lw, tags="cat")
        self.create_oval(hx - hr, hy - hr, hx + hr, hy + hr * 0.92, fill=white, outline=line, width=lw, tags="cat")
        self.create_oval(hx + px(1), hy - hr + px(1.5), hx + px(5), hy - hr + px(4.5), fill=spot, outline="",
                         tags="cat")
        if p["face"]:  # turned towards us: eyes (slowly blinking) and a pink nose
            eye = p["eyes"]
            for ex in (hx - px(3.2), hx + px(3.2)):
                if eye > 0.2:
                    self.create_oval(ex - px(1.4), hy - px(1.6) * eye, ex + px(1.4), hy + px(1.6) * eye,
                                     fill="#3b3a3e", outline="", tags="cat")
                else:
                    self.create_arc(ex - px(1.8), hy - px(1.6), ex + px(1.8), hy + px(1.2), start=180, extent=180,
                                    style="arc", outline="#3b3a3e", width=lw, tags="cat")
            self.create_polygon(hx - px(1.3), hy + px(2.4), hx + px(1.3), hy + px(2.4), hx, hy + px(3.8),
                                fill="#e9a3b0", outline="", tags="cat")
        self.cat_box = (min(bx0, tip_x) - px(4), hy - hr - px(6), bx1 + px(14), base + px(24))

    def animate_cat(self) -> str | None:
        """Play the next of the three cat animations (shuffled each round)."""
        if self.animating or not self.cat_box:
            return None
        if not self.cat_queue:
            self.cat_queue = random.sample(["tail", "blink", "paw"], 3)
        kind = self.cat_queue.pop()
        frames: list[dict] = []
        if kind == "tail":  # three swings left and right
            frames = [{"tail": math.sin(i / 16 * 2 * math.pi * 3) * 1.0} for i in range(49)]
        elif kind == "blink":  # turn the head, a slow blink, turn back
            frames = ([{"face": True, "eyes": 1.0}] * 8 + [{"face": True, "eyes": 1 - i / 6} for i in range(7)]
                      + [{"face": True, "eyes": 0.0}] * 5 + [{"face": True, "eyes": i / 6} for i in range(7)]
                      + [{"face": True, "eyes": 1.0}] * 8)
        else:  # a quick swat with the paw
            frames = ([{"paw": i / 4} for i in range(5)] + [{"paw": 1.0}] * 3
                      + [{"paw": 1 - i / 8} for i in range(9)])
        frames.append({})
        self.animating = True

        def step(i=0):
            if not self.winfo_exists():
                return
            self.cat_pose = {"tail": 0.0, "face": False, "eyes": 1.0, "paw": 0.0, **frames[i]}
            self.draw()
            if i + 1 < len(frames):
                self.after(40, step, i + 1)
            else:
                self.animating = False

        step()
        return kind


class TitleBar(tk.Canvas):
    """Title strip styled by the theme; with on_menu it gets a small menu button on the left."""

    def __init__(self, master, title: str, on_menu=None):
        self.h = {"ears": px(44), "mondrian": px(28), "oranges": px(22), "egg": px(22), "dandelion": px(22),
                  "coffee": px(26)}.get(T.title_style, px(18))
        super().__init__(master, height=self.h, bg=T.body, highlightthickness=0)
        self.title = title
        self.on_menu = on_menu
        self.pieces: list[str] = []  # Setsuna: orange pieces earned by the running timer
        self.bind("<Configure>", lambda e: self.draw())

    def set_pieces(self, pieces: list[str]) -> None:
        if pieces != self.pieces:
            self.pieces = list(pieces)
            self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.h
        style = T.title_style
        text_color, text_y = T.text, h / 2
        if style == "ears":  # a dark head band with two cat ears sticking up
            band = px(18)
            for ex in (w * 0.14, w * 0.86):
                bw, eh = px(42), px(24)
                base, tip = h - band + px(4), h - band - eh
                self.create_polygon(ex - bw / 2, base, ex - bw * 0.06, tip, ex + bw / 2, base,
                                    fill=T.lcd_bg, outline="")
                self.create_polygon(ex - bw * 0.27, base, ex - bw * 0.06, tip + eh * 0.32, ex + bw * 0.27, base,
                                    fill=T.body_dark, outline="")
            round_rect(self, 0, h - band, w - 1, h + px(8), px(8), fill=T.lcd_bg, outline="")
            text_color, text_y = T.lcd_text, h - band / 2
        if style == "mondrian":  # color fields between thick black lines
            b = px(4)
            for x0_, x1_, color in ((0, w * 0.17, MONDRIAN_RED), (w * 0.8, w * 0.92, MONDRIAN_BLUE),
                                    (w * 0.92, w, MONDRIAN_YELLOW)):
                self.create_rectangle(x0_, 0, x1_, h, fill=color, outline="")
            for x in (w * 0.17, w * 0.8, w * 0.92):
                self.create_line(x, 0, x, h, fill="#111111", width=b)
            self.create_line(0, h - b / 2, w, h - b / 2, fill="#111111", width=b)
            text_y = h / 2 - px(1)
        if style == "grain":  # wood grain
            for i, y in enumerate((3, 6, 10, 13, 16)):
                pts = []
                for x in range(0, w + 20, 20):
                    pts += [x, px(y) + math.sin((x + i * 37) / 23) * px(1.2)]
                self.create_line(pts, fill=T.body_light, smooth=True)
        font = T.font("sans", 8 if T.upper else 9, "bold" if T.upper or style == "coffee" else "normal")
        if T.glow:  # iced text: a soft light halo around it
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                self.create_text(w / 2 + dx, text_y + dy, text=T.tx(self.title), fill=blend(T.body, T.glow, 0.8),
                                 font=font)
            text_color = blend(T.body, "#eef8fb", 0.88)  # a little see-through, like ice
        text = self.create_text(w / 2, text_y, text=T.tx(self.title), fill=text_color, font=font)
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
        elif style == "oranges":  # earned pieces, alternating left and right of the title, outwards
            r, step = px(6), px(15)
            for i, kind in enumerate(self.pieces):
                k = i // 2 + 1
                x = x0 - k * step + px(4) if i % 2 == 0 else x1 + k * step - px(4)
                if r < x < w - r:
                    draw_orange_piece(self, x, h / 2 + px(2), r, kind)
        elif style == "dandelion":  # a seed floating off on each side, subtly
            for x, d in ((x0 - px(14), -1), (x1 + px(14), 1)):
                y = h / 2
                self.create_line(x, y + px(5), x + d * px(2), y - px(2), fill="#b9b9b9")
                for k in range(-3, 4):
                    a = -math.pi / 2 + d * 0.25 + k * 0.33
                    self.create_line(x + d * px(2), y - px(2), x + d * px(2) + math.cos(a) * px(5),
                                     y - px(2) + math.sin(a) * px(5), fill="#cfcfcf")
        elif style == "coffee":
            for x in (x0 - px(16), x1 + px(16)):
                draw_iced_americano(self, x, h / 2 + px(1), px(18))
        elif style == "egg":
            lit = T.key.endswith("_lit")
            for x in (x0 - px(16), x1 + px(16)):
                draw_egg(self, x, h / 2, px(12), lit)
        if self.on_menu:
            r = px(6)
            cx, cy = px(11), text_y
            if style == "ears":  # on the dark band: a cream button
                box = self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=T.lcd_text, outline="")
            elif style == "mondrian":  # a white square on the red field
                cx = px(13)
                box = self.create_rectangle(cx - r, cy - r, cx + r, cy + r, fill="#ffffff", outline="#111111",
                                            width=2)
            elif T.shape == "round":
                box = self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=T.btn_face, outline=T.btn_dark)
            elif T.shape == "chamfer":
                box = self.create_polygon(cx, cy - r, cx + r, cy, cx, cy + r, cx - r, cy, fill=T.btn_face,
                                          outline=T.accent)
            else:
                box = self.create_rectangle(cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1, fill=T.btn_face,
                                            outline=T.btn_dark)
            bar = self.create_line(cx - r / 2, cy, cx + r / 2, cy, fill=T.lcd_bg if style == "ears" else T.btn_glyph,
                                   width=max(1, px(2)))
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
