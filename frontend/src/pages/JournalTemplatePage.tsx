import { Button, Table, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';

interface JournalTemplateRow {
  id: string;
  name: string;
  status: string;
  latest_version: number;
}

const ROWS: JournalTemplateRow[] = [
  { id: '1', name: '标准日记账模板', status: 'active', latest_version: 5 },
  { id: '2', name: '简化版日记账模板', status: 'draft', latest_version: 1 }
];

export function JournalTemplatePage() {
  const columns: ColumnsType<JournalTemplateRow> = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (_, r) => <StatusTag status={r.status} /> },
    { title: '最新版本', dataIndex: 'latest_version', key: 'latest_version', render: (_, r) => <VersionBadge version={r.latest_version} /> }
  ];
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>日记账模板</Typography.Title>
        <Button type="primary" onClick={() => message.success('已创建')}>新建</Button>
      </div>
      <Table<JournalTemplateRow> rowKey="id" columns={columns} dataSource={ROWS} pagination={false} />
    </div>
  );
}
