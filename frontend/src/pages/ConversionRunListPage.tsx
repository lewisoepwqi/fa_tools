import { Table, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { StatusTag } from '../components/StatusTag';

interface ConversionRunRow {
  id: string;
  company: string;
  bank_account: string;
  status: string;
  total_rows: number;
  exception_rows: number;
  created_at: string;
}

const ROWS: ConversionRunRow[] = [
  { id: 'RUN-2026-001', company: '示例科技有限公司', bank_account: 'BOC-001', status: 'auto_confirmed', total_rows: 320, exception_rows: 4, created_at: '2026-06-27 09:12' },
  { id: 'RUN-2026-002', company: '示例科技有限公司', bank_account: 'ICBC-002', status: 'needs_confirmation', total_rows: 158, exception_rows: 12, created_at: '2026-06-27 10:30' },
  { id: 'RUN-2026-003', company: '另一家贸易公司', bank_account: 'CMB-007', status: 'conflict', total_rows: 87, exception_rows: 7, created_at: '2026-06-26 16:45' }
];

export function ConversionRunListPage() {
  const columns: ColumnsType<ConversionRunRow> = [
    { title: '批次号', dataIndex: 'id', key: 'id' },
    { title: '公司', dataIndex: 'company', key: 'company' },
    { title: '银行账号', dataIndex: 'bank_account', key: 'bank_account' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (_, r) => <StatusTag status={r.status} /> },
    { title: '总行数', dataIndex: 'total_rows', key: 'total_rows' },
    { title: '异常行数', dataIndex: 'exception_rows', key: 'exception_rows' },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at' }
  ];
  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 16 }}>处理批次</Typography.Title>
      <Table<ConversionRunRow> rowKey="id" columns={columns} dataSource={ROWS} pagination={false} />
    </div>
  );
}
