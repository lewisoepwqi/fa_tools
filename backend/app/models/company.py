from sqlalchemy import ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import EncryptedString
from app.db.base import Base
from app.models.common import IdMixin, TimestampMixin


class Company(Base, IdMixin, TimestampMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )


class BankAccount(Base, IdMixin, TimestampMixin):
    __tablename__ = "bank_accounts"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_no_encrypted: Mapped[str] = mapped_column(EncryptedString(512), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="CNY",
        server_default=text("'CNY'"),
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )
