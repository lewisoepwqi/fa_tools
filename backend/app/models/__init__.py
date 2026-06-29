"""平台共享数据模型（用户、公司账套、审计日志、源文件）。

各财务工具的领域模型位于 ``app.tools.<tool>.models``，不在此导出。
本模块的导入会触发共享表注册到 ``Base.metadata``，供 Alembic 和测试发现。
"""

from app.models import associations  # noqa: F401  触发关联表注册到 Base.metadata
from app.models.audit import AuditLog
from app.models.company import BankAccount, Company
from app.models.file import SourceFile
from app.models.user import Role, User

__all__ = [
    "AuditLog",
    "BankAccount",
    "Company",
    "Role",
    "SourceFile",
    "User",
]
