from sqlalchemy import String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.associations import user_companies, user_roles
from app.models.common import IdMixin, TimestampMixin
from app.models.company import Company


class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )

    # 多对多关系：用户拥有的角色与所属公司
    roles: Mapped[list["Role"]] = relationship("Role", secondary=user_roles, lazy="selectin")
    companies: Mapped[list[Company]] = relationship(
        "Company", secondary=user_companies, lazy="selectin"
    )


class Role(Base, IdMixin):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text())
