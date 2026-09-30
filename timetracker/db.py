"""SQLite storage for projects, time entries, app activity and screenshots.

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
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    color       TEXT    NOT NULL DEFAULT '#4a90d9',
    hourly_rate REAL    NOT NULL DEFAULT 0,
    archived    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY,
    project_id  INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    description TEXT    NOT NULL DEFAULT '',
    start_ts    REAL    NOT NULL,
    end_ts      REAL,
    billable    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_entries_start ON entries(start_ts);
CREATE TABLE IF NOT EXISTS activity (
    id       INTEGER PRIMARY KEY,
    start_ts REAL NOT NULL,
    end_ts   REAL NOT NULL,
    app      TEXT NOT NULL,
    title    TEXT NOT NULL,
    entry_id INTEGER REFERENCES entries(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_activity_start ON activity(start_ts);
CREATE TABLE IF NOT EXISTS screenshots (
    id       INTEGER PRIMARY KEY,
    ts       REAL NOT NULL,
    path     TEXT NOT NULL,
    entry_id INTEGER REFERENCES entries(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_screenshots_ts ON screenshots(ts);
"""


@dataclass
class Project:
    id: int
    name: str
    color: str
    hourly_rate: float
    archived: bool


@dataclass
class Entry:
    id: int
    project_id: int | None
    description: str
    start_ts: float
    end_ts: float | None
    billable: bool

    @property
    def running(self) -> bool:
        return self.end_ts is None

    def duration(self, now: float | None = None) -> float:
        end = self.end_ts if self.end_ts is not None else (now or time.time())
        return max(0.0, end - self.start_ts)


@dataclass
class Activity:
    id: int
    start_ts: float
    end_ts: float
    app: str
    title: str
    entry_id: int | None


@dataclass
class Screenshot:
    id: int
    ts: float
    path: str
    entry_id: int | None


def _project(row) -> Project:
    return Project(row["id"], row["name"], row["color"], row["hourly_rate"], bool(row["archived"]))


def _entry(row) -> Entry:
    return Entry(row["id"], row["project_id"], row["description"], row["start_ts"], row["end_ts"],
                 bool(row["billable"]))


def _activity(row) -> Activity:
    return Activity(row["id"], row["start_ts"], row["end_ts"], row["app"], row["title"], row["entry_id"])


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

    def backup(self, path: str) -> None:
        """Write a consistent copy of the database to path."""
        target = sqlite3.connect(path)
        try:
            with self._lock:
                self._conn.backup(target)
        finally:
            target.close()

    def _exec(self, sql: str, params=()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _query(self, sql: str, params=()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    # ---------------------------------------------------------------- projects

    def add_project(self, name: str, color: str = "#4a90d9", hourly_rate: float = 0.0) -> int:
        name = name.strip()
        if not name:
            raise ValueError("Naziv projekta ne može biti prazan")
        try:
            cur = self._exec("INSERT INTO projects(name, color, hourly_rate) VALUES (?, ?, ?)",
                             (name, color, float(hourly_rate)))
        except sqlite3.IntegrityError:
            raise ValueError(f"Projekat '{name}' već postoji") from None
        return cur.lastrowid

    def update_project(self, project_id: int, *, name: str | None = None, color: str | None = None,
                       hourly_rate: float | None = None, archived: bool | None = None) -> None:
        fields, params = [], []
        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError("Naziv projekta ne može biti prazan")
            fields.append("name = ?")
            params.append(name)
        if color is not None:
            fields.append("color = ?")
            params.append(color)
        if hourly_rate is not None:
            fields.append("hourly_rate = ?")
            params.append(float(hourly_rate))
        if archived is not None:
            fields.append("archived = ?")
            params.append(int(archived))
        if not fields:
            return
        params.append(project_id)
        try:
            self._exec(f"UPDATE projects SET {', '.join(fields)} WHERE id = ?", params)
        except sqlite3.IntegrityError:
            raise ValueError(f"Projekat '{name}' već postoji") from None

    def delete_project(self, project_id: int) -> None:
        self._exec("DELETE FROM projects WHERE id = ?", (project_id,))

    def get_project(self, project_id: int | None) -> Project | None:
        if project_id is None:
            return None
        rows = self._query("SELECT * FROM projects WHERE id = ?", (project_id,))
        return _project(rows[0]) if rows else None

    def list_projects(self, include_archived: bool = False) -> list[Project]:
        sql = "SELECT * FROM projects"
        if not include_archived:
            sql += " WHERE archived = 0"
        sql += " ORDER BY archived, name COLLATE NOCASE"
        return [_project(r) for r in self._query(sql)]

    def project_map(self) -> dict[int, Project]:
        return {p.id: p for p in self.list_projects(include_archived=True)}

    # ----------------------------------------------------------------- entries

    def running_entry(self) -> Entry | None:
        rows = self._query("SELECT * FROM entries WHERE end_ts IS NULL ORDER BY start_ts DESC LIMIT 1")
        return _entry(rows[0]) if rows else None

    def start_entry(self, description: str = "", project_id: int | None = None, billable: bool = False,
                    start: float | None = None) -> int:
        """Start a new running entry, stopping any entry that is already running."""
        start = time.time() if start is None else start
        with self._lock:
            self.stop_running(start)
            cur = self._exec(
                "INSERT INTO entries(project_id, description, start_ts, end_ts, billable) VALUES (?, ?, ?, NULL, ?)",
                (project_id, description.strip(), start, int(billable)))
            return cur.lastrowid

    def stop_running(self, end: float | None = None) -> Entry | None:
        end = time.time() if end is None else end
        with self._lock:
            entry = self.running_entry()
            if entry is None:
                return None
            end = max(end, entry.start_ts)
            self._exec("UPDATE entries SET end_ts = ? WHERE id = ?", (end, entry.id))
            entry.end_ts = end
            return entry

    def add_entry(self, description: str, project_id: int | None, start: float, end: float,
                  billable: bool = False) -> int:
        if end <= start:
            raise ValueError("Kraj mora biti posle početka")
        cur = self._exec(
            "INSERT INTO entries(project_id, description, start_ts, end_ts, billable) VALUES (?, ?, ?, ?, ?)",
            (project_id, description.strip(), start, end, int(billable)))
        return cur.lastrowid

    _UNSET = object()

    def update_entry(self, entry_id: int, *, description: str | None = None, project_id=_UNSET,
                     start: float | None = None, end=_UNSET, billable: bool | None = None) -> None:
        fields, params = [], []
        if description is not None:
            fields.append("description = ?")
            params.append(description.strip())
        if project_id is not self._UNSET:
            fields.append("project_id = ?")
            params.append(project_id)
        if start is not None:
            fields.append("start_ts = ?")
            params.append(start)
        if end is not self._UNSET:
            fields.append("end_ts = ?")
            params.append(end)
        if billable is not None:
            fields.append("billable = ?")
            params.append(int(billable))
        if not fields:
            return
        params.append(entry_id)
        with self._lock:
            entry = self.get_entry(entry_id)
            if entry is None:
                return
            new_start = entry.start_ts if start is None else start
            new_end = entry.end_ts if end is self._UNSET else end
            if new_end is not None and new_end < new_start:
                raise ValueError("Kraj mora biti posle početka")
            self._exec(f"UPDATE entries SET {', '.join(fields)} WHERE id = ?", params)

    def delete_entry(self, entry_id: int) -> None:
        self._exec("DELETE FROM entries WHERE id = ?", (entry_id,))

    def get_entry(self, entry_id: int) -> Entry | None:
        rows = self._query("SELECT * FROM entries WHERE id = ?", (entry_id,))
        return _entry(rows[0]) if rows else None

    def entries_between(self, start: float, end: float) -> list[Entry]:
        """Entries overlapping [start, end), running entries included."""
        rows = self._query(
            "SELECT * FROM entries WHERE start_ts < ? AND (end_ts IS NULL OR end_ts > ?) ORDER BY start_ts DESC",
            (end, start))
        return [_entry(r) for r in rows]

    def recent_descriptions(self, limit: int = 30) -> list[tuple[str, int | None]]:
        rows = self._query(
            "SELECT description, project_id, MAX(start_ts) AS last FROM entries WHERE description != '' "
            "GROUP BY description, project_id ORDER BY last DESC LIMIT ?", (limit,))
        return [(r["description"], r["project_id"]) for r in rows]

    def discard_interval(self, entry_id: int, idle_start: float, idle_end: float,
                         continue_after: bool) -> int | None:
        """Remove [idle_start, idle_end) from an entry (used when idle time is discarded).

        The entry is cut at idle_start. If continue_after is set and the entry was
        running, a new running entry with the same details starts at idle_end.
        Returns the id of the new running entry, if any.
        """
        with self._lock:
            entry = self.get_entry(entry_id)
            if entry is None:
                return None
            was_running = entry.running
            if entry.start_ts >= idle_start:
                # The whole entry lies inside the idle period.
                if continue_after and was_running:
                    self.update_entry(entry.id, start=idle_end)
                    return entry.id
                self.delete_entry(entry.id)
                return None
            if was_running or entry.end_ts > idle_start:
                self.update_entry(entry.id, end=idle_start)
            if continue_after and was_running:
                cur = self._exec(
                    "INSERT INTO entries(project_id, description, start_ts, end_ts, billable) "
                    "VALUES (?, ?, ?, NULL, ?)",
                    (entry.project_id, entry.description, idle_end, int(entry.billable)))
                return cur.lastrowid
            return None

    # ---------------------------------------------------------------- activity

    def add_activity(self, app: str, title: str, start: float, end: float, entry_id: int | None) -> int:
        cur = self._exec("INSERT INTO activity(start_ts, end_ts, app, title, entry_id) VALUES (?, ?, ?, ?, ?)",
                         (start, end, app, title, entry_id))
        return cur.lastrowid

    def extend_activity(self, activity_id: int, end: float) -> None:
        self._exec("UPDATE activity SET end_ts = ? WHERE id = ?", (end, activity_id))

    def trim_activity_after(self, ts: float) -> None:
        """Drop activity recorded after ts (samples taken before idle was confirmed)."""
        with self._lock:
            self._exec("DELETE FROM activity WHERE start_ts >= ?", (ts,))
            self._exec("UPDATE activity SET end_ts = ? WHERE end_ts > ?", (ts, ts))

    def activity_between(self, start: float, end: float) -> list[Activity]:
        rows = self._query("SELECT * FROM activity WHERE start_ts < ? AND end_ts > ? ORDER BY start_ts",
                           (end, start))
        return [_activity(r) for r in rows]

    def delete_activity_before(self, ts: float) -> int:
        return self._exec("DELETE FROM activity WHERE end_ts < ?", (ts,)).rowcount

    # ------------------------------------------------------------- screenshots

    def add_screenshot(self, ts: float, path: str, entry_id: int | None) -> int:
        cur = self._exec("INSERT INTO screenshots(ts, path, entry_id) VALUES (?, ?, ?)", (ts, path, entry_id))
        return cur.lastrowid

    def screenshots_between(self, start: float, end: float) -> list[Screenshot]:
        rows = self._query("SELECT * FROM screenshots WHERE ts >= ? AND ts < ? ORDER BY ts", (start, end))
        return [Screenshot(r["id"], r["ts"], r["path"], r["entry_id"]) for r in rows]

    def pop_screenshots_before(self, ts: float) -> list[Screenshot]:
        with self._lock:
            rows = self._query("SELECT * FROM screenshots WHERE ts < ?", (ts,))
            self._exec("DELETE FROM screenshots WHERE ts < ?", (ts,))
        return [Screenshot(r["id"], r["ts"], r["path"], r["entry_id"]) for r in rows]
