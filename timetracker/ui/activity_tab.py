"""Per-day app and window usage (Time Doctor style) plus screenshots."""

from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import messagebox, ttk

from .. import platform_win, reports, timeutil
from .common import ACCENT, GRID, SURFACE, scrolled_tree


class ActivityTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.day = date.today()
        self.only_tracked = tk.BooleanVar(value=False)

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Button(bar, text="◀", width=3, command=lambda: self.shift(-1)).pack(side="left")
        self.day_label = ttk.Label(bar, text="", style="Title.TLabel", width=24, anchor="center")
        self.day_label.pack(side="left", padx=6)
        ttk.Button(bar, text="▶", width=3, command=lambda: self.shift(1)).pack(side="left")
        ttk.Button(bar, text="Danas", command=self.go_today).pack(side="left", padx=(8, 0))
        ttk.Checkbutton(bar, text="Samo vreme dok radi tajmer", variable=self.only_tracked,
                        command=self.refresh).pack(side="left", padx=(16, 0))
        ttk.Button(bar, text="Screenshotovi…", command=self.open_screenshots).pack(side="right")

        self.summary = ttk.Label(self, text="", style="Muted.TLabel")
        self.summary.pack(anchor="w")
        self.coverage = tk.Canvas(self, height=10, background=SURFACE, highlightthickness=0)
        self.coverage.pack(fill="x", pady=(4, 10))
        self.coverage.bind("<Configure>", lambda e: self._draw_coverage())
        self._coverage_ratio = 0.0

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=1)
        panes.add(right, weight=2)

        ttk.Label(left, text="Aplikacije", style="Title.TLabel").pack(anchor="w")
        f, self.apps = scrolled_tree(left, ("time", "pct"), show="headings", selectmode="browse")
        f.pack(fill="both", expand=True, pady=(4, 0))
        self.apps["columns"] = ("app", "time", "pct")
        for col, text, width, anchor in (("app", "Aplikacija", 160, "w"), ("time", "Vreme", 70, "e"),
                                         ("pct", "%", 50, "e")):
            self.apps.heading(col, text=text, anchor=anchor)
            self.apps.column(col, width=width, anchor=anchor, stretch=(col == "app"))
        self.apps.bind("<<TreeviewSelect>>", lambda e: self._fill_titles())

        ttk.Label(right, text="Prozori / dokumenti / sajtovi", style="Title.TLabel").pack(anchor="w",
                                                                                      padx=(10, 0))
        f, self.titles = scrolled_tree(right, ("app", "time"), show="headings")
        f.pack(fill="both", expand=True, pady=(4, 0), padx=(10, 0))
        self.titles["columns"] = ("title", "app", "time")
        for col, text, width, anchor in (("title", "Naslov prozora", 380, "w"), ("app", "Aplikacija", 110, "w"),
                                         ("time", "Vreme", 70, "e")):
            self.titles.heading(col, text=text, anchor=anchor)
            self.titles.column(col, width=width, anchor=anchor, stretch=(col == "title"))

        self.hint = ttk.Label(self, text="", style="Muted.TLabel")
        self.hint.pack(anchor="w", pady=(6, 0))

    def shift(self, days: int):
        self.day += timedelta(days=days)
        self.refresh()

    def go_today(self):
        self.day = date.today()
        self.refresh()

    def refresh(self) -> None:
        self.day_label.configure(text=timeutil.fmt_day_header(self.day))
        a, b = timeutil.day_bounds(self.day)
        active, tracked = reports.tracked_vs_active(self.app.db, a, b)
        self._coverage_ratio = tracked / active if active else 0.0
        if active:
            self.summary.configure(
                text=f"Aktivno za računarom: {timeutil.fmt_hours(active)}   •   pokriveno tajmerom: "
                     f"{timeutil.fmt_hours(tracked)} ({self._coverage_ratio:.0%})")
        else:
            self.summary.configure(text="Nema zabeležene aktivnosti za ovaj dan.")
        self._draw_coverage()

        usage = reports.app_usage(self.app.db, a, b, only_tracked=self.only_tracked.get())
        total = sum(s for _, s in usage) or 1
        self.apps.delete(*self.apps.get_children())
        for name, secs in usage:
            self.apps.insert("", "end", iid=name, values=(name, timeutil.fmt_hours(secs), f"{secs / total:.0%}"))
        self._fill_titles()

        mode = self.app.settings["activity_mode"]
        if mode == "off":
            self.hint.configure(text="Praćenje aplikacija je isključeno (Podešavanja).")
        elif mode == "timer":
            self.hint.configure(text="Aplikacije se beleže samo dok radi tajmer. "
                                     "U Podešavanjima možeš uključiti stalno praćenje.")
        else:
            self.hint.configure(text="Aplikacije se beleže uvek kad si aktivan (sve ostaje lokalno na ovom računaru).")

    def _fill_titles(self):
        a, b = timeutil.day_bounds(self.day)
        sel = self.apps.selection()
        app = sel[0] if sel else None
        self.titles.delete(*self.titles.get_children())
        for name, title, secs in reports.title_usage(self.app.db, a, b, app=app, limit=300):
            self.titles.insert("", "end", values=(title, name, timeutil.fmt_hours(secs)))

    def _draw_coverage(self):
        c = self.coverage
        c.delete("all")
        w = c.winfo_width()
        c.create_rectangle(0, 0, w, 10, fill=GRID, width=0)
        if self._coverage_ratio:
            c.create_rectangle(0, 0, w * self._coverage_ratio, 10, fill=ACCENT, width=0)

    def open_screenshots(self):
        a, b = timeutil.day_bounds(self.day)
        shots = self.app.db.screenshots_between(a, b)
        if not shots:
            msg = "Nema screenshotova za ovaj dan."
            if not self.app.settings["screenshots"]:
                msg += "\n\nScreenshotovi su isključeni (Podešavanja)."
            messagebox.showinfo("Screenshotovi", msg, parent=self)
            return
        folder = Path(shots[0].path).parent
        try:
            platform_win.open_path(folder)
        except OSError as exc:
            messagebox.showerror("Greška", str(exc), parent=self)
