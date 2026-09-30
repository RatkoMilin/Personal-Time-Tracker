"""Real Windows API calls (run on the windows-latest CI job)."""

import sys

import pytest

from timetracker import platform_win

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


def test_idle_seconds_is_sane():
    idle = platform_win.idle_seconds()
    assert isinstance(idle, float) and 0 <= idle < 50 * 86400


def test_single_instance_mutex(tmp_path):
    name = "PersonalTimeTrackerTestMutex"
    assert platform_win.acquire_single_instance(name, tmp_path) is True
    assert platform_win.acquire_single_instance(name, tmp_path) is False


def test_autostart_roundtrip():
    name = "PersonalTimeTrackerCITest"
    try:
        assert platform_win.set_autostart(name, True)
        assert platform_win.is_autostart_enabled(name)
    finally:
        platform_win.set_autostart(name, False)
    assert not platform_win.is_autostart_enabled(name)

