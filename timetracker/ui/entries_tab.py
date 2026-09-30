"""Time entries list grouped by day (Clockify style)."""

from __future__ import annotations

import time
import tkinter as tk
from collections import OrderedDict
from datetime import date, timedelta
from tkinter import messagebox, ttk

from .. import timeutil
from ..reports import overlap
from .common import TEXT_MUTED, scrolled_tree
from .dialogs import EntryDialog

RANGES = OrderedDict([("7 dana", 7), ("14 dana", 14), ("30 dana", 30), ("90 dana", 90), ("365 dana", 365)])


class EntriesTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.range = tk.StringVar(value="14 dana")

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Button(bar, text="+ Dodaj ručno", style="Accent.TButton", command=self.add).pack(side="left")
        ttk.Button(bar, text="Izmeni", command=self.edit).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="▶ Nastavi", command=self.continue_selected).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Dupliraj", command=self.duplicate).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Obriši", command=self.delete).pack(side="left", padx=(6, 0))
        cb = ttk.Combobox(bar, textvariable=self.range, values=list(RANGES), state="readonly", width=10)
        cb.pack(side="right")
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Label(bar, text="Prikaži poslednjih").pack(side="right", padx=(0, 6))

        frame, self.tree = scrolled_tree(self, ("project", "billable", "range", "duration"),
                                         selectmode="extended")
        frame.pack(fill="both", expand=True)
        t = self.tree
        t.heading("#0", text="Opis", anchor="w")
        t.heading("project", text="Projekat", anchor="w")
        t.heading("billable", text="Naplativo", anchor="center")
        t.heading("range", text="Vreme", anchor="w")
        t.heading("duration", text="Trajanje", anchor="e")
        t.column("#0", width=380, stretch=True)
        t.column("project", width=170, stretch=False)
        t.column("billable", width=80, stretch=False, anchor="center")
        t.column("range", width=120, stretch=False)
        t.column("duration", width=90, stretch=False, anchor="e")
        t.tag_configure("day", background="#eeede9", font=("", 10, "bold"))
        t.tag_configure("running", foreground="#1a8f4c")
        t.tag_configure("nodesc", foreground=TEXT_MUTED)
        t.bind("<Double-1>", self._on_double)
        t.bind("<Delete>", lambda e: self.delete())
        t.bind("<Button-3>", self._context_menu)

        self.menu = tk.Menu(self, tearoff=False)
        self.menu.add_command(label="Izmeni", command=self.edit)
        self.menu.add_command(label="Nastavi (pokreni ponovo)", command=self.continue_selected)
        self.menu.add_command(label="Dupliraj", command=self.duplicate)
        self.menu.add_separator()
        self.menu.add_command(label="Obriši", command=self.delete)

    # ---------------------------------------------------------------- data

    def refresh(self) -> None:
        t = self.tree
        selected = set(t.selection())
        open_state = {iid: t.item(iid, "open") for iid in t.get_children()}
        t.delete(*t.get_children())
        days = RANGES.get(self.range.get(), 14)
        today = date.today()
        a = timeutil.day_start(today - timedelta(days=days - 1))
        b = timeutil.day_start(today + timedelta(days=1))
        now = time.time()
        projects = self.app.db.project_map()

        by_day: dict[date, list] = OrderedDict()
        for e in self.app.db.entries_between(a, b):  # newest first
            by_day.setdefault(timeutil.ts_to_date(e.start_ts), []).append(e)

        for d, entries in by_day.items():
            ds, de = timeutil.day_bounds(d)
            total = sum(overlap(e.start_ts, e.end_ts or now, ds, de) for e in entries)
            day_id = f"d{d.isoformat()}"
            t.insert("", "end", iid=day_id, text=timeutil.fmt_day_header(d, today), values=("", "", "Ukupno", timeutil.fmt_clock(total)), open=open_state.get(day_id, True), tags=("day",))
            for e in entries:
                p = projects.get(e.project_id) if e.project_id is not None else None
                end_txt = "…" if e.running else timeutil.fmt_time(e.end_ts)
                if not e.running and timeutil.ts_to_date(e.end_ts) != d:
                    end_txt += " (+1)"
                tags = []
                if e.running:
                    tags.append("running")
                elif not e.description:
                    tags.append("nodesc")
                desc = e.description or "(bez opisa)"
                if e.running:
                    desc = "● " + desc
                t.insert(day_id, "end", iid=f"e{e.id}", text=desc,
                         values=(p.name if p else "", "✓" if e.billable else "", f"{timeutil.fmt_time(e.start_ts)} – {end_txt}",
                                 timeutil.fmt_clock(e.duration(now))), tags=tags)
        still = [i for i in selected if t.exists(i)]
        if still:
            t.selection_set(still)

    def tick(self) -> None:
        """Update the running entry's duration without rebuilding the tree."""
        running = self.app.db.running_entry()
        if running and self.tree.exists(f"e{running.id}"):
            self.tree.set(f"e{running.id}", "duration", timeutil.fmt_clock(running.duration()))

    # ------------------------------------------------------------- actions

    def _selected_entries(self):
        ids = [int(i[1:]) for i in self.tree.selection() if i.startswith("e")]
        return [e for e in (self.app.db.get_entry(i) for i in ids) if e]

    def _selected_day(self) -> date | None:
        for iid in self.tree.selection():
            if iid.startswith("d"):
                return date.fromisoformat(iid[1:])
            parent = self.tree.parent(iid)
            if parent:
                return date.fromisoformat(parent[1:])
        return None

    def _on_double(self, event):
        iid = self.tree.identify_row(event.y)
        if iid.startswith("e"):
            self.edit()

    def _context_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid.startswith("e"):
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
            self.menu.tk_popup(event.x_root, event.y_root)

    def add(self):
        res = EntryDialog(self.winfo_toplevel(), self.app.db, day=self._selected_day()).show()
        if res:
            try:
                self.app.db.add_entry(res["description"], res["project_id"], res["start"], res["end"],
                                      res["billable"])
            except ValueError as exc:
                messagebox.showerror("Greška", str(exc), parent=self)
                return
            self.app.refresh_all()

    def edit(self):
        entries = self._selected_entries()
        if not entries:
            return
        e = entries[0]
        res = EntryDialog(self.winfo_toplevel(), self.app.db, entry=e).show()
        if res:
            kwargs = dict(description=res["description"], project_id=res["project_id"], start=res["start"],
                          billable=res["billable"])
            if not e.running:
                kwargs["end"] = res["end"]
            try:
                self.app.db.update_entry(e.id, **kwargs)
            except ValueError as exc:
                messagebox.showerror("Greška", str(exc), parent=self)
                return
            self.app.refresh_all()

    def continue_selected(self):
        entries = self._selected_entries()
        if entries:
            self.app.continue_entry(entries[0])

    def duplicate(self):
        for e in self._selected_entries():
            if e.running:
                continue
            self.app.db.add_entry(e.description, e.project_id, e.start_ts, e.end_ts, e.billable)
        self.app.refresh_all()

    def delete(self):
        entries = self._selected_entries()
        if not entries:
            return
        text = "Obrisati izabrani unos?" if len(entries) == 1 else f"Obrisati {len(entries)} unosa?"
        if not messagebox.askyesno("Brisanje", text, parent=self):
            return
        for e in entries:
            self.app.db.delete_entry(e.id)
        self.app.refresh_all()
