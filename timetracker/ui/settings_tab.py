"""Settings form."""

from __future__ import annotations

import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from .. import APP_ID, platform_win

ACTIVITY_MODES = [("Isključeno", "off"), ("Samo dok radi tajmer", "timer"), ("Uvek kad sam aktivan", "always")]


class SettingsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=14)
        self.app = app
        s = app.settings
        self.vars = {
            "idle_detection": tk.BooleanVar(value=s["idle_detection"]),
            "idle_minutes": tk.IntVar(value=s["idle_minutes"]),
            "activity_mode": tk.StringVar(value=s["activity_mode"]),
            "screenshots": tk.BooleanVar(value=s["screenshots"]),
            "screenshot_interval_min": tk.IntVar(value=s["screenshot_interval_min"]),
            "screenshot_retention_days": tk.IntVar(value=s["screenshot_retention_days"]),
            "reminder_minutes": tk.IntVar(value=s["reminder_minutes"]),
            "long_timer_hours": tk.IntVar(value=s["long_timer_hours"]),
            "daily_goal_hours": tk.IntVar(value=s["daily_goal_hours"]),
            "minimize_to_tray": tk.BooleanVar(value=s["minimize_to_tray"]),
            "start_minimized": tk.BooleanVar(value=s["start_minimized"]),
            "autostart": tk.BooleanVar(value=platform_win.is_autostart_enabled(APP_ID) or s["autostart"]),
            "currency": tk.StringVar(value=s["currency"]),
        }
        v = self.vars
        cols = ttk.Frame(self)
        cols.pack(fill="both", expand=True)
        cols.columnconfigure(0, weight=1, uniform="c")
        cols.columnconfigure(1, weight=1, uniform="c")
        left = ttk.Frame(cols)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right = ttk.Frame(cols)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        idle = ttk.LabelFrame(left, text="Neaktivnost", padding=10)
        idle.pack(fill="x")
        ttk.Checkbutton(idle, text="Pitaj šta da radim sa vremenom bez tastature/miša",
                        variable=v["idle_detection"]).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(idle, text="Neaktivan posle").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Spinbox(idle, from_=1, to=120, width=5, textvariable=v["idle_minutes"]).grid(row=1, column=1, padx=6,
                                                                                      pady=(4, 0))
        ttk.Label(idle, text="min").grid(row=1, column=2, sticky="w", pady=(4, 0))
        ttk.Label(idle, text="Zatvaranje laptopa (sleep) se takođe prepoznaje.",
                  style="Muted.TLabel").grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))

        act = ttk.LabelFrame(left, text="Praćenje aplikacija i prozora", padding=10)
        act.pack(fill="x", pady=(10, 0))
        for i, (label, value) in enumerate(ACTIVITY_MODES):
            ttk.Radiobutton(act, text=label, value=value, variable=v["activity_mode"]).grid(row=i, column=0,
                                                                                         sticky="w")

        shots = ttk.LabelFrame(left, text="Screenshotovi (lokalno, samo dok radi tajmer)", padding=10)
        shots.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(shots, text="Pravi screenshotove", variable=v["screenshots"]).grid(row=0, column=0,
                                                                                        columnspan=3, sticky="w")
        ttk.Label(shots, text="Svakih").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Spinbox(shots, from_=1, to=120, width=5, textvariable=v["screenshot_interval_min"]).grid(
            row=1, column=1, padx=6, pady=(4, 0))
        ttk.Label(shots, text="min").grid(row=1, column=2, sticky="w", pady=(4, 0))
        ttk.Label(shots, text="Čuvaj").grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Spinbox(shots, from_=1, to=365, width=5, textvariable=v["screenshot_retention_days"]).grid(
            row=2, column=1, padx=6, pady=(4, 0))
        ttk.Label(shots, text="dana").grid(row=2, column=2, sticky="w", pady=(4, 0))

        rem = ttk.LabelFrame(right, text="Podsetnici i ciljevi", padding=10)
        rem.pack(fill="x", pady=(10, 0))
        rows = (("Podsetnik za tajmer posle (min rada)", "reminder_minutes", 240),
                ("Upozori ako tajmer radi duže od (h)", "long_timer_hours", 24),
                ("Dnevni cilj (h)", "daily_goal_hours", 24))
        for i, (label, key, maximum) in enumerate(rows):
            ttk.Label(rem, text=label).grid(row=i, column=0, sticky="w", pady=2)
            ttk.Spinbox(rem, from_=0, to=maximum, width=5, textvariable=v[key]).grid(row=i, column=1, padx=6)
        ttk.Label(rem, text="0 = isključeno", style="Muted.TLabel").grid(row=len(rows), column=0, sticky="w")

        gen = ttk.LabelFrame(right, text="Opšte", padding=10)
        gen.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(gen, text="Pokreni sa Windows-om", variable=v["autostart"]).grid(row=0, column=0,
                                                                                       sticky="w")
        ttk.Checkbutton(gen, text="Zatvaranje prozora sklanja aplikaciju u tray",
                        variable=v["minimize_to_tray"]).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(gen, text="Pokreni minimizovano", variable=v["start_minimized"]).grid(row=2, column=0,
                                                                                            sticky="w")
        cur = ttk.Frame(gen)
        cur.grid(row=3, column=0, sticky="w", pady=(4, 0))
        ttk.Label(cur, text="Valuta").pack(side="left")
        ttk.Combobox(cur, textvariable=v["currency"], values=["EUR", "RSD", "USD", "CHF", "GBP"],
                     width=6).pack(side="left", padx=6)
        if not app.tray_available:
            ttk.Label(gen, text="Tray ikonica nije dostupna (instaliraj pystray i Pillow).",
                      style="Muted.TLabel").grid(row=4, column=0, sticky="w")

        data = ttk.LabelFrame(right, text="Podaci", padding=10)
        data.pack(fill="x", pady=(10, 0))
        ttk.Label(data, text=str(app.data_dir), style="Muted.TLabel", wraplength=420).grid(
            row=0, column=0, columnspan=3, sticky="w")
        ttk.Button(data, text="Otvori folder", command=lambda: platform_win.open_path(app.data_dir)).grid(
            row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Button(data, text="Napravi rezervnu kopiju…", command=self.backup).grid(row=1, column=1, sticky="w",
                                                                                   padx=6, pady=(6, 0))

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(14, 0))
        ttk.Button(bar, text="Sačuvaj podešavanja", style="Accent.TButton", command=self.save).pack(side="left")
        self.status = ttk.Label(bar, text="", style="Muted.TLabel")
        self.status.pack(side="left", padx=10)

    def save(self):
        values = {}
        try:
            for key, var in self.vars.items():
                values[key] = var.get()
        except tk.TclError:
            messagebox.showerror("Greška", "Proveri brojeve u podešavanjima.", parent=self)
            return
        values["currency"] = values["currency"].strip().upper()[:5] or "EUR"
        for key in ("idle_minutes", "screenshot_interval_min", "screenshot_retention_days"):
            values[key] = max(1, values[key])
        for key in ("reminder_minutes", "long_timer_hours", "daily_goal_hours"):
            values[key] = max(0, values[key])
        if values["autostart"] != platform_win.is_autostart_enabled(APP_ID):
            if not platform_win.set_autostart(APP_ID, values["autostart"]) and platform_win.IS_WINDOWS:
                messagebox.showwarning("Autostart", "Nisam uspeo da podesim pokretanje sa Windows-om.", parent=self)
        self.app.settings.update(values)
        self.status.configure(text=f"Sačuvano u {datetime.now():%H:%M:%S}")
        self.app.refresh_all()

    def backup(self):
        name = f"timetracker-backup-{datetime.now():%Y-%m-%d}.db"
        path = filedialog.asksaveasfilename(parent=self, title="Rezervna kopija", initialfile=name,
                                            defaultextension=".db", filetypes=[("SQLite baza", "*.db")])
        if not path:
            return
        try:
            self.app.db.backup(path)
        except (OSError, sqlite3.Error) as exc:
            messagebox.showerror("Greška", str(exc), parent=self)
            return
        messagebox.showinfo("Rezervna kopija", f"Sačuvano:\n{path}", parent=self)

