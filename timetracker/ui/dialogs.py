"""Skinned dialogs: edit/add an entry and the idle reminder."""

from __future__ import annotations

import time
import tkinter as tk
from datetime import date
from tkinter import messagebox

from .. import timeutil
from ..db import Database, Entry
from . import skin


def _place(win: tk.Toplevel, parent: tk.Misc) -> None:
    """Center over the parent when it is visible, otherwise on the screen."""
    win.update_idletasks()
    if parent.winfo_viewable():
        x = parent.winfo_rootx() + (parent.winfo_width() - win.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + parent.winfo_height() // 4
    else:
        x = (win.winfo_screenwidth() - win.winfo_reqwidth()) // 2
        y = (win.winfo_screenheight() - win.winfo_reqheight()) // 3
    win.geometry(f"+{max(0, x)}+{max(0, y)}")


class _Window(tk.Toplevel):
    def __init__(self, parent, title: str):
        T = skin.T
        super().__init__(parent, bg=T.body)
        self.withdraw()
        self.title(title)
        if parent.winfo_viewable():  # a transient of a hidden (tray) window would stay hidden too
            self.transient(parent)
        self.resizable(False, False)
        skin.TitleBar(self, title).pack(fill="x")
        self.body = tk.Frame(self, bg=T.body, padx=10, pady=8)
        self.body.pack(fill="both", expand=True)


class EntryDialog(_Window):
    """Modal add/edit of a time entry. Result: dict(description, project, start, end)."""

    def __init__(self, parent, db: Database, entry: Entry | None = None, day: date | None = None):
        super().__init__(parent, "Izmeni unos" if entry else "Dodaj unos")
        self.entry = entry
        self.result = None
        b = self.body
        projects = db.project_names()
        if entry:
            start, end = entry.start_ts, entry.end_ts
        else:
            d = day or date.today()
            end = time.time() if d == date.today() else timeutil.to_ts(d, (17, 0))
            start = max(end - 3600, timeutil.day_start(d))  # last hour, but not before midnight
        self.desc = tk.StringVar(value=entry.description if entry else "")
        self.project = tk.StringVar(value=projects.get(entry.project_id, "") if entry else "")
        self.date = tk.StringVar(value=timeutil.fmt_date(start))
        self.start = tk.StringVar(value=timeutil.fmt_time(start))
        self.end = tk.StringVar(value=timeutil.fmt_time(end) if end else "")

        skin.label(b, "Zadatak").grid(row=0, column=0, columnspan=3, sticky="w")
        panel, e = skin.field(b, self.desc, 36)
        panel.grid(row=1, column=0, columnspan=3, sticky="we", pady=(1, 6))
        e.focus_set()
        skin.label(b, "Projekat").grid(row=2, column=0, columnspan=3, sticky="w")
        panel, cb = skin.combo(b, self.project, 34)
        cb.configure(values=list(projects.values()))
        panel.grid(row=3, column=0, columnspan=3, sticky="we", pady=(1, 6))
        skin.label(b, "Datum").grid(row=4, column=0, sticky="w")
        skin.label(b, "Od").grid(row=4, column=1, sticky="w", padx=(8, 0))
        skin.label(b, "Do").grid(row=4, column=2, sticky="w", padx=(8, 0))
        skin.field(b, self.date, 11)[0].grid(row=5, column=0, sticky="w")
        skin.field(b, self.start, 6)[0].grid(row=5, column=1, sticky="w", padx=(8, 0))
        panel, end_entry = skin.field(b, self.end, 6)
        panel.grid(row=5, column=2, sticky="w", padx=(8, 0))
        if entry and entry.running:
            end_entry.configure(state="disabled")

        bar = tk.Frame(b, bg=b["bg"])
        bar.grid(row=6, column=0, columnspan=3, sticky="e", pady=(10, 0))
        skin.SkinButton(bar, self.ok, text="OK", width=50).pack(side="left", padx=(0, 4))
        skin.SkinButton(bar, self.cancel, text="Otkaži", width=50).pack(side="left")
        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.cancel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)

    def show(self):
        _place(self, self.master)
        self.deiconify()
        self.grab_set()
        self.focus_force()
        self.wait_window()
        return self.result

    def ok(self):
        try:
            d = timeutil.parse_date(self.date.get())
            start = timeutil.to_ts(d, timeutil.parse_time(self.start.get()))
            end = None
            if not (self.entry and self.entry.running):
                end = timeutil.to_ts(d, timeutil.parse_time(self.end.get()))
                if end <= start:  # past midnight
                    end += 86400
        except ValueError as exc:
            messagebox.showerror("Greška", str(exc), parent=self)
            return
        if end is None and start > time.time():
            messagebox.showerror("Greška", "Početak ne može biti u budućnosti.", parent=self)
            return
        self.result = {"description": self.desc.get().strip(), "project": self.project.get().strip(),
                       "start": start, "end": end}
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


class IdleReminder(_Window):
    """Pops up as soon as the idle limit is reached and stays on top until answered.

    While the user is away it counts the idle time live; once they are back it
    freezes the interval. The answer is reported through on_choice(choice, reminder).
    """

    KEEP, DISCARD, DISCARD_STOP = "keep", "discard", "discard_stop"

    def __init__(self, parent, entry_id: int, idle_start: float, task: str, on_choice):
        super().__init__(parent, "Neaktivnost")
        T = skin.T
        self.entry_id = entry_id
        self.idle_start = idle_start
        self.idle_end: float | None = None
        self.task = task or "bez naziva"
        self.on_choice = on_choice
        self.attributes("-topmost", True)
        b = self.body
        panel = skin.Panel(b, pad=8)
        panel.pack(fill="x")
        self.headline = tk.Label(panel.inner, bg=T.lcd_bg, fg=T.lcd_on, font=T.font("mono", 14, "bold"),
                                 anchor="w")
        self.headline.pack(fill="x")
        self.detail = tk.Label(panel.inner, bg=T.lcd_bg, fg=T.lcd_text, font=T.font("sans", 9), anchor="w",
                               justify="left")
        self.detail.pack(fill="x")
        bar = tk.Frame(b, bg=b["bg"])
        bar.pack(fill="x", pady=(10, 0))
        skin.SkinButton(bar, lambda: self.choose(self.DISCARD), text="Odbaci",
                        tooltip="Izbaci to vreme, tajmer nastavlja").pack(side="left")
        skin.SkinButton(bar, lambda: self.choose(self.DISCARD_STOP), text="Odbaci i stani",
                        tooltip="Izbaci to vreme i zaustavi tajmer").pack(side="left", padx=4)
        skin.SkinButton(bar, lambda: self.choose(self.KEEP), text="Zadrži",
                        tooltip="Radio sam, zadrži vreme").pack(side="left")
        self.bind("<Return>", lambda e: self.choose(self.DISCARD))
        self.protocol("WM_DELETE_WINDOW", lambda: self.choose(self.KEEP))
        self._update()
        _place(self, parent)
        self.deiconify()
        self.lift()

    def user_back(self, idle_end: float) -> None:
        self.idle_end = idle_end
        self._update()
        self.lift()
        self.focus_force()

    def _update(self) -> None:
        if not self.winfo_exists():
            return
        T = skin.T
        start = timeutil.fmt_time(self.idle_start)
        if self.idle_end is None:
            secs = int(time.time() - self.idle_start)
            h, rem = divmod(secs, 3600)
            clock = f"{h}:{rem // 60:02d}:{rem % 60:02d}" if h else f"{rem // 60:02d}:{rem % 60:02d}"
            self.headline.configure(text=T.tx(f"Neaktivan {clock}"))
            self.detail.configure(text=f"Tajmer i dalje radi: {self.task}\nOd {start} nema tastature ni miša.")
            self.after(1000, self._update)
        else:
            self.headline.configure(text=T.tx(f"Neaktivan {timeutil.fmt_hours(self.idle_end - self.idle_start)}"))
            self.detail.configure(text=f"{start} - {timeutil.fmt_time(self.idle_end)}  ({self.task})\n"
                                       "Šta da radim sa tim vremenom?")

    def choose(self, choice: str) -> None:
        if self.idle_end is None:
            self.idle_end = time.time()
        self.destroy()
        self.on_choice(choice, self)


class ProductivityDialog(_Window):
    """Small dashboard behind the productivity meter: time per category and its top items."""

    def __init__(self, parent, summary, day_title: str):
        super().__init__(parent, "Produktivnost")
        from ..productivity import DISTRACTING, NEUTRAL, PRODUCTIVE

        T = skin.T
        b = self.body
        skin.label(b, day_title, fg=T.accent).pack(anchor="w")
        panel = skin.Panel(b, pad=8)
        panel.pack(fill="x", pady=(4, 0))
        total = summary.total
        rows = ((PRODUCTIVE, "Produktivno", T.lcd_on), (DISTRACTING, "Ometanje", T.accent),
                (NEUTRAL, "Ostalo", T.lcd_dim))
        for category, title, color in rows:
            secs = summary.seconds[category]
            share = f"{secs / total:.0%}" if total else "-"
            tk.Label(panel.inner, text=T.tx(f"{title}  {timeutil.fmt_hours(secs)}  ({share})"), bg=T.lcd_bg,
                     fg=color, font=T.font("mono", 10, "bold"), anchor="w").pack(fill="x", pady=(6, 0))
            top = summary.labels.get(category, [])[:5]
            text = "\n".join(f"  {label:<18} {timeutil.fmt_hours(s):>7}" for label, s in top) or "  -"
            tk.Label(panel.inner, text=text, bg=T.lcd_bg, fg=T.lcd_text, font=T.font("mono", 9), anchor="w",
                     justify="left").pack(fill="x")
        bar = tk.Frame(b, bg=b["bg"])
        bar.pack(fill="x", pady=(8, 0))
        skin.SkinButton(bar, self.destroy, text="Zatvori").pack(side="right")
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self.destroy())
        _place(self, parent)
        self.deiconify()


class MiniBar(tk.Toplevel):
    """Winamp-style "windowshade": a slim, half see-through strip above the taskbar while minimized.

    Shows the state, time and task with play/pause; hovering makes it opaque, clicking it restores the
    main window.
    """

    def __init__(self, parent, on_restore, on_play_pause):
        T = skin.T
        super().__init__(parent, bg=T.body_dark)
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.on_restore = on_restore
        panel = tk.Frame(self, bg=T.lcd_bg, padx=skin.px(8), pady=skin.px(3))
        panel.pack(padx=1, pady=1)
        self.icon = tk.Canvas(panel, width=skin.px(10), height=skin.px(10), bg=T.lcd_bg, highlightthickness=0)
        self.icon.pack(side="left", padx=(0, skin.px(6)))
        self.time = tk.Label(panel, text="--:--:--", bg=T.lcd_bg, fg=T.lcd_on, font=T.font("mono", 12, "bold"))
        self.time.pack(side="left")
        self.task = tk.Label(panel, text="", bg=T.lcd_bg, fg=T.lcd_text, font=T.font("sans", 9), width=18,
                             anchor="w")
        self.task.pack(side="left", padx=(skin.px(8), skin.px(6)))
        self.play = skin.SkinButton(panel, on_play_pause, glyph="play", width=20, height=16, tooltip="Start / pauza")
        self.play.configure(bg=T.lcd_bg)
        self.play.pack(side="left")
        restore = tk.Label(panel, text="▴", bg=T.lcd_bg, fg=T.lcd_text, font=T.font("sans", 11, "bold"),
                           cursor="hand2", padx=skin.px(6))
        restore.pack(side="left")
        for w in (self, panel, self.time, self.task, self.icon, restore):
            w.bind("<Button-1>", lambda e: self.on_restore())
        self._corner: tuple[int, int] | None = None
        self.bind("<Enter>", lambda e: self._alpha(1.0))
        self.bind("<Leave>", lambda e: self._alpha(0.72))
        self._alpha(0.72)

    def _alpha(self, value: float) -> None:
        try:
            self.attributes("-alpha", value)
        except tk.TclError:  # window managers without transparency
            pass

    def show(self, work_area=None) -> None:
        if work_area:
            _left, _top, right, bottom = work_area
        else:
            right, bottom = self.winfo_screenwidth(), self.winfo_screenheight() - skin.px(48)
        self._corner = (right - skin.px(12), bottom - skin.px(8))
        self._place()
        self.deiconify()
        self.lift()

    def _place(self) -> None:
        """Keep the bottom-right corner fixed, whatever the current size."""
        if self._corner is None:
            return
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"+{self._corner[0] - w}+{self._corner[1] - h}")

    def update_view(self, state: str, clock: str, task: str) -> None:
        T = skin.T
        width = self.winfo_reqwidth()
        if self.time.cget("text") != clock:
            self.time.configure(text=clock, fg=T.lcd_on if state == "playing" else T.lcd_dim)
        if self.task.cget("text") != task:
            self.task.configure(text=task)
        self.update_idletasks()
        if self.winfo_reqwidth() != width:
            self._place()
        c, s = self.icon, skin.px(10)
        c.delete("all")
        if state == "playing":
            c.create_polygon(1, 1, 1, s - 1, s - 1, s / 2, fill=T.lcd_on)
        elif state == "paused":
            c.create_rectangle(1, 1, s * 0.4, s - 1, fill=T.lcd_on, width=0)
            c.create_rectangle(s * 0.6, 1, s - 1, s - 1, fill=T.lcd_on, width=0)
        else:
            c.create_rectangle(1, 1, s - 1, s - 1, fill=T.lcd_dim, width=0)
