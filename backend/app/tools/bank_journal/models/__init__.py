"""银行流水转日记账工具的数据模型。

导入即把这些模型注册到 ``Base.metadata``，使 Alembic（migrations/env.py）
和测试库（tests/conftest.py）能发现全部工具表。
"""

from app.tools.bank_journal.models.builtin_field_override import BuiltinFieldOverride
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
from app.tools.bank_journal.models.custom_field import (
    ALL_SLOTS,
    AMOUNT_SLOTS,
    DATE_SLOTS,
    SLOTS_BY_TYPE,
    TEXT_SLOTS,
    CustomField,
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
    "ALL_SLOTS",
    "AMOUNT_SLOTS",
    "BankTemplate",
    "BankTemplateVersion",
    "BankTransaction",
    "BuiltinFieldOverride",
    "CompanyJournalTemplate",
    "CompanyJournalTemplateVersion",
    "Confirmation",
    "ConversionRun",
    "ConversionRunFile",
    "ConversionRunRuleVersion",
    "CustomField",
    "DATE_SLOTS",
    "Export",
    "JournalPreviewRow",
    "ManualAdjustment",
    "MappingProfile",
    "MappingProfileVersion",
    "Rule",
    "RuleVersion",
    "SLOTS_BY_TYPE",
    "TEXT_SLOTS",
]
