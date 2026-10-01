"""SQLite storage for projects and time entries.

One connection is shared between the UI thread and the tracker thread and every
access is serialized with a lock, which is plenty for a single-user desktop app.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);
CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY,
    project_id  INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    description TEXT NOT NULL DEFAULT '',
    start_ts    REAL NOT NULL,
    end_ts      REAL
);
CREATE INDEX IF NOT EXISTS idx_entries_start ON entries(start_ts);
CREATE TABLE IF NOT EXISTS activity (
    id       INTEGER PRIMARY KEY,
    start_ts REAL NOT NULL,
    end_ts   REAL NOT NULL,
    category TEXT NOT NULL,
    label    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_activity_start ON activity(start_ts);
"""


@dataclass
class Entry:
    id: int
    project_id: int | None
    description: str
    start_ts: float
    end_ts: float | None

    @property
    def running(self) -> bool:
        return self.end_ts is None

    def duration(self, now: float | None = None) -> float:
        end = self.end_ts if self.end_ts is not None else (now or time.time())
        return max(0.0, end - self.start_ts)


def _entry(row) -> Entry:
    return Entry(row["id"], row["project_id"], row["description"], row["start_ts"], row["end_ts"])


class Database:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            if self.path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _exec(self, sql: str, params=()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _query(self, sql: str, params=()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    # ---------------------------------------------------------------- projects

    def project_id(self, name: str) -> int | None:
        """Id of the project with this name, creating it if needed. Empty name means no project."""
        name = name.strip()
        if not name:
            return None
        with self._lock:
            rows = self._query("SELECT id FROM projects WHERE name = ?", (name,))
            if rows:
                return rows[0]["id"]
            return self._exec("INSERT INTO projects(name) VALUES (?)", (name,)).lastrowid

    def project_names(self) -> dict[int, str]:
        return {r["id"]: r["name"] for r in self._query("SELECT * FROM projects ORDER BY name COLLATE NOCASE")}

    # ----------------------------------------------------------------- entries

    def running_entry(self) -> Entry | None:
        rows = self._query("SELECT * FROM entries WHERE end_ts IS NULL ORDER BY start_ts DESC LIMIT 1")
        return _entry(rows[0]) if rows else None

    def start_entry(self, description: str = "", project_id: int | None = None,
                    start: float | None = None) -> int:
        """Start a new running entry, stopping any entry that is already running."""
        start = time.time() if start is None else start
        with self._lock:
            self.stop_running(start)
            return self._exec("INSERT INTO entries(project_id, description, start_ts) VALUES (?, ?, ?)",
                              (project_id, description.strip(), start)).lastrowid

    def stop_running(self, end: float | None = None) -> Entry | None:
        end = time.time() if end is None else end
        with self._lock:
            entry = self.running_entry()
            if entry is None:
                return None
            entry.end_ts = max(end, entry.start_ts)
            self._exec("UPDATE entries SET end_ts = ? WHERE id = ?", (entry.end_ts, entry.id))
            return entry

    def add_entry(self, description: str, project_id: int | None, start: float, end: float) -> int:
        if end <= start:
            raise ValueError("Kraj mora biti posle početka")
        return self._exec("INSERT INTO entries(project_id, description, start_ts, end_ts) VALUES (?, ?, ?, ?)",
                          (project_id, description.strip(), start, end)).lastrowid

    def update_entry(self, entry_id: int, description: str, project_id: int | None, start: float,
                     end: float | None) -> None:
        if end is not None and end <= start:
            raise ValueError("Kraj mora biti posle početka")
        self._exec("UPDATE entries SET description = ?, project_id = ?, start_ts = ?, end_ts = ? WHERE id = ?",
                   (description.strip(), project_id, start, end, entry_id))

    def delete_entry(self, entry_id: int) -> None:
        self._exec("DELETE FROM entries WHERE id = ?", (entry_id,))

    def get_entry(self, entry_id: int) -> Entry | None:
        rows = self._query("SELECT * FROM entries WHERE id = ?", (entry_id,))
        return _entry(rows[0]) if rows else None

    def entries_between(self, start: float, end: float) -> list[Entry]:
        """Entries overlapping [start, end), oldest first, running entry included."""
        rows = self._query(
            "SELECT * FROM entries WHERE start_ts < ? AND (end_ts IS NULL OR end_ts > ?) ORDER BY start_ts",
            (end, start))
        return [_entry(r) for r in rows]

    def discard_interval(self, entry_id: int, idle_start: float, idle_end: float, continue_after: bool) -> None:
        """Cut [idle_start, idle_end) out of a running entry (idle time the user discarded).

        The entry ends at idle_start; with continue_after a new running entry with the
        same task and project starts at idle_end.
        """
        with self._lock:
            entry = self.get_entry(entry_id)
            if entry is None or not entry.running:
                return
            if entry.start_ts >= idle_start:
                self.delete_entry(entry.id)
            else:
                self._exec("UPDATE entries SET end_ts = ? WHERE id = ?", (idle_start, entry.id))
            if continue_after:
                self._exec("INSERT INTO entries(project_id, description, start_ts) VALUES (?, ?, ?)",
                           (entry.project_id, entry.description, idle_end))

    # ---------------------------------------------------------------- activity

    def add_activity(self, category: str, label: str, start: float, end: float) -> int:
        return self._exec("INSERT INTO activity(start_ts, end_ts, category, label) VALUES (?, ?, ?, ?)",
                          (start, end, category, label)).lastrowid

    def extend_activity(self, activity_id: int, end: float) -> None:
        self._exec("UPDATE activity SET end_ts = ? WHERE id = ?", (end, activity_id))

    def trim_activity_after(self, ts: float) -> None:
        """Drop activity after ts (samples taken before an idle period was recognised)."""
        with self._lock:
            self._exec("DELETE FROM activity WHERE start_ts >= ?", (ts,))
            self._exec("UPDATE activity SET end_ts = ? WHERE end_ts > ?", (ts, ts))

    def activity_between(self, start: float, end: float) -> list[tuple[float, float, str, str]]:
        rows = self._query("SELECT start_ts, end_ts, category, label FROM activity "
                           "WHERE start_ts < ? AND end_ts > ? ORDER BY start_ts", (end, start))
        return [(r["start_ts"], r["end_ts"], r["category"], r["label"]) for r in rows]
