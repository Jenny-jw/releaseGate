"""SQLite 資料庫：稽核紀錄、法務工單、問答紀錄。

這一層只收雜湊與遮罩摘要，不收原文；遮罩在 app/audit.py 完成。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at     TEXT NOT NULL,
    user_id        TEXT NOT NULL,
    endpoint       TEXT NOT NULL,
    decision       TEXT NOT NULL CHECK (decision IN ('allow', 'block', 'mask')),
    detection_type TEXT,
    content_hash   TEXT,
    masked_summary TEXT
);

CREATE TABLE IF NOT EXISTS tickets (
    id               TEXT PRIMARY KEY,
    created_at       TEXT NOT NULL,
    requester        TEXT NOT NULL,
    reason           TEXT NOT NULL,
    question_summary TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'delivered', 'failed')),
    attempts         INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS qa_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at       TEXT NOT NULL,
    user_id          TEXT NOT NULL,
    question_hash    TEXT NOT NULL,
    question_summary TEXT NOT NULL,
    answer_mode      TEXT NOT NULL CHECK (answer_mode IN ('llm', 'keyless')),
    prompt_version   TEXT,
    citations        TEXT NOT NULL DEFAULT '[]',
    referred         INTEGER NOT NULL DEFAULT 0 CHECK (referred IN (0, 1)),
    ticket_id        TEXT REFERENCES tickets (id)
);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.path)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            with conn:
                yield conn

    def insert_audit_event(
        self,
        *,
        user_id: str,
        endpoint: str,
        decision: str,
        detection_type: str | None,
        content_hash: str | None,
        masked_summary: str | None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO audit_events
                    (created_at, user_id, endpoint, decision,
                     detection_type, content_hash, masked_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    utc_now(),
                    user_id,
                    endpoint,
                    decision,
                    detection_type,
                    content_hash,
                    masked_summary,
                ),
            )
            return int(cursor.lastrowid)

    def recent_audit_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]


@lru_cache
def get_database() -> Database:
    return Database(get_settings().database_path)
