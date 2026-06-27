import { Card, Space, Table, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ExceptionTag } from '../components/ExceptionTag';
import { StatusTag } from '../components/StatusTag';
import type { ConversionRunResponse, PreviewRow } from '../types/conversion';

function renderValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '-';
  }
  return String(value);
}

export function ConversionRunDetailPage({ run }: { run: ConversionRunResponse }) {
  const columns: ColumnsType<PreviewRow> = [
    {
      title: '日期',
      dataIndex: 'output_values',
      key: '日期',
      render: (_, record) => renderValue(record.output_values['日期'])
    },
    {
      title: '摘要',
      dataIndex: 'output_values',
      key: '摘要',
      render: (_, record) => renderValue(record.output_values['摘要'])
    },
    {
      title: '科目',
      dataIndex: 'output_values',
      key: '科目',
      render: (_, record) => renderValue(record.output_values['科目'])
    },
    {
      title: '金额',
      dataIndex: 'output_values',
      key: '金额',
      render: (_, record) => renderValue(record.output_values['金额'])
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: '状态',
      render: (_, record) => <StatusTag status={record.status} />
    },
    {
      title: '异常',
      dataIndex: 'exception_codes',
      key: '异常',
      render: (_, record) =>
        record.exception_codes.length > 0 ? (
          <Space size={4}>
            {record.exception_codes.map((code) => (
              <ExceptionTag key={code} code={code} />
            ))}
          </Space>
        ) : (
          '-'
        )
    }
  ];

  return (
    <Card className="work-card">
      <Typography.Title level={4}>转换结果 · 共 {run.summary.total_rows} 行</Typography.Title>
      <Table<PreviewRow>
        rowKey="row_index"
        columns={columns}
        dataSource={run.preview_rows}
        pagination={false}
        scroll={{ x: 'max-content' }}
      />
    </Card>
  );
}
