"""银行流水转公司日记账工具。

本工具作为 fa_tools 工具包中的一个独立模块：
- ``models`` 子包的导入会触发工具表注册到 ``Base.metadata``；
- ``register(app)`` 把该工具的全部 HTTP 路由挂载到 FastAPI app。

新增第二个财务工具时，照此结构在 ``app/tools/<name>/`` 下另建一个包，
并在 ``app.main`` 中调用其 ``register``，无需改动本工具。
"""

from app.tools.bank_journal import models as _models  # noqa: F401  触发模型注册

TOOL_ID = "bank-journal"


def register(app) -> None:
    """把银行流水转日记账工具的全部路由挂载到 FastAPI app。"""
    from app.tools.bank_journal.routes import routers

    for router in routers:
        app.include_router(router)


__all__ = ["TOOL_ID", "register"]
