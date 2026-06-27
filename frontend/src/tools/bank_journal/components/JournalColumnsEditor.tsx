import { ArrowDownOutlined, ArrowUpOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { Button, Checkbox, Input, Space, Table, Typography } from 'antd';
import { useMemo } from 'react';

/** 日记账列：列名 + 是否必填。 */
export interface JournalColumn {
  name: string;
  required: boolean;
}

interface JournalColumnsEditorProps {
  value: JournalColumn[];
  onChange: (value: JournalColumn[]) => void;
}

/**
 * 日记账输出列可视化编辑器。
 * 替代写死的默认列：可增删列、调整顺序、勾选必填。
 * 提交时由调用方转为 columns_json / required_columns_json。
 */
export function JournalColumnsEditor({ value, onChange }: JournalColumnsEditorProps) {
  const move = (index: number, delta: -1 | 1) => {
    const target = index + delta;
    if (target < 0 || target >= value.length) return;
    const next = [...value];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  };

  const update = (index: number, patch: Partial<JournalColumn>) => {
    onChange(value.map((c, i) => (i === index ? { ...c, ...patch } : c)));
  };

  const add = () => onChange([...value, { name: '', required: false }]);
  const remove = (index: number) => onChange(value.filter((_, i) => i !== index));

  const summary = useMemo(() => {
    const required = value.filter((c) => c.required && c.name).map((c) => c.name);
    const all = value.filter((c) => c.name).map((c) => c.name);
    return `共 ${all.length} 列，其中必填 ${required.length} 列（${required.join('、') || '无'}）`;
  }, [value]);

  return (
    <Space direction="vertical" size={8} style={{ width: '100%' }}>
      <Table<JournalColumn & { key: number }>
        rowKey={(_, i) => String(i)}
        dataSource={value.map((c, i) => ({ ...c, key: i }))}
        pagination={false}
        size="small"
        columns={[
          {
            title: '列名',
            key: 'name',
            width: '50%',
            render: (_, row, i) => (
              <Input
                value={row.name}
                placeholder="如：日期、摘要、科目、金额"
                onChange={(e) => update(i, { name: e.target.value })}
              />
            )
          },
          {
            title: '必填',
            key: 'required',
            width: '20%',
            render: (_, row, i) => (
              <Checkbox
                checked={row.required}
                onChange={(e) => update(i, { required: e.target.checked })}
              />
            )
          },
          {
            title: '排序',
            key: 'order',
            width: '30%',
            render: (_, _row, i) => (
              <Space>
                <Button size="small" icon={<ArrowUpOutlined />} disabled={i === 0} onClick={() => move(i, -1)} />
                <Button size="small" icon={<ArrowDownOutlined />} disabled={i === value.length - 1} onClick={() => move(i, 1)} />
                <Button size="small" icon={<DeleteOutlined />} danger onClick={() => remove(i)} />
              </Space>
            )
          }
        ]}
      />
      <Button type="dashed" icon={<PlusOutlined />} onClick={add} block>
        添加列
      </Button>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        {summary}
      </Typography.Text>
    </Space>
  );
}

/** columns_json + required_columns_json ↔ 编辑器结构互转。 */
export function columnsFromBackend(
  columnsJson: unknown[] | null | undefined,
  requiredJson: unknown[] | null | undefined
): JournalColumn[] {
  const cols = (columnsJson ?? []).map(String);
  const requiredSet = new Set((requiredJson ?? []).map(String));
  if (cols.length === 0) {
    // 默认列
    return [
      { name: '日期', required: true },
      { name: '摘要', required: false },
      { name: '科目', required: true },
      { name: '金额', required: true }
    ];
  }
  return cols.map((name) => ({ name, required: requiredSet.has(name) }));
}

export function columnsToBackend(value: JournalColumn[]): {
  columns_json: string[];
  required_columns_json: string[];
} {
  const named = value.filter((c) => c.name.trim());
  return {
    columns_json: named.map((c) => c.name.trim()),
    required_columns_json: named.filter((c) => c.required).map((c) => c.name.trim())
  };
}
