"""System tray icon (optional: needs pystray and Pillow).

pystray runs its own message loop on a separate thread, so every callback is
forwarded to the UI thread through `dispatch` instead of touching tkinter.
"""

from __future__ import annotations

from typing import Callable

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:  # ImportError, or a backend failing to load on Linux
    pystray = None

from . import APP_ID, APP_NAME


def available() -> bool:
    return pystray is not None


def make_icon_image(running: bool, size: int = 64):
    """Clock face; green while the timer runs, grey when stopped."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = (26, 143, 76, 255) if running else (110, 110, 110, 255)
    pad = size // 16
    d.ellipse((pad, pad, size - pad, size - pad), fill=color)
    c = size // 2
    w = max(2, size // 12)
    d.line((c, c, c, size // 4), fill="white", width=w)
    d.line((c, c, c + size // 5, c), fill="white", width=w)
    return img


class Tray:
    def __init__(self, dispatch: Callable[[Callable], None], on_show: Callable, on_toggle: Callable,
                 on_quit: Callable, is_running: Callable[[], bool]):
        self._dispatch = dispatch
        self._on_show = on_show
        self._on_toggle = on_toggle
        self._on_quit = on_quit
        self._is_running = is_running
        self._icon = None

    def start(self) -> bool:
        if pystray is None:
            return False
        menu = pystray.Menu(
            pystray.MenuItem("Prikaži", lambda: self._dispatch(self._on_show), default=True),
            pystray.MenuItem(lambda item: "Zaustavi tajmer" if self._is_running() else "Pokreni tajmer",
                             lambda: self._dispatch(self._on_toggle)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Izlaz", lambda: self._dispatch(self._on_quit)),
        )
        try:
            self._icon = pystray.Icon(APP_ID, make_icon_image(False), APP_NAME, menu)
            self._icon.run_detached()
        except Exception:
            self._icon = None
            return False
        return True

    def update(self, running: bool, tooltip: str) -> None:
        if self._icon is None:
            return
        try:
            self._icon.icon = make_icon_image(running)
            self._icon.title = tooltip[:120]
            self._icon.update_menu()
        except Exception:
            pass

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
