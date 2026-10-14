import hashlib

from app import audit
from app.config import get_settings
from app.db import get_database

PROMPT = "幫我翻譯這段歌詞："
LYRICS = (
    "Quand la mer se retire, je compte les éclats de lumière\n"
    "Cachés depuis hier dans les fentes des rochers"
)
CONTENT = PROMPT + LYRICS
LYRICS_SPAN = (len(PROMPT), len(CONTENT))


def test_summary_masks_sensitive_spans():
    assert audit.masked_summary(CONTENT, [LYRICS_SPAN]) == PROMPT + audit.MASK


def test_summary_merges_overlapping_spans():
    assert audit.masked_summary("abcdefgh", [(1, 4), (3, 6)]) == "a" + audit.MASK + "gh"


def test_summary_ignores_out_of_range_and_empty_spans():
    assert audit.masked_summary("abc", [(-5, 1), (2, 2), (2, 99)]) == (
        audit.MASK + "b" + audit.MASK
    )


def test_summary_collapses_whitespace_and_truncates_to_40_chars():
    summary = audit.masked_summary("第一行\n\n第二行   " + "字" * 60)

    assert "\n" not in summary
    assert summary.startswith("第一行 第二行 字")
    assert summary.endswith("…")
    assert len(summary) == audit.SUMMARY_LENGTH + 1


def test_event_without_content_stores_no_hash_or_summary():
    audit.record_event(user_id="kai", endpoint="/api/me", decision="block")

    [event] = get_database().recent_audit_events()
    assert event["content_hash"] is None
    assert event["masked_summary"] is None


def test_raw_content_never_reaches_the_database_file():
    audit.record_event(
        user_id="amy",
        endpoint="/gateway/check",
        decision="block",
        detection_type="unreleased_lyrics",
        content=CONTENT,
        sensitive_spans=[LYRICS_SPAN],
    )

    [event] = get_database().recent_audit_events()
    assert event["content_hash"] == hashlib.sha256(CONTENT.encode("utf-8")).hexdigest()
    assert event["masked_summary"] == PROMPT + audit.MASK

    stored = get_settings().database_path.read_bytes()
    assert CONTENT.encode("utf-8") not in stored
    for line in LYRICS.splitlines():
        assert line.encode("utf-8") not in stored
    assert "je compte les éclats".encode() not in stored
