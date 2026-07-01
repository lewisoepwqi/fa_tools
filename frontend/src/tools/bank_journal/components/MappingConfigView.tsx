import { Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { FIELD_LABEL } from '../constants';
import {
  MAPPING_TYPE_OPTIONS,
  type MappingEntry,
  type MappingType
} from './MappingEditor';

/** 映射类型 → 中文标签。 */
const TYPE_LABEL: Record<MappingType, string> = Object.fromEntries(
  MAPPING_TYPE_OPTIONS.map((o) => [o.value, o.label])
) as Record<MappingType, string>;

/** 流水字段 key → 中文（非标准字段原样返回）。 */
function fieldLabel(key?: string): string {
  if (!key) return '-';
  return FIELD_LABEL[key] ?? key;
}

interface MappingConfigViewProps {
  /** 已解析的映射条目（由 mappingFromBackend 从 mappings_json 解析得到）。 */
  entries: MappingEntry[];
}

/**
 * 映射方案的只读结构化视图（详情页 / 版本历史复用）。
 *
 * 详情页默认状态应是「可读展示」（Carbon Design System 最佳实践）。本组件把
 * 每条映射（目标列 ← 来源）以表格形式直接呈现，支持全部 5 种映射类型，
 * 无需点开编辑 Modal 即可核对配置明细。
 */
export function MappingConfigView({ entries }: MappingConfigViewProps) {
  const valid = entries.filter((e) => e.target);

  if (valid.length === 0) {
    return <Typography.Text type="secondary">该方案尚未配置任何映射。</Typography.Text>;
  }

  const columns: ColumnsType<MappingEntry> = [
    {
      title: '日记账列',
      dataIndex: 'target',
      key: 'target',
      render: (_, e) => <Tag color="geekblue">{e.target}</Tag>
    },
    {
      title: '取值方式',
      dataIndex: 'type',
      key: 'type',
      width: 120,
      render: (_, e) => TYPE_LABEL[e.type] ?? e.type
    },
    {
      title: '来源',
      key: 'source',
      render: (_, e) => {
        switch (e.type) {
          case 'field':
            return <Typography.Text>{fieldLabel(e.source)}</Typography.Text>;
          case 'rule_output':
            return (
              <Typography.Text>
                规则输出（{fieldLabel(e.source)}）
              </Typography.Text>
            );
          case 'fixed':
            return <Typography.Text code>{e.value || '-'}</Typography.Text>;
          case 'concat':
            return (
              <Typography.Text>
                {(e.sources ?? []).map((s) => fieldLabel(s)).join(` ${e.separator ?? '+'} `)}
              </Typography.Text>
            );
          case 'manual':
            return <Typography.Text type="secondary">转换后人工填写</Typography.Text>;
          default:
            return <Typography.Text type="secondary">-</Typography.Text>;
        }
      }
    }
  ];

  return (
    <Table<MappingEntry>
      rowKey={(_, i) => String(i)}
      columns={columns}
      dataSource={valid}
      pagination={false}
      size="small"
    />
  );
}
