import { Button, Table, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';

interface MappingProfileRow {
  id: string;
  name: string;
  bank_template: string;
  journal_template: string;
  status: string;
  latest_version: number;
}

const ROWS: MappingProfileRow[] = [
  {
    id: '1',
    name: '中行-标准映射',
    bank_template: '中国银行 CSV 模板',
    journal_template: '标准日记账模板',
    status: 'active',
    latest_version: 2
  },
  {
    id: '2',
    name: '工行-简化映射',
    bank_template: '工商银行 XLSX 模板',
    journal_template: '简化版日记账模板',
    status: 'draft',
    latest_version: 1
  }
];

export function MappingProfilePage() {
  const columns: ColumnsType<MappingProfileRow> = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '银行流水模板', dataIndex: 'bank_template', key: 'bank_template' },
    { title: '日记账模板', dataIndex: 'journal_template', key: 'journal_template' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (_, r) => <StatusTag status={r.status} /> },
    { title: '最新版本', dataIndex: 'latest_version', key: 'latest_version', render: (_, r) => <VersionBadge version={r.latest_version} /> }
  ];
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>映射方案</Typography.Title>
        <Button type="primary" onClick={() => message.success('已创建')}>新建</Button>
      </div>
      <Table<MappingProfileRow> rowKey="id" columns={columns} dataSource={ROWS} pagination={false} />
    </div>
  );
}
