"""Shared look and small widgets for the tkinter UI."""

from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import ttk

# Categorical project colors, assigned in this fixed order (CVD-validated palette).
PROJECT_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]

BG = "#f7f7f5"
SURFACE = "#ffffff"
TEXT = "#1f1f1f"
TEXT_MUTED = "#6b6a66"
GRID = "#e4e3df"
ACCENT = "#2a78d6"
START_GREEN = "#1a8f4c"
STOP_RED = "#d33b3b"

if sys.platform == "win32":
    FONT = "Segoe UI"
    MONO = "Consolas"
else:
    FONT = "DejaVu Sans"
    MONO = "DejaVu Sans Mono"


def resource_path(name: str) -> Path:
    """Locate bundled assets both from source and from a PyInstaller build."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent))
    return base / "assets" / name


def setup_style(root: tk.Tk) -> ttk.Style:
    style = ttk.Style(root)
    for theme in ("vista", "clam"):
        if theme in style.theme_names():
            style.theme_use(theme)
            break
    root.configure(background=BG)
    # Named fonts, not option_add("*Font"): the option database would override ttk style fonts.
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        try:
            tkfont.nametofont(name).configure(family=FONT, size=10)
        except tk.TclError:
            pass
    style.configure(".", font=(FONT, 10))
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=SURFACE)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Card.TLabel", background=SURFACE)
    style.configure("Muted.TLabel", foreground=TEXT_MUTED)
    style.configure("CardMuted.TLabel", background=SURFACE, foreground=TEXT_MUTED)
    style.configure("Title.TLabel", font=(FONT, 13, "bold"))
    style.configure("Big.TLabel", font=(FONT, 18, "bold"), background=SURFACE)
    style.configure("Stat.TLabel", font=(FONT, 16, "bold"), background=SURFACE)
    style.configure("Timer.TLabel", font=(MONO, 22, "bold"), background=SURFACE, foreground=TEXT)
    style.configure("TCheckbutton", background=BG)
    style.configure("Card.TCheckbutton", background=SURFACE)
    style.configure("TRadiobutton", background=BG)
    style.configure("TLabelframe", background=BG)
    style.configure("TLabelframe.Label", background=BG, font=(FONT, 10, "bold"))
    style.configure("Treeview", rowheight=26, font=(FONT, 10))
    style.configure("Treeview.Heading", font=(FONT, 10, "bold"))
    style.configure("TNotebook", background=BG)
    style.configure("TNotebook.Tab", padding=(14, 6), font=(FONT, 10))
    style.configure("Accent.TButton", font=(FONT, 10, "bold"))
    style.configure("Goal.Horizontal.TProgressbar", background=ACCENT, troughcolor=GRID, bordercolor=GRID,
                    lightcolor=ACCENT, darkcolor=ACCENT)
    return style


class BigButton(tk.Button):
    """Flat colored Start/Stop button (ttk buttons cannot be recolored on the vista theme)."""

    def __init__(self, master, **kw):
        kw.setdefault("font", (FONT, 12, "bold"))
        kw.setdefault("fg", "white")
        kw.setdefault("activeforeground", "white")
        kw.setdefault("relief", "flat")
        kw.setdefault("bd", 0)
        kw.setdefault("padx", 22)
        kw.setdefault("pady", 8)
        kw.setdefault("cursor", "hand2")
        super().__init__(master, **kw)

    def set_state(self, running: bool) -> None:
        if running:
            self.configure(text="■  STOP", bg=STOP_RED, activebackground="#b52f2f")
        else:
            self.configure(text="▶  START", bg=START_GREEN, activebackground="#157a40")


class PlaceholderEntry(ttk.Entry):
    """Entry that shows grey hint text while empty."""

    def __init__(self, master, placeholder: str, textvariable: tk.StringVar, **kw):
        super().__init__(master, textvariable=textvariable, **kw)
        self._placeholder = placeholder
        self._var = textvariable
        self._showing = False
        self.bind("<FocusIn>", self._focus_in, add="+")
        self.bind("<FocusOut>", self._focus_out, add="+")
        self._focus_out()

    def _focus_in(self, _event=None):
        if self._showing:
            self._showing = False
            self.delete(0, "end")
            self.configure(foreground=TEXT)

    def _focus_out(self, _event=None):
        if not self._var.get():
            self._showing = True
            self.insert(0, self._placeholder)
            self.configure(foreground=TEXT_MUTED)

    def value(self) -> str:
        return "" if self._showing else self._var.get()

    def set_value(self, text: str) -> None:
        self._showing = False
        self.configure(foreground=TEXT)
        self.delete(0, "end")
        self.insert(0, text)
        if not text and self.focus_get() is not self:
            self._focus_out()


def scrolled_tree(master, columns, **kw) -> tuple[ttk.Frame, ttk.Treeview]:
    frame = ttk.Frame(master)
    tree = ttk.Treeview(frame, columns=columns, **kw)
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    sb.grid(row=0, column=1, sticky="ns")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    return frame, tree


class Tooltip:
    """Small hover label for canvas items."""

    def __init__(self, widget: tk.Widget):
        self.widget = widget
        self.tip: tk.Toplevel | None = None

    def show(self, text: str, x_root: int, y_root: int) -> None:
        if self.tip is None:
            self.tip = tk.Toplevel(self.widget)
            self.tip.wm_overrideredirect(True)
            self.tip.attributes("-topmost", True)
            self.label = tk.Label(self.tip, bg="#1f1f1f", fg="white", font=(FONT, 9), padx=8, pady=4,
                                  justify="left")
            self.label.pack()
        self.label.configure(text=text)
        self.tip.wm_geometry(f"+{x_root + 12}+{y_root + 12}")
        self.tip.deiconify()

    def hide(self, _event=None) -> None:
        if self.tip is not None:
            self.tip.withdraw()


def color_square(widget: tk.Misc, color: str, size: int = 12) -> tk.PhotoImage:
    """Small solid square image used as a project color marker in tree views.

    Cached on the root window, because images belong to one Tk interpreter.
    """
    root = widget._root()
    cache = root.__dict__.setdefault("_color_squares", {})
    img = cache.get((color, size))
    if img is None:
        img = tk.PhotoImage(master=root, width=size, height=size)
        img.put(color, to=(1, 1, size - 1, size - 1))
        cache[(color, size)] = img
    return img


def set_window_icon(win: tk.Misc) -> None:
    ico = resource_path("icon.ico")
    png = resource_path("icon.png")
    try:
        if sys.platform == "win32" and ico.exists():
            win.iconbitmap(default=str(ico))
        elif png.exists():
            img = tk.PhotoImage(file=str(png))
            win.iconphoto(True, img)
            win._icon_ref = img  # keep a reference
    except tk.TclError:
        pass


def center_on_parent(win: tk.Toplevel, parent: tk.Misc) -> None:
    win.update_idletasks()
    if parent.winfo_viewable():
        x = parent.winfo_rootx() + (parent.winfo_width() - win.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win.winfo_height()) // 3
    else:
        x = (win.winfo_screenwidth() - win.winfo_width()) // 2
        y = (win.winfo_screenheight() - win.winfo_height()) // 3
    win.geometry(f"+{max(0, x)}+{max(0, y)}")
