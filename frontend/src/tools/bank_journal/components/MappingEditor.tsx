import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { Button, Input, Select, Space, Typography } from 'antd';
import { FIELD_LABEL, STANDARD_FIELD_OPTIONS } from '../constants';

/** 映射类型（对齐后端 mapping_service.apply_mappings 支持的全部 type）。 */
export type MappingType = 'field' | 'fixed' | 'rule_output' | 'concat' | 'manual';

export const MAPPING_TYPE_OPTIONS: { value: MappingType; label: string; hint: string }[] = [
  { value: 'field', label: '取字段值', hint: '日记账列 ← 某个银行流水标准字段' },
  { value: 'rule_output', label: '取规则输出', hint: '日记账列 ← 规则计算出的值（如科目）' },
  { value: 'fixed', label: '固定值', hint: '该列填一个写死的常量' },
  { value: 'concat', label: '拼接多个字段', hint: '把多个流水字段拼成一个字符串' },
  { value: 'manual', label: '留空手填', hint: '转换后由人工在预览里填写' }
];

/**
 * 一行列映射（富模型，P1）。
 *
 * 后端 apply_mappings 支持 5 种 type，但历史存储 mappings_json 只表达 field 类型
 * （扁平 {目标列:标准字段}）。本编辑器使用富模型呈现全部类型；序列化时
 * field 类型仍写成扁平键（兼容旧存储），其余类型写入 _advanced 数组。
 */
export interface MappingEntry {
  target: string;
  type: MappingType;
  /** field / rule_output 的来源 key。 */
  source?: string;
  /** fixed 的常量值。 */
  value?: string;
  /** concat 的多个来源字段。 */
  sources?: string[];
  /** concat 的分隔符。 */
  separator?: string;
}

interface MappingEditorProps {
  value: MappingEntry[];
  onChange: (value: MappingEntry[]) => void;
  /** 日记账可选目标列（来自已绑定的日记账模板）。缺失则允许自由输入。 */
  targetOptions?: string[];
  /** 规则可输出的业务字段（用于 rule_output 类型的来源选项）。 */
  ruleOutputOptions?: { value: string; label: string }[];
  /** 流水标准字段下拉（含公司扩展字段）。默认用构建期内置字段；页面注入运行时全集。 */
  standardFieldOptions?: { value: string; label: string }[];
}

/**
 * 列映射可视化编辑器：左列选日记账目标列，右列按映射类型配置来源。
 * 替代手写 JSON `{"日期":"transaction_date"}`，并支持固定值/拼接/规则输出等高级类型。
 */
export function MappingEditor({
  value,
  onChange,
  targetOptions,
  ruleOutputOptions = [],
  standardFieldOptions
}: MappingEditorProps) {
  const fieldOptions = standardFieldOptions ?? STANDARD_FIELD_OPTIONS;
  const update = (index: number, patch: Partial<MappingEntry>) => {
    onChange(value.map((e, i) => (i === index ? { ...e, ...patch } : e)));
  };
  const add = () => onChange([...value, { target: '', type: 'field', source: '' }]);
  const remove = (index: number) => onChange(value.filter((_, i) => i !== index));

  // 切换类型时清空无关字段，避免脏数据
  const changeType = (index: number, type: MappingType) => {
    const patch: Partial<MappingEntry> = { type };
    if (type === 'field') patch.source = '';
    if (type === 'rule_output') patch.source = '';
    if (type === 'fixed') patch.value = '';
    if (type === 'concat') {
      patch.sources = [];
      patch.separator = '';
    }
    update(index, patch);
  };

  return (
    <Space direction="vertical" size={8} style={{ width: '100%' }}>
      <Typography.Text type="secondary">
        把日记账的列，对应到银行流水的标准字段、规则输出或固定值：
      </Typography.Text>
      {value.map((entry, i) => (
        <MappingRow
          key={i}
          entry={entry}
          targetOptions={targetOptions}
          ruleOutputOptions={ruleOutputOptions}
          fieldOptions={fieldOptions}
          onTarget={(t) => update(i, { target: t ?? '' })}
          onType={(t) => changeType(i, t)}
          onPatch={(p) => update(i, p)}
          onRemove={() => remove(i)}
        />
      ))}
      <Button type="dashed" icon={<PlusOutlined />} onClick={add} block>
        添加一行映射
      </Button>
    </Space>
  );
}

function MappingRow({
  entry,
  targetOptions,
  ruleOutputOptions,
  fieldOptions,
  onTarget,
  onType,
  onPatch,
  onRemove
}: {
  entry: MappingEntry;
  targetOptions?: string[];
  ruleOutputOptions: { value: string; label: string }[];
  fieldOptions: { value: string; label: string }[];
  onTarget: (t: string) => void;
  onType: (t: MappingType) => void;
  onPatch: (p: Partial<MappingEntry>) => void;
  onRemove: () => void;
}) {
  return (
    <Space direction="vertical" size={4} style={{ width: '100%' }}>
      <Space.Compact style={{ width: '100%' }}>
        {/* 目标列：有 targetOptions 走下拉，否则自由输入 */}
        {targetOptions ? (
          <Select
            style={{ width: '40%' }}
            value={entry.target || undefined}
            placeholder="选择日记账列"
            showSearch
            allowClear
            options={targetOptions.map((t) => ({ value: t, label: t }))}
            onChange={(v) => onTarget(v ?? '')}
          />
        ) : (
          <Input
            style={{ width: '40%' }}
            value={entry.target}
            placeholder="日记账列名（如：日期）"
            onChange={(e) => onTarget(e.target.value)}
          />
        )}
        <Select
          style={{ width: '28%' }}
          value={entry.type}
          options={MAPPING_TYPE_OPTIONS}
          onChange={(t) => onType(t)}
        />
        <Button
          icon={<DeleteOutlined />}
          onClick={onRemove}
          danger
          style={{ width: '12%' }}
        />
      </Space.Compact>
      <MappingSourceControl
        entry={entry}
        ruleOutputOptions={ruleOutputOptions}
        fieldOptions={fieldOptions}
        onPatch={onPatch}
      />
    </Space>
  );
}

/** 按映射类型渲染不同的来源配置控件。 */
function MappingSourceControl({
  entry,
  ruleOutputOptions,
  fieldOptions,
  onPatch
}: {
  entry: MappingEntry;
  ruleOutputOptions: { value: string; label: string }[];
  fieldOptions: { value: string; label: string }[];
  onPatch: (p: Partial<MappingEntry>) => void;
}) {
  if (entry.type === 'field') {
    return (
      <Select
        style={{ width: '100%' }}
        value={entry.source || undefined}
        placeholder="银行标准字段"
        allowClear
        options={fieldOptions}
        onChange={(v) => onPatch({ source: v ?? '' })}
      />
    );
  }
  if (entry.type === 'rule_output') {
    return (
      <Select
        style={{ width: '100%' }}
        value={entry.source || undefined}
        placeholder="选择规则输出的业务字段"
        allowClear
        options={ruleOutputOptions}
        onChange={(v) => onPatch({ source: v ?? '' })}
        notFoundContent="未配置可用的规则输出字段"
      />
    );
  }
  if (entry.type === 'fixed') {
    return (
      <Input
        style={{ width: '100%' }}
        value={entry.value ?? ''}
        placeholder="固定值，如：银行存款"
        onChange={(e) => onPatch({ value: e.target.value })}
      />
    );
  }
  if (entry.type === 'concat') {
    return (
      <Space direction="vertical" size={4} style={{ width: '100%' }}>
        <Select
          mode="multiple"
          style={{ width: '100%' }}
          value={entry.sources ?? []}
          placeholder="选择要拼接的多个流水字段"
          options={fieldOptions}
          onChange={(v) => onPatch({ sources: v })}
        />
        <Input
          style={{ width: '100%' }}
          value={entry.separator ?? ''}
          placeholder="分隔符（可留空）"
          onChange={(e) => onPatch({ separator: e.target.value })}
        />
      </Space>
    );
  }
  // manual：无需配置来源，转换后由人工填写
  return (
    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
      该列将留空，转换后在预览页人工填写。
    </Typography.Text>
  );
}

/**
 * mappings_json ↔ 编辑器结构互转（P1 富模型，兼容旧扁平格式）。
 *
 * 存储格式约定：
 * - 旧扁平部分：{ 目标列: 标准字段 }（默认 field 类型，向后兼容）。
 * - 新富模型部分：mappings_json["_advanced"] = [ {target,type,...}, ... ]（非 field 类型）。
 * 序列化时 field 类型写扁平键、其余写 _advanced；反序列化时两者合并。
 */
interface StoredMapping {
  target: string;
  type: MappingType;
  source?: string;
  value?: string;
  sources?: string[];
  separator?: string;
}

export function mappingFromBackend(
  mappingsJson: Record<string, unknown> | null | undefined
): MappingEntry[] {
  if (!mappingsJson) return [];
  const entries: MappingEntry[] = [];
  // 扁平部分（field 类型）
  for (const [target, source] of Object.entries(mappingsJson)) {
    if (target === '_advanced') continue;
    entries.push({ target, type: 'field', source: String(source ?? '') });
  }
  // 富模型部分
  const advanced = (mappingsJson._advanced as StoredMapping[] | undefined) ?? [];
  for (const a of advanced) {
    entries.push({
      target: a.target,
      type: a.type,
      source: a.source,
      value: a.value,
      sources: a.sources,
      separator: a.separator
    });
  }
  return entries;
}

export function mappingToBackend(entries: MappingEntry[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  const advanced: StoredMapping[] = [];
  for (const e of entries) {
    if (!e.target) continue;
    if (e.type === 'field') {
      if (e.source) out[e.target] = e.source;
    } else {
      advanced.push({
        target: e.target,
        type: e.type,
        source: e.source,
        value: e.value,
        sources: e.sources,
        separator: e.separator
      });
    }
  }
  if (advanced.length > 0) out._advanced = advanced;
  return out;
}

/** 映射方案的中文描述（用于详情页/版本历史）。 */
export function describeMappings(entries: MappingEntry[]): string {
  const valid = entries.filter((e) => e.target);
  if (valid.length === 0) return '暂无映射';
  return valid
    .map((e) => {
      const tgt = e.target;
      switch (e.type) {
        case 'fixed':
          return `${tgt} = 固定值"${e.value ?? ''}"`;
        case 'concat':
          return `${tgt} = 拼接[${(e.sources ?? []).map((s) => FIELD_LABEL[s] ?? s).join(' + ')}]`;
        case 'rule_output':
          return `${tgt} ← 规则输出(${e.source ?? '-'})`;
        case 'manual':
          return `${tgt} = 人工填写`;
        default:
          return `${tgt} ← ${FIELD_LABEL[e.source ?? ''] ?? e.source ?? '-'}`;
      }
    })
    .join('，');
}
