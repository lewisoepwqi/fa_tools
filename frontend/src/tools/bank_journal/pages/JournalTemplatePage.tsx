import { PlusOutlined } from '@ant-design/icons';
import { Button, Form, Input, Modal, Select, Table, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createJournalTemplate, listJournalTemplates } from '../api/journalTemplates';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';
import type { JournalTemplate } from '../types/templates';

const ACTOR = 'user-1';

export function JournalTemplatePage() {
  const [rows, setRows] = useState<JournalTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    listJournalTemplates()
      .then(setRows)
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    let active = true;
    setLoading(true);
    listJournalTemplates()
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
      await createJournalTemplate({
        company_id: 'company-1',
        name: values.name,
        version: {
          file_type: values.file_type,
          sheet_name: values.sheet_name,
          columns_json: values.columns_json,
          required_columns_json: values.required_columns_json,
          created_by: ACTOR
        }
      });
      message.success('模板已创建');
      form.resetFields();
      setModalOpen(false);
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '创建失败');
    } finally {
      setCreating(false);
    }
  };

  const columns: ColumnsType<JournalTemplate> = [
    { title: '名称', dataIndex: 'name', key: 'name' },
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
          日记账模板
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
      <Table<JournalTemplate>
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={loading}
        pagination={false}
        onRow={(record) => ({
          onClick: () => navigate(`/bank-journal/templates/journal/${record.id}`),
          style: { cursor: 'pointer' }
        })}
      />

      <Modal
        open={modalOpen}
        title="新建日记账模板"
        okText="创建"
        cancelText="取消"
        confirmLoading={creating}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ file_type: 'xlsx', sheet_name: '日记账', columns_json: ['日期', '摘要', '科目', '金额'], required_columns_json: ['日期', '科目', '金额'] }}
          style={{ marginTop: 16 }}
        >
          <Form.Item name="name" label="模板名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="file_type" label="文件类型" rules={[{ required: true }]}>
            <Select options={[{ value: 'csv', label: 'CSV' }, { value: 'xlsx', label: 'XLSX' }]} />
          </Form.Item>
          <Form.Item name="sheet_name" label="Sheet 名">
            <Input />
          </Form.Item>
        </Form>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          输出字段 / 必填字段将使用默认值（日期、摘要、科目、金额）。可在详情页通过新建版本修改。
        </Typography.Text>
      </Modal>
    </div>
  );
}
