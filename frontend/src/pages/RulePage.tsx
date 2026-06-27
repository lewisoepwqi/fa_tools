import { PlusOutlined } from '@ant-design/icons';
import { Button, Form, Input, InputNumber, Modal, Switch, Table, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createRule, listRules } from '../api/rules';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';
import type { Rule } from '../types/rules';

const ACTOR = 'user-1';

export function RulePage() {
  const [rows, setRows] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    listRules()
      .then(setRows)
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    let active = true;
    setLoading(true);
    listRules()
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
      await createRule({
        company_id: 'company-1',
        name: values.name,
        version: {
          priority: values.priority,
          conditions_json: values.conditions_json ? JSON.parse(values.conditions_json) : {},
          actions_json: values.actions_json ? JSON.parse(values.actions_json) : {},
          allow_auto_confirm: values.allow_auto_confirm ?? false,
          created_by: ACTOR
        }
      });
      message.success('规则已创建');
      form.resetFields();
      setModalOpen(false);
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '创建失败（检查 JSON 格式）');
    } finally {
      setCreating(false);
    }
  };

  const columns: ColumnsType<Rule> = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    {
      title: '优先级',
      key: 'priority',
      render: (_, r) => r.latest_version.priority ?? '-'
    },
    {
      title: '作用域',
      key: 'scope',
      render: (_, r) =>
        r.scope_type ? `${r.scope_type}${r.scope_id ? ':' + r.scope_id : ''}` : '全局'
    },
    { title: '状态', dataIndex: 'status', key: 'status', render: (_, r) => <StatusTag status={r.status} /> },
    {
      title: '允许自动确认',
      key: 'allow_auto_confirm',
      render: (_, r) => (
        <Tag color={r.latest_version.allow_auto_confirm ? 'green' : 'default'}>
          {r.latest_version.allow_auto_confirm ? '是' : '否'}
        </Tag>
      )
    },
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
          规则
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
      <Table<Rule>
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={loading}
        pagination={false}
        onRow={(record) => ({
          onClick: () => navigate(`/templates/rule/${record.id}`),
          style: { cursor: 'pointer' }
        })}
      />

      <Modal
        open={modalOpen}
        title="新建规则"
        okText="创建"
        cancelText="取消"
        confirmLoading={creating}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        destroyOnClose
        width={560}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }} initialValues={{ priority: 10, allow_auto_confirm: false }}>
          <Form.Item name="name" label="规则名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="priority" label="优先级（数值越小越先执行）">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            name="conditions_json"
            label="条件（JSON）"
            extra='例：{"all": [{"field": "summary", "op": "contains", "value": "货款"}]}'
          >
            <Input.TextArea rows={2} placeholder='{"all": [{"field": "summary", "op": "contains", "value": "货款"}]}' />
          </Form.Item>
          <Form.Item
            name="actions_json"
            label="动作（JSON）"
            extra='例：{"set": {"account_subject": "银行存款"}}'
          >
            <Input.TextArea rows={2} placeholder='{"set": {"account_subject": "银行存款"}}' />
          </Form.Item>
          <Form.Item name="allow_auto_confirm" label="允许自动确认" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
