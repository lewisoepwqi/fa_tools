import { Button, Table, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';

interface RuleRow {
  id: string;
  name: string;
  priority: number;
  scope: string;
  status: string;
  allow_auto_confirm: boolean;
  latest_version: number;
}

const ROWS: RuleRow[] = [
  { id: '1', name: '大额支出规则', priority: 10, scope: '全局', status: 'active', allow_auto_confirm: false, latest_version: 4 },
  { id: '2', name: '工资收入匹配', priority: 5, scope: '科目:应付职工薪酬', status: 'active', allow_auto_confirm: true, latest_version: 2 },
  { id: '3', name: '手续费忽略', priority: 1, scope: '全局', status: 'draft', allow_auto_confirm: true, latest_version: 1 }
];

export function RulePage() {
  const columns: ColumnsType<RuleRow> = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '优先级', dataIndex: 'priority', key: 'priority' },
    { title: '作用域', dataIndex: 'scope', key: 'scope' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (_, r) => <StatusTag status={r.status} /> },
    {
      title: '允许自动确认',
      dataIndex: 'allow_auto_confirm',
      key: 'allow_auto_confirm',
      render: (_, r) => <Tag color={r.allow_auto_confirm ? 'green' : 'default'}>{r.allow_auto_confirm ? '是' : '否'}</Tag>
    },
    { title: '最新版本', dataIndex: 'latest_version', key: 'latest_version', render: (_, r) => <VersionBadge version={r.latest_version} /> }
  ];
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>规则</Typography.Title>
        <Button type="primary" onClick={() => message.success('已创建')}>新建</Button>
      </div>
      <Table<RuleRow> rowKey="id" columns={columns} dataSource={ROWS} pagination={false} />
    </div>
  );
}
