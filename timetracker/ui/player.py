"""The main window: a small Winamp-style player with a playlist of time entries."""

from __future__ import annotations

import queue
import time
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import APP_ID, APP_NAME, platform_win, reports, timeutil, tray
from ..config import Settings
from ..db import Database
from ..tracker import IdleEvent, Tracker
from . import skin
from .dialogs import EntryDialog, IdleDialog

PL_WIDTH = 50  # playlist width in characters
IDLE_CHOICES = [(0, "Isključeno"), (5, "5 min"), (10, "10 min"), (15, "15 min"), (30, "30 min")]
EXPORTS = [("Ova nedelja", "this_week"), ("Prošla nedelja", "last_week"), ("Ovaj mesec", "this_month"),
           ("Prošli mesec", "last_month"), ("Ova godina", "this_year")]


class Player(tk.Tk):
    STOPPED, PLAYING, PAUSED = "stopped", "playing", "paused"

    def __init__(self, db: Database, settings: Settings, data_dir: Path, start_minimized: bool = False,
                 platform=None, start_tracker: bool = True):
        super().__init__(className="PersonalTimeTracker")
        self.db, self.settings, self.data_dir = db, settings, data_dir
        self.events: queue.Queue = queue.Queue()
        self.paused = False
        self.day_offset = 0  # playlist day: 0 = today, 1 = yesterday, ...
        self._pl_ids: list[int] = []
        self._blink = False
        self._quitting = False
        self._idle_open = False
        self._tray_key = None

        self.title(APP_NAME)
        self.resizable(False, False)
        skin.init(self)
        skin.set_window_icon(self)
        self.attributes("-topmost", settings["always_on_top"])

        self.tracker = Tracker(db, settings, self.events, **({"platform": platform} if platform else {}))
        self.tray = tray.Tray(self.events.put, self.show, self.play_pause, self.quit_app,
                              lambda: self.db.running_entry() is not None)
        self.tray_available = False

        self._build_menu()
        skin.TitleBar(self, APP_NAME.upper(), self._popup_menu).pack(fill="x")
        self._build_main()
        self._build_playlist()
        if settings["show_playlist"]:
            self.pl_frame.pack(fill="x")
        self.bind("<Button-3>", self._popup_menu)  # root binding tag: any widget in this window
        self.bind_all("<Control-space>", lambda e: self.play_pause())
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        running = db.running_entry()
        if running:
            self.task_var.set(running.description)
            self.project_var.set(db.project_names().get(running.project_id, ""))
        self.refresh()
        self._restore_position()
        if start_tracker:
            self.tracker.start()
            self.tray_available = self.tray.start()
        if start_minimized and self.tray_available:
            self.withdraw()
        self.after(500, self._poll_events)
        self.after(250, self._tick)

    # ------------------------------------------------------------------ layout

    def _build_main(self):
        main = tk.Frame(self, bg=skin.BODY, padx=6, pady=4)
        main.pack(fill="x")

        well, lcd = skin.sunken(main, padx=6, pady=4)
        well.pack(fill="x")
        left = tk.Frame(lcd, bg=skin.LCD_BG)
        left.pack(side="left")
        self.state_icon = tk.Canvas(left, width=skin.px(12), height=skin.px(12), bg=skin.LCD_BG,
                                    highlightthickness=0)
        self.state_icon.pack(side="left", anchor="n", padx=(0, 6), pady=(2, 0))
        self.clock = skin.SevenSegment(left)
        self.clock.pack(side="left")
        right = tk.Frame(lcd, bg=skin.LCD_BG)
        right.pack(side="left", padx=(12, 0), fill="x", expand=True)
        self.marquee = skin.Marquee(right, chars=24)
        self.marquee.pack(anchor="w")
        self.info = tk.Label(right, text="", bg=skin.LCD_BG, fg=skin.LCD_DIM, font=(skin.MONO, 8), justify="left",
                             anchor="w")
        self.info.pack(anchor="w", fill="x", pady=(2, 0))

        row = tk.Frame(main, bg=skin.BODY)
        row.pack(fill="x", pady=(5, 0))
        self.task_var = tk.StringVar()
        self.project_var = tk.StringVar()
        skin.label(row, "ZADATAK").grid(row=0, column=0, sticky="w")
        skin.label(row, "PROJEKAT").grid(row=0, column=1, sticky="w", padx=(6, 0))
        self.task_entry = skin.lcd_entry(row, self.task_var, 28)
        self.task_entry.grid(row=1, column=0, sticky="we")
        self.project_cb = ttk.Combobox(row, textvariable=self.project_var, style="Skin.TCombobox", width=16,
                                       font=(skin.MONO, 10))
        self.project_cb.grid(row=1, column=1, sticky="we", padx=(6, 0))
        row.columnconfigure(0, weight=1)
        for w in (self.task_entry, self.project_cb):
            w.bind("<Return>", self._enter)
            w.bind("<FocusOut>", lambda e: self._apply_fields(), add="+")
        self.project_cb.bind("<<ComboboxSelected>>", lambda e: self._apply_fields())

        buttons = tk.Frame(main, bg=skin.BODY)
        buttons.pack(fill="x", pady=(6, 2))
        skin.SkinButton(buttons, self.play, glyph="play", tooltip="Start (Enter)").pack(side="left")
        skin.SkinButton(buttons, self.pause, glyph="pause", tooltip="Pauza").pack(side="left", padx=1)
        skin.SkinButton(buttons, self.stop, glyph="stop", tooltip="Stop").pack(side="left")
        skin.SkinButton(buttons, self._export_menu, glyph="eject", tooltip="Izvezi u Excel (CSV)").pack(
            side="left", padx=(6, 0))
        skin.SkinButton(buttons, self.toggle_playlist, text="PL", tooltip="Prikaži/sakrij listu").pack(
            side="right")

    def _build_playlist(self):
        self.pl_frame = tk.Frame(self, bg=skin.BODY, padx=6, pady=2)
        head = tk.Frame(self.pl_frame, bg=skin.BODY)
        head.pack(fill="x", pady=(0, 3))
        skin.SkinButton(head, lambda: self.shift_day(1), glyph="prev", width=18, height=16,
                        tooltip="Prethodni dan").pack(side="left")
        self.day_label = skin.label(head, "", fg=skin.GOLD)
        self.day_label.pack(side="left", expand=True)
        skin.SkinButton(head, lambda: self.shift_day(-1), glyph="next", width=18, height=16,
                        tooltip="Sledeći dan").pack(side="right")

        well, inner = skin.sunken(self.pl_frame)
        well.pack(fill="x")
        self.listbox = tk.Listbox(inner, width=PL_WIDTH, height=8, bg=skin.LCD_BG, fg=skin.LCD_ON,
                                  selectbackground=skin.SEL_BG, selectforeground=skin.WHITE, font=(skin.MONO, 9),
                                  relief="flat", highlightthickness=0, activestyle="none", bd=0)
        self.listbox.pack(fill="both", padx=2, pady=2)
        self.listbox.bind("<Double-1>", lambda e: self.continue_selected())
        self.listbox.bind("<Delete>", lambda e: self.delete_selected())
        self.listbox.bind("<Return>", lambda e: self.edit_selected())
        self.listbox.bind("<Button-3>", self._row_menu)

        foot = tk.Frame(self.pl_frame, bg=skin.BODY)
        foot.pack(fill="x", pady=(3, 4))
        skin.SkinButton(foot, self.add_entry, text="+ DODAJ", tooltip="Ručno dodaj vreme").pack(side="left")
        skin.SkinButton(foot, self.edit_selected, text="IZMENI").pack(side="left", padx=2)
        skin.SkinButton(foot, self.delete_selected, text="OBRIŠI").pack(side="left")
        self.total_label = tk.Label(foot, text="", bg=skin.BODY, fg=skin.LCD_ON, font=(skin.MONO, 9, "bold"))
        self.total_label.pack(side="right")

        self.row_menu = tk.Menu(self, tearoff=False)
        self.row_menu.add_command(label="Nastavi ovaj zadatak", command=self.continue_selected)
        self.row_menu.add_command(label="Izmeni", command=self.edit_selected)
        self.row_menu.add_command(label="Obriši", command=self.delete_selected)

    def _build_menu(self):
        self.menu = tk.Menu(self, tearoff=False)
        self.idle_var = tk.IntVar(value=self.settings["idle_minutes"])
        idle = tk.Menu(self.menu, tearoff=False)
        for minutes, text in IDLE_CHOICES:
            idle.add_radiobutton(label=text, value=minutes, variable=self.idle_var,
                                 command=lambda: self.settings.update({"idle_minutes": self.idle_var.get()}))
        self.menu.add_cascade(label="Pitaj za neaktivnost posle", menu=idle)
        self.top_var = tk.BooleanVar(value=self.settings["always_on_top"])
        self.menu.add_checkbutton(label="Uvek na vrhu", variable=self.top_var, command=self._toggle_top)
        self.autostart_var = tk.BooleanVar(value=platform_win.is_autostart_enabled(APP_ID))
        self.menu.add_checkbutton(label="Pokreni sa Windows-om", variable=self.autostart_var,
                                  command=self._toggle_autostart,
                                  state="normal" if platform_win.IS_WINDOWS else "disabled")
        self.export_menu = tk.Menu(self.menu, tearoff=False)
        for text, kind in EXPORTS:
            self.export_menu.add_command(label=text, command=lambda k=kind: self.export(k))
        self.menu.add_cascade(label="Izvezi u Excel (CSV)", menu=self.export_menu)
        self.menu.add_command(label="Otvori folder sa podacima", command=lambda: platform_win.open_path(self.data_dir))
        self.menu.add_separator()
        self.menu.add_command(label="Izlaz", command=self.quit_app)

    def _popup_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def _export_menu(self):
        self.export_menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

    # ------------------------------------------------------------------ state

    @property
    def state(self) -> str:
        if self.db.running_entry():
            return self.PLAYING
        return self.PAUSED if self.paused else self.STOPPED

    def play(self):
        if self.db.running_entry():
            return
        self.db.start_entry(self.task_var.get(), self.db.project_id(self.project_var.get()))
        self.paused = False
        self.refresh()

    def pause(self):
        if self.db.running_entry():
            self._apply_fields()
            self.db.stop_running()
            self.paused = True
            self.refresh()
        elif self.paused:
            self.play()

    def play_pause(self):
        if self.db.running_entry():
            self.pause()
        else:
            self.play()

    def stop(self):
        self._apply_fields()
        self.db.stop_running()
        self.paused = False
        self.task_var.set("")
        self.project_var.set("")
        self.refresh()

    def _enter(self, _event=None):
        if self.db.running_entry():
            self._apply_fields()
            self.focus_set()
        else:
            self.play()
        return "break"

    def _apply_fields(self):
        """Typing into the task/project fields while the timer runs updates the running entry."""
        running = self.db.running_entry()
        if not running:
            return
        desc = self.task_var.get().strip()
        pid = self.db.project_id(self.project_var.get())
        if (desc, pid) != (running.description, running.project_id):
            self.db.update_entry(running.id, desc, pid, running.start_ts, None)
            self.refresh()

    # --------------------------------------------------------------- playlist

    def _selected(self):
        sel = self.listbox.curselection()
        return self.db.get_entry(self._pl_ids[sel[0]]) if sel and sel[0] < len(self._pl_ids) else None

    def _row_menu(self, event):
        i = self.listbox.nearest(event.y)
        if i >= 0 and self._pl_ids:
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(i)
            self.row_menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def continue_selected(self):
        e = self._selected()
        if not e or e.running:
            return
        self.db.start_entry(e.description, e.project_id)
        self.task_var.set(e.description)
        self.project_var.set(self.db.project_names().get(e.project_id, ""))
        self.paused = False
        self.day_offset = 0
        self.refresh()

    def edit_selected(self):
        e = self._selected()
        if not e:
            return
        res = EntryDialog(self, self.db, entry=e).show()
        if res:
            try:
                self.db.update_entry(e.id, res["description"], self.db.project_id(res["project"]), res["start"],
                                     res["end"])
            except ValueError as exc:
                messagebox.showerror("Greška", str(exc), parent=self)
                return
            if e.running:
                self.task_var.set(res["description"])
                self.project_var.set(res["project"])
            self.refresh()

    def add_entry(self):
        res = EntryDialog(self, self.db, day=date.today() - timedelta(days=self.day_offset)).show()
        if res:
            try:
                self.db.add_entry(res["description"], self.db.project_id(res["project"]), res["start"], res["end"])
            except ValueError as exc:
                messagebox.showerror("Greška", str(exc), parent=self)
                return
            self.refresh()

    def delete_selected(self):
        e = self._selected()
        if e and messagebox.askyesno("Obriši", f"Obrisati '{e.description or 'bez naziva'}'?", parent=self):
            self.db.delete_entry(e.id)
            if e.running:
                self.stop()
            self.refresh()

    def shift_day(self, days_back: int):
        self.day_offset = max(0, self.day_offset + days_back)
        self.refresh()

    def toggle_playlist(self):
        show = not self.pl_frame.winfo_ismapped()
        if show:
            self.pl_frame.pack(fill="x")
        else:
            self.pl_frame.pack_forget()
        self.settings.update({"show_playlist": show})

    # ---------------------------------------------------------------- refresh

    def refresh(self):
        """Rebuild everything that depends on the database."""
        self.project_cb.configure(values=list(self.db.project_names().values()))
        self._fill_playlist()
        self._update_display()

    def _fill_playlist(self):
        day = date.today() - timedelta(days=self.day_offset)
        self.day_label.configure(text=timeutil.fmt_day_header(day).upper())
        a, b = timeutil.day_bounds(day)
        now = time.time()
        projects = self.db.project_names()
        sel = self.listbox.curselection()
        self.listbox.delete(0, "end")
        self._pl_ids = []
        for i, e in enumerate(self.db.entries_between(a, b), start=1):
            name = e.description or "(bez naziva)"
            if e.project_id in projects:
                name += f" [{projects[e.project_id]}]"
            end = "..." if e.running else timeutil.fmt_time(e.end_ts)
            left = f"{i:>2}. {timeutil.fmt_time(e.start_ts)}-{end:<5} {name}"
            right = timeutil.fmt_clock(e.duration(now))
            room = PL_WIDTH - len(right) - 1
            if len(left) > room:
                left = left[: room - 1] + "~"
            self.listbox.insert("end", left.ljust(room) + " " + right)
            if e.running:
                self.listbox.itemconfigure("end", fg=skin.WHITE)
            self._pl_ids.append(e.id)
        if not self._pl_ids:
            self.listbox.insert("end", "  nema unosa za ovaj dan")
            self.listbox.itemconfigure(0, fg=skin.LCD_DIM)
        elif sel and sel[0] < len(self._pl_ids):
            self.listbox.selection_set(sel[0])
        self.total_label.configure(text=f"UKUPNO {timeutil.fmt_clock(reports.total_between(self.db, a, b, now))}")

    def _update_display(self):
        running = self.db.running_entry()
        now = time.time()
        state = self.state
        if running:
            secs = running.duration(now)
        elif self.paused:
            last = self.db.entries_between(now - 86400 * 7, now + 1)
            secs = last[-1].duration(now) if last else 0
        else:
            secs = 0
        h, rem = divmod(int(secs), 3600)
        text = f"{min(h, 99):02d}:{rem // 60:02d}:{rem % 60:02d}"
        if state == self.PAUSED and self._blink:
            self.clock.set("  :  :  ")
        else:
            self.clock.set(text, skin.LCD_ON if state != self.STOPPED else skin.LCD_DIM)
        self._draw_state_icon(state)

        task = self.task_var.get().strip() or "(bez naziva)"
        project = self.project_var.get().strip()
        if state == self.STOPPED:
            title = f"{APP_NAME.upper()}: upiši zadatak i pritisni PLAY"
        else:
            title = f"{task}" + (f" - {project}" if project else "")
        self.marquee.set_text(title)

        today = reports.total_between(self.db, *timeutil.period_bounds("today"), now)
        week = reports.total_between(self.db, *timeutil.period_bounds("this_week"), now)
        idle = self.settings["idle_minutes"]
        self.info.configure(text=f"DANAS   {timeutil.fmt_clock(today)}\nNEDELJA {timeutil.fmt_clock(week)}"
                                 f"   {'IDLE ' + str(idle) + 'm' if idle else 'IDLE OFF'}")
        if running:
            self.title(f"{text} {task} - {APP_NAME}")
        else:
            self.title(APP_NAME)
        tip = f"{text} {task}" if running else f"{APP_NAME}: tajmer stoji"
        key = (state, task, int(now // 60))
        if key != self._tray_key:
            self._tray_key = key
            self.tray.update(running is not None, tip)

    def _draw_state_icon(self, state: str):
        c = self.state_icon
        c.delete("all")
        s = skin.px(12)
        if state == self.PLAYING:
            c.create_polygon(1, 1, 1, s - 1, s - 1, s / 2, fill=skin.LCD_ON)
        elif state == self.PAUSED:
            c.create_rectangle(1, 1, s * 0.4, s - 1, fill=skin.LCD_ON, width=0)
            c.create_rectangle(s * 0.6, 1, s - 1, s - 1, fill=skin.LCD_ON, width=0)
        else:
            c.create_rectangle(1, 1, s - 1, s - 1, fill=skin.LCD_DIM, width=0)

    def _tick(self):
        if self._quitting:
            return
        self._blink = not self._blink
        self._update_display()
        running = self.db.running_entry()
        if running and self.day_offset == 0 and running.id in self._pl_ids and self._blink:
            self._fill_playlist()
        self.after(500, self._tick)

    # ---------------------------------------------------------------- actions

    def export(self, kind: str):
        a, b = timeutil.period_bounds(kind)
        name = f"vreme_{timeutil.ts_to_date(a).isoformat()}_{timeutil.ts_to_date(b - 1).isoformat()}.csv"
        path = filedialog.asksaveasfilename(parent=self, title="Izvezi CSV", defaultextension=".csv",
                                            initialfile=name, filetypes=[("CSV (Excel)", "*.csv")])
        if not path:
            return
        try:
            n = reports.export_csv(self.db, path, a, b)
        except OSError as exc:
            messagebox.showerror("Greška", f"Ne mogu da sačuvam fajl:\n{exc}", parent=self)
            return
        messagebox.showinfo("Izvoz", f"Sačuvano {n} unosa:\n{path}", parent=self)

    def _toggle_top(self):
        self.settings.update({"always_on_top": self.top_var.get()})
        self.attributes("-topmost", self.top_var.get())

    def _toggle_autostart(self):
        if not platform_win.set_autostart(APP_ID, self.autostart_var.get()):
            self.autostart_var.set(platform_win.is_autostart_enabled(APP_ID))

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
        except queue.Empty:
            pass
        self.after(500, self._poll_events)

    def _handle_idle(self, ev: IdleEvent):
        entry = self.db.get_entry(ev.entry_id)
        if self._idle_open or entry is None or not entry.running:
            return
        self._idle_open = True
        try:
            self.show()
            choice = IdleDialog(self, ev.idle_start, ev.idle_end).show()
        finally:
            self._idle_open = False
        if choice in (IdleDialog.DISCARD, IdleDialog.DISCARD_STOP):
            self.db.discard_interval(entry.id, ev.idle_start, ev.idle_end,
                                     continue_after=(choice == IdleDialog.DISCARD))
            self.paused = choice == IdleDialog.DISCARD_STOP
        self.refresh()

    # -------------------------------------------------------------- lifecycle

    def _restore_position(self):
        pos = self.settings["window_pos"]
        if not pos:
            return
        try:
            x, y = (int(v) for v in pos.split(","))
        except ValueError:
            return
        if 0 <= x < self.winfo_screenwidth() - 50 and 0 <= y < self.winfo_screenheight() - 50:
            self.geometry(f"+{x}+{y}")

    def show(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def on_close(self):
        if self.tray_available:
            self.withdraw()
        else:
            self.quit_app()

    def quit_app(self):
        if self._quitting:
            return
        if self.db.running_entry():
            self.show()
            answer = messagebox.askyesnocancel(
                "Izlaz", "Tajmer radi.\n\nDa: zaustavi ga i izađi\nNe: izađi, a vreme se i dalje računa",
                parent=self)
            if answer is None:
                return
            if answer:
                self.db.stop_running()
        if self.winfo_viewable():
            self.settings.update({"window_pos": f"{self.winfo_x()},{self.winfo_y()}"})
        self._quitting = True
        self.tracker.stop()
        self.tray.stop()
        self.destroy()
