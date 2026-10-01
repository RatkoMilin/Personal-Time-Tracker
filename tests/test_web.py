"""End-to-end tests of the mobile web app (web/) in a phone-sized Chromium.

Skipped when Playwright is not installed. Set PTT_CHROMIUM to use a specific browser binary;
set PTT_WEB_SHOTS to a folder to save a screenshot of every skin.
"""

import functools
import http.server
import json
import os
import threading
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

WEB = Path(__file__).resolve().parent.parent / "web"
PHONE = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2, "is_mobile": True, "has_touch": True}


@pytest.fixture(scope="module")
def server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(WEB))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    handler.log_message = lambda *a: None
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    httpd.shutdown()


@pytest.fixture(scope="module")
def browser():
    exe = os.environ.get("PTT_CHROMIUM") or ("/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists()
                                             else None)
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        except Exception as exc:  # browser not installed
            pytest.skip(f"Chromium not available: {exc}")
        yield b
        b.close()


@pytest.fixture
def page(browser, server):
    ctx = browser.new_context(**PHONE, accept_downloads=True)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("dialog", lambda d: d.accept())
    pg.goto(server)
    pg.wait_for_selector("#clock polygon")
    yield pg
    assert errors == []
    ctx.close()


def db(pg):
    return pg.evaluate("JSON.parse(JSON.stringify(window.PTT.db))")


def test_fits_phone_screen_without_horizontal_scroll(page):
    assert page.evaluate("document.documentElement.scrollWidth") <= 390
    for sel in ("#playBtn", "#pauseBtn", "#stopBtn", "#plBtn", "#addBtn"):
        box = page.locator(sel).bounding_box()
        assert box["height"] >= 32 and box["width"] >= 32, sel


def test_play_pause_stop_and_playlist(page):
    page.fill("#task", "Pisanje ponude")
    page.fill("#project", "Klijent A")
    page.click("#playBtn")
    data = db(page)
    [entry] = data["entries"]
    assert entry["description"] == "Pisanje ponude" and entry["end"] is None
    assert data["projects"][0]["name"] == "Klijent A"
    assert "Pisanje ponude [Klijent A]" in page.inner_text("#list")
    page.click("#pauseBtn")
    assert db(page)["ui"]["paused"] is True and db(page)["entries"][0]["end"] is not None
    page.click("#pauseBtn")  # resume = new entry with the same task
    assert len(db(page)["entries"]) == 2 and db(page)["entries"][1]["end"] is None
    page.click("#stopBtn")
    assert page.input_value("#task") == "" and db(page)["ui"]["paused"] is False
    assert all(e["end"] is not None for e in db(page)["entries"])
    page.click("#plBtn")
    assert page.locator("#playlist").is_hidden()
    page.click("#plBtn")
    assert page.locator("#playlist").is_visible()


def test_pause_play_continues_the_clock(page):
    page.fill("#task", "Nastavak")
    page.click("#playBtn")
    page.evaluate("window.PTT.db.entries[0].start = Date.now() - 10 * 60000")
    page.click("#pauseBtn")
    page.click("#pauseBtn")  # play again: a new entry, the clock carries on from 10 minutes
    assert len(db(page)["entries"]) == 2
    page.wait_for_function("document.title.startsWith('00:10')")
    page.click("#stopBtn")
    page.click("#list li >> nth=1")
    page.click("#eContinue")
    page.wait_for_function("document.title.startsWith('00:10')")


def test_coffee_play_button_gets_shot(page):
    pick_skin(page, "coffee")
    page.fill("#task", "Espresso")
    page.click("#playBtn")
    assert page.locator("#playBtn .hole").count() == 1
    page.wait_for_function("!document.querySelector('#playBtn .hole')", timeout=4000)


def test_running_timer_survives_reload(page):
    page.fill("#task", "Dugačak zadatak")
    page.press("#task", "Enter")
    start = db(page)["entries"][0]["start"]
    page.reload()
    page.wait_for_selector("#clock polygon")
    data = db(page)
    assert data["entries"][0]["start"] == start and data["entries"][0]["end"] is None
    assert page.input_value("#task") == "Dugačak zadatak"


def test_add_edit_delete_entry(page):
    page.click("#addBtn")
    page.fill("#eDesc", "Sastanak")
    page.fill("#eProject", "Interno")
    page.fill("#eStart", "09:00")
    page.fill("#eEnd", "10:30")
    page.click("#eOk")
    [entry] = db(page)["entries"]
    assert entry["end"] - entry["start"] == 90 * 60 * 1000
    page.click("#list li")
    assert page.locator("#entryDlg").is_visible()
    page.fill("#eEnd", "11:00")
    page.click("#eOk")
    entry = db(page)["entries"][0]
    assert entry["end"] - entry["start"] == 2 * 3600 * 1000
    page.click("#list li")
    page.click("#eContinue")
    assert db(page)["entries"][-1]["end"] is None and page.input_value("#task") == "Sastanak"
    page.click("#list li >> nth=0")
    page.click("#eDelete")
    assert len(db(page)["entries"]) == 1


def test_every_skin_renders(page):
    shots = os.environ.get("PTT_WEB_SHOTS")
    page.fill("#task", "Dizajn početne strane")
    page.fill("#project", "Sajt Beta")
    page.click("#playBtn")
    for skin in ("matrix", "pastel", "wood", "cyber", "cat", "setsuna", "mondrian", "egg", "dandelion", "coffee", "hourglass", "eink"):
        page.click("#menuBtn")
        page.click(f"#skins [data-skin={skin}]")
        page.click("#menuClose")
        assert page.get_attribute("body", "data-skin") == skin
        if skin == "wood":
            assert page.locator("#dial").is_visible() and page.locator("#clock").is_hidden()
            assert "Dizajn" in page.inner_text("#taskLine")
        else:
            assert page.locator("#clock").is_visible() and page.locator("#dial").is_hidden()
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        if shots:
            page.wait_for_timeout(600)
            page.screenshot(path=str(Path(shots) / f"web_{skin}.png"), full_page=True)
    assert db(page)["settings"]["skin"] == "eink"


def pick_skin(page, skin):
    page.click("#menuBtn")
    page.click(f"#skins [data-skin={skin}]")
    page.click("#menuClose")


def test_egg_lamp_lights_only_while_working(page):
    pick_skin(page, "egg")
    lit = "document.body.classList.contains('lit')"
    assert page.evaluate(lit) is False
    page.fill("#task", "Lampa")
    page.click("#playBtn")
    assert page.evaluate(lit) is True
    page.click("#pauseBtn")
    assert page.evaluate(lit) is False
    page.click("#pauseBtn")
    assert page.evaluate(lit) is True
    page.click("#stopBtn")
    assert page.evaluate(lit) is False


def test_setsuna_confetti_and_oranges(page):
    pick_skin(page, "setsuna")
    page.fill("#task", "Narandže")
    page.click("#playBtn")
    assert page.locator(".fx .confetto").count() > 20
    page.evaluate("window.PTT.db.entries[0].start = Date.now() - 75 * 60000")
    page.wait_for_function("document.querySelectorAll('.titlebar .piece').length === 2")
    assert page.locator("#piecesL .piece.w").count() == 1 and page.locator("#piecesR .piece.q").count() == 1
    page.click("#stopBtn")
    page.wait_for_function("document.querySelectorAll('.titlebar .piece').length === 0")


def test_matrix_digits_jumble_and_pastel_bubbles(page):
    page.fill("#task", "Matrix")
    page.click("#playBtn")
    shown = page.evaluate("""() => new Promise(resolve => {
        const seen = new Set();
        const t = setInterval(() => seen.add([...document.querySelectorAll('#clock [style]')].map(n => n.style.fill).join()), 20);
        setTimeout(() => { clearInterval(t); resolve(seen.size); }, 500);
    })""")
    assert shown > 3  # the segments kept changing while the digits jumbled
    page.click("#stopBtn")
    pick_skin(page, "pastel")
    page.click("#plBtn")
    page.click("#plBtn")
    assert page.locator(".fx .bubble").count() > 10


def test_dandelion_blows_only_after_midnight(browser, server):
    ctx = browser.new_context(**PHONE)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time="2026-10-01T15:00:00")
    pg.goto(server)
    pg.wait_for_selector("#clock polygon")
    pick_skin(pg, "dandelion")
    pg.wait_for_selector("#dandelion .man")
    assert pg.locator("#dandelion .petal").count() == 18 and pg.locator("#dandelion .seed").count() == 6
    assert pg.evaluate("window.PTT.blowDandelion()") is False
    pg.click("#dandelion .man", force=True)  # he waves
    assert pg.locator("#dandelion .man.waving").count() == 1
    assert pg.evaluate("document.documentElement.scrollWidth") <= 390
    shots = os.environ.get("PTT_WEB_SHOTS")
    if shots:
        pg.screenshot(path=str(Path(shots) / "web_dandelion_15h.png"), full_page=True)
    pg.clock.set_system_time("2026-10-02T00:20:00")
    pg.reload()
    pg.wait_for_selector("#dandelion .head.can-blow")
    assert pg.locator("#dandelion .seed").count() == 24
    pg.click("#dandelion .head.can-blow", force=True)
    assert db(pg)["settings"]["dandelionBlown"] == "2026-10-02"
    assert pg.locator("#dandelion.blowing").count() == 1
    pg.clock.run_for(3500)
    pg.wait_for_function("document.querySelectorAll('#dandelion .seed').length === 0")
    assert pg.locator("#dandelion .man").count() == 0
    assert errors == []
    ctx.close()


def test_hourglass_turns_every_25_minutes(page):
    pick_skin(page, "hourglass")
    page.fill("#task", "Pesak")
    page.click("#playBtn")
    assert page.locator("#hourglass polygon").count() >= 2 and page.locator("#hourglass.running").count() == 1
    page.evaluate("window.PTT.db.entries[0].start = Date.now() - 26 * 60000")  # past the first turn
    page.wait_for_selector("#hourglass.flip")
    page.wait_for_function("document.querySelectorAll('.titlebar .piece.d').length === 1")
    page.click("#pauseBtn")
    page.wait_for_function("!document.querySelector('#hourglass.running')")  # the sand stops in mid-air
    page.click("#stopBtn")
    page.wait_for_function("document.querySelectorAll('.titlebar .piece.d').length === 0")


def test_csv_export_and_backup_restore(page, tmp_path):
    page.fill("#task", "rad; sa tačkom-zarezom")
    page.click("#playBtn")
    page.click("#stopBtn")
    csv = page.evaluate("window.PTT.csvFor('all')")
    assert csv["count"] == 1 and csv["text"].startswith("﻿Datum;Od;Do")
    assert '"rad; sa tačkom-zarezom"' in csv["text"]
    page.click("#exportBtn")
    with page.expect_download() as dl:
        page.click("#exports [data-kind=this_week]")
    assert dl.value.suggested_filename.startswith("vreme_") and dl.value.suggested_filename.endswith(".csv")
    with page.expect_download() as dl:
        page.click("#backupBtn")
    backup = json.loads(Path(dl.value.path()).read_text(encoding="utf-8"))
    assert len(backup["entries"]) == 1
    backup["entries"].append(dict(backup["entries"][0], id=999, description="iz kopije"))
    restore = tmp_path / "backup.json"
    restore.write_text(json.dumps(backup), encoding="utf-8")
    page.set_input_files("#restoreFile", str(restore))
    page.wait_for_function("window.PTT.db.entries.length === 2")


def test_sounds_render_for_every_skin(page):
    result = page.evaluate("""() => {
        const out = {};
        for (const skin of ['matrix', 'pastel', 'wood', 'cyber', 'cat', 'setsuna', 'mondrian', 'egg', 'dandelion', 'coffee', 'hourglass', 'eink'])
            for (const ev of PTTSounds.EVENTS) {
                const s = PTTSounds.render(skin, ev);
                out[skin + ':' + ev] = [s.length / PTTSounds.RATE, Math.max(...s.map(Math.abs))];
            }
        return out;
    }""")
    assert len(result) == 60
    for key, (seconds, peak) in result.items():
        assert 0 < seconds < 1 and peak <= 0.81, key


def test_service_worker_caches_app_for_offline(page):
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")
    page.wait_for_function("caches.has('ptt-v7')")
    cached = page.evaluate("caches.open('ptt-v7').then(c => c.keys()).then(k => k.map(r => new URL(r.url).pathname))")
    assert "/index.html" in cached and "/app.js" in cached


KOMPAKT = {"viewport": {"width": 320, "height": 533}, "device_scale_factor": 1.5, "is_mobile": True, "has_touch": True}


def test_eink_device_starts_quiet_black_and_white_and_stays_still(browser, server):
    """The Android build (Mudita Kompakt) opens ?device=eink: e-ink skin, sounds off, minute-level display."""
    ctx = browser.new_context(**KOMPAKT)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(server + "index.html?device=eink")
    pg.wait_for_selector("#clock polygon")
    data = db(pg)
    assert data["settings"]["skin"] == "eink" and data["settings"]["sounds"] is False
    assert pg.evaluate("document.documentElement.scrollWidth") <= 320
    # hours:minutes only -> 4 digits (7 segments each) + 1 colon (2 dots)
    assert pg.locator("#clock polygon").count() == 4 * 7 + 2
    pg.fill("#task", "Čitanje")
    pg.click("#playBtn")
    pg.wait_for_timeout(300)
    # Within the same minute nothing on screen may change: every DOM write is an e-ink redraw.
    mutations = pg.evaluate("""() => new Promise(resolve => {
        let n = 0;
        const obs = new MutationObserver(list => { n += list.length; });
        obs.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true });
        setTimeout(() => { obs.disconnect(); resolve(n); }, 2500);
    })""")
    assert mutations == 0
    shots = os.environ.get("PTT_WEB_SHOTS")
    if shots:
        pg.screenshot(path=str(Path(shots) / "web_eink_kompakt.png"), full_page=True)
    # The Kompakt gets only the e-ink skin: no skin choices in the menu, even if another one was saved.
    pg.click("#menuBtn")
    assert pg.locator("#skins").is_hidden() and pg.locator("#skinsLabel").is_hidden()
    pg.click("#menuClose")
    pg.evaluate("window.PTT.db.settings.skin = 'matrix'; localStorage.setItem(window.PTT.KEY, JSON.stringify(window.PTT.db))")
    pg.reload()
    pg.wait_for_selector("#clock polygon")
    assert pg.get_attribute("body", "data-skin") == "eink"
    assert errors == []
    ctx.close()


def test_android_bridge_receives_exports(page):
    page.evaluate("""() => { window.saved = []; window.AndroidBridge = {
        saveFile: (name, text, type) => window.saved.push([name, type, text.length]) }; }""")
    page.click("#exportBtn")
    page.click("#exports [data-kind=all]")
    page.click("#backupBtn")
    saved = page.evaluate("window.saved")
    assert [s[1] for s in saved] == ["text/csv", "application/json"]
    assert saved[0][0].startswith("vreme_sve_") and saved[1][0].startswith("timetracker-backup-")
    assert page.evaluate("window.PTT.back()") is True  # closes the open menu
    assert page.evaluate("window.PTT.back()") is False


def test_new_entry_just_after_midnight_defaults_to_today(browser, server):
    ctx = browser.new_context(**PHONE)
    pg = ctx.new_page()
    pg.clock.install(time="2026-10-01T00:05:00")
    pg.goto(server)
    pg.wait_for_selector("#clock polygon")
    pg.click("#addBtn")
    assert pg.input_value("#eDate") == "2026-10-01"
    assert (pg.input_value("#eStart"), pg.input_value("#eEnd")) == ("00:00", "00:05")
    ctx.close()
