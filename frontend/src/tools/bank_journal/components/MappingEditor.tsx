import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { Button, Input, Select, Space, Typography } from 'antd';
import { FIELD_LABEL, STANDARD_FIELD_OPTIONS } from '../constants';

/**
 * 一行列映射：日记账目标列 ← 银行标准字段。
 * 与 mappings_json 结构一致：{ 目标列名: 标准字段key }。
 */
export interface MappingEntry {
  /** 日记账输出列名（如"日期""摘要"）。 */
  target: string;
  /** 银行标准字段 key（如 transaction_date），空串表示不映射。 */
  source: string;
}

interface MappingEditorProps {
  value: MappingEntry[];
  onChange: (value: MappingEntry[]) => void;
  /** 日记账可选目标列（来自已绑定的日记账模板）。缺失则允许自由输入。 */
  targetOptions?: string[];
}

/**
 * 列映射可视化编辑器：左列选日记账目标列，右列选银行标准字段。
 * 替代手写 JSON `{"日期":"transaction_date"}`。
 */
export function MappingEditor({ value, onChange, targetOptions }: MappingEditorProps) {
  const update = (index: number, patch: Partial<MappingEntry>) => {
    onChange(value.map((e, i) => (i === index ? { ...e, ...patch } : e)));
  };
  const add = () => onChange([...value, { target: '', source: '' }]);
  const remove = (index: number) => onChange(value.filter((_, i) => i !== index));

  return (
    <Space direction="vertical" size={8} style={{ width: '100%' }}>
      <Typography.Text type="secondary">
        把日记账的列，对应到银行流水的标准字段：
      </Typography.Text>
      {value.map((entry, i) => (
        <Space.Compact key={i} style={{ width: '100%' }}>
          <Select
            style={{ width: '45%' }}
            value={entry.target || undefined}
            placeholder="选择日记账列"
            showSearch
            allowClear
            options={targetOptions?.map((t) => ({ value: t, label: t }))}
            // 允许自由输入目标列名（未绑定模板时）
            onChange={(v) => update(i, { target: v ?? '' })}
            disabled={!targetOptions}
          />
          {targetOptions ? null : (
            <Input
              style={{ width: '45%' }}
              value={entry.target}
              placeholder="日记账列名（如：日期）"
              onChange={(e) => update(i, { target: e.target.value })}
            />
          )}
          <Input style={{ width: '8%', textAlign: 'center', backgroundColor: '#fafafa' }} value=" ← " disabled />
          <Select
            style={{ width: '37%' }}
            value={entry.source || undefined}
            placeholder="银行标准字段"
            allowClear
            options={STANDARD_FIELD_OPTIONS}
            onChange={(v) => update(i, { source: v ?? '' })}
          />
          <Button icon={<DeleteOutlined />} onClick={() => remove(i)} danger style={{ width: '10%' }} />
        </Space.Compact>
      ))}
      <Button type="dashed" icon={<PlusOutlined />} onClick={add} block>
        添加一行映射
      </Button>
    </Space>
  );
}

/** mappings_json（{目标列:标准字段}）↔ 编辑器结构互转。 */
export function mappingFromBackend(
  mappingsJson: Record<string, unknown> | null | undefined
): MappingEntry[] {
  if (!mappingsJson) return [];
  return Object.entries(mappingsJson).map(([target, source]) => ({
    target,
    source: String(source ?? '')
  }));
}

export function mappingToBackend(entries: MappingEntry[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const e of entries) {
    if (e.target && e.source) {
      out[e.target] = e.source;
    }
  }
  return out;
}

/** 映射方案的中文描述（用于详情页/版本历史）。 */
export function describeMappings(entries: MappingEntry[]): string {
  const valid = entries.filter((e) => e.target && e.source);
  if (valid.length === 0) return '暂无映射';
  return valid.map((e) => `${e.target} ← ${FIELD_LABEL[e.source] ?? e.source}`).join('，');
}
