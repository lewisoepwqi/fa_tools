"""平台共享路由：公司列表。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import CurrentUserDep, DbSession, accessible_company_filter, require
from app.core.permissions import Permission
from app.models.company import Company

router = APIRouter(prefix="/api/companies", tags=["companies"])


class CompanyResponse(BaseModel):
    id: str
    name: str


@router.get(
    "",
    response_model=list[CompanyResponse],
    dependencies=[Depends(require(Permission.READ))],
)
def list_companies(db: DbSession, user: CurrentUserDep) -> list[CompanyResponse]:
    """返回当前用户可访问的公司列表，按名称排序。跨公司角色返回全部。"""
    accessible = accessible_company_filter(user)
    q = db.query(Company)
    if accessible is not None:
        q = q.filter(Company.id.in_(accessible))
    return [CompanyResponse(id=c.id, name=c.name) for c in q.order_by(Company.name).all()]
