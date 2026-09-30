"""Project management."""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, ttk

from .. import reports, timeutil
from .common import PROJECT_COLORS, color_square, scrolled_tree
from .dialogs import ProjectDialog


class ProjectsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.show_archived = tk.BooleanVar(value=False)

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Button(bar, text="+ Novi projekat", style="Accent.TButton", command=self.add).pack(side="left")
        ttk.Button(bar, text="Izmeni", command=self.edit).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Arhiviraj / vrati", command=self.toggle_archive).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Obriši", command=self.delete).pack(side="left", padx=(6, 0))
        ttk.Checkbutton(bar, text="Prikaži arhivirane", variable=self.show_archived,
                        command=self.refresh).pack(side="right")

        frame, self.tree = scrolled_tree(self, ("rate", "week", "month", "status"), selectmode="browse")
        frame.pack(fill="both", expand=True)
        t = self.tree
        for col, text, width, anchor in (("#0", "Projekat", 280, "w"), ("rate", "Satnica", 100, "e"),
                                         ("week", "Ova nedelja", 110, "e"), ("month", "Ovaj mesec", 110, "e"),
                                         ("status", "Status", 100, "w")):
            t.heading(col, text=text, anchor=anchor)
            t.column(col, width=width, anchor=anchor, stretch=(col == "#0"))
        t.tag_configure("archived", foreground="#9aa0a6")
        t.bind("<Double-1>", lambda e: self.edit())

        ttk.Label(self, text="Brisanje projekta ne briše unose; oni ostaju bez projekta. "
                             "Arhiviranje ga samo sklanja iz izbora.",
                  style="Muted.TLabel").pack(anchor="w", pady=(8, 0))

    def refresh(self) -> None:
        t = self.tree
        t.delete(*t.get_children())
        now = time.time()
        week = reports.summarize(self.app.db, *timeutil.period_bounds("this_week"), now=now)
        month = reports.summarize(self.app.db, *timeutil.period_bounds("this_month"), now=now)
        wk = {p.project_id: p.seconds for p in week.by_project}
        mo = {p.project_id: p.seconds for p in month.by_project}
        cur = self.app.settings["currency"]
        for p in self.app.db.list_projects(include_archived=self.show_archived.get()):
            t.insert("", "end", iid=str(p.id), text="  " + p.name, image=color_square(self, p.color),
                     tags=("archived",) if p.archived else (),
                     values=(f"{p.hourly_rate:g} {cur}" if p.hourly_rate else "—",
                             timeutil.fmt_hours(wk.get(p.id, 0)), timeutil.fmt_hours(mo.get(p.id, 0)),
                             "arhiviran" if p.archived else "aktivan"))

    def _selected(self):
        sel = self.tree.selection()
        return self.app.db.get_project(int(sel[0])) if sel else None

    def add(self):
        count = len(self.app.db.list_projects(include_archived=True))
        res = ProjectDialog(self.winfo_toplevel(), default_color=PROJECT_COLORS[count % len(PROJECT_COLORS)],
                            currency=self.app.settings["currency"]).show()
        if res:
            try:
                self.app.db.add_project(res["name"], res["color"], res["hourly_rate"])
            except ValueError as exc:
                messagebox.showerror("Greška", str(exc), parent=self)
                return
            self.app.refresh_all()

    def edit(self):
        p = self._selected()
        if not p:
            return
        res = ProjectDialog(self.winfo_toplevel(), p, currency=self.app.settings["currency"]).show()
        if res:
            try:
                self.app.db.update_project(p.id, **res)
            except ValueError as exc:
                messagebox.showerror("Greška", str(exc), parent=self)
                return
            self.app.refresh_all()

    def toggle_archive(self):
        p = self._selected()
        if p:
            self.app.db.update_project(p.id, archived=not p.archived)
            self.app.refresh_all()

    def delete(self):
        p = self._selected()
        if p and messagebox.askyesno("Brisanje", f"Obrisati projekat '{p.name}'?\nUnosi ostaju, bez projekta.",
                                     parent=self):
            self.app.db.delete_project(p.id)
            self.app.refresh_all()
