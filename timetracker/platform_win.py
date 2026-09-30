"""Windows integration through ctypes (no pywin32 needed).

Provides idle time, a single-instance mutex, DPI awareness and the "start
with Windows" registry entry. On other platforms every function degrades to a
harmless fallback so the app (and the tests) still run during development.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class _LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    _user32.GetLastInputInfo.argtypes = [ctypes.POINTER(_LASTINPUTINFO)]
    _user32.GetLastInputInfo.restype = wintypes.BOOL
    _kernel32.GetTickCount.argtypes = []
    _kernel32.GetTickCount.restype = wintypes.DWORD
    _kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    _kernel32.CreateMutexW.restype = wintypes.HANDLE

    _ERROR_ALREADY_EXISTS = 183


def idle_seconds() -> float:
    """Seconds since the last keyboard or mouse input (system wide)."""
    if not IS_WINDOWS:
        return 0.0
    info = _LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not _user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    # Both values are 32-bit tick counts that wrap every ~49.7 days.
    millis = (_kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF
    return millis / 1000.0


def enable_dpi_awareness() -> None:
    """Keep tkinter crisp on high-DPI laptop screens."""
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def set_app_user_model_id(app_id: str) -> None:
    """Give the process its own taskbar identity (icon/grouping) instead of python.exe."""
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


_mutex_handle = None
_lock_file = None


def acquire_single_instance(name: str, lock_dir: Path) -> bool:
    """Return False if another instance of the app is already running."""
    global _mutex_handle, _lock_file
    if IS_WINDOWS:
        _mutex_handle = _kernel32.CreateMutexW(None, False, f"Local\\{name}")
        return ctypes.get_last_error() != _ERROR_ALREADY_EXISTS
    try:
        import fcntl
    except ImportError:
        return True
    _lock_file = open(lock_dir / f"{name}.lock", "w")
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


# ----------------------------------------------------------------- autostart

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    if pythonw.exists():
        exe = pythonw
    script = Path(__file__).resolve().parent.parent / "main.pyw"
    return f'"{exe}" "{script}" --minimized'


def set_autostart(name: str, enabled: bool) -> bool:
    """Add or remove the HKCU Run entry. Returns True on success."""
    if not IS_WINDOWS:
        return False
    import winreg

    try:
        # CreateKeyEx also opens the key; it only creates it on profiles where it is missing.
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, autostart_command())
            else:
                try:
                    winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def is_autostart_enabled(name: str) -> bool:
    if not IS_WINDOWS:
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, name)
            return True
    except OSError:
        return False


def alert_sound() -> bool:
    """Play the Windows exclamation sound. Returns False where it is unavailable."""
    if not IS_WINDOWS:
        return False
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        return True
    except (ImportError, RuntimeError):
        return False


def open_path(path: Path) -> None:
    """Open a file or folder with the default application."""
    if IS_WINDOWS:
        os.startfile(str(path))  # noqa: S606 - opening local user data
    else:
        import subprocess

        subprocess.Popen(["xdg-open", str(path)])
