"""Modal dialogs and notification popups."""

from __future__ import annotations

import time
import tkinter as tk
from datetime import date
from tkinter import colorchooser, messagebox, ttk

from .. import timeutil
from ..db import Database, Entry, Project
from .common import FONT, PROJECT_COLORS, SURFACE, TEXT_MUTED, center_on_parent

NO_PROJECT_LABEL = "(bez projekta)"


class _Dialog(tk.Toplevel):
    def __init__(self, parent, title: str):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.result = None
        self.body = ttk.Frame(self, padding=16)
        self.body.pack(fill="both", expand=True)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda e: self.cancel())

    def show(self):
        center_on_parent(self, self.master)
        self.deiconify()
        self.grab_set()
        self.focus_force()
        self.wait_window()
        return self.result

    def buttons(self, row: int, ok_text: str = "Sačuvaj") -> None:
        bar = ttk.Frame(self.body)
        bar.grid(row=row, column=0, columnspan=4, sticky="e", pady=(14, 0))
        ttk.Button(bar, text="Otkaži", command=self.cancel).pack(side="right")
        ttk.Button(bar, text=ok_text, style="Accent.TButton", command=self.ok).pack(side="right", padx=(0, 8))
        self.bind("<Return>", lambda e: self.ok())

    def ok(self):
        raise NotImplementedError

    def cancel(self):
        self.result = None
        self.destroy()


def project_choices(db: Database, include_id: int | None = None) -> list[tuple[str, int | None]]:
    """(label, id) pairs for a project combobox, keeping an archived project if it is selected."""
    choices: list[tuple[str, int | None]] = [(NO_PROJECT_LABEL, None)]
    for p in db.list_projects(include_archived=True):
        if not p.archived or p.id == include_id:
            choices.append((p.name + (" (arhiviran)" if p.archived else ""), p.id))
    return choices


class EntryDialog(_Dialog):
    """Add or edit a time entry."""

    def __init__(self, parent, db: Database, entry: Entry | None = None, day: date | None = None):
        super().__init__(parent, "Izmeni unos" if entry else "Dodaj vreme ručno")
        self.db = db
        self.entry = entry
        b = self.body
        self.choices = project_choices(db, entry.project_id if entry else None)

        now = time.time()
        if entry:
            start = entry.start_ts
            end = entry.end_ts
        else:
            d = day or date.today()
            end_default = now if d == date.today() else timeutil.to_ts(d, (17, 0))
            start = end_default - 3600
            end = end_default
            if d != date.today():
                start = timeutil.to_ts(d, (16, 0))

        self.desc = tk.StringVar(value=entry.description if entry else "")
        self.project = tk.StringVar()
        self.date = tk.StringVar(value=timeutil.fmt_date(start))
        self.start = tk.StringVar(value=timeutil.fmt_time(start))
        self.end = tk.StringVar(value=timeutil.fmt_time(end) if end else "")
        self.duration = tk.StringVar()
        self.billable = tk.BooleanVar(value=entry.billable if entry else False)

        ttk.Label(b, text="Opis").grid(row=0, column=0, sticky="w")
        e = ttk.Entry(b, textvariable=self.desc, width=44)
        e.grid(row=1, column=0, columnspan=4, sticky="we", pady=(2, 10))
        e.focus_set()

        ttk.Label(b, text="Projekat").grid(row=2, column=0, sticky="w")
        cb = ttk.Combobox(b, textvariable=self.project, state="readonly", values=[c[0] for c in self.choices])
        cb.grid(row=3, column=0, columnspan=4, sticky="we", pady=(2, 10))
        current = entry.project_id if entry else None
        for label, pid in self.choices:
            if pid == current:
                self.project.set(label)

        ttk.Label(b, text="Datum (dd.mm.gggg)").grid(row=4, column=0, sticky="w")
        ttk.Label(b, text="Od").grid(row=4, column=1, sticky="w", padx=(10, 0))
        ttk.Label(b, text="Do").grid(row=4, column=2, sticky="w", padx=(10, 0))
        ttk.Label(b, text="Trajanje").grid(row=4, column=3, sticky="w", padx=(10, 0))
        ttk.Entry(b, textvariable=self.date, width=12).grid(row=5, column=0, sticky="w")
        ttk.Entry(b, textvariable=self.start, width=7).grid(row=5, column=1, sticky="w", padx=(10, 0))
        end_entry = ttk.Entry(b, textvariable=self.end, width=7)
        end_entry.grid(row=5, column=2, sticky="w", padx=(10, 0))
        self.dur_entry = dur_entry = ttk.Entry(b, textvariable=self.duration, width=9)
        dur_entry.grid(row=5, column=3, sticky="w", padx=(10, 0))
        if entry and entry.running:
            end_entry.configure(state="disabled")
            dur_entry.configure(state="disabled")
            ttk.Label(b, text="Tajmer je u toku: menja se samo početak.", style="Muted.TLabel").grid(
                row=6, column=0, columnspan=4, sticky="w", pady=(4, 0))
        else:
            ttk.Label(b, text="Kraj posle ponoći ide na sledeći dan. Trajanje (npr. 1:30) menja kraj.",
                      style="Muted.TLabel").grid(row=6, column=0, columnspan=4, sticky="w", pady=(4, 0))
        self._sync_duration()
        self.start.trace_add("write", lambda *a: self._sync_duration())
        self.end.trace_add("write", lambda *a: self._sync_duration())
        dur_entry.bind("<FocusOut>", lambda e: self._apply_duration())

        ttk.Checkbutton(b, text="Naplativo", variable=self.billable).grid(row=7, column=0, sticky="w",
                                                                         pady=(10, 0))
        self.buttons(8)

    def _times(self) -> tuple[float, float | None]:
        d = timeutil.parse_date(self.date.get())
        start = timeutil.to_ts(d, timeutil.parse_time(self.start.get()))
        if self.entry and self.entry.running:
            return start, None
        end = timeutil.to_ts(d, timeutil.parse_time(self.end.get()))
        if end <= start:
            end += 86400
        return start, end

    def _sync_duration(self):
        try:
            start, end = self._times()
        except ValueError:
            return
        if end is not None:
            self.duration.set(timeutil.fmt_clock(end - start)[:-3])

    def _apply_duration(self):
        try:
            secs = timeutil.parse_duration(self.duration.get())
            d = timeutil.parse_date(self.date.get())
            start = timeutil.to_ts(d, timeutil.parse_time(self.start.get()))
        except ValueError:
            return
        if secs > 0:
            self.end.set(timeutil.fmt_time(start + secs))

    def ok(self):
        if self.focus_get() is self.dur_entry:
            self._apply_duration()
        try:
            start, end = self._times()
        except ValueError as exc:
            messagebox.showerror("Greška", str(exc), parent=self)
            return
        if end is None and start > time.time():
            messagebox.showerror("Greška", "Početak tajmera ne može biti u budućnosti.", parent=self)
            return
        project_id = dict(self.choices).get(self.project.get())
        self.result = {
            "description": self.desc.get().strip(),
            "project_id": project_id,
            "start": start,
            "end": end,
            "billable": self.billable.get(),
        }
        self.destroy()


class ProjectDialog(_Dialog):
    def __init__(self, parent, project: Project | None = None, default_color: str = PROJECT_COLORS[0],
                 currency: str = "EUR"):
        super().__init__(parent, "Izmeni projekat" if project else "Novi projekat")
        b = self.body
        self.name = tk.StringVar(value=project.name if project else "")
        self.rate = tk.StringVar(value=f"{project.hourly_rate:g}" if project else "0")
        self.color = project.color if project else default_color

        ttk.Label(b, text="Naziv").grid(row=0, column=0, sticky="w")
        e = ttk.Entry(b, textvariable=self.name, width=36)
        e.grid(row=1, column=0, columnspan=2, sticky="we", pady=(2, 10))
        e.focus_set()

        ttk.Label(b, text=f"Satnica ({currency}/h, 0 = bez)").grid(row=2, column=0, sticky="w")
        ttk.Entry(b, textvariable=self.rate, width=10).grid(row=3, column=0, sticky="w", pady=(2, 10))

        ttk.Label(b, text="Boja").grid(row=4, column=0, sticky="w")
        swatches = ttk.Frame(b)
        swatches.grid(row=5, column=0, columnspan=2, sticky="w", pady=(2, 0))
        self.preview = tk.Label(swatches, width=3, bg=self.color, relief="solid", bd=1)
        self.preview.pack(side="left", padx=(0, 10))
        for c in PROJECT_COLORS:
            sw = tk.Label(swatches, width=2, bg=c, cursor="hand2")
            sw.pack(side="left", padx=2)
            sw.bind("<Button-1>", lambda ev, c=c: self._set_color(c))
        ttk.Button(swatches, text="Druga...", command=self._pick).pack(side="left", padx=(8, 0))
        self.buttons(6)

    def _set_color(self, c: str):
        self.color = c
        self.preview.configure(bg=c)

    def _pick(self):
        _, hexcolor = colorchooser.askcolor(self.color, parent=self)
        if hexcolor:
            self._set_color(hexcolor)

    def ok(self):
        name = self.name.get().strip()
        if not name:
            messagebox.showerror("Greška", "Unesi naziv projekta.", parent=self)
            return
        try:
            rate = float(self.rate.get().replace(",", ".") or 0)
            if rate < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Greška", "Satnica mora biti broj (npr. 25 ili 12,5).", parent=self)
            return
        self.result = {"name": name, "color": self.color, "hourly_rate": rate}
        self.destroy()


class IdleDialog(_Dialog):
    """Ask what to do with time during which there was no keyboard/mouse input."""

    KEEP, DISCARD_CONTINUE, DISCARD_STOP = "keep", "discard_continue", "discard_stop"

    def __init__(self, parent, idle_start: float, idle_end: float, description: str):
        super().__init__(parent, "Bio si neaktivan")
        self.attributes("-topmost", True)
        b = self.body
        minutes = (idle_end - idle_start) / 60
        ttk.Label(b, text=f"Nije bilo aktivnosti {timeutil.fmt_hours(idle_end - idle_start)}",
                  style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(b, text=f"od {timeutil.fmt_time(idle_start)} do {timeutil.fmt_time(idle_end)}"
                          + (f"  •  {description}" if description else ""),
                  style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 12))
        ttk.Label(b, text="Šta da radim sa tim vremenom?").grid(row=2, column=0, sticky="w")
        bar = ttk.Frame(b)
        bar.grid(row=3, column=0, sticky="we", pady=(10, 0))
        ttk.Button(bar, text="Odbaci i nastavi", style="Accent.TButton",
                   command=lambda: self._done(self.DISCARD_CONTINUE)).pack(side="left")
        ttk.Button(bar, text="Odbaci i zaustavi",
                   command=lambda: self._done(self.DISCARD_STOP)).pack(side="left", padx=8)
        ttk.Button(bar, text="Zadrži (radio sam)", command=lambda: self._done(self.KEEP)).pack(side="left")
        self.minutes = minutes
        self.bind("<Return>", lambda e: self._done(self.DISCARD_CONTINUE))

    def _done(self, choice: str):
        self.result = choice
        self.destroy()

    def cancel(self):
        self.result = self.KEEP
        self.destroy()


class Toast(tk.Toplevel):
    """Non-blocking notification in the bottom-right corner with an optional action."""

    def __init__(self, parent, title: str, message: str, action_text: str | None = None,
                 action=None, timeout_ms: int = 15000):
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#c9c8c3")
        inner = tk.Frame(self, bg=SURFACE, padx=14, pady=12)
        inner.pack(padx=1, pady=1)
        tk.Label(inner, text=title, bg=SURFACE, font=(FONT, 11, "bold"), anchor="w").pack(fill="x")
        tk.Label(inner, text=message, bg=SURFACE, fg=TEXT_MUTED, font=(FONT, 10), justify="left",
                 wraplength=300, anchor="w").pack(fill="x", pady=(4, 10))
        bar = tk.Frame(inner, bg=SURFACE)
        bar.pack(fill="x")
        ttk.Button(bar, text="Zatvori", command=self.destroy).pack(side="right")
        if action_text and action:
            def run():
                self.destroy()
                action()
            ttk.Button(bar, text=action_text, style="Accent.TButton", command=run).pack(side="right", padx=(0, 8))
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = self.winfo_screenwidth() - w - 24
        y = self.winfo_screenheight() - h - 72  # stay above the taskbar
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.after(timeout_ms, self._expire)

    def _expire(self):
        if self.winfo_exists():
            self.destroy()
