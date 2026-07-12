"""SQLite storage for voice profiles and their recorded takes.

One database file, stdlib sqlite3, dict rows. This is the durable record
of what voices exist and where their trained models live; the takes table
tracks the raw recordings collected before training.
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from typing import Any, Optional

from . import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS voice_profiles (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'collecting',
    created_at  REAL NOT NULL,
    trained_at  REAL,
    model_path  TEXT,
    index_path  TEXT,
    sample_rate INTEGER NOT NULL DEFAULT 40000,
    epochs      INTEGER,
    detail      TEXT,
    error       TEXT
);

CREATE TABLE IF NOT EXISTS voice_takes (
    id           TEXT PRIMARY KEY,
    profile_id   TEXT NOT NULL,
    filename     TEXT NOT NULL,
    seconds      REAL NOT NULL,
    script_index INTEGER,
    created_at   REAL NOT NULL,
    FOREIGN KEY (profile_id) REFERENCES voice_profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tracks (
    id               TEXT PRIMARY KEY,
    prompt           TEXT NOT NULL,
    caption          TEXT,
    lyrics           TEXT,
    vocal_language   TEXT,
    bpm              INTEGER,
    audio_path       TEXT NOT NULL,
    voice_profile_id TEXT,
    voice_name       TEXT,
    instrumental     INTEGER NOT NULL DEFAULT 0,
    created_at       REAL NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)


# ---------- profiles ----------

def create_profile(name: str, sample_rate: int = 40000) -> dict[str, Any]:
    pid = uuid.uuid4().hex[:12]
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO voice_profiles (id, name, status, created_at, sample_rate) "
            "VALUES (?, ?, 'collecting', ?, ?)",
            (pid, name, now, sample_rate),
        )
    return get_profile(pid)  # type: ignore[return-value]


def get_profile(profile_id: str) -> Optional[dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM voice_profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["total_seconds"] = _total_seconds(conn, profile_id)
        return data


def list_profiles() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM voice_profiles ORDER BY created_at DESC"
        ).fetchall()
        out = []
        for row in rows:
            data = dict(row)
            data["total_seconds"] = _total_seconds(conn, data["id"])
            out.append(data)
        return out


def update_profile(profile_id: str, **fields: Any) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _connect() as conn:
        conn.execute(
            f"UPDATE voice_profiles SET {cols} WHERE id = ?",
            (*fields.values(), profile_id),
        )


def delete_profile(profile_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM voice_profiles WHERE id = ?", (profile_id,))


# ---------- takes ----------

def add_take(profile_id: str, filename: str, seconds: float, script_index: int | None) -> dict[str, Any]:
    tid = uuid.uuid4().hex[:12]
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO voice_takes (id, profile_id, filename, seconds, script_index, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (tid, profile_id, filename, seconds, script_index, now),
        )
        row = conn.execute("SELECT * FROM voice_takes WHERE id = ?", (tid,)).fetchone()
        return dict(row)


def list_takes(profile_id: str) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM voice_takes WHERE profile_id = ? ORDER BY created_at",
            (profile_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_take(take_id: str) -> Optional[dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM voice_takes WHERE id = ?", (take_id,)).fetchone()
        return dict(row) if row else None


def delete_take(take_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM voice_takes WHERE id = ?", (take_id,))


# ---------- tracks ----------

def create_track(**fields: Any) -> dict[str, Any]:
    tid = uuid.uuid4().hex[:12]
    fields["id"] = tid
    fields["created_at"] = time.time()
    cols = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    with _connect() as conn:
        conn.execute(f"INSERT INTO tracks ({cols}) VALUES ({marks})", tuple(fields.values()))
        row = conn.execute("SELECT * FROM tracks WHERE id = ?", (tid,)).fetchone()
        return dict(row)


def list_tracks() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM tracks ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_track(track_id: str) -> Optional[dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
        return dict(row) if row else None


def delete_track(track_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM tracks WHERE id = ?", (track_id,))


def _total_seconds(conn: sqlite3.Connection, profile_id: str) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(seconds), 0) AS total FROM voice_takes WHERE profile_id = ?",
        (profile_id,),
    ).fetchone()
    return float(row["total"])
