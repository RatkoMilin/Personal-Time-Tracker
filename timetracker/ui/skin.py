"""Winamp-style skin: colors, LCD seven-segment display, marquee, beveled buttons."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

BODY = "#2b2b3a"
BODY_LIGHT = "#55556b"
BODY_DARK = "#121219"
TEXT = "#d8d8e4"
GOLD = "#c9a94b"
LCD_BG = "#000000"
LCD_ON = "#00e800"
LCD_OFF = "#0a260a"
LCD_DIM = "#1c8a1c"
BTN_FACE = "#b4b4c2"
BTN_LIGHT = "#ececf4"
BTN_DARK = "#56566a"
BTN_GLYPH = "#1c1c26"
SEL_BG = "#0000c6"
WHITE = "#ffffff"

if sys.platform == "win32":
    MONO = "Consolas"
    SANS = "Tahoma"
else:
    MONO = "DejaVu Sans Mono"
    SANS = "DejaVu Sans"

# Pixel scale for canvas drawings, so they grow with fonts on high-DPI screens.
S = 1.0


def px(v: float) -> int:
    return int(round(v * S))


def init(root: tk.Tk) -> None:
    global S
    S = max(1.0, root.winfo_fpixels("1i") / 96.0)
    root.configure(bg=BODY)
    style = ttk.Style(root)
    style.theme_use("clam")  # the only built-in theme that honors custom colors everywhere
    style.configure("Skin.TCombobox", fieldbackground=LCD_BG, background=BTN_FACE, foreground=LCD_ON,
                    arrowcolor=BTN_GLYPH, bordercolor=BODY_DARK, lightcolor=BODY_DARK, darkcolor=BODY_DARK,
                    selectbackground=LCD_BG, selectforeground=LCD_ON, insertcolor=LCD_ON, padding=2)
    style.map("Skin.TCombobox", fieldbackground=[("readonly", LCD_BG)], foreground=[("readonly", LCD_ON)],
              selectbackground=[("focus", LCD_BG)], selectforeground=[("focus", LCD_ON)])
    root.option_add("*TCombobox*Listbox.background", LCD_BG)
    root.option_add("*TCombobox*Listbox.foreground", LCD_ON)
    root.option_add("*TCombobox*Listbox.selectBackground", SEL_BG)
    root.option_add("*TCombobox*Listbox.selectForeground", WHITE)
    root.option_add("*TCombobox*Listbox.font", (MONO, 10))
    root.option_add("*Menu.background", BODY)
    root.option_add("*Menu.foreground", TEXT)
    root.option_add("*Menu.activeBackground", SEL_BG)
    root.option_add("*Menu.activeForeground", WHITE)
    root.option_add("*Menu.selectColor", LCD_ON)


def lcd_entry(master, textvariable: tk.StringVar, width: int) -> tk.Entry:
    return tk.Entry(master, textvariable=textvariable, width=width, bg=LCD_BG, fg=LCD_ON, insertbackground=LCD_ON,
                    selectbackground=SEL_BG, selectforeground=WHITE, relief="flat", font=(MONO, 10),
                    highlightthickness=1, highlightbackground=BODY_DARK, highlightcolor=GOLD)


def label(master, text: str = "", **kw) -> tk.Label:
    kw.setdefault("font", (SANS, 8, "bold"))
    kw.setdefault("fg", TEXT)
    return tk.Label(master, text=text, bg=BODY, **kw)


def sunken(master, **kw) -> tuple[tk.Frame, tk.Frame]:
    """Black LCD well with a dark/light bevel."""
    outer = tk.Frame(master, bg=BODY_LIGHT, padx=0, pady=0)
    inner = tk.Frame(outer, bg=LCD_BG, **kw)
    inner.pack(padx=1, pady=1, fill="both", expand=True)
    tk.Frame(outer, bg=BODY_DARK, height=1).place(x=0, y=0, relwidth=1)
    tk.Frame(outer, bg=BODY_DARK, width=1).place(x=0, y=0, relheight=1)
    return outer, inner


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
    """LCD digits drawn as polygons, with dim 'ghost' segments like a real display."""

    def __init__(self, master, pattern: str = "88:88:88", digit_w: float = 20, digit_h: float = 36,
                 thick: float = 4.5):
        self.dw, self.dh, self.t = px(digit_w), px(digit_h), max(2.0, thick * S)
        self.gap = px(5)
        self.colon_w = px(9)
        self.pattern = pattern
        width = sum(self.colon_w if ch == ":" else self.dw + self.gap for ch in pattern)
        super().__init__(master, width=width, height=self.dh + px(2), bg=LCD_BG, highlightthickness=0)
        self.cells: list[dict[str, int] | list[int]] = []
        x = 0
        for ch in pattern:
            if ch == ":":
                self.cells.append(self._colon(x))
                x += self.colon_w
            else:
                self.cells.append(self._digit(x))
                x += self.dw + self.gap
        self.set("  :  :  ")

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
        polys = {
            "a": self._hseg(left + g, top, right - left - 2 * g),
            "g": self._hseg(left + g, mid, right - left - 2 * g),
            "d": self._hseg(left + g, bot, right - left - 2 * g),
            "f": self._vseg(left, top + g, mid - top - 2 * g),
            "b": self._vseg(right, top + g, mid - top - 2 * g),
            "e": self._vseg(left, mid + g, bot - mid - 2 * g),
            "c": self._vseg(right, mid + g, bot - mid - 2 * g),
        }
        return {k: self.create_polygon(p, fill=LCD_OFF, outline="") for k, p in polys.items()}

    def _colon(self, x0) -> list[int]:
        s = self.t
        cx = x0 + self.colon_w / 2 - self.gap / 2
        y1, y2 = px(1) + self.dh * 0.32, px(1) + self.dh * 0.7
        return [self.create_rectangle(cx - s / 2, y - s / 2, cx + s / 2, y + s / 2, fill=LCD_OFF, width=0)
                for y in (y1, y2)]

    def set(self, text: str, on: str = LCD_ON) -> None:
        for cell, ch in zip(self.cells, text.rjust(len(self.pattern))):
            if isinstance(cell, list):
                for item in cell:
                    self.itemconfigure(item, fill=on if ch == ":" else LCD_OFF)
            else:
                lit = DIGITS.get(ch, "")
                for seg, item in cell.items():
                    self.itemconfigure(item, fill=on if seg in lit else LCD_OFF)


class Marquee(tk.Canvas):
    """Scrolling song-title style text."""

    def __init__(self, master, chars: int = 30):
        self.chars = chars
        self.font = (MONO, 10)
        probe = tk.Label(master, text="M" * chars, font=self.font)
        width = probe.winfo_reqwidth()
        probe.destroy()
        super().__init__(master, width=width, height=px(18), bg=LCD_BG, highlightthickness=0)
        self.item = self.create_text(0, px(9), anchor="w", text="", fill=LCD_ON, font=self.font)
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
        self.offset += 1
        self._render()
        self.after(250, self._step)


# ------------------------------------------------------------------ buttons

class SkinButton(tk.Canvas):
    """Beveled silver button with a drawn glyph (play/pause/stop/eject/prev/next) or a text label."""

    def __init__(self, master, command, glyph: str | None = None, text: str | None = None,
                 width: float = 26, height: float = 20, tooltip: str | None = None):
        font = (SANS, 7, "bold")
        w, h = px(width), px(height)
        if text:
            probe = tk.Label(master, text=text, font=font)
            w = max(w, probe.winfo_reqwidth() + px(10))
            probe.destroy()
        super().__init__(master, width=w, height=h, bg=BODY, highlightthickness=0, cursor="hand2")
        self.command = command
        self.w, self.h = w, h
        self.face = self.create_rectangle(0, 0, w - 1, h - 1, fill=BTN_FACE, width=0)
        self.light = [self.create_line(0, h - 1, 0, 0, w - 1, 0, fill=BTN_LIGHT)]
        self.dark = [self.create_line(1, h - 1, w - 1, h - 1, w - 1, 0, fill=BTN_DARK)]
        self.glyph_items = self._glyph(glyph) if glyph else [
            self.create_text(w / 2, h / 2, text=text, fill=BTN_GLYPH, font=font)]
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.tip = Tooltip(self, tooltip) if tooltip else None

    def _glyph(self, glyph: str) -> list[int]:
        cx, cy = self.w / 2, self.h / 2
        s = min(self.w, self.h) * 0.28
        fill = BTN_GLYPH
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

    def _press(self, _event):
        for item in self.light:
            self.itemconfigure(item, fill=BTN_DARK)
        for item in self.dark:
            self.itemconfigure(item, fill=BTN_LIGHT)
        for item in self.glyph_items:
            self.move(item, 1, 1)

    def _release(self, event):
        for item in self.light:
            self.itemconfigure(item, fill=BTN_LIGHT)
        for item in self.dark:
            self.itemconfigure(item, fill=BTN_DARK)
        for item in self.glyph_items:
            self.move(item, -1, -1)
        if 0 <= event.x < self.w and 0 <= event.y < self.h:
            self.command()


class TitleBar(tk.Canvas):
    """Winamp-like title strip: gold stripes around the name, a menu square on the left."""

    def __init__(self, master, title: str, on_menu=None):
        super().__init__(master, height=px(16), bg=BODY, highlightthickness=0)
        self.title = title
        self.on_menu = on_menu
        self.bind("<Configure>", lambda e: self.draw())

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), px(16)
        if self.on_menu:
            box = self.create_rectangle(px(4), px(3), px(14), px(13), fill=BTN_FACE, outline=BTN_DARK)
            self.create_line(px(6), px(8), px(12), px(8), fill=BTN_GLYPH, width=max(1, px(2)))
            self.tag_bind(box, "<Button-1>", lambda e: self.on_menu(e))
        text = self.create_text(w / 2, h / 2, text=self.title, fill=TEXT, font=(SANS, 7, "bold"))
        x0, _, x1, _ = self.bbox(text)
        for y in (px(5), px(8), px(11)):
            self.create_line(px(20) if self.on_menu else px(6), y, x0 - px(8), y, fill=GOLD)
            self.create_line(x1 + px(8), y, w - px(6), y, fill=GOLD)


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str):
        self.widget, self.text, self.tip, self._job = widget, text, None, None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event):
        self._job = self.widget.after(500, self._show)

    def _show(self):
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        tk.Label(self.tip, text=self.text, bg="#ffffe1", fg="black", relief="solid", bd=1, font=(SANS, 8),
                 padx=4, pady=1).pack()
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
        if sys.platform == "win32" and ico.exists():
            win.iconbitmap(default=str(ico))
        elif png.exists():
            img = tk.PhotoImage(file=str(png))
            win.iconphoto(True, img)
            win._icon_ref = img
    except tk.TclError:
        pass
