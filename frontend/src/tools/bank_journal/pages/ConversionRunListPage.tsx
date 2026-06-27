import { Table } from 'antd';
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
    { title: '批次号', dataIndex: 'id', key: 'id', render: (v) => <span className="num">{v}</span> },
    { title: '公司', dataIndex: 'company_id', key: 'company_id' },
    {
      title: '银行账号',
      dataIndex: 'bank_account_id',
      key: 'bank_account_id',
      render: (v) => v ?? '-'
    },
    { title: '状态', dataIndex: 'status', key: 'status', render: (_, r) => <StatusTag status={r.status} /> },
    {
      title: '总行数',
      dataIndex: ['summary', 'total_rows'],
      key: 'total_rows',
      align: 'right',
      render: (v) => <span className="num num-right">{v ?? '-'}</span>
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string | null) => (v ? new Date(v).toLocaleString() : '-')
    }
  ];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <h2 className="section-title">处理批次</h2>
      </div>
      <Table<ConversionRunListItem>
        rowKey="id"
        columns={columns}
        dataSource={runs}
        loading={loading}
        pagination={false}
        locale={{
          emptyText: (
            <div className="empty-teach">
              <strong>暂无处理批次</strong>
              前往「流水上传」上传银行流水文件以创建第一个转换批次
            </div>
          )
        }}
        onRow={(record) => ({
          onClick: () => navigate(`/bank-journal/runs/${record.id}`),
          style: { cursor: 'pointer' }
        })}
      />
    </div>
  );
}
