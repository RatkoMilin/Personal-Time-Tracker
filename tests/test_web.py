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
    for skin in ("matrix", "pastel", "wood", "cyber"):
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
    assert db(page)["settings"]["skin"] == "cyber"


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
        for (const skin of ['matrix', 'pastel', 'wood', 'cyber'])
            for (const ev of PTTSounds.EVENTS) {
                const s = PTTSounds.render(skin, ev);
                out[skin + ':' + ev] = [s.length / PTTSounds.RATE, Math.max(...s.map(Math.abs))];
            }
        return out;
    }""")
    assert len(result) == 20
    for key, (seconds, peak) in result.items():
        assert 0 < seconds < 1 and peak <= 0.81, key


def test_service_worker_caches_app_for_offline(page):
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")
    page.wait_for_function("caches.has('ptt-v1')")
    cached = page.evaluate("caches.open('ptt-v1').then(c => c.keys()).then(k => k.map(r => new URL(r.url).pathname))")
    assert "/index.html" in cached and "/app.js" in cached
