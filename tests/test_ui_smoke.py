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
    for key, theme in skin.THEMES.items():
        if theme.hidden:
            continue
        app.set_skin(key)
        # lamp skins show their lit variant while the timer runs
        assert skin.T.key == (theme.lit_variant or key) and app.settings["skin"] == key
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


def test_skin_menu_hides_lamp_variants(app):
    from timetracker.ui import skin

    menu = app.menu.nametowidget(app.menu.entrycget("Skin", "menu"))
    names = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)]
    assert names == [t.name for t in skin.THEMES.values() if not t.hidden]
    assert all("(" not in n for n in names)


def test_egg_lamp_is_lit_only_while_working(app):
    from timetracker.ui import skin

    app.set_skin("egg")
    assert skin.T.key == "egg"
    app.task_var.set("Lampa")
    app.play()
    assert skin.T.key == "egg_lit" and app.settings["skin"] == "egg"
    app.pause()
    assert skin.T.key == "egg"
    app.pause()  # resume
    assert skin.T.key == "egg_lit"
    app.stop()
    assert skin.T.key == "egg"
    app.set_skin("matrix")


def test_matrix_digits_jumble_on_play_and_pause(app):
    from timetracker.ui import skin

    app.set_skin("matrix")
    app.task_var.set("Matrix")
    app.play()
    assert app._scramble_left > 0
    deadline = time.time() + 3
    while app._scramble_left > 0 and time.time() < deadline:
        app.update()
        time.sleep(0.02)
    assert app._scramble_left == 0
    app.pause()
    assert app._scramble_left > 0
    app.stop()
    assert skin.T.scramble


def test_setsuna_oranges_grow_with_running_time(app):
    from timetracker.ui import skin

    assert skin.orange_pieces(14 * 60) == []
    assert skin.orange_pieces(15 * 60) == ["q"]
    assert skin.orange_pieces(30 * 60) == ["h"]
    assert skin.orange_pieces(45 * 60) == ["h", "q"]
    assert skin.orange_pieces(60 * 60) == ["w"]
    assert skin.orange_pieces(2 * 3600 + 50 * 60) == ["w", "w", "h", "q"]
    app.set_skin("setsuna")
    app.task_var.set("Setsuna")
    app.play()  # confetti: an overlay window on Windows, nothing where windows cannot be see-through
    entry = app.db.running_entry()
    app.db.update_entry(entry.id, entry.description, entry.project_id, time.time() - 75 * 60, None)
    app._update_display()
    assert app.titlebar.pieces == ["w", "q"]
    app.update()
    app.stop()
    assert app.titlebar.pieces == []
    app.set_skin("matrix")


def test_effect_painters_draw_frames(app):
    from timetracker.ui import skin

    c = tk.Canvas(app, width=300, height=200)
    for painter, frames in ((skin.confetti_painter(("#DB4C01", "#111111"), seed=1), 60),
                            (skin.bubble_painter(("#8fb8ec",), seed=1, frames=75), 75)):
        drawn = 0
        for i in range(frames):
            c.delete("all")
            painter(c, i, 300, 200)
            drawn += len(c.find_all())
        assert drawn > 0
    c.destroy()
    app.set_skin("pastel")
    app.toggle_playlist()
    app.toggle_playlist()  # opening the playlist bubbles
    app.update()
    app.set_skin("matrix")


def test_walnut_flowers_stay_for_the_day(app):
    from datetime import timedelta

    app.set_skin("wood")
    if not app.settings["show_playlist"]:
        app.toggle_playlist()
    app.db.add_activity("productive", "Word", time.time() - 600, time.time() - 1)
    app.refresh()
    app.update()
    meter = app.meter
    flowers = sorted({t for i in meter.find_all() for t in meter.gettags(i) if t.startswith("flower")})
    assert flowers, "a fully productive branch has flowers"
    x0, y0, x1, y1 = meter.bbox(flowers[1])
    meter._clicked(type("E", (), {"x": (x0 + x1) / 2, "y": (y0 + y1) / 2})())
    index = int(flowers[1][6:])
    assert app.settings["walnuts"] == [index] and app.settings["walnut_day"] == date.today().isoformat()
    assert f"flower{index}" not in {t for i in meter.find_all() for t in meter.gettags(i)}
    app.set_skin("matrix")
    app.set_skin("wood")
    assert app.meter.walnuts == {index}
    app.settings.update({"walnut_day": (date.today() - timedelta(days=1)).isoformat()})
    app._update_meter()
    assert app.meter.walnuts == set()
    app.db._exec("DELETE FROM activity")
    app.set_skin("matrix")


def test_cat_on_the_meter_at_80_percent(app):
    app.set_skin("cat")
    if not app.settings["show_playlist"]:
        app.toggle_playlist()
    app.update()
    meter = app.meter
    meter.set(70, 0, 30, 100)
    assert meter.cat_box is None
    meter.set(85, 10, 5, 100)
    assert meter.cat_box is not None
    kinds = set()
    for _ in range(3):
        kinds.add(meter.animate_cat())
        meter.animating = False
    assert kinds == {"tail", "blink", "paw"}
    x0, y0, x1, y1 = meter.cat_box
    meter.animating = False
    meter._clicked(type("E", (), {"x": (x0 + x1) / 2, "y": (y0 + y1) / 2})())
    assert meter.animating
    app.update()
    app.set_skin("matrix")


def test_mondrian_colors(app):
    from timetracker.ui import skin

    app.set_skin("mondrian")
    assert app.listbox.cget("bg") == skin.MONDRIAN_RED
    assert app.task_entry.cget("bg") == skin.MONDRIAN_BLUE
    app._tick()
    app.update()
    app.set_skin("matrix")


def test_productive_sites_dialog(app):
    from timetracker import productivity
    from timetracker.ui import dialogs

    assert dialogs.parse_words(" figma \n\ncanva.com, Figma\nblender.exe") == ["figma", "canva.com", "blender.exe"]
    app.db.add_activity("neutral", "Krita", time.time() - 300, time.time() - 1)
    app.edit_sites()
    dlg = [w for w in app.winfo_children() if isinstance(w, dialogs.SitesDialog)][-1]
    assert "Krita" in dlg.others
    dlg.other_list.selection_set(dlg.others.index("Krita"))
    dlg.move("productive")
    dlg.texts["distracting"].insert("end", "\n9gag")
    dlg.save()
    assert app.settings["extra_productive"] == ["Krita.exe"]
    assert app.settings["extra_distracting"] == ["9gag"]
    assert app.tracker.classifier.classify("krita.exe", "Untitled")[0] == productivity.PRODUCTIVE
    assert app.tracker.classifier.classify("chrome.exe", "funny - 9GAG")[0] == productivity.DISTRACTING
    summary = productivity.summarize(app.db, *timeutil.day_bounds(date.today()))
    assert summary.seconds[productivity.NEUTRAL] == 0 and summary.seconds[productivity.PRODUCTIVE] > 0
    app.db._exec("DELETE FROM activity")
    app.settings.update({"extra_productive": [], "extra_distracting": []})


def test_dandelion_clock_states():
    from timetracker.ui import dandelion

    def at(h, m=0):
        return datetime(2026, 10, 1, h, m)

    petals, man, can_blow = dandelion.state(at(12, 5), "")
    assert petals == ["y"] * 24 and man and not can_blow
    petals, man, _ = dandelion.state(at(17, 59), "")
    assert petals[:10] == ["s"] * 10 and petals[10:] == ["y"] * 14 and man
    petals, man, can_blow = dandelion.state(at(23, 30), "")
    assert petals.count("s") == 22
    petals, man, can_blow = dandelion.state(at(0, 30), "")
    assert petals == ["s"] * 24 and man and can_blow
    petals, man, can_blow = dandelion.state(at(0, 40), "2026-10-01")  # already blown tonight
    assert petals == [""] * 24 and not man and not can_blow
    petals, man, _ = dandelion.state(at(1, 10), "")  # nobody blew it: the wind took the seeds
    assert petals[:2] == ["y", "y"] and petals[2:] == [""] * 22 and not man
    petals, man, _ = dandelion.state(at(11, 59), "2026-10-01")
    assert petals.count("y") == 22 and not man
    assert not dandelion.field_yellow(at(11, 59)) and dandelion.field_yellow(at(12))


def test_dandelion_skin_blow_after_midnight(app):
    from timetracker.ui import dandelion, skin

    app.set_skin("dandelion")
    if not app.settings["show_playlist"]:
        app.toggle_playlist()
    app.update()
    side = app.side
    assert side is not None and app.listbox.cget("bg") == skin.T.pl_body
    side.clock = lambda: datetime(2026, 10, 1, 15, 0)
    side.draw()
    assert not side.blow()  # only between 00:00 and 01:00
    assert side.find_withtag("man") and len(side.find_withtag("petal")) == 18
    x0, y0, x1, y1 = side.bbox("man")
    side._clicked(type("E", (), {"x": (x0 + x1) / 2, "y": (y0 + y1) / 2})())  # a click on the gentleman
    assert side.animating and not app.settings["dandelion_blown"]
    deadline = time.time() + 5
    while side.animating and time.time() < deadline:
        app.update()
        time.sleep(0.02)
    assert side.arm is None
    swings = [dandelion.wave_angle(i / 100) for i in range(101)]
    assert swings[0] is None and swings[-1] is None
    tilts = [a for a in swings if a is not None]
    assert max(tilts) > 20 and min(tilts) < -20
    assert sum(1 for x, y in zip(tilts, tilts[1:]) if x < 0 <= y) >= 2  # twice left and right
    side.clock = lambda: datetime(2026, 10, 1, 0, 20)
    side.draw()
    cx, cy, r = side.head()
    side._clicked(type("E", (), {"x": cx, "y": cy})())
    assert app.settings["dandelion_blown"] == "2026-10-01" and side.animating
    deadline = time.time() + 5
    while side.animating and time.time() < deadline:
        app.update()
        time.sleep(0.02)
    assert not side.animating and not side.find_withtag("seed") and not side.find_withtag("man")
    bands = app._dandelion_bands()
    assert [c for _, c in bands][:3] == [skin.T.body, skin.T.body, skin.T.pl_body]
    app.toggle_playlist()
    app.update()
    assert skin.T.pl_body not in [c for _, c in app._dandelion_bands()]
    app.toggle_playlist()
    app.settings.update({"dandelion_blown": ""})
    app.set_skin("matrix")


def test_coffee_skin_meter_words_at_80_percent(app):
    from timetracker.ui import skin

    app.set_skin("coffee")
    if not app.settings["show_playlist"]:
        app.toggle_playlist()
    app.update()
    meter = app.meter
    texts = lambda: [meter.itemcget(i, "text") for i in meter.find_all() if meter.type(i) == "text"]  # noqa: E731
    meter.set(70, 20, 10, 100)
    assert skin.ProductivityMeter.COFFEE_TEXT not in texts()
    meter.set(85, 10, 5, 100)
    assert skin.ProductivityMeter.COFFEE_TEXT in texts()
    yesterday = timeutil.day_start(date.today()) - 86400
    app.db.add_activity("productive", "Word", yesterday + 3600, yesterday + 3 * 3600)  # 100% that day
    app.shift_day(1)
    dlg = app.show_productivity()
    assert dlg.title() == "Impossible!"  # the answer to "How is possible?"
    dlg.destroy()
    app.db.add_activity("distracting", "YouTube", yesterday + 4 * 3600, yesterday + 6 * 3600)  # now 50%
    dlg = app.show_productivity()
    assert dlg.title() == "Produktivnost"
    dlg.destroy()
    app.shift_day(-1)
    app.db._exec("DELETE FROM activity")
    app._tick()
    app.update()
    app.set_skin("matrix")


def test_pause_play_and_continue_keep_counting(app):
    app.set_skin("matrix")
    app.task_var.set("Nastavak")
    app.project_var.set("")
    app.play()
    entry = app.db.running_entry()
    app.db.update_entry(entry.id, entry.description, entry.project_id, time.time() - 600, None)  # 10 min in
    app.pause()
    app._update_display()
    assert app._clock_text >= "00:10:00"
    app.pause()  # play again: a new entry, but the clock carries on
    app._update_display()
    assert app._clock_text >= "00:10:00" and len([e for e in app.db.entries_between(time.time() - 3600, time.time() + 1)
                                                  if e.description == "Nastavak"]) == 2
    app.stop()
    app._update_display()
    assert app._clock_text == "00:00:00"
    app.refresh()
    app.listbox.selection_clear(0, "end")
    app.listbox.selection_set(len(app._pl_ids) - 1)  # the last "Nastavak" entry
    app.continue_selected()
    app._update_display()
    assert app.task_var.get() == "Nastavak" and app._clock_text >= "00:10:00"
    app.stop()


def test_coffee_play_button_gets_shot(app):
    app.set_skin("coffee")
    app.task_var.set("Espresso")
    app.play()
    assert app.play_btn.find_withtag("hole")
    deadline = time.time() + 4
    while app.play_btn.find_withtag("hole") and time.time() < deadline:
        app.update()
        time.sleep(0.02)
    assert not app.play_btn.find_withtag("hole")  # the hole is gone again
    app.stop()
    app.set_skin("matrix")


def test_transport_buttons_act_on_press_others_on_release(app):
    from timetracker.ui import skin

    log = []
    press = skin.SkinButton(app, lambda: log.append("pressed"), glyph="play", on_press=True,
                            sound=lambda: log.append("sound"))
    press.pack()
    app.update()
    press._press(None)
    assert log == ["sound", "pressed"]
    press._release(type("E", (), {"x": 2, "y": 2})())
    assert log == ["sound", "pressed"]  # not twice
    log.clear()
    normal = skin.SkinButton(app, lambda: log.append("released"), text="OK", sound=lambda: log.append("sound"))
    normal.pack()
    app.update()
    normal._press(None)
    assert log == ["sound"]
    normal._release(type("E", (), {"x": 2, "y": 2})())
    assert log == ["sound", "released"]
    press.destroy()
    normal.destroy()
