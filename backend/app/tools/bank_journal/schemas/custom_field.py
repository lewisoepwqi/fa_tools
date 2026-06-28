"""公司级自定义扩展字段 + 内置字段覆盖的 Pydantic schema。"""

from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import RecordStatus


class CustomFieldCreate(BaseModel):
    company_id: str
    # 标准字段空间名（规则/映射引用此 key）；蛇形，不可与内置标准字段冲突
    field_key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    name: str
    # text / amount / date
    data_type: str = Field(pattern=r"^(text|amount|date)$")
    # 中文表头识别关键词（至少 1 个，否则 detect 无法识别该列）
    header_keywords: list[str] = Field(min_length=1)
    created_by: str | None = None


class CustomFieldUpdate(BaseModel):
    name: str | None = None
    header_keywords: list[str] | None = None
    status: RecordStatus | None = None


class CustomFieldResponse(BaseModel):
    id: str
    company_id: str
    field_key: str
    name: str
    slot_key: str
    data_type: str
    header_keywords: list[str]
    status: str


# 内置标准字段（与前端 constants.ts 的 STANDARD_FIELDS 对齐）。
# keywords 为 detect 识别用的中文表头默认关键词（与 parser_service.HEADER_FIELD_MAP 同源）。
BUILTIN_STANDARD_FIELDS: list[dict[str, Any]] = [
    {"key": "transaction_date", "label": "交易日期", "type": "date",
     "keywords": ["交易日期", "记账日期", "日期"]},
    {"key": "posting_date", "label": "入账日期", "type": "date", "keywords": ["入账日期"]},
    {"key": "amount", "label": "金额", "type": "amount",
     "keywords": ["金额", "发生额", "交易金额"]},
    {"key": "income_amount", "label": "收入金额", "type": "amount", "keywords": ["收入"]},
    {"key": "expense_amount", "label": "支出金额", "type": "amount", "keywords": ["支出"]},
    {"key": "debit_amount", "label": "借方金额", "type": "amount",
     "keywords": ["借方发生额", "借方金额", "借方"]},
    {"key": "credit_amount", "label": "贷方金额", "type": "amount",
     "keywords": ["贷方发生额", "贷方金额", "贷方"]},
    {"key": "net_amount", "label": "净额", "type": "amount", "keywords": ["净额"]},
    {"key": "direction", "label": "收支方向", "type": "enum", "keywords": ["方向", "收支方向"]},
    {"key": "balance", "label": "余额", "type": "amount", "keywords": ["余额", "账户余额"]},
    {"key": "counterparty_name", "label": "对方户名", "type": "text",
     "keywords": ["对方户名", "对方名称", "对方账户名称"]},
    {"key": "counterparty_account_no", "label": "对方账号", "type": "text",
     "keywords": ["对方账号", "对方账户", "对方账户账号"]},
    {"key": "counterparty_bank_name", "label": "对方开户行", "type": "text",
     "keywords": ["对方开户行", "对方银行"]},
    {"key": "summary", "label": "摘要", "type": "text", "keywords": ["摘要", "摘要信息"]},
    {"key": "purpose", "label": "用途", "type": "text", "keywords": ["用途", "附言"]},
    {"key": "transaction_type", "label": "交易类型", "type": "text",
     "keywords": ["交易类型", "业务类型"]},
    {"key": "bank_transaction_id", "label": "流水号", "type": "text",
     "keywords": ["流水号", "交易流水号", "交易号"]},
    {"key": "receipt_no", "label": "回单号", "type": "text", "keywords": ["回单号"]},
]

BUILTIN_FIELD_KEYS = {f["key"] for f in BUILTIN_STANDARD_FIELDS}

# key → 默认关键词集合（供 parser overlay union）
BUILTIN_KEYWORDS: dict[str, list[str]] = {
    f["key"]: list(f["keywords"]) for f in BUILTIN_STANDARD_FIELDS
}
BUILTIN_LABELS: dict[str, str] = {f["key"]: f["label"] for f in BUILTIN_STANDARD_FIELDS}
BUILTIN_TYPES: dict[str, str] = {f["key"]: f["type"] for f in BUILTIN_STANDARD_FIELDS}

ALLOWED_TYPES = {"text", "amount", "date", "enum"}


class StandardFieldDef(BaseModel):
    """合并视图：内置字段（含覆盖）+ 公司扩展字段，供前端下拉。"""

    key: str
    label: str
    type: str
    builtin: bool = False  # True=内置字段，False=公司扩展字段
    # 当前生效的识别关键词（内置默认 ∪ 公司覆盖）
    keywords: list[str] = []
    # 内置字段是否有公司覆盖（前端用于显示"恢复默认"）
    overridden: bool = False


class StandardSchemaResponse(BaseModel):
    """标准字段全集（内置含覆盖 + 公司扩展），供前端字段下拉运行时拉取。"""

    fields: list[StandardFieldDef]
    slot_quota: dict[str, dict[str, int]]  # data_type → {used, total}


# ---------------------------------------------------------------------------
# 内置字段覆盖的 schema
# ---------------------------------------------------------------------------


class BuiltinFieldOverrideUpsert(BaseModel):
    company_id: str
    field_key: str  # 必须在 BUILTIN_FIELD_KEYS 内
    label_override: str | None = None
    header_keywords_override: list[str] | None = None
    type_override: str | None = None  # text/amount/date/enum


class BuiltinFieldOverrideResponse(BaseModel):
    id: str
    company_id: str
    field_key: str
    label_override: str | None
    header_keywords_override: list[str] | None
    type_override: str | None
