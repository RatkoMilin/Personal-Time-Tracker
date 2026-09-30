"""Reports: totals, per-day chart, per-project breakdown and CSV export."""

from __future__ import annotations

import time
import tkinter as tk
from collections import OrderedDict
from datetime import date, timedelta
from tkinter import filedialog, messagebox, ttk

from .. import reports, timeutil
from .common import ACCENT, FONT, GRID, SURFACE, TEXT, TEXT_MUTED, Tooltip, color_square, scrolled_tree

PERIODS = OrderedDict([
    ("Danas", "today"), ("Juče", "yesterday"), ("Ova nedelja", "this_week"), ("Prošla nedelja", "last_week"),
    ("Ovaj mesec", "this_month"), ("Prošli mesec", "last_month"), ("Ova godina", "this_year"),
    ("Prilagođeno", "custom"),
])


def stat_card(master, title: str) -> tuple[ttk.Frame, ttk.Label]:
    card = ttk.Frame(master, style="Card.TFrame", padding=(14, 10))
    ttk.Label(card, text=title, style="CardMuted.TLabel").pack(anchor="w")
    value = ttk.Label(card, text="—", style="Stat.TLabel")
    value.pack(anchor="w")
    return card, value


class BarChart(tk.Canvas):
    """Single-series vertical bar chart with hover tooltips."""

    def __init__(self, master, height: int = 200):
        super().__init__(master, height=height, background=SURFACE, highlightthickness=0)
        self.data: list[tuple[str, str, float]] = []  # (axis label, tooltip label, seconds)
        self.goal: float = 0
        self.tooltip = Tooltip(self)
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Leave>", self.tooltip.hide)
        self.bind("<Motion>", self._motion)

    def set_data(self, data: list[tuple[str, str, float]], goal_seconds: float = 0) -> None:
        self.data = data
        self.goal = goal_seconds
        self.draw()

    def draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50 or not self.data:
            return
        left, right, top, bottom = 44, 12, 14, 28
        plot_h = h - top - bottom
        max_val = max([v for _, _, v in self.data] + [self.goal, 3600])
        step_h = 1
        for candidate in (1, 2, 4, 5, 10, 20, 25, 50, 100, 200, 500):
            step_h = candidate
            if max_val / 3600 / candidate <= 5:
                break
        top_val = step_h * 3600 * (int(max_val / 3600 / step_h) + 1)

        def y_of(v: float) -> float:
            return top + plot_h - plot_h * v / top_val

        # Recessive grid and axis labels.
        v = 0
        while v <= top_val + 1:
            y = y_of(v)
            self.create_line(left, y, w - right, y, fill=GRID)
            self.create_text(left - 6, y, text=f"{int(v / 3600)}h", anchor="e", fill=TEXT_MUTED,
                             font=(FONT, 8))
            v += step_h * 3600
        if self.goal:
            y = y_of(self.goal)
            self.create_line(left, y, w - right, y, fill=TEXT_MUTED, dash=(4, 3))
            self.create_text(w - right, y - 2, text="cilj", anchor="se", fill=TEXT_MUTED, font=(FONT, 8))

        n = len(self.data)
        slot = (w - left - right) / n
        bar_w = max(2, min(38, slot * 0.7))
        label_every = max(1, int(40 / slot) + (1 if slot < 40 else 0))
        for i, (label, tip, value) in enumerate(self.data):
            cx = left + slot * (i + 0.5)
            if value > 0:
                y = y_of(value)
                self.create_rectangle(cx - bar_w / 2, y, cx + bar_w / 2, y_of(0), fill=ACCENT, width=0)
                if n <= 14 and bar_w >= 24:
                    self.create_text(cx, y - 2, text=timeutil.fmt_hours(value), anchor="s", fill=TEXT,
                                     font=(FONT, 8))
            if i % label_every == 0:
                self.create_text(cx, h - bottom + 6, text=label, anchor="n", fill=TEXT_MUTED, font=(FONT, 8))
        self._geom = (left, slot, top, y_of(0))

    def _motion(self, event) -> None:
        """Hover anywhere in a bar's column (hit target bigger than the mark)."""
        if not self.data or not hasattr(self, "_geom"):
            return
        left, slot, top, base = self._geom
        i = int((event.x - left) // slot)
        if 0 <= i < len(self.data) and top <= event.y <= base:
            _, tip, value = self.data[i]
            self.tooltip.show(f"{tip}\n{timeutil.fmt_hours(value)}", event.x_root, event.y_root)
        else:
            self.tooltip.hide()


class ReportsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.period = tk.StringVar(value="Ova nedelja")
        self.from_var = tk.StringVar(value=timeutil.fmt_date(time.time() - 6 * 86400))
        self.to_var = tk.StringVar(value=timeutil.fmt_date(time.time()))

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 10))
        ttk.Label(bar, text="Period").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.period, values=list(PERIODS), state="readonly", width=15)
        cb.pack(side="left", padx=(6, 12))
        cb.bind("<<ComboboxSelected>>", lambda e: self._period_changed())
        self.custom = ttk.Frame(bar)
        ttk.Label(self.custom, text="od").pack(side="left")
        ttk.Entry(self.custom, textvariable=self.from_var, width=11).pack(side="left", padx=4)
        ttk.Label(self.custom, text="do").pack(side="left")
        ttk.Entry(self.custom, textvariable=self.to_var, width=11).pack(side="left", padx=4)
        ttk.Button(self.custom, text="Prikaži", command=self.refresh).pack(side="left", padx=(4, 0))
        ttk.Button(bar, text="Izvezi CSV (Excel)", command=self.export).pack(side="right")

        cards = ttk.Frame(self)
        cards.pack(fill="x")
        self.cards = {}
        for i, (key, title) in enumerate((("total", "Ukupno vreme"), ("billable", "Naplativo"),
                                          ("amount", "Zarada"), ("avg", "Prosek po radnom danu"))):
            card, label = stat_card(cards, title)
            card.grid(row=0, column=i, sticky="we", padx=(0 if i == 0 else 8, 0))
            cards.columnconfigure(i, weight=1)
            self.cards[key] = label

        ttk.Label(self, text="Vreme po danu", style="Title.TLabel").pack(anchor="w", pady=(14, 4))
        self.chart = BarChart(self, height=190)
        self.chart.pack(fill="x")

        bottom = ttk.Frame(self)
        bottom.pack(fill="both", expand=True, pady=(14, 0))
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)
        bottom.rowconfigure(1, weight=1)
        ttk.Label(bottom, text="Po projektu", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(bottom, text="Po opisu zadatka", style="Title.TLabel").grid(row=0, column=1, sticky="w",
                                                                          padx=(12, 0))
        pf, self.proj_tree = scrolled_tree(bottom, ("time", "pct", "amount"), height=6)
        pf.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        for col, text, width, anchor in (("#0", "Projekat", 200, "w"), ("time", "Vreme", 80, "e"),
                                         ("pct", "%", 60, "e"), ("amount", "Iznos", 90, "e")):
            self.proj_tree.heading(col, text=text, anchor=anchor)
            self.proj_tree.column(col, width=width, anchor=anchor, stretch=(col == "#0"))
        df, self.desc_tree = scrolled_tree(bottom, ("project", "time"), show="headings", height=6)
        df.grid(row=1, column=1, sticky="nsew", pady=(4, 0), padx=(12, 0))
        self.desc_tree["columns"] = ("desc", "project", "time")
        for col, text, width, anchor in (("desc", "Opis", 220, "w"), ("project", "Projekat", 120, "w"),
                                         ("time", "Vreme", 80, "e")):
            self.desc_tree.heading(col, text=text, anchor=anchor)
            self.desc_tree.column(col, width=width, anchor=anchor, stretch=(col == "desc"))

    def _period_changed(self):
        if PERIODS[self.period.get()] == "custom":
            self.custom.pack(side="left")
        else:
            self.custom.pack_forget()
        self.refresh()

    def bounds(self) -> tuple[float, float]:
        kind = PERIODS[self.period.get()]
        if kind != "custom":
            return timeutil.period_bounds(kind)
        a = timeutil.parse_date(self.from_var.get())
        b = timeutil.parse_date(self.to_var.get())
        if b < a:
            a, b = b, a
        return timeutil.day_start(a), timeutil.day_start(b + timedelta(days=1))

    def refresh(self) -> None:
        try:
            a, b = self.bounds()
        except ValueError as exc:
            messagebox.showerror("Greška", str(exc), parent=self)
            return
        s = reports.summarize(self.app.db, a, b)
        cur = self.app.settings["currency"]
        self.cards["total"].configure(text=timeutil.fmt_hours(s.total))
        pct = f" ({s.billable / s.total:.0%})" if s.total else ""
        self.cards["billable"].configure(text=timeutil.fmt_hours(s.billable) + pct)
        self.cards["amount"].configure(text=f"{s.amount:,.2f} {cur}".replace(",", " "))
        worked_days = [d for d, v in s.by_day.items() if v > 0]
        avg = s.total / len(worked_days) if worked_days else 0
        self.cards["avg"].configure(text=timeutil.fmt_hours(avg))

        days = list(s.by_day.items())
        goal = float(self.app.settings["daily_goal_hours"]) * 3600
        if len(days) <= 45:
            data = [(d.strftime("%d.%m") if len(days) > 7 else timeutil.WEEKDAYS[d.weekday()][:3] + " "
                     + d.strftime("%d.%m"), timeutil.fmt_day_header(d), v) for d, v in days]
            self.chart.set_data(data, goal)
        else:  # long periods: one bar per week
            weeks: OrderedDict[date, float] = OrderedDict()
            for d, v in days:
                monday = d - timedelta(days=d.weekday())
                weeks[monday] = weeks.get(monday, 0) + v
            data = [(m.strftime("%d.%m"), f"Nedelja od {m.strftime('%d.%m.%Y')}", v) for m, v in weeks.items()]
            self.chart.set_data(data)

        t = self.proj_tree
        t.delete(*t.get_children())
        for p in s.by_project:
            t.insert("", "end", text="  " + p.name, image=color_square(self, p.color),
                     values=(timeutil.fmt_hours(p.seconds), f"{p.seconds / s.total:.0%}" if s.total else "",
                             f"{p.amount:,.2f}".replace(",", " ") if p.amount else "—"))
        t = self.desc_tree
        t.delete(*t.get_children())
        for desc, project, secs in s.by_description[:200]:
            t.insert("", "end", values=(desc, project, timeutil.fmt_hours(secs)))

    def export(self):
        try:
            a, b = self.bounds()
        except ValueError as exc:
            messagebox.showerror("Greška", str(exc), parent=self)
            return
        name = f"vreme_{timeutil.ts_to_date(a).isoformat()}_{timeutil.ts_to_date(b - 1).isoformat()}.csv"
        path = filedialog.asksaveasfilename(parent=self, title="Izvezi CSV", defaultextension=".csv",
                                            initialfile=name, filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = reports.export_csv(self.app.db, path, a, b, currency=self.app.settings["currency"])
        except OSError as exc:
            messagebox.showerror("Greška", f"Ne mogu da sačuvam fajl:\n{exc}", parent=self)
            return
        messagebox.showinfo("Izvoz", f"Sačuvano {n} unosa u:\n{path}", parent=self)
