import pytest

from app.config import DEFAULT_OPENAI_BASE_URL, PROJECT_ROOT, Settings


def test_empty_env_is_keyless_with_defaults():
    settings = Settings.from_env({})

    assert settings.keyless
    assert settings.openai_base_url == DEFAULT_OPENAI_BASE_URL
    assert settings.local_embeddings == "chroma"
    assert settings.database_path == PROJECT_ROOT / "var" / "release_gate.db"


def test_database_path_accepts_absolute_path(tmp_path):
    settings = Settings.from_env({"DATABASE_PATH": str(tmp_path / "demo.db")})

    assert settings.database_path == tmp_path / "demo.db"


def test_blank_key_is_keyless():
    assert Settings.from_env({"OPENAI_API_KEY": "   "}).keyless


def test_key_disables_keyless():
    assert not Settings.from_env({"OPENAI_API_KEY": "sk-test"}).keyless


def test_invalid_local_embeddings_is_rejected():
    with pytest.raises(ValueError, match="LOCAL_EMBEDDINGS"):
        Settings.from_env({"LOCAL_EMBEDDINGS": "bert"})


def test_repr_hides_secrets():
    settings = Settings.from_env(
        {
            "OPENAI_API_KEY": "sk-secret",
            "WEBHOOK_SECRET": "hmac-secret",
            "ADMIN_TOKEN": "admin-secret",
        }
    )

    assert "sk-secret" not in repr(settings)
    assert "hmac-secret" not in repr(settings)
    assert "admin-secret" not in repr(settings)
