import pytest

from app.config import get_settings
from app.db import get_database
from app.identity import get_directory

CACHED = (get_settings, get_database, get_directory)


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    for cached in CACHED:
        cached.cache_clear()
    yield
    for cached in CACHED:
        cached.cache_clear()
