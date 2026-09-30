import queue
from datetime import date, datetime

import pytest

from timetracker import reports, timeutil
from timetracker.config import Settings
from timetracker.db import Database
from timetracker.tracker import IdleEvent, LongTimerEvent, ReminderEvent, Tracker


@pytest.fixture
def db():
    d = Database(":memory:")
    yield d
    d.close()


@pytest.fixture
def settings(tmp_path):
    return Settings(tmp_path / "settings.json")


def ts(h, m=0, day=date(2026, 9, 30)):
    return datetime(day.year, day.month, day.day, h, m).timestamp()


class FakePlatform:
    def __init__(self):
        self.idle = 0.0
        self.window = ("code.exe", "main.py - VS Code")
        self.shots = []

    def idle_seconds(self):
        return self.idle

    def active_window(self):
        return self.window

    def take_screenshot(self, path):
        self.shots.append(path)
        return True


# ------------------------------------------------------------------ timeutil

def test_parse_time_variants():
    assert timeutil.parse_time("9:05") == (9, 5)
    assert timeutil.parse_time("0905") == (9, 5)
    assert timeutil.parse_time("14") == (14, 0)
    assert timeutil.parse_time("7.30") == (7, 30)
    with pytest.raises(ValueError):
        timeutil.parse_time("25:00")


def test_parse_date_variants():
    assert timeutil.parse_date("30.09.2026") == date(2026, 9, 30)
    assert timeutil.parse_date("1.2.2026.") == date(2026, 2, 1)
    assert timeutil.parse_date("2026-09-30") == date(2026, 9, 30)
    with pytest.raises(ValueError):
        timeutil.parse_date("30/13/2026")


def test_parse_duration():
    assert timeutil.parse_duration("1:30") == 5400
    assert timeutil.parse_duration("1h 15m") == 4500
    assert timeutil.parse_duration("45m") == 2700
    assert timeutil.parse_duration("1,5") == 5400


def test_formatting():
    assert timeutil.fmt_clock(3725) == "1:02:05"
    assert timeutil.fmt_hours(3725) == "1h 02m"
    assert timeutil.fmt_hours(600) == "10m"


def test_period_bounds_week_starts_monday():
    a, b = timeutil.period_bounds("this_week", date(2026, 9, 30))  # Wednesday
    assert timeutil.ts_to_date(a) == date(2026, 9, 28)
    assert timeutil.ts_to_date(b) == date(2026, 10, 5)
    a, b = timeutil.period_bounds("last_month", date(2026, 1, 15))
    assert timeutil.ts_to_date(a) == date(2025, 12, 1)
    assert timeutil.ts_to_date(b) == date(2026, 1, 1)


# ------------------------------------------------------------------ database

def test_only_one_running_entry(db):
    first = db.start_entry("A", start=ts(9))
    second = db.start_entry("B", start=ts(10))
    assert db.get_entry(first).end_ts == ts(10)
    assert db.running_entry().id == second
    stopped = db.stop_running(ts(11))
    assert stopped.id == second and db.running_entry() is None


def test_duplicate_project_rejected(db):
    db.add_project("Klijent")
    with pytest.raises(ValueError):
        db.add_project("klijent")


def test_deleting_project_keeps_entries(db):
    pid = db.add_project("X")
    eid = db.add_entry("rad", pid, ts(9), ts(10))
    db.delete_project(pid)
    assert db.get_entry(eid).project_id is None


def test_update_entry_rejects_end_before_start(db):
    eid = db.add_entry("rad", None, ts(9), ts(10))
    with pytest.raises(ValueError):
        db.update_entry(eid, end=ts(8))
    assert db.get_entry(eid).end_ts == ts(10)


def test_discard_idle_and_continue(db):
    pid = db.add_project("P")
    eid = db.start_entry("kodiranje", pid, True, start=ts(9))
    new_id = db.discard_interval(eid, ts(10), ts(10, 30), continue_after=True)
    assert db.get_entry(eid).end_ts == ts(10)
    new = db.get_entry(new_id)
    assert new.running and new.start_ts == ts(10, 30)
    assert (new.description, new.project_id, new.billable) == ("kodiranje", pid, True)


def test_discard_idle_and_stop(db):
    eid = db.start_entry("x", start=ts(9))
    assert db.discard_interval(eid, ts(10), ts(10, 30), continue_after=False) is None
    assert db.get_entry(eid).end_ts == ts(10)
    assert db.running_entry() is None


def test_entries_between_includes_overlaps(db):
    db.add_entry("preko ponoći", None, ts(23), ts(1, day=date(2026, 10, 1)))
    a, b = timeutil.day_bounds(date(2026, 10, 1))
    assert len(db.entries_between(a, b)) == 1


# ------------------------------------------------------------------- reports

def test_summary_splits_days_and_bills(db):
    pid = db.add_project("Klijent A", hourly_rate=40)
    db.add_entry("dev", pid, ts(22), ts(2, day=date(2026, 10, 1)), billable=True)
    db.add_entry("mail", None, ts(9), ts(9, 30))
    a, b = timeutil.day_start(date(2026, 9, 30)), timeutil.day_start(date(2026, 10, 2))
    s = reports.summarize(db, a, b)
    assert s.total == 4.5 * 3600
    assert s.billable == 4 * 3600
    assert s.amount == pytest.approx(160)
    assert s.by_day[date(2026, 9, 30)] == 2.5 * 3600
    assert s.by_day[date(2026, 10, 1)] == 2 * 3600
    assert [p.name for p in s.by_project] == ["Klijent A", reports.NO_PROJECT]


def test_summary_clips_to_range(db):
    db.add_entry("x", None, ts(8), ts(12))
    s = reports.summarize(db, ts(10), ts(11))
    assert s.total == 3600


def test_app_usage(db):
    eid = db.add_entry("rad", None, ts(9, 30), ts(10, 30))
    db.add_activity("chrome.exe", "GitHub", ts(9), ts(9, 30), None)
    db.add_activity("Code.exe", "main.py", ts(9, 30), ts(10, 30), eid)
    usage = reports.app_usage(db, ts(0), ts(23))
    assert usage == [("Code", 3600.0), ("chrome", 1800.0)]
    assert reports.app_usage(db, ts(0), ts(23), only_tracked=True) == [("Code", 3600.0)]


def test_export_csv(db, tmp_path):
    pid = db.add_project("P", hourly_rate=20)
    db.add_entry("rad", pid, ts(9), ts(10, 30), billable=True)
    path = tmp_path / "out.csv"
    assert reports.export_csv(db, str(path), ts(0), ts(23)) == 1
    text = path.read_text(encoding="utf-8-sig")
    assert "1:30:00" in text and "30,00" in text and "P;rad;da" in text


# -------------------------------------------------------------------- config

def test_settings_roundtrip_and_type_guard(tmp_path):
    s = Settings(tmp_path / "s.json")
    s.update({"idle_minutes": 7})
    (tmp_path / "s.json").write_text('{"idle_minutes": 9, "screenshots": "yes", "bogus": 1}')
    s2 = Settings(tmp_path / "s.json")
    assert s2["idle_minutes"] == 9
    assert s2["screenshots"] is False


# ------------------------------------------------------------------- tracker

def make_tracker(db, settings, tmp_path, platform):
    return Tracker(db, settings, queue.Queue(), tmp_path / "shots", platform=platform)


def test_tracker_records_merged_activity(db, settings, tmp_path):
    plat = FakePlatform()
    t = make_tracker(db, settings, tmp_path, plat)
    eid = db.start_entry("x", start=ts(9))
    for i in range(5):
        t.tick(ts(9) + i * 2)
    acts = db.activity_between(ts(0), ts(23))
    assert len(acts) == 1
    assert acts[0].entry_id == eid and acts[0].end_ts - acts[0].start_ts == 8
    plat.window = ("chrome.exe", "Docs")
    t.tick(ts(9) + 10)
    assert len(db.activity_between(ts(0), ts(23))) == 2


def test_tracker_activity_only_while_timer_by_default(db, settings, tmp_path):
    t = make_tracker(db, settings, tmp_path, FakePlatform())
    t.tick(ts(9))
    t.tick(ts(9) + 2)
    assert db.activity_between(ts(0), ts(23)) == []
    settings["activity_mode"] = "always"
    t.tick(ts(9) + 4)
    t.tick(ts(9) + 6)
    assert len(db.activity_between(ts(0), ts(23))) == 1


def test_tracker_idle_event_when_user_returns(db, settings, tmp_path):
    plat = FakePlatform()
    t = make_tracker(db, settings, tmp_path, plat)
    eid = db.start_entry("x", start=ts(9))
    t.tick(ts(9, 1))
    # 6 minutes without input (threshold is 5)
    plat.idle = 360
    t.tick(ts(9, 7))
    assert t.events.empty()
    plat.idle = 1
    t.tick(ts(9, 20))
    ev = t.events.get_nowait()
    assert isinstance(ev, IdleEvent)
    assert ev.entry_id == eid and ev.idle_start == ts(9, 1) and ev.idle_end == ts(9, 20)
    # Activity recorded after the idle start was trimmed.
    assert all(a.end_ts <= ts(9, 1) or a.start_ts >= ts(9, 20) for a in db.activity_between(ts(0), ts(23)))


def test_tracker_detects_sleep_gap(db, settings, tmp_path):
    plat = FakePlatform()
    t = make_tracker(db, settings, tmp_path, plat)
    db.start_entry("x", start=ts(9))
    t.tick(ts(10))
    t.tick(ts(11))  # laptop lid was closed for an hour
    ev = t.events.get_nowait()
    assert isinstance(ev, IdleEvent) and ev.idle_start == ts(10) and ev.idle_end == ts(11)


def test_tracker_no_idle_prompt_when_disabled(db, settings, tmp_path):
    settings["idle_detection"] = False
    plat = FakePlatform()
    t = make_tracker(db, settings, tmp_path, plat)
    db.start_entry("x", start=ts(9))
    t.tick(ts(9, 1))
    plat.idle = 600
    t.tick(ts(9, 11))
    plat.idle = 0
    t.tick(ts(9, 12))
    assert t.events.empty()


def test_tracker_reminder_without_timer(db, settings, tmp_path):
    settings["reminder_minutes"] = 1
    t = make_tracker(db, settings, tmp_path, FakePlatform())
    for i in range(40):
        t.tick(ts(9) + i * 2)
    assert isinstance(t.events.get_nowait(), ReminderEvent)


def test_tracker_long_timer_once(db, settings, tmp_path):
    settings["long_timer_hours"] = 1
    t = make_tracker(db, settings, tmp_path, FakePlatform())
    db.start_entry("x", start=ts(9))
    t.tick(ts(10, 1))
    t.tick(ts(10, 1) + 2)
    assert isinstance(t.events.get_nowait(), LongTimerEvent)
    assert t.events.empty()


def test_tracker_screenshots_and_cleanup(db, settings, tmp_path):
    settings["screenshots"] = True
    settings["screenshot_interval_min"] = 1
    plat = FakePlatform()
    t = make_tracker(db, settings, tmp_path, plat)
    db.start_entry("x", start=ts(9))
    for i in range(0, 130, 2):
        t.tick(ts(9) + i)
    assert len(plat.shots) == 3  # at 0s, 60s, 120s
    shot = tmp_path / "old.jpg"
    shot.write_bytes(b"x")
    db.add_screenshot(ts(9) - 40 * 86400, str(shot), None)
    t.cleanup(ts(9))
    assert not shot.exists()
    assert len(db.screenshots_between(0, ts(23))) == 3
