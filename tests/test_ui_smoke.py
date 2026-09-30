"""Smoke test for the tkinter UI: builds the window and drives the main flows.

Skipped when tkinter or a display is not available (run under xvfb-run on Linux CI).
"""

import os
import sys
from datetime import date, datetime

import pytest

tk = pytest.importorskip("tkinter")

from timetracker.config import Settings  # noqa: E402
from timetracker.db import Database  # noqa: E402
from timetracker.tracker import IdleEvent, LongTimerEvent, ReminderEvent  # noqa: E402


def _has_display():
    if sys.platform == "win32":
        return True
    if not os.environ.get("DISPLAY"):
        return False
    try:
        r = tk.Tk()
        r.destroy()
        return True
    except tk.TclError:
        return False


pytestmark = pytest.mark.skipif(not _has_display(), reason="no display")


class FakePlatform:
    def idle_seconds(self):
        return 0.0

    def active_window(self):
        return ("code.exe", "main.py")

    def take_screenshot(self, path):
        return False


@pytest.fixture
def app(tmp_path, monkeypatch):
    from timetracker.ui import main_window

    db = Database(tmp_path / "t.db")
    settings = Settings(tmp_path / "settings.json")
    win = main_window.MainWindow(db, settings, tmp_path, platform=FakePlatform(), start_tracker=False)
    win.update()
    yield win
    win._quitting = True
    win.destroy()
    db.close()


def pump(win, n=3):
    for _ in range(n):
        win.update()


def test_start_stop_and_tabs(app):
    pid = app.db.add_project("Klijent A", hourly_rate=30)
    app.refresh_all()
    app.desc_entry.set_value("Pisanje ponude")
    app._set_project(pid)
    app.billable_var.set(True)
    app.start_timer()
    running = app.db.running_entry()
    assert running.description == "Pisanje ponude" and running.project_id == pid and running.billable
    assert app.tabs["entries"].tree.exists(f"e{running.id}")
    # Editing the bar while running updates the entry.
    app.desc_entry.set_value("Pisanje ponude v2")
    app._apply_bar_to_running()
    assert app.db.running_entry().description == "Pisanje ponude v2"
    app._tick()
    app.stop_timer()
    assert app.db.running_entry() is None

    for i in range(len(app.tabs)):
        app.notebook.select(i)
        pump(app)
    app.tabs["reports"].period.set("Ova godina")
    app.tabs["reports"].refresh()
    app.tabs["reports"].period.set("Danas")
    app.tabs["reports"].refresh()
    pump(app)


def test_manual_entries_and_reports(app):
    d = date.today()
    pid = app.db.add_project("P")
    s = datetime(d.year, d.month, d.day, 9).timestamp()
    eid = app.db.add_entry("jutarnji rad", pid, s, s + 5400, billable=True)
    app.db.add_activity("chrome.exe", "Mail", s, s + 600, eid)
    app.refresh_all()
    tab = app.tabs["entries"]
    tab.tree.selection_set(f"e{eid}")
    tab.duplicate()
    assert len(app.db.entries_between(s - 1, s + 6000)) == 2
    tab.tree.selection_set(f"e{eid}")
    tab.continue_selected()
    assert app.db.running_entry().description == "jutarnji rad"
    app.notebook.select(2)
    pump(app)
    rep = app.tabs["reports"]
    assert rep.proj_tree.get_children()
    app.notebook.select(3)
    pump(app)
    assert app.tabs["activity"].apps.exists("chrome")


def test_idle_event_discard(app, monkeypatch):
    from timetracker.ui import dialogs

    now = datetime.now().timestamp()
    eid = app.db.start_entry("rad", start=now - 3600)
    monkeypatch.setattr(dialogs.IdleDialog, "show", lambda self: (self.destroy(), "discard_continue")[1])
    app._handle_idle(IdleEvent(eid, now - 1800, now - 60))
    assert app.db.get_entry(eid).end_ts == pytest.approx(now - 1800)
    assert app.db.running_entry().start_ts == pytest.approx(now - 60)


def test_toasts_and_dialogs_render(app):
    app.events.put(ReminderEvent(900))
    app.events.put(LongTimerEvent(1, 5 * 3600))
    app._poll_events()
    pump(app)
    from timetracker.ui import dialogs

    dlg = dialogs.EntryDialog(app, app.db)
    dlg.duration.set("2:15")
    dlg._apply_duration()
    dlg.ok()
    assert dlg.result["end"] - dlg.result["start"] == 2.25 * 3600
    pdlg = dialogs.ProjectDialog(app)
    pdlg.name.set("Novi")
    pdlg.rate.set("12,5")
    pdlg.ok()
    assert pdlg.result == {"name": "Novi", "color": pdlg.color, "hourly_rate": 12.5}
    idle = dialogs.IdleDialog(app, 0, 900, "x")
    idle.cancel()
    assert idle.result == "keep"


def test_settings_save(app):
    tab = app.tabs["settings"]
    tab.vars["idle_minutes"].set(0)
    tab.vars["currency"].set("rsd")
    tab.save()
    assert app.settings["idle_minutes"] == 1
    assert app.settings["currency"] == "RSD"
