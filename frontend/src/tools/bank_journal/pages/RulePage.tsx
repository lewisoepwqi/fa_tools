import { PlusOutlined } from '@ant-design/icons';
import { Button, Input, InputNumber, Modal, Popconfirm, Space, Switch, Table, Tag, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../auth/useAuth';
import { message } from '../../../components/antdApp';
import { createRule, deleteRule, listRules, setRuleStatus } from '../api/rules';
import {
  RuleEditor,
  ruleDataToBackend,
  type RuleEditorData
} from '../components/RuleEditor';
import { VersionBadge } from '../components/VersionBadge';
import type { Rule } from '../types/rules';

const EMPTY_RULE: RuleEditorData = { logic: 'all', conditions: [], actions: [] };

export function RulePage() {
  const { currentCompanyId, hasPermission } = useAuth();
  const canManage = hasPermission('template_manage');
  const [rows, setRows] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [priority, setPriority] = useState(10);
  const [allowAutoConfirm, setAllowAutoConfirm] = useState(false);
  const [ruleData, setRuleData] = useState<RuleEditorData>(EMPTY_RULE);
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

  const openCreate = () => {
    setName('');
    setPriority(10);
    setAllowAutoConfirm(false);
    setRuleData(EMPTY_RULE);
    setModalOpen(true);
  };

  const handleCreate = async () => {
    if (!name.trim()) {
      message.error('请输入规则名称');
      return;
    }
    if (ruleData.conditions.length === 0) {
      message.error('请至少添加一个条件');
      return;
    }
    // 防止模态框打开后公司切换为空时发送空字符串
    if (!currentCompanyId) {
      message.error('请先在右上角选择公司');
      return;
    }
    setCreating(true);
    try {
      const { conditions_json, actions_json } = ruleDataToBackend(ruleData);
      await createRule({
        company_id: currentCompanyId,
        name,
        version: {
          priority,
          conditions_json,
          actions_json,
          allow_auto_confirm: allowAutoConfirm
        }
      });
      message.success('规则已创建');
      setModalOpen(false);
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '创建失败');
    } finally {
      setCreating(false);
    }
  };

  const handleToggleStatus = async (id: string, next: 'active' | 'inactive') => {
    try {
      await setRuleStatus(id, next);
      message.success(next === 'active' ? '已启用' : '已停用');
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteRule(id);
      message.success('已删除');
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败');
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
    {
      title: '状态',
      key: 'status',
      width: 80,
      render: (_, r) => (
        <Switch
          size="small"
          checked={r.status === 'active'}
          onChange={(checked) => handleToggleStatus(r.id, checked ? 'active' : 'inactive')}
        />
      )
    },
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
    },
    {
      title: '操作',
      key: 'actions',
      width: 130,
      fixed: 'right',
      render: (_, r) => (
        <Space>
          <Button
            size="small"
            type="link"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/bank-journal/templates/rule/${r.id}`);
            }}
          >
            详情
          </Button>
          <Popconfirm
            title="确定删除该规则？"
            description="被转换批次引用的规则无法删除。"
            okText="删除"
            okButtonProps={{ danger: true }}
            cancelText="取消"
            onConfirm={(e) => {
              e?.stopPropagation();
              handleDelete(r.id);
            }}
            onCancel={(e) => e?.stopPropagation()}
          >
            <Button size="small" type="link" danger onClick={(e) => e.stopPropagation()}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ];

  return (
    <div>
      <div className="toolbar" style={{ marginBottom: 16 }}>
        <h2 className="section-title">规则</h2>
        <div className="toolbar-spacer" />
        {!currentCompanyId && (
          <Typography.Text type="secondary" style={{ marginRight: 8, fontSize: 12 }}>
            请先在右上角选择公司
          </Typography.Text>
        )}
        <Tooltip title={!canManage ? '权限不足' : undefined}>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            disabled={!canManage || !currentCompanyId}
            onClick={openCreate}
          >
            新建
          </Button>
        </Tooltip>
      </div>
      <Table<Rule>
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={loading}
        pagination={false}
        onRow={(record) => ({
          onClick: () => navigate(`/bank-journal/templates/rule/${record.id}`),
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
        destroyOnHidden
        width={680}
      >
        <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', gap: 16 }}>
            <div style={{ flex: 1 }}>
              <Typography.Text strong>规则名称</Typography.Text>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="如：货款自动入账" style={{ marginTop: 4 }} />
            </div>
            <div style={{ width: 140 }}>
              <Typography.Text strong>优先级（越小越先）</Typography.Text>
              <InputNumber min={0} value={priority} onChange={(v) => setPriority(v ?? 0)} style={{ width: '100%', marginTop: 4 }} />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Switch checked={allowAutoConfirm} onChange={setAllowAutoConfirm} />
            <Typography.Text>命中后允许自动确认（否则进入人工确认）</Typography.Text>
          </div>
          <RuleEditor value={ruleData} onChange={setRuleData} />
        </div>
      </Modal>
    </div>
  );
}
