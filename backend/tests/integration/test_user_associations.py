from uuid import uuid4

from app.models.company import Company
from app.models.user import Role, User


def test_user_role_and_company_relationships(client_with_db):
    _, db = client_with_db
    user = User(id=str(uuid4()), email="a@x.com", password_hash="h")
    role = Role(id=str(uuid4()), code="processor", name="财务处理员")
    company = Company(id=str(uuid4()), name="甲公司")
    user.roles.append(role)
    user.companies.append(company)
    db.add_all([user, role, company])
    db.commit()
    db.refresh(user)
    assert [r.code for r in user.roles] == ["processor"]
    assert [c.name for c in user.companies] == ["甲公司"]
