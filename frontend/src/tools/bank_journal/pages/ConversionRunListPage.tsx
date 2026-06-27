import { Table, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listConversionRuns } from '../api/conversionRuns';
import { StatusTag } from '../components/StatusTag';
import type { ConversionRunListItem } from '../types/conversion';

export function ConversionRunListPage() {
  const [runs, setRuns] = useState<ConversionRunListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    let active = true;
    setLoading(true);
    listConversionRuns()
      .then((data) => {
        if (active) setRuns(data);
      })
      .catch(() => {
        if (active) setRuns([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const columns: ColumnsType<ConversionRunListItem> = [
    { title: '批次号', dataIndex: 'id', key: 'id' },
    { title: '公司', dataIndex: 'company_id', key: 'company_id' },
    { title: '银行账号', dataIndex: 'bank_account_id', key: 'bank_account_id', render: (v) => v ?? '-' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (_, r) => <StatusTag status={r.status} /> },
    { title: '总行数', dataIndex: ['summary', 'total_rows'], key: 'total_rows' },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string | null) => (v ? new Date(v).toLocaleString() : '-')
    }
  ];

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 16 }}>处理批次</Typography.Title>
      <Table<ConversionRunListItem>
        rowKey="id"
        columns={columns}
        dataSource={runs}
        loading={loading}
        pagination={false}
        onRow={(record) => ({ onClick: () => navigate(`/runs/${record.id}`), style: { cursor: 'pointer' } })}
      />
    </div>
  );
}
