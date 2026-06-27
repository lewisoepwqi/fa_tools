import { Button, Table, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';

interface BankTemplateRow {
  id: string;
  name: string;
  bank_name: string;
  bank_account_id: string;
  status: string;
  latest_version: number;
}

const ROWS: BankTemplateRow[] = [
  { id: '1', name: '中国银行 CSV 模板', bank_name: '中国银行', bank_account_id: 'BOC-001', status: 'active', latest_version: 3 },
  { id: '2', name: '工商银行 XLSX 模板', bank_name: '工商银行', bank_account_id: 'ICBC-002', status: 'draft', latest_version: 1 },
  { id: '3', name: '招商银行 CSV 模板', bank_name: '招商银行', bank_account_id: 'CMB-007', status: 'active', latest_version: 2 }
];

export function BankTemplatePage() {
  const columns: ColumnsType<BankTemplateRow> = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '银行名称', dataIndex: 'bank_name', key: 'bank_name' },
    { title: '银行账号', dataIndex: 'bank_account_id', key: 'bank_account_id' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (_, r) => <StatusTag status={r.status} /> },
    { title: '最新版本', dataIndex: 'latest_version', key: 'latest_version', render: (_, r) => <VersionBadge version={r.latest_version} /> }
  ];
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>银行流水模板</Typography.Title>
        <Button type="primary" onClick={() => message.success('已创建')}>新建</Button>
      </div>
      <Table<BankTemplateRow> rowKey="id" columns={columns} dataSource={ROWS} pagination={false} />
    </div>
  );
}
