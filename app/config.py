"""從環境變數讀取設定，並判斷是否為無金鑰模式。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

LOCAL_EMBEDDINGS_CHOICES = ("chroma", "hash")
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_LOCAL_EMBEDDINGS = "chroma"
DEFAULT_LEGAL_WEBHOOK_URL = "http://localhost:8000/webhooks/legal-ticket"
DEFAULT_WEBHOOK_SECRET = "demo-webhook-secret"
DEFAULT_ADMIN_TOKEN = "demo-admin-token"


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None = field(repr=False)
    openai_base_url: str
    llm_model: str | None
    embedding_model: str | None
    local_embeddings: str
    legal_webhook_url: str
    webhook_secret: str = field(repr=False)
    admin_token: str = field(repr=False)

    @property
    def keyless(self) -> bool:
        return self.openai_api_key is None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Settings:
        local_embeddings = (_get(env, "LOCAL_EMBEDDINGS") or DEFAULT_LOCAL_EMBEDDINGS).lower()
        if local_embeddings not in LOCAL_EMBEDDINGS_CHOICES:
            raise ValueError(
                f"LOCAL_EMBEDDINGS 必須是 {' 或 '.join(LOCAL_EMBEDDINGS_CHOICES)}，"
                f"目前是 {local_embeddings!r}"
            )

        return cls(
            openai_api_key=_get(env, "OPENAI_API_KEY"),
            openai_base_url=_get(env, "OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL,
            llm_model=_get(env, "LLM_MODEL"),
            embedding_model=_get(env, "EMBEDDING_MODEL"),
            local_embeddings=local_embeddings,
            legal_webhook_url=_get(env, "LEGAL_WEBHOOK_URL") or DEFAULT_LEGAL_WEBHOOK_URL,
            webhook_secret=_get(env, "WEBHOOK_SECRET") or DEFAULT_WEBHOOK_SECRET,
            admin_token=_get(env, "ADMIN_TOKEN") or DEFAULT_ADMIN_TOKEN,
        )


def _get(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name, "").strip()
    return value or None


@lru_cache
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings.from_env(os.environ)
