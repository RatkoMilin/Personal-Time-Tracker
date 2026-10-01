"""The main window: a small skinnable player with a playlist of time entries."""

from __future__ import annotations

import queue
import random
import threading
import time
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox

from .. import APP_ID, APP_NAME, __version__, platform_win, productivity, reports, sounds, timeutil, tray, updater
from ..config import Settings
from ..db import Database
from ..tracker import IdleEnd, IdleStart, Tracker
from . import skin
from .dandelion import DandelionColumn, FieldStrip, GradientStrip
from .dialogs import EntryDialog, IdleReminder, MiniBar, ProductivityDialog, SitesDialog

PL_WIDTH = 50  # playlist width in characters
FIELD_TOP = "#d8edc6"  # the meadow's first green (Maslačko skin)
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
        self._tray_key = None
        self._scramble_left = 0
        self._clock_text = ""
        self.reminder: IdleReminder | None = None
        self.mini: MiniBar | None = None
        self.task_var = tk.StringVar()
        self.project_var = tk.StringVar()

        self.title(APP_NAME)
        self.resizable(False, False)
        skin.set_window_icon(self)
        self.attributes("-topmost", settings["always_on_top"])

        self.tracker = Tracker(db, settings, self.events, **({"platform": platform} if platform else {}))
        self.tray = tray.Tray(self.events.put, self.show, self.play_pause, self.quit_app,
                              lambda: self.db.running_entry() is not None)
        self.tray_available = False
        self.sounds = sounds.SoundPlayer(data_dir / "sounds", lambda: self.settings["sounds"], lambda: skin.T.dark_variant or skin.T.key)

        running = db.running_entry()
        if running:
            self.task_var.set(running.description)
            self.project_var.set(db.project_names().get(running.project_id, ""))
        self._build_ui()
        self.bind("<Button-3>", self._popup_menu)  # root binding tag: any widget in this window
        self.bind_all("<Control-space>", lambda e: self.play_pause())
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Unmap>", self._on_unmap)
        self._restore_position()
        if start_tracker:
            self.tracker.start()
            self.tray_available = self.tray.start()
            exe = updater.running_exe()
            if exe:
                updater.cleanup(exe, self.data_dir / "update")
            self.after(30_000, self._schedule_update_check)
        if start_minimized and self.tray_available:
            self.withdraw()
        self.after(500, self._poll_events)
        self.after(250, self._tick)

    # ------------------------------------------------------------------ layout

    def _skin_key(self) -> str:
        """Theme to show: the chosen skin, or its lit variant while the timer runs (lamp skins)."""
        theme = skin.THEMES.get(self.settings["skin"], skin.THEMES["matrix"])
        if theme.hidden:
            theme = skin.THEMES.get(theme.dark_variant, skin.THEMES["matrix"])
        if theme.lit_variant and self.db.running_entry():
            return theme.lit_variant
        return theme.key

    def _build_ui(self):
        T = skin.use(self, self._skin_key())
        self.sounds.prepare(T.dark_variant or T.key)
        self.ui = tk.Frame(self, bg=T.body)
        self.ui.pack(fill="both", expand=True)
        self.content = self.ui
        self.side = self.field = self.field_fade = None
        if T.side == "dandelion":  # the flower's strip on the right, the far meadow along the bottom
            self.content = tk.Frame(self.ui, bg=T.body)
            self.content.pack(side="left", fill="both", expand=True)
            self.side = DandelionColumn(self.ui, self._dandelion_bands, lambda: self.settings["dandelion_blown"],
                                        self._dandelion_blown)
            self.side.pack(side="right", fill="y")
            bottom = tk.Frame(self.content, bg=T.body)
            bottom.pack(side="bottom", fill="x")
            self.field_fade = GradientStrip(bottom, T.body, FIELD_TOP)
            self.field_fade.pack(fill="x")
            self.field = FieldStrip(bottom)
            self.field.pack(fill="x")
        self._build_menu()
        self.titlebar = skin.TitleBar(self.content, APP_NAME, self._popup_menu)
        self.titlebar.pack(fill="x")
        self._build_main()
        self._build_playlist()
        if self.settings["show_playlist"]:
            self.pl_outer.pack(fill="x")
        self._fade_to_field()
        if self.side is not None:  # follow the sections' layout (e.g. the playlist opening)
            self.content.bind("<Configure>", lambda e: self.after_idle(self.side.refresh))
        self.refresh()

    def set_skin(self, key: str):
        if key == self.settings["skin"] or key not in skin.THEMES:
            return
        self.settings.update({"skin": key})
        if self.mini is not None:  # rebuilt in the new skin the next time it is shown
            self.mini.destroy()
            self.mini = None
        self._rebuild_ui()
        self.sounds.play("start")  # a taste of the new skin

    def _rebuild_ui(self):
        self._scramble_left = 0
        self.ui.destroy()
        for menu in (self.menu, self.row_menu):
            menu.destroy()
        self._build_ui()

    def _click(self, command, event: str = "click"):
        """Wrap a button command so it plays the skin's click sound (or another effect) first."""
        def run():
            self.sounds.play(event)
            command()
        return run

    def _build_main(self):
        T = skin.T
        main = tk.Frame(self.content, bg=T.body, padx=skin.px(6), pady=skin.px(4))
        main.pack(fill="x")

        panel = skin.Panel(main, pad=5)
        panel.pack(fill="x")
        lcd = panel.inner
        self.clock = self.dial = self.marquee = None
        if T.display == "analog":
            self.dial = skin.AnalogDial(lcd)
            self.dial.pack(side="left")
            right = tk.Frame(lcd, bg=T.lcd_bg)
            right.pack(side="left", padx=(skin.px(12), 0), fill="both", expand=True)
            self.task_label = tk.Label(right, bg=T.lcd_bg, fg=T.lcd_text, font=T.font("sans", 11, "italic"),
                                       anchor="w")
            self.task_label.pack(fill="x", pady=(skin.px(4), 0))
            self.elapsed_label = tk.Label(right, bg=T.lcd_bg, fg=T.lcd_on, font=T.font("sans", 20), anchor="w")
            self.elapsed_label.pack(fill="x")
        else:
            self.state_icon = tk.Canvas(lcd, width=skin.px(12), height=skin.px(12), bg=T.lcd_bg,
                                        highlightthickness=0)
            self.state_icon.pack(side="left", anchor="n", padx=(0, skin.px(6)), pady=(skin.px(2), 0))
            if T.clock_deco == "oranges":
                fruit = tk.Canvas(lcd, width=skin.px(30), height=skin.px(36), bg=T.lcd_bg, highlightthickness=0)
                skin.draw_orange(fruit, skin.px(15), skin.px(21), skin.px(11))
                fruit.pack(side="left", padx=(0, skin.px(6)))
            self.clock = skin.SevenSegment(lcd)
            self.clock.pack(side="left")
            right = tk.Frame(lcd, bg=T.lcd_bg)
            right.pack(side="left", padx=(skin.px(12), 0), fill="x", expand=True)
            if T.marquee:
                self.marquee = skin.Marquee(right, chars=24)
                self.marquee.pack(anchor="w")
        self.info = tk.Label(right, text="", bg=T.lcd_bg, fg=T.lcd_dim, font=T.font("mono", 8), justify="left",
                             anchor="w")
        self.info.pack(anchor="w", fill="x", pady=(skin.px(2), 0))

        row = tk.Frame(main, bg=T.body)
        row.pack(fill="x", pady=(skin.px(5), 0))
        skin.label(row, "Zadatak").grid(row=0, column=0, sticky="w")
        skin.label(row, "Projekat").grid(row=0, column=1, sticky="w", padx=(skin.px(6), 0))
        task_panel, self.task_entry = skin.field(row, self.task_var, 26, bg=T.task_bg or None, fg=T.task_fg or None)
        task_panel.grid(row=1, column=0, sticky="we")
        proj_panel, self.project_cb = skin.combo(row, self.project_var, 15)
        proj_panel.grid(row=1, column=1, sticky="we", padx=(skin.px(6), 0))
        row.columnconfigure(0, weight=1)
        for w in (self.task_entry, self.project_cb):
            w.bind("<Return>", self._enter)
            w.bind("<FocusOut>", lambda e: self._apply_fields(), add="+")
        self.project_cb.bind("<<ComboboxSelected>>", lambda e: self._apply_fields())

        buttons = tk.Frame(main, bg=T.body)
        buttons.pack(fill="x", pady=(skin.px(6), skin.px(2)))
        self.play_btn = skin.SkinButton(buttons, self.play, glyph="play", tooltip="Start (Enter)")
        self.play_btn.pack(side="left")
        skin.SkinButton(buttons, self.pause, glyph="pause", tooltip="Pauza").pack(side="left", padx=2)
        skin.SkinButton(buttons, self.stop, glyph="stop", tooltip="Stop").pack(side="left")
        skin.SkinButton(buttons, self._click(self._export_menu), glyph="eject", tooltip="Izvezi u Excel (CSV)").pack(
            side="left", padx=(skin.px(6), 0))
        skin.SkinButton(buttons, self._click(self.toggle_playlist, "pl"), text="PL", tooltip="Prikaži/sakrij listu").pack(
            side="right")

    def _build_playlist(self):
        T = skin.T
        bg = T.pl_body or T.body
        self.pl_outer = tk.Frame(self.content, bg=bg)
        if T.pl_body:  # the playlist section has its own color: blend into it
            GradientStrip(self.pl_outer, T.body, T.pl_body).pack(fill="x")
        self.pl_frame = tk.Frame(self.pl_outer, bg=bg, padx=skin.px(6), pady=skin.px(2))
        self.pl_frame.pack(fill="x")
        head = tk.Frame(self.pl_frame, bg=bg)
        head.pack(fill="x", pady=(0, skin.px(3)))
        skin.SkinButton(head, self._click(lambda: self.shift_day(1)), glyph="prev", width=18, height=16,
                        tooltip="Prethodni dan").pack(side="left")
        self.day_label = skin.label(head, "", fg=T.accent)
        self.day_label.pack(side="left", expand=True)
        skin.SkinButton(head, self._click(lambda: self.shift_day(-1)), glyph="next", width=18, height=16,
                        tooltip="Sledeći dan").pack(side="right")

        panel = self.pl_panel = skin.Panel(self.pl_frame, pad=2, pattern=T.pl_pattern, bg=T.list_bg or None,
                                           plain=T.pl_plain)
        panel.pack(fill="x")
        self.listbox = tk.Listbox(panel.inner, width=PL_WIDTH, height=8, bg=T.list_bg or T.lcd_bg,
                                  fg=T.list_fg or T.lcd_text,
                                  selectbackground=T.sel_bg, selectforeground=T.sel_fg, font=T.font("mono", 9),
                                  relief="flat", highlightthickness=0, activestyle="none", bd=0)
        self.listbox.pack(fill="both")
        self.listbox.bind("<Double-1>", lambda e: self.continue_selected())
        self.listbox.bind("<Delete>", lambda e: self.delete_selected())
        self.listbox.bind("<Return>", lambda e: self.edit_selected())
        self.listbox.bind("<Button-3>", self._row_menu)

        self.meter = skin.ProductivityMeter(self.pl_frame, self._click(self.show_productivity),
                                            walnuts=self._walnuts_today(), on_walnut=self._save_walnuts)
        self.meter.pack(fill="x", pady=(skin.px(3), 0))

        foot = tk.Frame(self.pl_frame, bg=bg)
        foot.pack(fill="x", pady=(skin.px(3), skin.px(4)))
        skin.SkinButton(foot, self._click(self.add_entry), text="+ Dodaj", tooltip="Ručno dodaj vreme").pack(side="left")
        skin.SkinButton(foot, self._click(self.edit_selected), text="Izmeni").pack(side="left", padx=2)
        skin.SkinButton(foot, self._click(self.delete_selected), text="Obriši").pack(side="left")
        self.total_label = tk.Label(foot, text="", bg=bg, fg=T.text, font=T.font("mono", 9, "bold"))
        self.total_label.pack(side="right")

        self.row_menu = tk.Menu(self, tearoff=False)
        self.row_menu.add_command(label="Nastavi ovaj zadatak", command=self.continue_selected)
        self.row_menu.add_command(label="Izmeni", command=self.edit_selected)
        self.row_menu.add_command(label="Obriši", command=self.delete_selected)

    def _build_menu(self):
        self.menu = tk.Menu(self, tearoff=False)
        skins = tk.Menu(self.menu, tearoff=False)
        self.skin_var = tk.StringVar(value=self.settings["skin"])
        for theme in skin.THEMES.values():
            if theme.hidden:
                continue
            skins.add_radiobutton(label=theme.name, value=theme.key, variable=self.skin_var,
                                  command=lambda: self.set_skin(self.skin_var.get()))
        self.menu.add_cascade(label="Skin", menu=skins)
        self.sounds_var = tk.BooleanVar(value=self.settings["sounds"])
        self.menu.add_checkbutton(label="Zvučni efekti", variable=self.sounds_var,
                                  command=lambda: self.settings.update({"sounds": self.sounds_var.get()}))
        self.menu.add_command(label="Produktivni sajtovi i programi...", command=self.edit_sites)
        self.idle_var = tk.IntVar(value=self.settings["idle_minutes"])
        idle = tk.Menu(self.menu, tearoff=False)
        for minutes, text in IDLE_CHOICES:
            idle.add_radiobutton(label=text, value=minutes, variable=self.idle_var,
                                 command=lambda: self.settings.update({"idle_minutes": self.idle_var.get()}))
        self.menu.add_cascade(label="Podsetnik za neaktivnost posle", menu=idle)
        self.top_var = tk.BooleanVar(value=self.settings["always_on_top"])
        self.menu.add_checkbutton(label="Uvek na vrhu", variable=self.top_var, command=self._toggle_top)
        self.update_var = tk.BooleanVar(value=self.settings["auto_update"])
        self.menu.add_checkbutton(label="Automatsko ažuriranje", variable=self.update_var,
                                  command=lambda: self.settings.update({"auto_update": self.update_var.get()}))
        version = updater.build_version()
        self.menu.add_command(label=f"Proveri ažuriranje (verzija {version or __version__ + ' dev'})",
                              command=lambda: self.check_for_update(manual=True))
        self.mini_var = tk.BooleanVar(value=self.settings["mini_bar"])
        self.menu.add_checkbutton(label="Umanjeno: mini traka dole", variable=self.mini_var,
                                  command=lambda: self.settings.update({"mini_bar": self.mini_var.get()}))
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
        self.sounds.play("start")
        self.refresh()
        self._scramble()
        if skin.T.confetti:
            skin.confetti(self)
        if skin.T.play_fx == "bullet":  # My Passion: the play button gets shot
            self.play_btn.bullet_hole()

    def pause(self):
        if self.db.running_entry():
            self._apply_fields()
            self.db.stop_running()
            self.paused = True
            self.sounds.play("pause")
            self.refresh()
            self._scramble()
        elif self.paused:
            self.play()

    def play_pause(self):
        if self.db.running_entry():
            self.pause()
        else:
            self.play()

    def stop(self):
        self._apply_fields()
        if self.db.running_entry() or self.paused:
            self.sounds.play("stop")
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
        self.sounds.play("start")
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
        show = not self.settings["show_playlist"]  # not winfo_ismapped: false until the first redraw
        if show:
            self.pl_outer.pack(fill="x")
            if skin.T.pl_pattern == "bubbles":
                self.update_idletasks()
                if skin.bubbles(self.pl_frame) is None:  # no see-through windows: bubbles along the edges
                    self.pl_panel.bubble_burst()
        else:
            self.pl_outer.pack_forget()
        self.settings.update({"show_playlist": show})
        self._fade_to_field()

    # ---------------------------------------------------------------- refresh

    def refresh(self):
        """Rebuild everything that depends on the database."""
        if self._skin_key() != skin.T.key:  # lamp skin: lit only while the timer runs
            self._rebuild_ui()  # builds and refreshes everything
            return
        self.project_cb.configure(values=list(self.db.project_names().values()))
        self._fill_playlist()
        self._update_display()

    def _fill_playlist(self):
        T = skin.T
        day = date.today() - timedelta(days=self.day_offset)
        self.day_label.configure(text=T.tx(timeutil.fmt_day_header(day)))
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
                self.listbox.itemconfigure("end", fg=T.list_run or T.lcd_on)
            self._pl_ids.append(e.id)
        if not self._pl_ids:
            self.listbox.insert("end", "  nema unosa za ovaj dan")
            self.listbox.itemconfigure(0, fg=T.list_fg or T.lcd_dim)
        elif sel and sel[0] < len(self._pl_ids):
            self.listbox.selection_set(sel[0])
        total = timeutil.fmt_clock(reports.total_between(self.db, a, b, now))
        self.total_label.configure(text=T.tx(f"Ukupno {total}"))
        self._update_meter()

    def _viewed_day(self) -> date:
        return date.today() - timedelta(days=self.day_offset)

    def _update_meter(self):
        s = productivity.summarize(self.db, *timeutil.day_bounds(self._viewed_day()))
        today = self.day_offset == 0
        walnuts = set(self._walnuts_today()) if today else set()
        self.meter.walnut_ok = today
        if walnuts != self.meter.walnuts:
            self.meter.walnuts = walnuts
            self.meter.draw()
        self.meter.set(s.seconds[productivity.PRODUCTIVE], s.seconds[productivity.NEUTRAL],
                       s.seconds[productivity.DISTRACTING], s.total)

    # ------------------------------------------------------------- dandelion

    def _fade_to_field(self):
        """The strip above the meadow starts from whichever section is last (main or playlist)."""
        if self.field_fade is not None:
            T = skin.T
            self.field_fade.top = T.pl_body if self.settings["show_playlist"] and T.pl_body else T.body
            self.field_fade.draw()

    def _dandelion_bands(self) -> list[tuple[float, str]]:
        """Background stops for the dandelion strip, lined up with the sections on its left."""
        T = skin.T
        stops = [(0, T.body)]
        last = T.body
        if self.settings["show_playlist"] and T.pl_body and self.pl_outer.winfo_ismapped():
            y = self.pl_outer.winfo_y()
            stops += [(y, T.body), (y + skin.px(10), T.pl_body)]
            last = T.pl_body
        if self.field_fade is not None:
            y = self.field_fade.master.winfo_y()
            stops += [(y, last), (y + skin.px(10), FIELD_TOP)]
        return stops

    def _dandelion_blown(self, day: str):
        self.sounds.play("start")  # a gust of wind
        self.settings.update({"dandelion_blown": day})

    def _walnuts_today(self) -> list[int]:
        """Flowers turned into walnuts today (they stay walnuts until the next day)."""
        if self.settings["walnut_day"] != date.today().isoformat():
            return []
        return [i for i in self.settings["walnuts"] if isinstance(i, int)]

    def _save_walnuts(self, walnuts: list[int]):
        self.sounds.play("click")
        self.settings.update({"walnut_day": date.today().isoformat(), "walnuts": walnuts})

    def edit_sites(self):
        today = productivity.summarize(self.db, *timeutil.day_bounds(date.today()))
        others = [label for label, _ in today.labels.get(productivity.NEUTRAL, []) if label != "nepoznato"]
        SitesDialog(self, self.settings["extra_productive"], self.settings["extra_distracting"], others,
                    self.save_sites)

    def save_sites(self, productive: list[str], distracting: list[str]):
        """New productive / distracting words: used right away, and today's matching programs move over."""
        self.settings.update({"extra_productive": productive, "extra_distracting": distracting})
        self.tracker.classifier = productivity.Classifier(productive, distracting)
        since = timeutil.day_bounds(date.today())[0]
        for words, category in ((productive, productivity.PRODUCTIVE), (distracting, productivity.DISTRACTING)):
            for word in words:
                if word.lower().endswith(".exe"):
                    self.db.recategorize_activity(productivity.program_name(word), category, since)
        self._update_meter()

    def show_productivity(self):
        day = self._viewed_day()
        ProductivityDialog(self, productivity.summarize(self.db, *timeutil.day_bounds(day)),
                           skin.T.tx(timeutil.fmt_day_header(day)))

    def _update_display(self):
        T = skin.T
        running = self.db.running_entry()
        now = time.time()
        state = self.state
        # The clock shows today's total for the task, so pause / play and "Nastavi" continue counting.
        if running:
            secs = reports.task_total(self.db, running.description, running.project_id, now)
        elif self.paused:
            last = self.db.entries_between(now - 86400 * 7, now + 1)
            secs = reports.task_total(self.db, last[-1].description, last[-1].project_id, now) if last else 0
        else:
            secs = 0
        h, rem = divmod(int(secs), 3600)
        text = f"{min(h, 99):02d}:{rem // 60:02d}:{rem % 60:02d}"
        self._clock_text = text
        if T.title_style == "oranges":
            self.titlebar.set_pieces(skin.orange_pieces(secs) if state != self.STOPPED else [])
        task = self.task_var.get().strip() or "(bez naziva)"
        project = self.project_var.get().strip()
        today = reports.total_between(self.db, *timeutil.period_bounds("today"), now)

        if self.dial is not None:
            self.dial.set_seconds(secs)
            status = {self.PLAYING: "u toku", self.PAUSED: "pauza", self.STOPPED: "stoji"}[state]
            self.task_label.configure(text=(task + (f" · {project}" if project else ""))[:34]
                                      if state != self.STOPPED else "upiši zadatak i pritisni ▶")
            self.elapsed_label.configure(text=f"{h}:{rem // 60:02d}:{rem % 60:02d}",
                                         fg=T.lcd_on if state == self.PLAYING else T.lcd_dim)
            self.info.configure(text=f"danas {timeutil.fmt_hours(today)}  ·  {status}")
        else:
            if self._scramble_left > 0:
                pass  # the digits are jumbling (Matrix play/pause)
            elif state == self.PAUSED and self._blink and T.blink:
                self.clock.set("  :  :  ")
            else:
                self.clock.set(text, T.lcd_on if state != self.STOPPED else T.lcd_dim)
            self._draw_state_icon(state)
            if self.marquee is not None:
                title = (f"{task}" + (f" - {project}" if project else "") if state != self.STOPPED
                         else f"{APP_NAME}: upiši zadatak i pritisni PLAY")
                self.marquee.set_text(title)
            week = reports.total_between(self.db, *timeutil.period_bounds("this_week"), now)
            idle = self.settings["idle_minutes"]
            self.info.configure(text=T.tx(f"Danas   {timeutil.fmt_clock(today)}\nNedelja {timeutil.fmt_clock(week)}"
                                          f"   {'Idle ' + str(idle) + 'm' if idle else 'Idle off'}"))

        self.title(f"{text} {task} - {APP_NAME}" if running else APP_NAME)
        if self.mini is not None and self.mini.winfo_viewable():
            self.mini.update_view(state, text if running or state == self.PAUSED else "--:--:--",
                                  task if state != self.STOPPED else "tajmer stoji")
        tip = f"{text} {task}" if running else f"{APP_NAME}: tajmer stoji"
        key = (state, task, int(now // 60))
        if key != self._tray_key:
            self._tray_key = key
            self.tray.update(running is not None, tip)

    def _scramble(self, frames: int = 12):
        """Matrix: the digits jumble for a moment like a broken clock, then settle one by one."""
        if not skin.T.scramble or self.clock is None:
            return
        self._scramble_left = frames
        settle = [random.randint(frames // 3, frames) for _ in range(8)]

        def step():
            if self._quitting or self.clock is None or not self.clock.winfo_exists():
                self._scramble_left = 0
                return
            self._scramble_left -= 1
            if self._scramble_left <= 0:
                self._update_display()
                return
            frame = frames - self._scramble_left
            shown = "".join(ch if ch == ":" or frame >= settle[i] else random.choice("0123456789")
                            for i, ch in enumerate(self._clock_text))
            self.clock.set(shown, skin.T.lcd_on)
            self.after(50, step)

        step()

    def _draw_state_icon(self, state: str):
        T = skin.T
        c = self.state_icon
        c.delete("all")
        s = skin.px(12)
        if state == self.PLAYING:
            c.create_polygon(1, 1, 1, s - 1, s - 1, s / 2, fill=T.lcd_on)
        elif state == self.PAUSED:
            c.create_rectangle(1, 1, s * 0.4, s - 1, fill=T.lcd_on, width=0)
            c.create_rectangle(s * 0.6, 1, s - 1, s - 1, fill=T.lcd_on, width=0)
        else:
            c.create_rectangle(1, 1, s - 1, s - 1, fill=T.lcd_dim, width=0)

    def _tick(self):
        if self._quitting:
            return
        self._blink = not self._blink
        self._update_display()
        running = self.db.running_entry()
        if running and self.day_offset == 0 and running.id in self._pl_ids and self._blink:
            self._fill_playlist()
        if self.side is not None:
            self.side.refresh()
            self.field.refresh()
        self._meter_ticks = getattr(self, "_meter_ticks", 0) + 1
        if self._meter_ticks % 30 == 0:  # activity is recorded with or without a timer: refresh every 15 s
            self._update_meter()
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
                elif isinstance(ev, IdleStart):
                    self._idle_started(ev)
                elif isinstance(ev, IdleEnd):
                    if self.reminder is not None and self.reminder.entry_id == ev.entry_id:
                        self.reminder.user_back(ev.idle_end)
        except queue.Empty:
            pass
        self.after(500, self._poll_events)

    def _idle_started(self, ev: IdleStart):
        """Idle limit reached while the timer runs: pop up the reminder right away."""
        entry = self.db.get_entry(ev.entry_id)
        if self.reminder is not None or entry is None or not entry.running:
            return
        self.reminder = IdleReminder(self, entry.id, ev.idle_start, entry.description, self._idle_answered)
        # The reminder always makes a sound, even with effects off (then the plain system one).
        if not self.sounds.play("alert") and not platform_win.alert_sound():
            self.bell()

    def _idle_answered(self, choice: str, reminder: IdleReminder):
        self.reminder = None
        if choice in (IdleReminder.DISCARD, IdleReminder.DISCARD_STOP):
            self.db.discard_interval(reminder.entry_id, reminder.idle_start, reminder.idle_end,
                                     continue_after=(choice == IdleReminder.DISCARD))
            if choice == IdleReminder.DISCARD_STOP:
                self.paused = True
        self.refresh()

    # ---------------------------------------------------------------- updates

    def _schedule_update_check(self):
        if self._quitting:
            return
        if self.settings["auto_update"]:
            self.check_for_update()
        self.after(6 * 3600 * 1000, self._schedule_update_check)

    def check_for_update(self, manual: bool = False):
        """Look for a newer release in the background; download it and install it when found."""
        def work():
            try:
                found = updater.check(updater.build_version())
                if found is None:
                    if manual:
                        self.events.put(lambda: messagebox.showinfo(
                            "Ažuriranje", "Imaš najnoviju verziju." if updater.build_version()
                            else "Samoažuriranje radi samo u exe verziji sa stranice Releases.", parent=self))
                    return
                path = updater.download(found, self.data_dir / "update")
                self.events.put(lambda: self._apply_update(path, found.version))
            except Exception as exc:  # offline, GitHub down, bad download: try again later
                if manual:
                    msg = f"Provera nije uspela:\n{exc}"
                    self.events.put(lambda: messagebox.showwarning("Ažuriranje", msg, parent=self))

        threading.Thread(target=work, name="updater", daemon=True).start()

    def _apply_update(self, new_exe, version: str):
        exe = updater.running_exe()
        if exe is None or self._quitting:
            return
        if self.reminder is not None or self.grab_current() is not None:  # an open dialog: try again later
            self.after(5 * 60 * 1000, lambda: self._apply_update(new_exe, version))
            return
        try:
            updater.install(new_exe, exe)
        except OSError:
            return
        if self.winfo_viewable():
            self.settings.update({"window_pos": f"{self.winfo_x()},{self.winfo_y()}"})
        self._quitting = True
        self.tracker.stop()
        self.tray.stop()
        updater.restart(exe)
        self.destroy()

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
        if self.mini is not None:
            self.mini.withdraw()
        self.deiconify()
        self.lift()
        self.focus_force()

    def _on_unmap(self, event):
        # Minimize button: swap the window for the see-through mini bar at the bottom of the screen.
        if event.widget is self and not self._quitting and self.settings["mini_bar"]:
            self.after(10, self._maybe_show_mini)

    def _maybe_show_mini(self):
        if self._quitting or self.wm_state() != "iconic":  # wm_state: `state` is the timer state here
            return
        self.show_mini()

    def show_mini(self):
        self.withdraw()
        if self.mini is None:
            self.mini = MiniBar(self, self.show, self.play_pause)
        self.mini.show(platform_win.work_area())
        self._update_display()
        self.mini._place()

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
        if self.mini is not None:
            self.mini.destroy()
        self.destroy()
