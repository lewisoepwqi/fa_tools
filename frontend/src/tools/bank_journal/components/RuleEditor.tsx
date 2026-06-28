import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { Alert, Button, Input, InputNumber, Select, Space, Typography } from 'antd';
import { useMemo } from 'react';
import {
  FIELD_LABEL,
  RULE_ACTION_FIELD_LABEL,
  RULE_ACTION_FIELD_OPTIONS,
  RULE_OPERATORS,
  RULE_OPERATOR_LABEL,
  STANDARD_FIELDS,
  STANDARD_FIELD_OPTIONS,
  type StandardFieldType
} from '../constants';

/** 条件字段下拉选项（仅流水原始字段——条件只针对流水本身）。 */
const FIELD_OPTIONS = STANDARD_FIELD_OPTIONS;

/**
 * 动作字段下拉选项（P1）。
 *
 * 规则的动作不是改流水原始字段，而是产出供映射方案引用的输出键（科目、记账摘要等），
 * 因此选项 = 业务动作字段 ∪ 流水原始字段。条件字段则仍只用流水原始字段。
 * 可选注入 journalColumns（日记账输出列），把目标列也作为可设置项。
 */
function buildActionFieldOptions(
  journalColumns?: string[],
  standardFieldOptions?: { value: string; label: string }[]
) {
  const base = RULE_ACTION_FIELD_OPTIONS;
  const cols = (journalColumns ?? []).map((c) => ({ value: c, label: c }));
  // 动作字段去重（业务字段优先）
  const seen = new Set(base.map((b) => b.value));
  const merged = [...base, ...cols.filter((c) => !seen.has(c.value))];
  // 追加流水原始字段（含公司扩展字段），用 optGroup 分组便于辨识
  return [
    { label: '业务字段', options: merged },
    { label: '流水字段', options: standardFieldOptions ?? STANDARD_FIELD_OPTIONS }
  ];
}

/** 动作字段 label：优先业务字段字典，其次流水字段字典，最后原值。 */
function actionFieldLabel(key: string): string {
  return RULE_ACTION_FIELD_LABEL[key] ?? FIELD_LABEL[key] ?? key;
}

/** 单个条件（对齐后端 conditions_json.all[]）。 */
export interface RuleCondition {
  field: string;
  op: string;
  value: string;
}

/** 单个动作设置项（对齐后端 actions_json.set 内的 key/value）。 */
export interface RuleAction {
  field: string;
  value: string;
}

/** 可视化编辑产出的规则数据（提交前由调用方序列化为后端 JSON 结构）。 */
export interface RuleEditorData {
  logic: 'all'; // 当前仅支持 AND
  conditions: RuleCondition[];
  actions: RuleAction[];
}

interface RuleEditorProps {
  value: RuleEditorData;
  onChange: (data: RuleEditorData) => void;
  /** 日记账输出列（可选，来自已绑定日记账模板）；注入后动作字段可设置这些列。 */
  journalColumns?: string[];
  /** 流水标准字段下拉（含公司扩展字段）。默认用构建期内置字段；页面注入运行时全集。 */
  standardFieldOptions?: { value: string; label: string }[];
  /** 字段→类型映射（含扩展字段），用于条件操作符智能过滤。默认用内置 STANDARD_FIELDS。 */
  fieldTypeMap?: Record<string, string>;
}

/**
 * 规则可视化编辑器：条件构造器 + 动作编辑器 + 自然语言回显。
 * 财务无需手写 JSON，全部通过下拉框/输入框完成配置。
 */
export function RuleEditor({
  value,
  onChange,
  journalColumns,
  standardFieldOptions,
  fieldTypeMap
}: RuleEditorProps) {
  const fieldOptions = standardFieldOptions ?? FIELD_OPTIONS;
  // 合并内置 + 注入的类型映射（注入优先，含扩展字段）
  const typeMap = useMemo(() => {
    const base: Record<string, string> = {};
    for (const f of STANDARD_FIELDS) base[f.key] = f.type;
    return { ...base, ...(fieldTypeMap ?? {}) };
  }, [fieldTypeMap]);
  const actionFieldOptions = useMemo(
    () => buildActionFieldOptions(journalColumns, standardFieldOptions),
    [journalColumns, standardFieldOptions]
  );
  const updateCondition = (index: number, patch: Partial<RuleCondition>) => {
    const conditions = value.conditions.map((c, i) => (i === index ? { ...c, ...patch } : c));
    onChange({ ...value, conditions });
  };

  const addCondition = () => {
    onChange({
      ...value,
      conditions: [...value.conditions, { field: 'summary', op: 'contains', value: '' }]
    });
  };

  const removeCondition = (index: number) => {
    onChange({ ...value, conditions: value.conditions.filter((_, i) => i !== index) });
  };

  const updateAction = (index: number, patch: Partial<RuleAction>) => {
    const actions = value.actions.map((a, i) => (i === index ? { ...a, ...patch } : a));
    onChange({ ...value, actions });
  };

  const addAction = () => {
    onChange({ ...value, actions: [...value.actions, { field: 'account_subject', value: '' }] });
  };

  const removeAction = (index: number) => {
    onChange({ ...value, actions: value.actions.filter((_, i) => i !== index) });
  };

  const summary = useMemo(() => describeRule(value), [value]);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      {/* 自然语言回显 */}
      <Alert type="info" showIcon message="规则含义" description={summary} />

      {/* 条件区 */}
      <div>
        <Typography.Title level={5} style={{ marginTop: 0 }}>
          满足以下【全部】条件
        </Typography.Title>
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          {value.conditions.map((cond, i) => (
            <ConditionRow
              key={i}
              condition={cond}
              fieldOptions={fieldOptions}
              typeMap={typeMap}
              onChange={(patch) => updateCondition(i, patch)}
              onRemove={() => removeCondition(i)}
            />
          ))}
          <Button type="dashed" icon={<PlusOutlined />} onClick={addCondition} block>
            添加条件
          </Button>
        </Space>
      </div>

      {/* 动作区 */}
      <div>
        <Typography.Title level={5} style={{ marginTop: 0 }}>
          则 设置以下字段
        </Typography.Title>
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          {value.actions.map((action, i) => (
            <ActionRow
              key={i}
              action={action}
              fieldOptions={actionFieldOptions}
              onChange={(patch) => updateAction(i, patch)}
              onRemove={() => removeAction(i)}
            />
          ))}
          <Button type="dashed" icon={<PlusOutlined />} onClick={addAction} block>
            添加设置
          </Button>
        </Space>
      </div>
    </Space>
  );
}

/** 条件行：字段 + 操作符 + 值。操作符按字段类型智能过滤。 */
function ConditionRow({
  condition,
  fieldOptions,
  typeMap,
  onChange,
  onRemove
}: {
  condition: RuleCondition;
  fieldOptions: { value: string; label: string }[];
  typeMap: Record<string, string>;
  onChange: (patch: Partial<RuleCondition>) => void;
  onRemove: () => void;
}) {
  const fieldType = (typeMap[condition.field] ?? 'text') as StandardFieldType;
  const allowedOps = RULE_OPERATORS.filter((o) => o.fieldTypes.includes(fieldType));
  const opOption = RULE_OPERATORS.find((o) => o.value === condition.op);
  const isAmount = fieldType === 'amount';

  return (
    <Space.Compact style={{ width: '100%' }}>
      <Select
        style={{ width: '30%' }}
        value={condition.field}
        options={fieldOptions}
        onChange={(field) => {
          // 切换字段时，若当前操作符对新字段类型不适用，回落到首个可用操作符
          const newType = (typeMap[field] ?? 'text') as StandardFieldType;
          const stillValid = RULE_OPERATORS.some(
            (o) => o.value === condition.op && o.fieldTypes.includes(newType)
          );
          const fallbackOp = RULE_OPERATORS.find((o) => o.fieldTypes.includes(newType));
          onChange({ field, op: stillValid ? condition.op : fallbackOp?.value ?? 'eq', value: '' });
        }}
      />
      <Select
        style={{ width: '22%' }}
        value={condition.op}
        options={allowedOps.map((o) => ({ value: o.value, label: o.label }))}
        onChange={(op) => onChange({ op, value: '' })}
      />
      {isAmount ? (
        <InputNumber
          style={{ width: '38%' }}
          value={condition.value === '' ? null : Number(condition.value)}
          placeholder={opOption?.placeholder}
          onChange={(v) => onChange({ value: v === null ? '' : String(v) })}
        />
      ) : (
        <Input
          style={{ width: '38%' }}
          value={condition.value}
          placeholder={opOption?.placeholder}
          onChange={(e) => onChange({ value: e.target.value })}
        />
      )}
      <Button icon={<DeleteOutlined />} onClick={onRemove} danger style={{ width: '10%' }} />
    </Space.Compact>
  );
}

/** 动作行：设置字段 = 值。 */
function ActionRow({
  action,
  fieldOptions,
  onChange,
  onRemove
}: {
  action: RuleAction;
  fieldOptions: Array<{ label: string; options: { value: string; label: string }[] }>;
  onChange: (patch: Partial<RuleAction>) => void;
  onRemove: () => void;
}) {
  return (
    <Space.Compact style={{ width: '100%' }}>
      <Select
        style={{ width: '30%' }}
        value={action.field}
        options={fieldOptions}
        onChange={(field) => onChange({ field })}
        placeholder="选择要设置的字段"
      />
      <Input
        className="sep-fill"
        style={{ width: '12%' }}
        value=" = "
        disabled
      />
      <Input
        style={{ width: '48%' }}
        value={action.value}
        placeholder="输入要设置的值"
        onChange={(e) => onChange({ value: e.target.value })}
      />
      <Button icon={<DeleteOutlined />} onClick={onRemove} danger style={{ width: '10%' }} />
    </Space.Compact>
  );
}

/** 序列化/反序列化：与后端 JSON 结构互转。 */
export function ruleDataFromBackend(
  conditionsJson: { all?: Array<{ field: string; op: string; value: unknown }> } | null | undefined,
  actionsJson: { set?: Record<string, unknown> } | null | undefined
): RuleEditorData {
  const conditions: RuleCondition[] = (conditionsJson?.all ?? []).map((c) => ({
    field: c.field,
    op: c.op,
    value: Array.isArray(c.value) ? c.value.join(',') : String(c.value ?? '')
  }));
  const setObj = actionsJson?.set ?? {};
  const actions: RuleAction[] = Object.entries(setObj).map(([field, value]) => ({
    field,
    value: String(value ?? '')
  }));
  return { logic: 'all', conditions, actions };
}

export function ruleDataToBackend(data: RuleEditorData): {
  conditions_json: Record<string, unknown>;
  actions_json: Record<string, unknown>;
} {
  return {
    conditions_json: {
      all: data.conditions.map((c) => ({
        field: c.field,
        op: c.op,
        value: c.op === 'contains_any' ? c.value.split(',').map((s) => s.trim()).filter(Boolean) : c.value
      }))
    },
    actions_json: {
      set: Object.fromEntries(data.actions.filter((a) => a.field).map((a) => [a.field, a.value]))
    }
  };
}

/** 生成自然语言规则描述。 */
export function describeRule(data: RuleEditorData): string {
  if (data.conditions.length === 0 && data.actions.length === 0) {
    return '请添加条件和要设置的字段。';
  }
  const condText =
    data.conditions.length > 0
      ? '当 ' +
        data.conditions
          .map((c) => {
            const f = FIELD_LABEL[c.field] ?? c.field;
            const op = RULE_OPERATOR_LABEL[c.op] ?? c.op;
            return `${f}${op}"${c.value}"`;
          })
          .join(' 且 ')
      : '无条件（对所有流水生效）';
  const actionText =
    data.actions.length > 0
      ? '设置 ' +
        data.actions
          .map((a) => `${actionFieldLabel(a.field)}为"${a.value}"`)
          .join('、')
      : '不设置任何字段';
  return `${condText} 时，${actionText}。`;
}
