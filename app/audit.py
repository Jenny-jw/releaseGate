"""稽核紀錄：內容只存 SHA-256 雜湊與遮罩後的前 40 字，不存原文。"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Literal

from app.db import get_database

Decision = Literal["allow", "block", "mask"]
Span = tuple[int, int]

MASK = "[遮罩]"
SUMMARY_LENGTH = 40


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def masked_summary(content: str, sensitive_spans: Iterable[Span] = ()) -> str:
    pieces = []
    cursor = 0
    for start, end in _merge_spans(sensitive_spans, len(content)):
        pieces.append(content[cursor:start])
        pieces.append(MASK)
        cursor = end
    pieces.append(content[cursor:])

    masked = " ".join("".join(pieces).split())
    if len(masked) <= SUMMARY_LENGTH:
        return masked
    return masked[:SUMMARY_LENGTH] + "…"


def _merge_spans(spans: Iterable[Span], length: int) -> list[Span]:
    clamped = sorted((max(0, start), min(length, end)) for start, end in spans)
    merged: list[Span] = []
    for start, end in clamped:
        if start >= end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def record_event(
    *,
    user_id: str,
    endpoint: str,
    decision: Decision,
    detection_type: str | None = None,
    content: str | None = None,
    sensitive_spans: Iterable[Span] = (),
) -> int:
    return get_database().insert_audit_event(
        user_id=user_id,
        endpoint=endpoint,
        decision=decision,
        detection_type=detection_type,
        content_hash=None if content is None else content_hash(content),
        masked_summary=None if content is None else masked_summary(content, sensitive_spans),
    )
