"""Application entry point."""

from __future__ import annotations

import argparse
import sys

from . import APP_ID, APP_NAME, platform_win
from .config import Settings, data_dir
from .db import Database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="timetracker", description=APP_NAME)
    parser.add_argument("--minimized", action="store_true", help="start hidden in the system tray")
    args = parser.parse_args(argv)

    platform_win.enable_dpi_awareness()
    platform_win.set_app_user_model_id(APP_ID)
    ddir = data_dir()

    if not platform_win.acquire_single_instance(APP_ID, ddir):
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(APP_NAME, "Aplikacija već radi.\nPotraži ikonicu pored sata na taskbaru.")
        root.destroy()
        return 1

    from .ui.player import Player

    settings = Settings()
    db = Database(ddir / "timetracker.db")
    try:
        app = Player(db, settings, ddir, start_minimized=args.minimized)
        app.mainloop()
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
