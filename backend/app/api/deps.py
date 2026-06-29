from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import (
    CROSS_COMPANY_ROLES,
    Permission,
    permissions_for,
)
from app.core.security import TokenError, decode_access_token
from app.db.session import get_db
from app.models.user import User

DbSession = Annotated[Session, Depends(get_db)]


@dataclass
class CurrentUser:
    id: str
    roles: list[str]
    permissions: set[Permission]
    accessible_company_ids: set[str] | None  # None = 全公司(跨公司角色)


def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未认证")
    token = authorization.split(" ", 1)[1]
    try:
        claims = decode_access_token(token, get_settings().secret_key)
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "令牌无效") from exc
    user = db.get(User, claims.get("sub"))
    if user is None or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不可用")
    roles = [r.code for r in user.roles]
    cross = any(r in CROSS_COMPANY_ROLES for r in roles)
    accessible = None if cross else {c.id for c in user.companies}
    return CurrentUser(
        id=user.id,
        roles=roles,
        permissions=permissions_for(roles),
        accessible_company_ids=accessible,
    )


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require(*perms: Permission):
    def _checker(user: CurrentUserDep) -> CurrentUser:
        if not set(perms).issubset(user.permissions):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "权限不足")
        return user

    return _checker


def require_company_access(user: CurrentUser, company_id: str | None) -> None:
    if user.accessible_company_ids is None:
        return  # 跨公司角色
    if company_id is None or company_id not in user.accessible_company_ids:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该公司数据")


def accessible_company_filter(user: CurrentUser) -> set[str] | None:
    return user.accessible_company_ids
