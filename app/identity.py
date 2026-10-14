"""演示用身分：從 X-Demo-User 讀身分，檢查停權、群組與試點名單。

正式環境由 IdP 同步（SAML 群組屬性與 SCIM）取代 config/users.yaml。
"""

from __future__ import annotations

import hmac
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

import yaml
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app import audit
from app.config import PROJECT_ROOT, get_settings
from app.pilot import PILOT_FILE, PilotConfig, load_pilot

USERS_FILE = PROJECT_ROOT / "config" / "users.yaml"

Group = Literal["employees", "engineers", "contractors"]


class User(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    department: str
    groups: tuple[Group, ...] = Field(min_length=1)
    active: bool


class UsersFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    departments: dict[str, str]
    users: list[User]

    @model_validator(mode="after")
    def _check_references(self) -> UsersFile:
        ids = [user.id for user in self.users]
        if len(ids) != len(set(ids)):
            raise ValueError("users.yaml 有重複的帳號")
        unknown = {user.department for user in self.users} - self.departments.keys()
        if unknown:
            raise ValueError(f"users.yaml 用到未定義的部門：{sorted(unknown)}")
        return self


class Directory:
    def __init__(self, users_file: UsersFile, pilot: PilotConfig) -> None:
        unknown = set(pilot.pilot_teams + pilot.next_teams) - users_file.departments.keys()
        if unknown:
            raise ValueError(f"pilot.yaml 用到未定義的部門：{sorted(unknown)}")

        self.departments = dict(users_file.departments)
        self.pilot_teams = set(pilot.pilot_teams)
        self._users = {user.id: user for user in users_file.users}

    def get(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    def set_active(self, user_id: str, active: bool) -> User:
        user = self._users[user_id].model_copy(update={"active": active})
        self._users[user_id] = user
        return user

    def in_pilot(self, user: User) -> bool:
        return user.department in self.pilot_teams


def load_directory(users_path: Path = USERS_FILE, pilot_path: Path = PILOT_FILE) -> Directory:
    users_file = UsersFile.model_validate(yaml.safe_load(users_path.read_text(encoding="utf-8")))
    return Directory(users_file, load_pilot(pilot_path))


@lru_cache
def get_directory() -> Directory:
    return load_directory()


DirectoryDep = Annotated[Directory, Depends(get_directory)]
DemoUserHeader = Annotated[str | None, Header(alias="X-Demo-User")]


def _authenticate(user_id: str, directory: Directory, request: Request) -> User:
    user = directory.get(user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"查無帳號：{user_id}")
    if not user.active:
        audit.record_event(
            user_id=user.id,
            endpoint=request.url.path,
            decision="block",
            detection_type="suspended_account",
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "帳號已停權")
    return user


def reject_suspended(
    request: Request, directory: DirectoryDep, x_demo_user: DemoUserHeader = None
) -> None:
    if x_demo_user is not None:
        _authenticate(x_demo_user, directory, request)


def current_user(
    request: Request, directory: DirectoryDep, x_demo_user: DemoUserHeader = None
) -> User:
    if x_demo_user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "缺少 X-Demo-User 標頭")
    return _authenticate(x_demo_user, directory, request)


CurrentUser = Annotated[User, Depends(current_user)]


def require_group(*groups: Group) -> Callable[..., User]:
    def dependency(user: CurrentUser) -> User:
        if not set(groups) & set(user.groups):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"需要以下任一群組：{'、'.join(groups)}")
        return user

    return dependency


def require_pilot() -> Callable[..., User]:
    def dependency(user: CurrentUser, directory: DirectoryDep) -> User:
        if not directory.in_pilot(user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "尚未開放：你的團隊不在試點名單內")
        return user

    return dependency


def require_admin_token(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = f"Bearer {get_settings().admin_token}".encode()
    if authorization is None or not hmac.compare_digest(authorization.encode(), expected):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "需要有效的管理權杖",
            headers={"WWW-Authenticate": "Bearer"},
        )


class Profile(BaseModel):
    id: str
    department: str
    department_name: str
    groups: list[str]
    active: bool
    in_pilot: bool


def _profile(user: User, directory: Directory) -> Profile:
    return Profile(
        id=user.id,
        department=user.department,
        department_name=directory.departments[user.department],
        groups=list(user.groups),
        active=user.active,
        in_pilot=directory.in_pilot(user),
    )


router = APIRouter()


@router.get("/api/me")
def me(user: CurrentUser, directory: DirectoryDep) -> Profile:
    return _profile(user, directory)


admin_router = APIRouter(prefix="/admin/users", dependencies=[Depends(require_admin_token)])


@admin_router.post("/{user_id}/suspend")
def suspend(user_id: str, directory: DirectoryDep) -> Profile:
    return _set_active(directory, user_id, active=False)


@admin_router.post("/{user_id}/reactivate")
def reactivate(user_id: str, directory: DirectoryDep) -> Profile:
    return _set_active(directory, user_id, active=True)


def _set_active(directory: Directory, user_id: str, *, active: bool) -> Profile:
    try:
        user = directory.set_active(user_id, active)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"查無帳號：{user_id}") from None
    return _profile(user, directory)
