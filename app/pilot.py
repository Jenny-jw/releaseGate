"""試點設定：哪些團隊在試點內、下一個候選團隊、開放門檻。"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import PROJECT_ROOT

PILOT_FILE = PROJECT_ROOT / "config" / "pilot.yaml"


class Thresholds(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    redteam_misses_max: int = Field(ge=0)
    qa_accuracy_min: float = Field(ge=0, le=1)
    referral_rate_max: float = Field(ge=0, le=1)
    ticket_delivery_rate_min: float = Field(ge=0, le=1)


class PilotConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    pilot_teams: tuple[str, ...] = Field(min_length=1)
    next_teams: tuple[str, ...]
    thresholds: Thresholds

    @model_validator(mode="after")
    def _teams_do_not_overlap(self) -> PilotConfig:
        overlap = set(self.pilot_teams) & set(self.next_teams)
        if overlap:
            raise ValueError(f"這些團隊同時在試點內與候選名單：{sorted(overlap)}")
        return self


def load_pilot(path: Path = PILOT_FILE) -> PilotConfig:
    return PilotConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
