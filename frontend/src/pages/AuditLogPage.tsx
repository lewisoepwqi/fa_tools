import { Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

interface AuditLogRow {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  actor_id: string;
  created_at: string;
}

// 注：当前为演示数据，后续接入真实审计日志接口（/api/audit-logs）。
const ROWS: AuditLogRow[] = [
  { id: '1', action: '创建', entity_type: '银行流水模板', entity_id: '1', actor_id: 'user-001', created_at: '2026-06-27 09:00' },
  { id: '2', action: '更新', entity_type: '规则', entity_id: '2', actor_id: 'user-002', created_at: '2026-06-27 09:30' },
  { id: '3', action: '发布版本', entity_type: '映射方案', entity_id: '1', actor_id: 'user-001', created_at: '2026-06-27 10:15' }
];

/** 操作类型 → 品牌色（创建=蓝、更新=红、发布=红浅）。 */
const ACTION_COLOR: Record<string, string> = {
  创建: '#133f8e',
  更新: '#cc4f58',
  发布版本: '#b5141d'
};

export function AuditLogPage() {
  const columns: ColumnsType<AuditLogRow> = [
    {
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      render: (_, r) => <Tag color={ACTION_COLOR[r.action] ?? 'default'}>{r.action}</Tag>
    },
    { title: '实体类型', dataIndex: 'entity_type', key: 'entity_type' },
    { title: '实体 ID', dataIndex: 'entity_id', key: 'entity_id', render: (v) => <span className="num">{v}</span> },
    { title: '操作人', dataIndex: 'actor_id', key: 'actor_id', render: (v) => <span className="num">{v}</span> },
    { title: '时间', dataIndex: 'created_at', key: 'created_at' }
  ];

  return (
    <div>
      <div className="toolbar" style={{ marginBottom: 16 }}>
        <h2 className="section-title">审计日志</h2>
        <div className="toolbar-spacer" />
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          演示数据 · 后续接入真实接口
        </Typography.Text>
      </div>
      <Table<AuditLogRow>
        rowKey="id"
        columns={columns}
        dataSource={ROWS}
        pagination={false}
      />
    </div>
  );
}
