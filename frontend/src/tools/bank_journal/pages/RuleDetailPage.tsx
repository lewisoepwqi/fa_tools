import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  Descriptions,
  InputNumber,
  Modal,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Typography
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { message } from '../../../components/antdApp';
import {
  createRuleVersion,
  getRule,
  listRuleVersions,
  setRuleStatus
} from '../api/rules';
import {
  RuleEditor,
  describeRule,
  ruleDataFromBackend,
  ruleDataToBackend,
  type RuleEditorData
} from '../components/RuleEditor';
import { useStandardFields } from '../components/useStandardFields';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';
import type { Rule, RuleVersion } from '../types/rules';

const ACTOR = 'user-1';

export function RuleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const standardFields = useStandardFields();
  const [data, setData] = useState<Rule | null>(null);
  const [versions, setVersions] = useState<RuleVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  // 编辑态
  const [editData, setEditData] = useState<RuleEditorData>({ logic: 'all', conditions: [], actions: [] });
  const [editPriority, setEditPriority] = useState(10);
  const [editAuto, setEditAuto] = useState(false);

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

  const openEdit = () => {
    if (!data) return;
    const v = data.latest_version;
    setEditPriority(v.priority ?? 10);
    setEditAuto(v.allow_auto_confirm);
    setEditData(ruleDataFromBackend(v.conditions_json, v.actions_json));
    setEditOpen(true);
  };

  const handleEdit = async () => {
    if (!id) return;
    setEditing(true);
    try {
      const { conditions_json, actions_json } = ruleDataToBackend(editData);
      await createRuleVersion(id, {
        priority: editPriority,
        conditions_json,
        actions_json,
        allow_auto_confirm: editAuto,
        created_by: ACTOR
      });
      message.success('已创建新版本');
      setEditOpen(false);
      load(id);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '创建失败');
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
  const currentRuleData = ruleDataFromBackend(v.conditions_json, v.actions_json);

  const versionColumns: ColumnsType<RuleVersion> = [
    {
      title: '版本',
      key: 'version_no',
      render: (_, r) => <VersionBadge version={r.version_no} />
    },
    { title: '优先级', key: 'priority', render: (_, r) => r.priority ?? '-' },
    {
      title: '规则含义',
      key: 'desc',
      render: (_, r) => (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {describeRule(ruleDataFromBackend(r.conditions_json, r.actions_json))}
        </Typography.Text>
      )
    }
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card className="work-card">
        <div className="toolbar" style={{ marginBottom: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/bank-journal/templates/rule')}>
            返回
          </Button>
          <h2 className="section-title">{data.name}</h2>
          <div className="toolbar-spacer" />
          <Button icon={<EditOutlined />} onClick={openEdit}>
            编辑（新版本）
          </Button>
          <Button onClick={() => setHistoryOpen(true)}>版本历史</Button>
          <Button onClick={handleToggleStatus}>
            {data.status === 'active' ? '停用' : '启用'}
          </Button>
        </div>
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

      <Card className="work-card" title={`配置详情 · v${v.version_no}`}>
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Descriptions size="small" column={2} bordered>
            <Descriptions.Item label="优先级">{v.priority ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="允许自动确认">
              <Tag color={v.allow_auto_confirm ? 'green' : 'default'}>
                {v.allow_auto_confirm ? '是' : '否'}
              </Tag>
            </Descriptions.Item>
          </Descriptions>
          <Alert type="info" showIcon message="规则含义" description={describeRule(currentRuleData)} />
        </Space>
      </Card>

      <Modal
        open={editOpen}
        title="编辑规则（创建新版本）"
        okText="创建新版本"
        cancelText="取消"
        confirmLoading={editing}
        onOk={handleEdit}
        onCancel={() => setEditOpen(false)}
        destroyOnHidden
        width={680}
      >
        <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div>
              <Typography.Text strong>优先级</Typography.Text>
              <InputNumber min={0} value={editPriority} onChange={(v2) => setEditPriority(v2 ?? 0)} style={{ width: 120, marginLeft: 8 }} />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Switch checked={editAuto} onChange={setEditAuto} />
              <Typography.Text>允许自动确认</Typography.Text>
            </div>
          </div>
          <RuleEditor
            value={editData}
            onChange={setEditData}
            standardFieldOptions={standardFields.options}
            fieldTypeMap={standardFields.typeMap}
          />
        </div>
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
