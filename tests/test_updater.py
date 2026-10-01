import hashlib
from pathlib import Path

import pytest

from timetracker import updater


def release(tag="v1.2.0", data=b"new exe", digest=True, name="PersonalTimeTracker.exe"):
    asset = {"name": name, "browser_download_url": f"https://example.invalid/{tag}/{name}", "size": len(data)}
    if digest:
        asset["digest"] = "sha256:" + hashlib.sha256(data).hexdigest()
    return {"tag_name": tag, "draft": False, "prerelease": False, "assets": [asset]}


def test_version_compare():
    assert updater.is_newer("v1.10.0", "1.9.3")
    assert updater.is_newer("1.2", "1.1.9")
    assert not updater.is_newer("v1.2.0", "1.2.0")
    assert not updater.is_newer("v1.1.0", "1.2.0")
    assert not updater.is_newer("nightly", "1.0.0")


def test_check_finds_newer_release_only_for_release_builds():
    found = updater.check("1.1.0", get_json=lambda url: release())
    assert found.version == "1.2.0" and found.url.endswith("/PersonalTimeTracker.exe") and found.sha256
    assert updater.check("1.2.0", get_json=lambda url: release()) is None
    assert updater.check(None, get_json=lambda url: release()) is None  # source / artifact build
    assert updater.check("1.1.0", get_json=lambda url: release(name="other.zip")) is None
    assert updater.check("1.1.0", get_json=lambda url: dict(release(), prerelease=True)) is None


def test_download_verifies_size_and_digest(tmp_path):
    good = updater.check("1.0.0", get_json=lambda url: release(data=b"new exe"))
    path = updater.download(good, tmp_path, fetch=lambda url, dest: Path(dest).write_bytes(b"new exe"))
    assert path.read_bytes() == b"new exe" and path.name == "PersonalTimeTracker-1.2.0.exe"
    with pytest.raises(ValueError):
        updater.download(good, tmp_path, fetch=lambda url, dest: Path(dest).write_bytes(b"tampered"))
    good.size = 0  # no size info: the digest still catches it
    with pytest.raises(ValueError):
        updater.download(good, tmp_path, fetch=lambda url, dest: Path(dest).write_bytes(b"tampered"))
    assert not list(tmp_path.glob("*.part"))


def test_install_swaps_files_and_cleanup_removes_leftovers(tmp_path):
    exe = tmp_path / "PersonalTimeTracker.exe"
    exe.write_bytes(b"old")
    new = tmp_path / "update" / "PersonalTimeTracker-1.2.0.exe"
    new.parent.mkdir()
    new.write_bytes(b"new")
    updater.install(new, exe)
    assert exe.read_bytes() == b"new" and updater.old_path(exe).read_bytes() == b"old"
    updater.cleanup(exe, tmp_path / "update")
    assert not updater.old_path(exe).exists() and exe.exists()


def test_restart_launches_after_a_delay(tmp_path):
    calls = []
    updater.restart(tmp_path / "PersonalTimeTracker.exe", popen=lambda *a, **k: calls.append(a[0]))
    assert calls and "timeout /t 2" in calls[0][2] and "--minimized" in calls[0][2]
