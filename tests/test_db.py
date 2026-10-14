import sqlite3

import pytest

from app.db import Database

EXPECTED_COLUMNS = {
    "audit_events": {
        "id",
        "created_at",
        "user_id",
        "endpoint",
        "decision",
        "detection_type",
        "content_hash",
        "masked_summary",
    },
    "tickets": {
        "id",
        "created_at",
        "requester",
        "reason",
        "question_summary",
        "status",
        "attempts",
    },
    "qa_log": {
        "id",
        "created_at",
        "user_id",
        "question_hash",
        "question_summary",
        "answer_mode",
        "prompt_version",
        "citations",
        "referred",
        "ticket_id",
    },
}


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def insert_event(db: Database, **overrides) -> int:
    fields = {
        "user_id": "amy",
        "endpoint": "/gateway/check",
        "decision": "block",
        "detection_type": "unreleased_lyrics",
        "content_hash": "0" * 64,
        "masked_summary": "[遮罩]",
    }
    return db.insert_audit_event(**{**fields, **overrides})


@pytest.mark.parametrize("table", EXPECTED_COLUMNS)
def test_tables_have_expected_columns(db, table):
    with db.connect() as conn:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}

    assert columns == EXPECTED_COLUMNS[table]


def test_insert_and_read_audit_event(db):
    event_id = insert_event(db)

    [event] = db.recent_audit_events()
    assert event["id"] == event_id
    assert event["user_id"] == "amy"
    assert event["created_at"].endswith("+00:00")


def test_recent_audit_events_are_newest_first(db):
    first = insert_event(db)
    second = insert_event(db)

    assert [event["id"] for event in db.recent_audit_events()] == [second, first]


def test_invalid_decision_is_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        insert_event(db, decision="maybe")


def test_invalid_ticket_status_is_rejected(db):
    with pytest.raises(sqlite3.IntegrityError), db.connect() as conn:
        conn.execute(
            "INSERT INTO tickets (id, created_at, requester, reason, question_summary, status)"
            " VALUES ('LT-1', '2026-10-14T00:00:00+00:00', 'vendor01', 'contractor', '…', 'lost')"
        )


def test_reopening_keeps_existing_data(tmp_path):
    insert_event(Database(tmp_path / "test.db"))

    assert len(Database(tmp_path / "test.db").recent_audit_events()) == 1
