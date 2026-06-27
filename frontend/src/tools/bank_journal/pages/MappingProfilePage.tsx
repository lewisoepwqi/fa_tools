import { PlusOutlined } from '@ant-design/icons';
import { Button, Form, Input, Modal, Table, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createMappingProfile, listMappingProfiles } from '../api/mappingProfiles';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';
import type { MappingProfile } from '../types/mapping';

const ACTOR = 'user-1';

export function MappingProfilePage() {
  const [rows, setRows] = useState<MappingProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    listMappingProfiles()
      .then(setRows)
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    let active = true;
    setLoading(true);
    listMappingProfiles()
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
      await createMappingProfile({
        company_id: 'company-1',
        name: values.name,
        bank_template_id: values.bank_template_id || null,
        company_journal_template_id: values.company_journal_template_id || null,
        version: {
          mappings_json: values.mappings_json ? JSON.parse(values.mappings_json) : {},
          created_by: ACTOR
        }
      });
      message.success('映射方案已创建');
      form.resetFields();
      setModalOpen(false);
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '创建失败（检查 JSON 格式）');
    } finally {
      setCreating(false);
    }
  };

  const columns: ColumnsType<MappingProfile> = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    {
      title: '银行流水模板',
      dataIndex: 'bank_template_id',
      key: 'bank_template_id',
      render: (v) => v ?? '-'
    },
    {
      title: '日记账模板',
      dataIndex: 'company_journal_template_id',
      key: 'company_journal_template_id',
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
          映射方案
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
      <Table<MappingProfile>
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={loading}
        pagination={false}
        onRow={(record) => ({
          onClick: () => navigate(`/templates/mapping/${record.id}`),
          style: { cursor: 'pointer' }
        })}
      />

      <Modal
        open={modalOpen}
        title="新建映射方案"
        okText="创建"
        cancelText="取消"
        confirmLoading={creating}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="方案名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="bank_template_id" label="银行模板 ID（可选）">
            <Input placeholder="留空则不绑定" />
          </Form.Item>
          <Form.Item name="company_journal_template_id" label="日记账模板 ID（可选）">
            <Input placeholder="留空则不绑定" />
          </Form.Item>
          <Form.Item
            name="mappings_json"
            label="映射配置（JSON）"
            extra='例如：{"日期": "transaction_date", "摘要": "summary"}'
          >
            <Input.TextArea rows={3} placeholder='{"日期": "transaction_date"}' />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
