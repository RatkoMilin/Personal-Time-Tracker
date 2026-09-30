"""Skinned dialogs: edit/add an entry and the idle prompt."""

from __future__ import annotations

import time
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from .. import timeutil
from ..db import Database, Entry
from . import skin


class _Dialog(tk.Toplevel):
    def __init__(self, parent, title: str):
        super().__init__(parent, bg=skin.BODY)
        self.withdraw()
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.result = None
        skin.TitleBar(self, title.upper()).pack(fill="x")
        self.body = tk.Frame(self, bg=skin.BODY, padx=10, pady=8)
        self.body.pack(fill="both", expand=True)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda e: self.cancel())

    def show(self):
        self.update_idletasks()
        parent = self.master
        if parent.winfo_viewable():
            x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
            y = parent.winfo_rooty() + parent.winfo_height() // 4
        else:
            x = (self.winfo_screenwidth() - self.winfo_reqwidth()) // 2
            y = (self.winfo_screenheight() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.deiconify()
        self.grab_set()
        self.focus_force()
        self.wait_window()
        return self.result

    def cancel(self):
        self.result = None
        self.destroy()


class EntryDialog(_Dialog):
    """Add or edit a time entry. Result: dict(description, project, start, end)."""

    def __init__(self, parent, db: Database, entry: Entry | None = None, day: date | None = None):
        super().__init__(parent, "Izmeni unos" if entry else "Dodaj unos")
        self.entry = entry
        b = self.body
        projects = db.project_names()
        if entry:
            start, end = entry.start_ts, entry.end_ts
        else:
            d = day or date.today()
            end = time.time() if d == date.today() else timeutil.to_ts(d, (17, 0))
            start = end - 3600
        self.desc = tk.StringVar(value=entry.description if entry else "")
        self.project = tk.StringVar(value=projects.get(entry.project_id, "") if entry else "")
        self.date = tk.StringVar(value=timeutil.fmt_date(start))
        self.start = tk.StringVar(value=timeutil.fmt_time(start))
        self.end = tk.StringVar(value=timeutil.fmt_time(end) if end else "")

        skin.label(b, "ZADATAK").grid(row=0, column=0, columnspan=3, sticky="w")
        e = skin.lcd_entry(b, self.desc, 36)
        e.grid(row=1, column=0, columnspan=3, sticky="we", pady=(1, 6))
        e.focus_set()
        skin.label(b, "PROJEKAT").grid(row=2, column=0, columnspan=3, sticky="w")
        ttk.Combobox(b, textvariable=self.project, values=list(projects.values()), style="Skin.TCombobox",
                     font=(skin.MONO, 10)).grid(row=3, column=0, columnspan=3, sticky="we", pady=(1, 6))
        skin.label(b, "DATUM").grid(row=4, column=0, sticky="w")
        skin.label(b, "OD").grid(row=4, column=1, sticky="w", padx=(8, 0))
        skin.label(b, "DO").grid(row=4, column=2, sticky="w", padx=(8, 0))
        skin.lcd_entry(b, self.date, 11).grid(row=5, column=0, sticky="w")
        skin.lcd_entry(b, self.start, 6).grid(row=5, column=1, sticky="w", padx=(8, 0))
        end_entry = skin.lcd_entry(b, self.end, 6)
        end_entry.grid(row=5, column=2, sticky="w", padx=(8, 0))
        if entry and entry.running:
            end_entry.configure(state="disabled", disabledbackground=skin.LCD_BG)

        bar = tk.Frame(b, bg=skin.BODY)
        bar.grid(row=6, column=0, columnspan=3, sticky="e", pady=(10, 0))
        skin.SkinButton(bar, self.ok, text="OK", width=50).pack(side="left", padx=(0, 4))
        skin.SkinButton(bar, self.cancel, text="OTKAŽI", width=50).pack(side="left")
        self.bind("<Return>", lambda e: self.ok())

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


class IdleDialog(_Dialog):
    """What to do with time during which there was no keyboard/mouse input."""

    KEEP, DISCARD, DISCARD_STOP = "keep", "discard", "discard_stop"

    def __init__(self, parent, idle_start: float, idle_end: float):
        super().__init__(parent, "Neaktivnost")
        self.attributes("-topmost", True)
        b = self.body
        well, lcd = skin.sunken(b, padx=10, pady=6)
        well.pack(fill="x")
        tk.Label(lcd, text=f"NEAKTIVAN {timeutil.fmt_hours(idle_end - idle_start).upper()}", bg=skin.LCD_BG,
                 fg=skin.LCD_ON, font=(skin.MONO, 12, "bold")).pack(anchor="w")
        tk.Label(lcd, text=f"{timeutil.fmt_time(idle_start)} - {timeutil.fmt_time(idle_end)}", bg=skin.LCD_BG,
                 fg=skin.LCD_DIM, font=(skin.MONO, 10)).pack(anchor="w")
        bar = tk.Frame(b, bg=skin.BODY)
        bar.pack(fill="x", pady=(10, 0))
        skin.SkinButton(bar, lambda: self._done(self.DISCARD), text="ODBACI",
                        tooltip="Izbaci to vreme, tajmer nastavlja").pack(side="left")
        skin.SkinButton(bar, lambda: self._done(self.DISCARD_STOP), text="ODBACI I STANI",
                        tooltip="Izbaci to vreme i zaustavi tajmer").pack(side="left", padx=4)
        skin.SkinButton(bar, lambda: self._done(self.KEEP), text="ZADRŽI",
                        tooltip="Radio sam, zadrži vreme").pack(side="left")
        self.bind("<Return>", lambda e: self._done(self.DISCARD))

    def _done(self, choice: str):
        self.result = choice
        self.destroy()

    def cancel(self):
        self._done(self.KEEP)
