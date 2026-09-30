"""Main application window: timer bar on top, tabs below."""

from __future__ import annotations

import queue
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .. import APP_NAME, reports, timeutil, tray
from ..config import Settings
from ..db import Database, Entry
from ..tracker import IdleEvent, LongTimerEvent, ReminderEvent, Tracker
from .activity_tab import ActivityTab
from .common import BigButton, PlaceholderEntry, set_window_icon, setup_style
from .dialogs import IdleDialog, Toast, project_choices
from .entries_tab import EntriesTab
from .projects_tab import ProjectsTab
from .reports_tab import ReportsTab
from .settings_tab import SettingsTab


class MainWindow(tk.Tk):
    def __init__(self, db: Database, settings: Settings, data_dir: Path, start_minimized: bool = False,
                 platform=None, start_tracker: bool = True):
        super().__init__(className="PersonalTimeTracker")
        self.db = db
        self.settings = settings
        self.data_dir = data_dir
        self.events: queue.Queue = queue.Queue()
        self._quitting = False
        self._idle_dialog_open = False
        self._tray_state: tuple | None = None
        self._ticks = 0

        self.title(APP_NAME)
        self.geometry("1040x700")
        self.minsize(820, 560)
        setup_style(self)
        set_window_icon(self)

        tracker_kwargs = {"platform": platform} if platform is not None else {}
        self.tracker = Tracker(db, settings, self.events, data_dir / "screenshots", **tracker_kwargs)
        self.tray = tray.Tray(self.events.put, self.show, self.toggle_timer, self.quit_app,
                              lambda: self.db.running_entry() is not None)
        self.tray_available = tray.available()

        self._build_timer_bar()
        self._build_status_bar()
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(6, 0))
        self.tabs = {
            "entries": EntriesTab(self.notebook, self),
            "projects": ProjectsTab(self.notebook, self),
            "reports": ReportsTab(self.notebook, self),
            "activity": ActivityTab(self.notebook, self),
            "settings": SettingsTab(self.notebook, self),
        }
        for key, label in (("entries", "Unosi"), ("projects", "Projekti"), ("reports", "Izveštaji"),
                           ("activity", "Aktivnost"), ("settings", "Podešavanja")):
            self.notebook.add(self.tabs[key], text=label)
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self._refresh_current_tab())

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind_all("<Control-n>", lambda e: self.tabs["entries"].add())
        self.bind_all("<Control-space>", lambda e: self.toggle_timer())

        self.refresh_all()
        self.load_running_into_bar()
        if start_tracker:
            self.tracker.start()
            if self.tray.start():
                self.tray_available = True
        self.after(500, self._poll_events)
        self.after(1000, self._tick)
        if start_minimized and self.tray_available:
            self.withdraw()

    # ------------------------------------------------------------------ layout

    def _build_timer_bar(self):
        outer = tk.Frame(self, bg="#dddcd7")
        outer.pack(fill="x", padx=10, pady=(10, 0))
        bar = ttk.Frame(outer, style="Card.TFrame", padding=(12, 10))
        bar.pack(fill="x", padx=1, pady=1)

        self.desc_var = tk.StringVar()
        self.desc_entry = PlaceholderEntry(bar, "Na čemu radiš?", self.desc_var, font=("", 12))
        self.desc_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.desc_entry.bind("<Return>", self._desc_enter)
        self.desc_entry.bind("<FocusOut>", lambda e: self._apply_bar_to_running(), add="+")
        self.desc_entry.bind("<KeyRelease>", self._suggest)

        self.project_var = tk.StringVar()
        self.project_cb = ttk.Combobox(bar, textvariable=self.project_var, state="readonly", width=22)
        self.project_cb.pack(side="left", padx=(10, 0), ipady=3)
        self.project_cb.bind("<<ComboboxSelected>>", lambda e: self._apply_bar_to_running())

        self.billable_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Naplativo", variable=self.billable_var, style="Card.TCheckbutton",
                        command=self._apply_bar_to_running).pack(side="left", padx=(10, 0))

        self.timer_label = ttk.Label(bar, text="0:00:00", style="Timer.TLabel", width=9, anchor="e")
        self.timer_label.pack(side="left", padx=(14, 14))

        self.start_btn = BigButton(bar, command=self.toggle_timer)
        self.start_btn.pack(side="left")
        self.start_btn.set_state(False)

        # Autocomplete list for recent descriptions.
        self.suggest_box = tk.Listbox(self, height=6, activestyle="none", relief="solid", bd=1)
        self.suggest_box.bind("<ButtonRelease-1>", self._pick_suggestion)
        self.suggest_box.bind("<Return>", self._pick_suggestion)
        self.suggest_box.bind("<Escape>", lambda e: self._hide_suggestions())
        self._suggestions: list[tuple[str, int | None]] = []

    def _build_status_bar(self):
        bar = ttk.Frame(self, padding=(12, 6))
        bar.pack(side="bottom", fill="x")
        self.today_label = ttk.Label(bar, text="", style="Muted.TLabel")
        self.today_label.pack(side="left")
        self.goal_bar = ttk.Progressbar(bar, length=140, maximum=100, style="Goal.Horizontal.TProgressbar")
        self.goal_bar.pack(side="left", padx=(8, 0))
        self.app_label = ttk.Label(bar, text="", style="Muted.TLabel")
        self.app_label.pack(side="right")

    # --------------------------------------------------------------- timer bar

    def _project_choices(self, include_id=None):
        return project_choices(self.db, include_id)

    def _refresh_project_combo(self, include_id=None):
        self._choices = self._project_choices(include_id)
        self.project_cb.configure(values=[c[0] for c in self._choices])
        if self.project_var.get() not in dict(self._choices):
            self.project_var.set(self._choices[0][0])

    def _selected_project_id(self):
        return dict(self._choices).get(self.project_var.get())

    def _set_project(self, project_id):
        self._refresh_project_combo(project_id)
        for label, pid in self._choices:
            if pid == project_id:
                self.project_var.set(label)
                return

    def load_running_into_bar(self):
        running = self.db.running_entry()
        self.start_btn.set_state(running is not None)
        if running:
            self.desc_entry.set_value(running.description)
            self._set_project(running.project_id)
            self.billable_var.set(running.billable)
        self._update_timer_label()

    def _apply_bar_to_running(self):
        running = self.db.running_entry()
        if not running:
            return
        desc = self.desc_entry.value().strip()
        pid = self._selected_project_id()
        billable = self.billable_var.get()
        if (desc, pid, billable) != (running.description, running.project_id, running.billable):
            self.db.update_entry(running.id, description=desc, project_id=pid, billable=billable)
            self.refresh_all()

    def _desc_enter(self, _event=None):
        if self.suggest_box.winfo_ismapped() and self.suggest_box.curselection():
            self._pick_suggestion()
            return "break"
        self._hide_suggestions()
        if self.db.running_entry():
            self._apply_bar_to_running()
        else:
            self.start_timer()
        return "break"

    def toggle_timer(self):
        if self.db.running_entry():
            self.stop_timer()
        else:
            self.start_timer()

    def start_timer(self):
        self._hide_suggestions()
        self.db.start_entry(self.desc_entry.value(), self._selected_project_id(), self.billable_var.get())
        self.start_btn.set_state(True)
        self.refresh_all()

    def stop_timer(self):
        self._apply_bar_to_running()
        self.db.stop_running()
        self.start_btn.set_state(False)
        self.desc_entry.set_value("")
        self.billable_var.set(False)
        self.project_var.set(self._choices[0][0])
        self.refresh_all()

    def continue_entry(self, entry: Entry):
        self.db.start_entry(entry.description, entry.project_id, entry.billable)
        self.load_running_into_bar()
        self.refresh_all()

    # ------------------------------------------------------------- suggestions

    def _suggest(self, event):
        if event.keysym in ("Return", "Escape", "Tab"):
            if event.keysym == "Escape":
                self._hide_suggestions()
            return
        if event.keysym == "Down" and self.suggest_box.winfo_ismapped():
            self.suggest_box.focus_set()
            self.suggest_box.selection_clear(0, "end")
            self.suggest_box.selection_set(0)
            return
        text = self.desc_entry.value().strip().lower()
        if len(text) < 2:
            self._hide_suggestions()
            return
        projects = self.db.project_map()
        self._suggestions = [(d, pid) for d, pid in self.db.recent_descriptions(200)
                             if text in d.lower()][:6]
        if not self._suggestions:
            self._hide_suggestions()
            return
        self.suggest_box.delete(0, "end")
        for d, pid in self._suggestions:
            p = projects.get(pid) if pid is not None else None
            self.suggest_box.insert("end", f"{d}   —   {p.name}" if p else d)
        x = self.desc_entry.winfo_rootx() - self.winfo_rootx()
        y = self.desc_entry.winfo_rooty() - self.winfo_rooty() + self.desc_entry.winfo_height() + 2
        self.suggest_box.place(x=x, y=y, width=self.desc_entry.winfo_width())
        self.suggest_box.configure(height=len(self._suggestions))
        self.suggest_box.lift()

    def _pick_suggestion(self, _event=None):
        sel = self.suggest_box.curselection()
        if sel:
            desc, pid = self._suggestions[sel[0]]
            self.desc_entry.set_value(desc)
            self._set_project(pid)
            if self.db.running_entry():
                self._apply_bar_to_running()
        self._hide_suggestions()
        self.desc_entry.focus_set()
        self.desc_entry.icursor("end")

    def _hide_suggestions(self):
        self.suggest_box.place_forget()

    # ----------------------------------------------------------------- refresh

    def refresh_all(self):
        self._refresh_project_combo(getattr(self.db.running_entry(), "project_id", None))
        self.tabs["entries"].refresh()
        self._refresh_current_tab()
        self._update_today()

    def _refresh_current_tab(self):
        current = self.notebook.nametowidget(self.notebook.select()) if self.notebook.select() else None
        if current in (self.tabs["projects"], self.tabs["reports"], self.tabs["activity"]):
            current.refresh()

    def _update_timer_label(self):
        running = self.db.running_entry()
        self.timer_label.configure(text=timeutil.fmt_clock(running.duration()) if running else "0:00:00")
        return running

    def _update_today(self):
        a, b = timeutil.period_bounds("today")
        total = reports.summarize(self.db, a, b).total
        goal = float(self.settings["daily_goal_hours"]) * 3600
        text = f"Danas: {timeutil.fmt_hours(total)}"
        if goal:
            text += f" od {timeutil.fmt_hours(goal)}"
            self.goal_bar.configure(value=min(100, 100 * total / goal))
        self.today_label.configure(text=text)
        return total

    def _tick(self):
        if self._quitting:
            return
        running = self._update_timer_label()
        self.tabs["entries"].tick()
        now = time.time()
        self._ticks += 1
        if self._ticks % 30 == 0:
            self._update_today()
        win = self.tracker.current_app
        if self.tracker.error:
            self.app_label.configure(text=f"Greška trackera: {self.tracker.error}")
        elif win and self.settings["activity_mode"] != "off":
            name = reports.app_display_name(win[0])
            self.app_label.configure(text=f"Aktivno: {name}  •  {win[1][:60]}")
        else:
            self.app_label.configure(text="")
        state = (running is not None, running.description if running else "")
        if running:
            p = self.db.get_project(running.project_id)
            tip = f"{timeutil.fmt_clock(running.duration())[:-3]} • {running.description or '(bez opisa)'}"
            if p:
                tip += f" • {p.name}"
            self.title(f"{timeutil.fmt_clock(running.duration())} • {APP_NAME}")
        else:
            tip = f"{APP_NAME}: tajmer nije pokrenut"
            self.title(APP_NAME)
        # Refresh the tray at most once a minute unless the state changed.
        key = state + (int(now // 60),)
        if key != self._tray_state:
            self._tray_state = key
            self.tray.update(running is not None, tip)
        self.after(1000, self._tick)

    # ------------------------------------------------------------------ events

    def _poll_events(self):
        if self._quitting:
            return
        try:
            while True:
                ev = self.events.get_nowait()
                if callable(ev):
                    ev()
                elif isinstance(ev, IdleEvent):
                    self._handle_idle(ev)
                elif isinstance(ev, ReminderEvent):
                    Toast(self, "Tajmer nije pokrenut",
                          f"Aktivan si već {timeutil.fmt_hours(ev.active_seconds)} bez tajmera.",
                          "Pokreni tajmer", self._reminder_start)
                elif isinstance(ev, LongTimerEvent):
                    Toast(self, "Tajmer radi dugo",
                          f"Tajmer radi već {timeutil.fmt_hours(ev.seconds)}. Da nisi zaboravio da ga zaustaviš?",
                          "Zaustavi", self.stop_timer)
        except queue.Empty:
            pass
        self.after(500, self._poll_events)

    def _reminder_start(self):
        self.show()
        self.desc_entry.focus_set()
        self.start_timer()

    def _handle_idle(self, ev: IdleEvent):
        if self._idle_dialog_open:
            return
        entry = self.db.get_entry(ev.entry_id)
        if entry is None or not entry.running:
            return
        self._idle_dialog_open = True
        try:
            if not self.winfo_viewable():
                self.show()
            choice = IdleDialog(self, ev.idle_start, ev.idle_end, entry.description).show()
        finally:
            self._idle_dialog_open = False
        if choice == IdleDialog.DISCARD_CONTINUE:
            self.db.discard_interval(entry.id, ev.idle_start, ev.idle_end, continue_after=True)
        elif choice == IdleDialog.DISCARD_STOP:
            self.db.discard_interval(entry.id, ev.idle_start, ev.idle_end, continue_after=False)
            self.start_btn.set_state(False)
            self.desc_entry.set_value("")
        self.load_running_into_bar()
        self.refresh_all()

    # --------------------------------------------------------------- lifecycle

    def show(self):
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def on_close(self):
        if self.settings["minimize_to_tray"] and self.tray_available:
            self.withdraw()
            return
        self.quit_app()

    def quit_app(self):
        if self._quitting:
            return
        running = self.db.running_entry()
        if running:
            self.show()
            answer = messagebox.askyesnocancel(
                "Izlaz", "Tajmer još radi.\n\nDa → zaustavi tajmer i izađi\nNe → izađi, tajmer nastavlja "
                         "(vreme se računa i dok je aplikacija zatvorena)", parent=self)
            if answer is None:
                return
            if answer:
                self.db.stop_running()
        self._quitting = True
        self.tracker.stop()
        self.tray.stop()
        self.destroy()

