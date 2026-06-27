"""银行流水转日记账工具的 HTTP 路由聚合。

每个子模块定义一个 ``router``，本包把它们收集成 ``routers`` 列表，
供工具注册函数（``app.tools.bank_journal.register``）统一挂载到 app。
"""

from app.tools.bank_journal.routes import (
    bank_templates,
    conversion_runs,
    exports,
    journal_templates,
    mapping_profiles,
    preview_rows,
    rules,
)

routers = [
    bank_templates.router,
    journal_templates.router,
    mapping_profiles.router,
    rules.router,
    conversion_runs.router,
    preview_rows.router,
    exports.router,
]

__all__ = ["routers"]
