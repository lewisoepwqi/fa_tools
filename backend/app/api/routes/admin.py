"""管理端点：用户 CRUD、角色分配、公司授权管理。

所有端点均要求 USER_MANAGE 权限（仅 admin 角色拥有），在路由器层统一守卫。
"""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import CurrentUserDep, DbSession, require
from app.core.permissions import Permission
from app.core.security import hash_password
from app.models.company import Company
from app.models.user import Role, User
from app.schemas.auth import (
    AdminUserCreate,
    AdminUserResponse,
    CompanyIds,
    RoleCodes,
)
from app.services.audit_service import audit_ctx, record_audit_event

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require(Permission.USER_MANAGE))],
)


def _to_response(user: User) -> AdminUserResponse:
    """把 User ORM 对象转为响应 schema（不含 password_hash）。"""
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        roles=[r.code for r in user.roles],
        company_ids=[c.id for c in user.companies],
    )


def _bind_roles(db, user: User, role_codes: list[str]) -> None:
    """按 code 列表替换用户角色；未知 code 抛 422。"""
    user.roles = []
    for code in role_codes:
        role = db.query(Role).filter(Role.code == code).first()
        if role is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"未知角色 {code}")
        user.roles.append(role)


def _bind_companies(db, user: User, company_ids: list[str]) -> None:
    """按 id 列表替换公司授权；未知 id 抛 422。"""
    user.companies = []
    for cid in company_ids:
        company = db.get(Company, cid)
        if company is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"未知公司 {cid}")
        user.companies.append(company)


@router.post("/users", response_model=AdminUserResponse)
def create_user(
    db: DbSession,
    actor: CurrentUserDep,
    request: Request,
    payload: AdminUserCreate,
) -> AdminUserResponse:
    """创建用户，绑定角色和公司，写审计日志 user.created。"""
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "邮箱已存在")
    user = User(
        id=str(uuid4()),
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        status="active",
    )
    db.add(user)
    _bind_roles(db, user, payload.role_codes)
    _bind_companies(db, user, payload.company_ids)
    db.commit()
    db.refresh(user)
    resp = _to_response(user)
    record_audit_event(
        db,
        company_id=None,
        actor_id=actor.id,
        action="user.created",
        entity_type="user",
        entity_id=user.id,
        after=resp.model_dump(),
        **audit_ctx(request),
    )
    return resp


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(db: DbSession) -> list[AdminUserResponse]:
    """列出所有用户（不含 password_hash）。"""
    return [_to_response(u) for u in db.query(User).all()]


@router.put("/users/{user_id}/roles", response_model=AdminUserResponse)
def set_roles(
    db: DbSession,
    actor: CurrentUserDep,
    request: Request,
    user_id: str,
    payload: RoleCodes,
) -> AdminUserResponse:
    """替换用户角色，写审计日志 permission.changed（before/after）。"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    before = _to_response(user).model_dump()
    _bind_roles(db, user, payload.role_codes)
    db.commit()
    db.refresh(user)
    after = _to_response(user)
    record_audit_event(
        db,
        company_id=None,
        actor_id=actor.id,
        action="permission.changed",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after=after.model_dump(),
        **audit_ctx(request),
    )
    return after


@router.put("/users/{user_id}/companies", response_model=AdminUserResponse)
def set_companies(
    db: DbSession,
    actor: CurrentUserDep,
    request: Request,
    user_id: str,
    payload: CompanyIds,
) -> AdminUserResponse:
    """替换用户公司授权，写审计日志 permission.changed（before/after）。"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    before = _to_response(user).model_dump()
    _bind_companies(db, user, payload.company_ids)
    db.commit()
    db.refresh(user)
    after = _to_response(user)
    record_audit_event(
        db,
        company_id=None,
        actor_id=actor.id,
        action="permission.changed",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after=after.model_dump(),
        **audit_ctx(request),
    )
    return after
