from typing import Annotated

import pytest
import yaml
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import get_database
from app.identity import (
    USERS_FILE,
    Directory,
    User,
    UsersFile,
    load_directory,
    require_group,
    require_pilot,
)
from app.main import app
from app.pilot import load_pilot


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def as_user(user_id: str) -> dict[str, str]:
    return {"X-Demo-User": user_id}


def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_settings().admin_token}"}


def test_seed_has_the_six_demo_accounts():
    directory = load_directory()
    for user_id in ["amy", "ben", "lin", "chen", "vendor01", "kai"]:
        assert directory.get(user_id) is not None


def test_missing_header_is_401(client):
    assert client.get("/api/me").status_code == 401


def test_unknown_user_is_401(client):
    assert client.get("/api/me", headers=as_user("nobody")).status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/me"),
        ("GET", "/health"),
        ("POST", "/admin/users/kai/reactivate"),
    ],
)
def test_suspended_kai_gets_403_everywhere_and_is_audited(client, method, path):
    response = client.request(method, path, headers={**as_user("kai"), **admin_headers()})

    assert response.status_code == 403
    [event] = get_database().recent_audit_events()
    assert event["user_id"] == "kai"
    assert event["endpoint"] == path
    assert event["decision"] == "block"
    assert event["detection_type"] == "suspended_account"


@pytest.mark.parametrize(
    ("user_id", "in_pilot"),
    [("amy", False), ("ben", False), ("lin", True), ("chen", True), ("vendor01", True)],
)
def test_me_reports_pilot_membership(client, user_id, in_pilot):
    response = client.get("/api/me", headers=as_user(user_id))

    assert response.status_code == 200
    assert response.json()["id"] == user_id
    assert response.json()["in_pilot"] is in_pilot


def test_suspending_chen_blocks_him_immediately_and_reactivate_restores(client):
    assert client.get("/api/me", headers=as_user("chen")).status_code == 200

    response = client.post("/admin/users/chen/suspend", headers=admin_headers())
    assert response.status_code == 200
    assert response.json()["active"] is False
    assert client.get("/api/me", headers=as_user("chen")).status_code == 403

    assert client.post("/admin/users/chen/reactivate", headers=admin_headers()).status_code == 200
    assert client.get("/api/me", headers=as_user("chen")).status_code == 200


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong-token"}])
def test_admin_endpoints_require_token(client, headers):
    response = client.post("/admin/users/chen/suspend", headers=headers)

    assert response.status_code == 401
    assert client.get("/api/me", headers=as_user("chen")).status_code == 200


def test_admin_unknown_user_is_404(client):
    assert client.post("/admin/users/nobody/suspend", headers=admin_headers()).status_code == 404


@pytest.fixture
def guarded_client():
    guarded = FastAPI()

    @guarded.get("/engineers-only")
    def engineers_only(user: Annotated[User, Depends(require_group("engineers", "contractors"))]):
        return {"id": user.id}

    @guarded.get("/pilot-only")
    def pilot_only(user: Annotated[User, Depends(require_pilot())]):
        return {"id": user.id}

    return TestClient(guarded)


@pytest.mark.parametrize(
    ("user_id", "expected"),
    [("chen", 200), ("vendor01", 200), ("lin", 403), ("amy", 403)],
)
def test_require_group(guarded_client, user_id, expected):
    assert guarded_client.get("/engineers-only", headers=as_user(user_id)).status_code == expected


@pytest.mark.parametrize(
    ("user_id", "expected"),
    [("lin", 200), ("chen", 200), ("amy", 403), ("ben", 403)],
)
def test_require_pilot(guarded_client, user_id, expected):
    response = guarded_client.get("/pilot-only", headers=as_user(user_id))

    assert response.status_code == expected
    if expected == 403:
        assert "尚未開放" in response.json()["detail"]


def test_pilot_team_must_be_a_known_department():
    users_file = UsersFile.model_validate(yaml.safe_load(USERS_FILE.read_text(encoding="utf-8")))
    pilot = load_pilot().model_copy(update={"pilot_teams": ("finance",)})

    with pytest.raises(ValueError, match="finance"):
        Directory(users_file, pilot)
