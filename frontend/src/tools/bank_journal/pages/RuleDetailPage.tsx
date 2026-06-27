import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons';
import {
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Modal,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Typography,
  message
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  createRuleVersion,
  getRule,
  listRuleVersions,
  setRuleStatus
} from '../api/rules';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';
import type { Rule, RuleVersion } from '../types/rules';

const ACTOR = 'user-1';

function pretty(value: unknown): string {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

export function RuleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<Rule | null>(null);
  const [versions, setVersions] = useState<RuleVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [form] = Form.useForm();

  const load = (ruleId: string) => {
    setLoading(true);
    Promise.all([getRule(ruleId), listRuleVersions(ruleId)])
      .then(([d, vs]) => {
        setData(d);
        setVersions(vs);
      })
      .catch(() => {
        setData(null);
        setVersions([]);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!id) return;
    load(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const handleEdit = async () => {
    if (!id || !data) return;
    const values = await form.validateFields();
    setEditing(true);
    try {
      const patch: Partial<RuleVersion> = {
        priority: values.priority,
        allow_auto_confirm: values.allow_auto_confirm,
        created_by: ACTOR
      };
      if (values.conditions_json) patch.conditions_json = JSON.parse(values.conditions_json);
      if (values.actions_json) patch.actions_json = JSON.parse(values.actions_json);
      await createRuleVersion(id, patch);
      message.success('已创建新版本');
      setEditOpen(false);
      load(id);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '创建失败（检查 JSON）');
    } finally {
      setEditing(false);
    }
  };

  const handleToggleStatus = async () => {
    if (!id || !data) return;
    const next = data.status === 'active' ? 'inactive' : 'active';
    try {
      await setRuleStatus(id, next);
      message.success(next === 'active' ? '已启用' : '已停用');
      load(id);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败');
    }
  };

  const openEdit = () => {
    if (!data) return;
    const v = data.latest_version;
    form.setFieldsValue({
      priority: v.priority ?? 10,
      allow_auto_confirm: v.allow_auto_confirm,
      conditions_json: v.conditions_json ? JSON.stringify(v.conditions_json) : '',
      actions_json: v.actions_json ? JSON.stringify(v.actions_json) : ''
    });
    setEditOpen(true);
  };

  if (loading) {
    return (
      <Card className="work-card">
        <Spin />
      </Card>
    );
  }
  if (!data) {
    return (
      <Card className="work-card">
        <Typography.Text type="secondary">未找到该规则。</Typography.Text>
        <div style={{ marginTop: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/bank-journal/templates/rule')}>
            返回
          </Button>
        </div>
      </Card>
    );
  }

  const v = data.latest_version;
  const versionColumns: ColumnsType<RuleVersion> = [
    {
      title: '版本',
      key: 'version_no',
      render: (_, r) => <VersionBadge version={r.version_no} />
    },
    { title: '优先级', key: 'priority', render: (_, r) => r.priority ?? '-' },
    {
      title: '匹配条件',
      key: 'conditions_json',
      render: (_, r) => (
        <pre style={{ margin: 0, maxHeight: 60, overflow: 'auto' }}>
          {pretty(r.conditions_json)}
        </pre>
      )
    }
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card className="work-card">
        <Space style={{ marginBottom: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/bank-journal/templates/rule')}>
            返回
          </Button>
          <Typography.Title level={4} style={{ margin: 0 }}>
            {data.name}
          </Typography.Title>
          <Button icon={<EditOutlined />} onClick={openEdit}>
            编辑（新版本）
          </Button>
          <Button onClick={() => setHistoryOpen(true)}>版本历史</Button>
          <Button onClick={handleToggleStatus}>
            {data.status === 'active' ? '停用' : '启用'}
          </Button>
        </Space>
        <Descriptions size="small" column={2} bordered>
          <Descriptions.Item label="规则ID">{data.id}</Descriptions.Item>
          <Descriptions.Item label="公司">{data.company_id}</Descriptions.Item>
          <Descriptions.Item label="作用域类型">{data.scope_type ?? '全局'}</Descriptions.Item>
          <Descriptions.Item label="作用域ID">{data.scope_id ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <StatusTag status={data.status} />
          </Descriptions.Item>
          <Descriptions.Item label="最新版本">
            <VersionBadge version={v.version_no} />
          </Descriptions.Item>
        </Descriptions>
      </Card>
      <Card className="work-card" title={`版本配置 · v${v.version_no}`}>
        <Descriptions size="small" column={1} bordered>
          <Descriptions.Item label="优先级">{v.priority ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="允许自动确认">
            <Tag color={v.allow_auto_confirm ? 'green' : 'default'}>
              {v.allow_auto_confirm ? '是' : '否'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="匹配条件">
            <pre style={{ margin: 0 }}>{pretty(v.conditions_json)}</pre>
          </Descriptions.Item>
          <Descriptions.Item label="执行动作">
            <pre style={{ margin: 0 }}>{pretty(v.actions_json)}</pre>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Modal
        open={editOpen}
        title="编辑（创建新版本）"
        okText="创建新版本"
        cancelText="取消"
        confirmLoading={editing}
        onOk={handleEdit}
        onCancel={() => setEditOpen(false)}
        destroyOnClose
        width={560}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="priority" label="优先级（数值越小越先执行）">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            name="conditions_json"
            label="匹配条件（JSON）"
            extra='例：{"all": [{"field": "summary", "op": "contains", "value": "货款"}]}'
          >
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item
            name="actions_json"
            label="执行动作（JSON）"
            extra='例：{"set": {"account_subject": "银行存款"}}'
          >
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="allow_auto_confirm" label="允许自动确认" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={historyOpen}
        title="版本历史"
        footer={null}
        onCancel={() => setHistoryOpen(false)}
        width={720}
      >
        <Table<RuleVersion>
          rowKey="version_no"
          columns={versionColumns}
          dataSource={versions}
          pagination={false}
          size="small"
        />
      </Modal>
    </Space>
  );
}
