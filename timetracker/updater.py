"""Self-update for the Windows exe from GitHub Releases.

Only a release build knows its version (CI writes timetracker/_build.py from the release tag), so
source checkouts and artifact builds never update themselves. The flow:

1. ask the GitHub API for the latest release; newer tag with a PersonalTimeTracker.exe asset?
2. download it next to the data folder and check its size and SHA-256 digest;
3. rename the running exe to *.old.exe (Windows allows renaming a running exe), move the new one in,
   start it with --after-update <pid> (it waits for the old process to exit) and let the old process exit. The running timer lives in the database,
   so it simply continues in the new version.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

REPO = "RatkoMilin/Personal-Time-Tracker"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_NAME = "PersonalTimeTracker.exe"
HEADERS = {"User-Agent": "PersonalTimeTracker-updater", "Accept": "application/vnd.github+json"}


def build_version() -> str | None:
    """Version stamped into release builds; None for source runs and non-release builds."""
    try:
        from . import _build  # written by CI for releases
    except ImportError:
        return None
    return getattr(_build, "VERSION", None)


def parse_version(text: str) -> tuple[int, ...] | None:
    text = (text or "").strip().lstrip("vV")
    try:
        parts = tuple(int(p) for p in text.split("."))
    except ValueError:
        return None
    return parts or None


def is_newer(remote: str, local: str) -> bool:
    r, l_ = parse_version(remote), parse_version(local)
    return bool(r and l_ and r > l_)


@dataclass
class Update:
    version: str
    url: str
    size: int
    sha256: str | None


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 - fixed https GitHub URL
        return json.load(resp)


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": HEADERS["User-Agent"]})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as out:  # noqa: S310
        while chunk := resp.read(1 << 16):
            out.write(chunk)


def check(current: str | None, get_json: Callable[[str], dict] = _get_json) -> Update | None:
    """The newer release for this build, or None (no update, not a release build, or no exe asset)."""
    if not current:
        return None
    data = get_json(LATEST_URL)
    tag = data.get("tag_name", "")
    if data.get("draft") or data.get("prerelease") or not is_newer(tag, current):
        return None
    for asset in data.get("assets", []):
        if asset.get("name") == ASSET_NAME and asset.get("browser_download_url"):
            digest = asset.get("digest") or ""
            return Update(tag.lstrip("vV"), asset["browser_download_url"], int(asset.get("size") or 0),
                          digest.split(":", 1)[1] if digest.startswith("sha256:") else None)
    return None


def download(update: Update, folder: Path, fetch: Callable[[str, Path], None] = _download) -> Path:
    """Download and verify the new exe; returns its path. Raises ValueError if it does not check out."""
    folder.mkdir(parents=True, exist_ok=True)
    part = folder / f"PersonalTimeTracker-{update.version}.part"
    fetch(update.url, part)
    data = part.read_bytes()
    if update.size and len(data) != update.size:
        part.unlink(missing_ok=True)
        raise ValueError("preuzeti fajl nema očekivanu veličinu")
    if update.sha256 and hashlib.sha256(data).hexdigest() != update.sha256.lower():
        part.unlink(missing_ok=True)
        raise ValueError("preuzeti fajl ne odgovara SHA-256 otisku")
    ready = folder / f"PersonalTimeTracker-{update.version}.exe"
    os.replace(part, ready)
    return ready


def old_path(exe: Path) -> Path:
    return exe.with_name(exe.stem + ".old.exe")


def install(new_exe: Path, current_exe: Path) -> None:
    """Swap the files: running exe -> *.old.exe, new exe -> the original name. Undone on failure."""
    old = old_path(current_exe)
    old.unlink(missing_ok=True)
    os.replace(current_exe, old)
    try:
        os.replace(new_exe, current_exe)
    except OSError:
        os.replace(old, current_exe)
        raise


def restart(exe: Path, popen=subprocess.Popen) -> None:
    """Start the new exe directly; it waits for this process to exit before its single-instance check.

    (No cmd.exe in between: quoting a path through `cmd /c start` broke it into "\\".)
    """
    flags = 0x00000008 if sys.platform == "win32" else 0  # DETACHED_PROCESS
    popen([str(exe), "--minimized", "--after-update", str(os.getpid())], creationflags=flags, close_fds=True)


def cleanup(current_exe: Path, folder: Path) -> None:
    """Remove leftovers of a previous update."""
    for path in [old_path(current_exe), *folder.glob("PersonalTimeTracker-*.part"),
                 *folder.glob("PersonalTimeTracker-*.exe")]:
        try:
            path.unlink()
        except OSError:
            pass


def running_exe() -> Path | None:
    """Path of the frozen exe, or None when running from source."""
    return Path(sys.executable) if getattr(sys, "frozen", False) else None
