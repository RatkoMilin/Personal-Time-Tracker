"""Smoke test for the tkinter UI: builds the player and drives the main flows.

Skipped when tkinter or a display is not available (run under xvfb-run on Linux CI).
"""

import os
import sys
import time

import pytest

tk = pytest.importorskip("tkinter")

from timetracker.config import Settings  # noqa: E402
from timetracker.db import Database  # noqa: E402
from timetracker.tracker import IdleEvent  # noqa: E402


def _has_display():
    if sys.platform == "win32":
        return True
    if not os.environ.get("DISPLAY"):
        return False
    try:
        tk.Tk().destroy()
        return True
    except tk.TclError:
        return False


pytestmark = pytest.mark.skipif(not _has_display(), reason="no display")


class FakePlatform:
    def idle_seconds(self):
        return 0.0


@pytest.fixture
def app(tmp_path):
    from timetracker.ui.player import Player

    db = Database(tmp_path / "t.db")
    win = Player(db, Settings(tmp_path / "s.json"), tmp_path, platform=FakePlatform(), start_tracker=False)
    win.update()
    yield win
    win._quitting = True
    win.destroy()
    db.close()


def test_play_pause_stop(app):
    app.task_var.set("Pisanje ponude")
    app.project_var.set("Klijent A")
    app.play()
    e = app.db.running_entry()
    assert e.description == "Pisanje ponude" and app.db.project_names()[e.project_id] == "Klijent A"
    assert app.state == app.PLAYING and app.listbox.size() == 1
    # Editing the fields while running updates the entry.
    app.task_var.set("Ponuda v2")
    app._apply_fields()
    assert app.db.running_entry().description == "Ponuda v2"
    app.pause()
    assert app.state == app.PAUSED and app.task_var.get() == "Ponuda v2"
    app.pause()  # pause again resumes as a new entry
    assert app.state == app.PLAYING and len(app.db.entries_between(0, time.time() + 1)) == 2
    app.stop()
    assert app.state == app.STOPPED and app.task_var.get() == ""
    for _ in range(3):
        app._tick()
    app.update()


def test_playlist_continue_delete_and_days(app):
    now = time.time()
    eid = app.db.add_entry("jutro", app.db.project_id("P"), now - 7200, now - 3600)
    app.refresh()
    assert "jutro [P]" in app.listbox.get(0)
    app.listbox.selection_set(0)
    app.continue_selected()
    assert app.db.running_entry().description == "jutro" and app.project_var.get() == "P"
    app.shift_day(1)
    assert app.day_offset == 1
    app.shift_day(-5)
    assert app.day_offset == 0
    app.toggle_playlist()
    assert not app.settings["show_playlist"]
    app.toggle_playlist()
    app.update()
    assert app.db.get_entry(eid)


def test_idle_discard(app, monkeypatch):
    from timetracker.ui import dialogs

    now = time.time()
    eid = app.db.start_entry("rad", start=now - 3600)
    monkeypatch.setattr(dialogs.IdleDialog, "show", lambda self: (self.destroy(), "discard")[1])
    app._handle_idle(IdleEvent(eid, now - 1800, now - 60))
    assert app.db.get_entry(eid).end_ts == pytest.approx(now - 1800)
    assert app.db.running_entry().start_ts == pytest.approx(now - 60)


def test_dialogs(app):
    from timetracker.ui import dialogs

    dlg = dialogs.EntryDialog(app, app.db)
    dlg.desc.set("sastanak")
    dlg.project.set("Interno")
    dlg.date.set("30.09.2026")
    dlg.start.set("9:00")
    dlg.end.set("10:30")
    dlg.ok()
    assert dlg.result["end"] - dlg.result["start"] == 5400
    assert dlg.result["project"] == "Interno"
    idle = dialogs.IdleDialog(app, 0, 900)
    idle.cancel()
    assert idle.result == "keep"
