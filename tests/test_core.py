import queue
from datetime import date, datetime

import pytest

from timetracker import productivity, reports, timeutil
from timetracker.config import Settings
from timetracker.db import Database
from timetracker.tracker import IdleEnd, IdleStart, Tracker


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
    idle = 0.0
    window = None

    def idle_seconds(self):
        return self.idle

    def active_window(self):
        return self.window


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
    assert db.stop_running(ts(11)).id == second
    assert db.running_entry() is None


def test_project_created_on_demand_case_insensitive(db):
    pid = db.project_id("Klijent")
    assert db.project_id("klijent") == pid
    assert db.project_id("  ") is None
    assert db.project_names() == {pid: "Klijent"}


def test_update_entry_rejects_end_before_start(db):
    eid = db.add_entry("rad", None, ts(9), ts(10))
    with pytest.raises(ValueError):
        db.update_entry(eid, "rad", None, ts(9), ts(8))
    assert db.get_entry(eid).end_ts == ts(10)


def test_discard_idle_and_continue(db):
    pid = db.project_id("P")
    eid = db.start_entry("kodiranje", pid, start=ts(9))
    db.discard_interval(eid, ts(10), ts(10, 30), continue_after=True)
    assert db.get_entry(eid).end_ts == ts(10)
    new = db.running_entry()
    assert new.start_ts == ts(10, 30) and (new.description, new.project_id) == ("kodiranje", pid)


def test_discard_idle_and_stop(db):
    eid = db.start_entry("x", start=ts(9))
    db.discard_interval(eid, ts(10), ts(10, 30), continue_after=False)
    assert db.get_entry(eid).end_ts == ts(10)
    assert db.running_entry() is None


def test_entries_between_includes_overlaps(db):
    db.add_entry("preko ponoći", None, ts(23), ts(1, day=date(2026, 10, 1)))
    a, b = timeutil.day_bounds(date(2026, 10, 1))
    assert len(db.entries_between(a, b)) == 1


# ------------------------------------------------------------------- reports

def test_total_clips_to_range_and_counts_running(db):
    db.add_entry("x", None, ts(8), ts(12))
    db.start_entry("y", start=ts(13))
    assert reports.total_between(db, ts(10), ts(11)) == 3600
    assert reports.total_between(db, ts(0), ts(23), now=ts(14)) == 5 * 3600


def test_export_csv(db, tmp_path):
    db.add_entry("rad", db.project_id("P"), ts(9), ts(10, 30))
    path = tmp_path / "out.csv"
    assert reports.export_csv(db, str(path), ts(0), ts(23)) == 1
    text = path.read_text(encoding="utf-8-sig")
    assert "1:30:00;1,50;P;rad" in text


# -------------------------------------------------------------------- config

def test_settings_roundtrip_and_type_guard(tmp_path):
    s = Settings(tmp_path / "s.json")
    s.update({"idle_minutes": 10})
    assert Settings(tmp_path / "s.json")["idle_minutes"] == 10
    (tmp_path / "s.json").write_text('{"idle_minutes": "a lot", "always_on_top": true, "bogus": 1}')
    s2 = Settings(tmp_path / "s.json")
    assert s2["idle_minutes"] == 5 and s2["always_on_top"] is True


# ------------------------------------------------------------------- tracker

def make_tracker(db, settings, plat):
    return Tracker(db, settings, queue.Queue(), platform=plat)


def drain(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


def test_idle_reminder_starts_at_limit_and_ends_on_return(db, settings):
    plat = FakePlatform()
    t = make_tracker(db, settings, plat)
    eid = db.start_entry("x", start=ts(9))
    t.tick(ts(9, 1))
    plat.idle = 200  # under the 5 min limit: nothing yet
    t.tick(ts(9, 4))
    assert t.events.empty()
    plat.idle = 300  # limit reached: the reminder pops up right away
    t.tick(ts(9, 5))
    assert drain(t.events) == [IdleStart(eid, ts(9, 0))]
    plat.idle = 900
    t.tick(ts(9, 15))
    assert t.events.empty()  # only one reminder per idle period
    plat.idle = 1
    t.tick(ts(9, 20))
    assert drain(t.events) == [IdleEnd(eid, ts(9, 0), ts(9, 20))]


def test_sleep_gap_counts_as_idle(db, settings):
    t = make_tracker(db, settings, FakePlatform())
    eid = db.start_entry("x", start=ts(9))
    t.tick(ts(10))
    t.tick(ts(11))  # laptop lid closed for an hour
    assert drain(t.events) == [IdleStart(eid, ts(10)), IdleEnd(eid, ts(10), ts(11))]


def test_no_idle_reminder_when_off_or_no_timer(db, settings):
    plat = FakePlatform()
    t = make_tracker(db, settings, plat)
    plat.idle = 600
    t.tick(ts(9))
    plat.idle = 0
    t.tick(ts(9, 1))
    settings["idle_minutes"] = 0
    db.start_entry("x", start=ts(9))
    plat.idle = 600
    t.tick(ts(9, 11))
    plat.idle = 0
    t.tick(ts(9, 12))
    assert t.events.empty()


# -------------------------------------------------------------- productivity

@pytest.mark.parametrize("exe,title,expected", [
    ("chrome.exe", "Ponuda 2026 - Google Docs - Google Chrome", ("productive", "Google Docs")),
    ("WINWORD.EXE", "Ugovor.docx - Word", ("productive", "Word")),
    ("msedge.exe", "Budžet - Google Sheets \u2014 Microsoft\u200b Edge", ("productive", "Google Sheets")),
    ("chrome.exe", "Cat video - YouTube - Google Chrome", ("distracting", "YouTube")),
    ("firefox.exe", "(3) Facebook - Mozilla Firefox", ("distracting", "Facebook")),
    ("chrome.exe", "Instagram - Google Chrome", ("distracting", "Instagram")),
    ("chrome.exe", "Patike | Zalando - Google Chrome", ("distracting", "Kupovina")),
    ("chrome.exe", "Amazon.de: Kopfhörer - Google Chrome", ("distracting", "Kupovina")),
    ("chrome.exe", "Word tips for beginners - YouTube - Google Chrome", ("distracting", "YouTube")),
    ("Photoshop.exe", "Adobe Photoshop 2026", ("neutral", "Photoshop")),
    ("explorer.exe", "Downloads", ("neutral", "explorer")),
])
def test_classifier(exe, title, expected):
    assert productivity.Classifier().classify(exe, title) == expected


def test_classifier_extra_words_from_settings():
    c = productivity.Classifier(extra_productive=["Figma", "blender.exe"], extra_distracting=["9gag"])
    assert c.classify("chrome.exe", "Logo - Figma - Google Chrome") == ("productive", "Figma")
    assert c.classify("blender.exe", "scene.blend") == ("productive", "blender")
    assert c.classify("chrome.exe", "Funny - 9GAG - Google Chrome") == ("distracting", "9gag")


def test_activity_is_tracked_without_titles_and_summarized(db, settings):
    plat = FakePlatform()
    t = make_tracker(db, settings, plat)
    plat.window = ("WINWORD.EXE", "Tajni ugovor.docx - Word")
    for i in range(31):  # 60 s of Word
        t.tick(ts(9) + i * 2)
    plat.window = ("chrome.exe", "Something - YouTube - Google Chrome")
    for i in range(1, 16):  # 30 s of YouTube
        t.tick(ts(9) + 60 + i * 2)
    plat.window = ("explorer.exe", "Downloads")
    t.tick(ts(9) + 92)
    rows = db.activity_between(ts(0), ts(23))
    assert [(c, l) for _, _, c, l in rows] == [("productive", "Word"), ("distracting", "YouTube"),
                                                ("neutral", "explorer")]
    assert all("Tajni" not in l for _, _, _, l in rows)
    s = productivity.summarize(db, ts(0), ts(23), now=ts(10))
    assert s.seconds["productive"] == 60 and s.seconds["distracting"] == 30 and s.seconds["neutral"] == 2
    assert s.share("productive") == pytest.approx(60 / 92)
    assert s.labels["distracting"] == [("YouTube", 30.0)]


def test_activity_not_counted_while_idle_or_locked(db, settings):
    plat = FakePlatform()
    t = make_tracker(db, settings, plat)
    plat.window = ("WINWORD.EXE", "x - Word")
    for i in range(31):
        t.tick(ts(9) + i * 2)
    plat.idle = 400  # away for more than the 5 min limit: the last 400 s are not work
    t.tick(ts(9) + 62)
    plat.idle, plat.window = 0, None  # locked screen
    t.tick(ts(9) + 64)
    assert productivity.summarize(db, ts(0), ts(23), now=ts(10)).total == 0
    plat.window = ("WINWORD.EXE", "x - Word")
    t.tick(ts(10))
    t.tick(ts(10) + 2)
    assert productivity.summarize(db, ts(0), ts(23), now=ts(11)).total == 2


def test_task_total_adds_up_todays_entries_of_one_task(tmp_path):
    from datetime import datetime

    from timetracker import reports
    from timetracker.db import Database

    db = Database(tmp_path / "t.db")
    d = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0).timestamp()
    pid = db.project_id("A")
    db.add_entry("pisanje", pid, d - 3600, d - 3000)          # 10 min
    db.add_entry("pisanje", None, d - 2900, d - 2800)         # other project: not counted
    db.add_entry("sastanak", pid, d - 2700, d - 2400)         # other task: not counted
    db.add_entry("pisanje", pid, d - 2000, d - 1700)          # 5 min after a pause
    assert reports.task_total(db, "pisanje", pid, now=d) == 900
    db.close()
