"""Smoke test for the tkinter UI: builds the player and drives the main flows.

Skipped when tkinter or a display is not available (run under xvfb-run on Linux CI).
"""

import gc
import os
import sys
import time
from datetime import date, datetime

import pytest

tk = pytest.importorskip("tkinter")

from timetracker import timeutil  # noqa: E402
from timetracker.config import Settings  # noqa: E402
from timetracker.db import Database  # noqa: E402
from timetracker.tracker import IdleEnd, IdleStart  # noqa: E402


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

    def active_window(self):
        return None


@pytest.fixture(scope="module")
def player(tmp_path_factory):
    # One window per module: creating many Tk interpreters in one process is unreliable on Windows.
    from timetracker.ui.player import Player

    tmp = tmp_path_factory.mktemp("ui")
    db = Database(tmp / "t.db")
    win = Player(db, Settings(tmp / "s.json"), tmp, platform=FakePlatform(), start_tracker=False)
    win.update()
    yield win
    win._quitting = True
    win.destroy()
    del win
    gc.collect()  # free Tk variables now, on this thread, not during a later test
    db.close()


@pytest.fixture
def app(player):
    player.db._exec("DELETE FROM entries")
    player.db._exec("DELETE FROM projects")
    player.paused = False
    player.day_offset = 0
    player.task_var.set("")
    player.project_var.set("")
    player.refresh()
    return player


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
    today = timeutil.day_start(date.today())  # fixed times inside today, whatever the clock says
    eid = app.db.add_entry("jutro", app.db.project_id("P"), today + 60, today + 120)
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


def test_idle_reminder_pops_up_and_discards(app):
    now = time.time()
    eid = app.db.start_entry("rad", start=now - 3600)
    app.events.put(IdleStart(eid, now - 1800))
    app._poll_events()
    rem = app.reminder
    assert rem is not None and rem.winfo_exists() and rem.idle_end is None
    assert "tajmer i dalje radi" in rem.detail.cget("text").lower()
    app.events.put(IdleEnd(eid, now - 1800, now - 60))
    app._poll_events()
    assert rem.idle_end == now - 60
    rem.choose(rem.DISCARD)
    assert app.reminder is None
    assert app.db.get_entry(eid).end_ts == pytest.approx(now - 1800)
    assert app.db.running_entry().start_ts == pytest.approx(now - 60)


def test_idle_reminder_discard_and_stop_while_away(app):
    now = time.time()
    eid = app.db.start_entry("rad", start=now - 3600)
    app.events.put(IdleStart(eid, now - 600))
    app._poll_events()
    app.reminder.choose("discard_stop")  # answered without an IdleEnd: ends at click time
    assert app.db.running_entry() is None
    assert app.db.get_entry(eid).end_ts == pytest.approx(now - 600)
    assert app.state == app.PAUSED


def test_every_skin_builds_and_ticks(app):
    from timetracker.ui import dialogs, skin

    app.task_var.set("skin test")
    app.play()
    for key in skin.THEMES:
        app.set_skin(key)
        assert skin.T.key == key and app.settings["skin"] == key
        for _ in range(2):
            app._tick()
        app.update()
        dlg = dialogs.EntryDialog(app, app.db)
        dlg.cancel()
        rem = dialogs.IdleReminder(app, 1, time.time() - 400, "x", lambda c, r: None)
        rem.choose(rem.KEEP)
    app.set_skin("matrix")
    app.stop()


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


def test_new_entry_just_after_midnight_defaults_to_today(app, monkeypatch):
    from timetracker.ui import dialogs

    d = date.today()
    monkeypatch.setattr(dialogs.time, "time", lambda: datetime(d.year, d.month, d.day, 0, 5).timestamp())
    dlg = dialogs.EntryDialog(app, app.db, day=d)
    assert dlg.date.get() == timeutil.fmt_date(timeutil.day_start(d))
    assert (dlg.start.get(), dlg.end.get()) == ("00:00", "00:05")
    dlg.cancel()


def test_productivity_meter_and_dashboard(app):
    from datetime import timedelta

    from timetracker.ui import dialogs

    # Yesterday is entirely in the past, so nothing is clipped at "now" whatever the clock says.
    yesterday = timeutil.day_start(date.today() - timedelta(days=1))
    app.db.add_activity("productive", "Google Docs", yesterday + 3600, yesterday + 2 * 3600)
    app.db.add_activity("distracting", "YouTube", yesterday + 3 * 3600, yesterday + 3 * 3600 + 1200)
    app.shift_day(1)
    app.update()
    assert app.meter.shares == pytest.approx((0.75, 0.0, 0.25))
    app.show_productivity()
    dlg = [w for w in app.winfo_children() if isinstance(w, dialogs.ProductivityDialog)][-1]
    dlg.update()
    labels = [w.cget("text") for w in dlg.body.winfo_children()[1].inner.winfo_children()]
    assert labels[0].lower().startswith("produktivno  1h 00m  (75%)")
    assert "YouTube" in labels[3]
    dlg.destroy()
    app.shift_day(-1)
    app.db._exec("DELETE FROM activity")
    app.refresh()
    assert app.meter.shares is None


def test_minimize_to_mini_bar_and_restore(app):
    app.task_var.set("Mini test")
    app.play()
    app._maybe_show_mini()  # not minimized: nothing happens (and wm_state, not the timer state, is checked)
    assert app.mini is None
    app.show_mini()
    app.update()
    assert app.mini is not None and app.mini.winfo_viewable() and not app.winfo_viewable()
    app._update_display()
    assert app.mini.task.cget("text") == "Mini test"
    assert app.mini.time.cget("text").count(":") == 2
    app.mini.play.command()  # pause from the mini bar
    assert app.state == app.PAUSED
    app.show()
    app.update()
    assert app.winfo_viewable() and not app.mini.winfo_viewable()
    app.stop()
