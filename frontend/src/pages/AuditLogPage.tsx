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

const ROWS: AuditLogRow[] = [
  { id: '1', action: '创建', entity_type: '银行流水模板', entity_id: '1', actor_id: 'user-001', created_at: '2026-06-27 09:00' },
  { id: '2', action: '更新', entity_type: '规则', entity_id: '2', actor_id: 'user-002', created_at: '2026-06-27 09:30' },
  { id: '3', action: '发布版本', entity_type: '映射方案', entity_id: '1', actor_id: 'user-001', created_at: '2026-06-27 10:15' }
];

const ACTION_COLOR: Record<string, string> = {
  创建: 'green',
  更新: 'blue',
  发布版本: 'gold'
};

export function AuditLogPage() {
  const columns: ColumnsType<AuditLogRow> = [
    { title: '操作', dataIndex: 'action', key: 'action', render: (_, r) => <Tag color={ACTION_COLOR[r.action] ?? 'default'}>{r.action}</Tag> },
    { title: '实体类型', dataIndex: 'entity_type', key: 'entity_type' },
    { title: '实体 ID', dataIndex: 'entity_id', key: 'entity_id' },
    { title: '操作人', dataIndex: 'actor_id', key: 'actor_id' },
    { title: '时间', dataIndex: 'created_at', key: 'created_at' }
  ];
  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 16 }}>审计日志</Typography.Title>
      <Table<AuditLogRow> rowKey="id" columns={columns} dataSource={ROWS} pagination={false} />
    </div>
  );
}
