import { PlusOutlined } from '@ant-design/icons';
import { Button, Form, Input, InputNumber, Modal, Select, Space, Table, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createBankTemplate, listBankTemplates } from '../api/bankTemplates';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';
import type { BankTemplate } from '../types/templates';

const ACTOR = 'user-1';
const AMOUNT_MODES = [
  { value: 'income_expense_columns', label: '收入/支出双列' },
  { value: 'debit_credit_columns', label: '借方/贷方双列' },
  { value: 'single_amount_with_direction', label: '单金额+方向列' },
  { value: 'signed_amount', label: '带符号金额' }
];

export function BankTemplatePage() {
  const [rows, setRows] = useState<BankTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    listBankTemplates()
      .then(setRows)
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    let active = true;
    setLoading(true);
    listBankTemplates()
      .then((data) => {
        if (active) setRows(data);
      })
      .catch(() => {
        if (active) setRows([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleCreate = async () => {
    const values = await form.validateFields();
    setCreating(true);
    try {
      await createBankTemplate({
        company_id: 'company-1',
        name: values.name,
        bank_name: values.bank_name,
        version: {
          file_type: values.file_type,
          header_row_index: values.header_row_index,
          data_start_row_index: values.data_start_row_index,
          amount_mode: values.amount_mode,
          created_by: ACTOR
        }
      });
      message.success('模板已创建');
      form.resetFields();
      setCreating(false);
      setModalOpen(false);
      load();
    } catch (err) {
      setCreating(false);
      message.error(err instanceof Error ? err.message : '创建失败');
    }
  };

  const columns: ColumnsType<BankTemplate> = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    {
      title: '银行名称',
      dataIndex: 'bank_name',
      key: 'bank_name',
      render: (v) => v ?? '-'
    },
    {
      title: '银行账号',
      dataIndex: 'bank_account_id',
      key: 'bank_account_id',
      render: (v) => v ?? '-'
    },
    { title: '状态', dataIndex: 'status', key: 'status', render: (_, r) => <StatusTag status={r.status} /> },
    {
      title: '最新版本',
      key: 'latest_version',
      render: (_, r) => <VersionBadge version={r.latest_version.version_no} />
    }
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          银行流水模板
        </Typography.Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            form.resetFields();
            setModalOpen(true);
          }}
        >
          新建
        </Button>
      </div>
      <Table<BankTemplate>
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={loading}
        pagination={false}
        onRow={(record) => ({
          onClick: () => navigate(`/templates/bank/${record.id}`),
          style: { cursor: 'pointer' }
        })}
      />

      <Modal
        open={modalOpen}
        title="新建银行模板"
        okText="创建"
        cancelText="取消"
        confirmLoading={creating}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        destroyOnClose
      >
        <Space direction="vertical" style={{ width: '100%', marginTop: 16 }}>
          <Form form={form} layout="vertical" initialValues={{ file_type: 'csv', amount_mode: 'income_expense_columns', header_row_index: 0, data_start_row_index: 1 }}>
            <Form.Item name="name" label="模板名称" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="bank_name" label="银行名称">
              <Input />
            </Form.Item>
            <Form.Item name="file_type" label="文件类型" rules={[{ required: true }]}>
              <Select options={[{ value: 'csv', label: 'CSV' }, { value: 'xlsx', label: 'XLSX' }]} />
            </Form.Item>
            <Form.Item name="amount_mode" label="金额模式" rules={[{ required: true }]}>
              <Select options={AMOUNT_MODES} />
            </Form.Item>
            <Form.Item name="header_row_index" label="表头行（0 基）">
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="data_start_row_index" label="数据起始行（0 基）">
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
          </Form>
        </Space>
      </Modal>
    </div>
  );
}
