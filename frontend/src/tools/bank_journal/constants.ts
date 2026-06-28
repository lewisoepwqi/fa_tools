/**
 * 银行流水转日记账工具的字段字典常量。
 *
 * 把后端的技术标识符（英文枚举、字段 key）统一映射为面向财务人员的中文标签，
 * 供银行模板、映射方案、规则等多个配置页面复用。单点维护，避免散落各处。
 */

/** 银行流水的标准字段（后端 StandardBankTransaction / HEADER_FIELD_MAP）。 */
export type StandardFieldType = 'text' | 'amount' | 'date' | 'enum';

export interface StandardField {
  /** 后端字段 key（提交时用）。 */
  key: string;
  /** 面向财务人员的中文标签。 */
  label: string;
  /** 字段值类型，用于规则操作符智能过滤。 */
  type: StandardFieldType;
}

export const STANDARD_FIELDS: StandardField[] = [
  { key: 'transaction_date', label: '交易日期', type: 'date' },
  { key: 'posting_date', label: '入账日期', type: 'date' },
  { key: 'amount', label: '金额', type: 'amount' },
  { key: 'income_amount', label: '收入金额', type: 'amount' },
  { key: 'expense_amount', label: '支出金额', type: 'amount' },
  { key: 'debit_amount', label: '借方金额', type: 'amount' },
  { key: 'credit_amount', label: '贷方金额', type: 'amount' },
  { key: 'net_amount', label: '净额', type: 'amount' },
  { key: 'direction', label: '收支方向', type: 'enum' },
  { key: 'balance', label: '余额', type: 'amount' },
  { key: 'counterparty_name', label: '对方户名', type: 'text' },
  { key: 'counterparty_account_no', label: '对方账号', type: 'text' },
  { key: 'counterparty_bank_name', label: '对方开户行', type: 'text' },
  { key: 'summary', label: '摘要', type: 'text' },
  { key: 'purpose', label: '用途', type: 'text' },
  { key: 'transaction_type', label: '交易类型', type: 'text' },
  { key: 'bank_transaction_id', label: '流水号', type: 'text' },
  { key: 'receipt_no', label: '回单号', type: 'text' }
];

/** 按 key 快速取标签。 */
export const FIELD_LABEL: Record<string, string> = Object.fromEntries(
  STANDARD_FIELDS.map((f) => [f.key, f.label])
);

/** 标准字段下拉选项（含"不映射"占位由调用方按需拼接）。 */
export const STANDARD_FIELD_OPTIONS = STANDARD_FIELDS.map((f) => ({
  value: f.key,
  label: f.label
}));

/**
 * 规则可设置的「业务输出字段」（P1）。
 *
 * 规则的动作（actions）不是改流水原始字段，而是产出供映射方案引用的输出键，
 * 如科目、记账摘要。这些字段不在 STANDARD_FIELDS（流水原始字段）里，因此单列。
 * 命名与后端 rule_service 的 actions_json.set 键、mapping_service 的 rule_output
 * 类型 source 一致（如 account_subject / journal_summary）。
 */
export interface RuleActionField {
  key: string;
  label: string;
}

export const RULE_ACTION_FIELDS: RuleActionField[] = [
  { key: 'account_subject', label: '记账科目' },
  { key: 'journal_summary', label: '记账摘要' },
  { key: 'counterparty_subject', label: '对方科目' },
  { key: 'remark', label: '备注' }
];

/** 业务动作字段 key → 中文标签。 */
export const RULE_ACTION_FIELD_LABEL: Record<string, string> = Object.fromEntries(
  RULE_ACTION_FIELDS.map((f) => [f.key, f.label])
);

/** 规则动作字段下拉选项。 */
export const RULE_ACTION_FIELD_OPTIONS = RULE_ACTION_FIELDS.map((f) => ({
  value: f.key,
  label: f.label
}));

/** 金额模式（后端 AmountMode 枚举）。 */
export interface AmountModeOption {
  value: string;
  label: string;
  /** 该模式下金额列的配置键 → 中文说明。 */
  configKeys: { key: string; label: string }[];
}

export const AMOUNT_MODES: AmountModeOption[] = [
  {
    value: 'income_expense_columns',
    label: '收入/支出双列',
    configKeys: [
      { key: 'income', label: '收入列' },
      { key: 'expense', label: '支出列' }
    ]
  },
  {
    value: 'debit_credit_columns',
    label: '借方/贷方双列',
    configKeys: [
      { key: 'debit', label: '借方列' },
      { key: 'credit', label: '贷方列' }
    ]
  },
  {
    value: 'single_amount_with_direction',
    label: '单金额 + 方向列',
    configKeys: [
      { key: 'amount', label: '金额列' },
      { key: 'direction', label: '方向列' }
    ]
  },
  {
    value: 'signed_amount',
    label: '带符号金额（单列）',
    configKeys: [{ key: 'amount', label: '金额列' }]
  }
];

/** 金额模式 value → 中文标签。 */
export const AMOUNT_MODE_LABEL: Record<string, string> = Object.fromEntries(
  AMOUNT_MODES.map((m) => [m.value, m.label])
);

/** 文件类型。 */
export const FILE_TYPE_OPTIONS = [
  { value: 'csv', label: 'CSV' },
  { value: 'xlsx', label: 'Excel (.xlsx)' },
  { value: 'xls', label: 'Excel (.xls)' }
];

export const FILE_TYPE_LABEL: Record<string, string> = {
  csv: 'CSV',
  xlsx: 'Excel (.xlsx)',
  xls: 'Excel (.xls)'
};

/** 把 0-based 行索引转成面向用户的"第 N 行"。 */
export function rowIndexOf(index: number | null | undefined): string {
  if (index === null || index === undefined) return '-';
  return `第 ${index + 1} 行`;
}

/**
 * 规则条件操作符（对齐后端 rule_service._match_condition 支持的全部 op）。
 */
export interface RuleOperatorOption {
  value: string;
  label: string;
  /** 该操作符适用的字段类型（用于按选中字段智能过滤可选操作符）。 */
  fieldTypes: Array<'text' | 'amount' | 'date' | 'enum'>;
  /** 值输入框占位提示。 */
  placeholder: string;
}

export const RULE_OPERATORS: RuleOperatorOption[] = [
  { value: 'eq', label: '等于', fieldTypes: ['text', 'amount', 'enum'], placeholder: '输入完全相同的值' },
  { value: 'contains', label: '包含', fieldTypes: ['text'], placeholder: '输入包含的文字' },
  { value: 'contains_any', label: '包含任一', fieldTypes: ['text'], placeholder: '多个词用逗号分隔，如：货款,退款' },
  { value: 'not_contains', label: '不包含', fieldTypes: ['text'], placeholder: '输入不包含的文字' },
  { value: 'gte', label: '大于等于', fieldTypes: ['amount'], placeholder: '输入金额下限' },
  { value: 'lte', label: '小于等于', fieldTypes: ['amount'], placeholder: '输入金额上限' },
  { value: 'date_gte', label: '日期不早于', fieldTypes: ['date'], placeholder: 'YYYY-MM-DD' },
  { value: 'date_lte', label: '日期不晚于', fieldTypes: ['date'], placeholder: 'YYYY-MM-DD' }
];

/** 操作符 value → 中文标签。 */
export const RULE_OPERATOR_LABEL: Record<string, string> = Object.fromEntries(
  RULE_OPERATORS.map((o) => [o.value, o.label])
);

