"""银行流水转日记账工具的数据模型。

导入即把这些模型注册到 ``Base.metadata``，使 Alembic（migrations/env.py）
和测试库（tests/conftest.py）能发现全部工具表。
"""

from app.tools.bank_journal.models.conversion import (
    BankTransaction,
    Confirmation,
    ConversionRun,
    ConversionRunFile,
    ConversionRunRuleVersion,
    Export,
    JournalPreviewRow,
    ManualAdjustment,
)
from app.tools.bank_journal.models.mapping import (
    MappingProfile,
    MappingProfileVersion,
)
from app.tools.bank_journal.models.rule import Rule, RuleVersion
from app.tools.bank_journal.models.template import (
    BankTemplate,
    BankTemplateVersion,
    CompanyJournalTemplate,
    CompanyJournalTemplateVersion,
)

__all__ = [
    "BankTemplate",
    "BankTemplateVersion",
    "BankTransaction",
    "CompanyJournalTemplate",
    "CompanyJournalTemplateVersion",
    "Confirmation",
    "ConversionRun",
    "ConversionRunFile",
    "ConversionRunRuleVersion",
    "Export",
    "JournalPreviewRow",
    "ManualAdjustment",
    "MappingProfile",
    "MappingProfileVersion",
    "Rule",
    "RuleVersion",
]
