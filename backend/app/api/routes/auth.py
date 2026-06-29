from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.config import get_settings
from app.core.permissions import CROSS_COMPANY_ROLES
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import CompanyRef, LoginRequest, MeResponse, TokenResponse
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 定时侧信道防护：用户不存在时仍做一次 bcrypt 比较，使响应时间趋于一致。
_DUMMY_HASH = hash_password("dummy-password-for-timing")


@router.post("/login", response_model=TokenResponse)
def login(db: DbSession, payload: LoginRequest, request: Request) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None:
        # 仍做 bcrypt 比较以平衡响应时间，防止通过耗时枚举邮箱。
        verify_password(payload.password, _DUMMY_HASH)
    ok = user is not None and user.status == "active" and verify_password(
        payload.password, user.password_hash
    )
    if not ok:
        record_audit_event(
            db,
            company_id=None,
            actor_id=user.id if user else None,
            action="login",
            entity_type="user",
            entity_id=user.id if user else "unknown",
            after={"success": False},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码错误")
    settings = get_settings()
    token = create_access_token(
        user_id=user.id,
        roles=[r.code for r in user.roles],
        ttl_minutes=settings.access_token_ttl_minutes,
        secret=settings.secret_key,
    )
    record_audit_event(
        db,
        company_id=None,
        actor_id=user.id,
        action="login",
        entity_type="user",
        entity_id=user.id,
        after={"success": True},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(db: DbSession, user: CurrentUserDep) -> MeResponse:
    db_user = db.get(User, user.id)
    if db_user is None:
        # Token 签发后用户已被删除。
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    cross = any(r in CROSS_COMPANY_ROLES for r in user.roles)
    companies: list[CompanyRef] | str
    if cross:
        companies = "all"
    else:
        companies = [CompanyRef(id=c.id, name=c.name) for c in db_user.companies]
    return MeResponse(
        id=db_user.id,
        email=db_user.email,
        name=db_user.name,
        roles=user.roles,
        accessible_companies=companies,
    )
