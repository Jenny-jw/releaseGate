"""稽核紀錄的入口。目前只寫進 log；1.4 改成寫入 SQLite 的 audit_events。"""

from __future__ import annotations

import logging
from typing import Literal

Decision = Literal["allow", "block", "mask"]

logger = logging.getLogger("release_gate.audit")


def record_event(
    *,
    user_id: str,
    endpoint: str,
    decision: Decision,
    detection_type: str | None = None,
) -> None:
    logger.warning(
        "audit user=%s endpoint=%s decision=%s detection_type=%s",
        user_id,
        endpoint,
        decision,
        detection_type,
    )
