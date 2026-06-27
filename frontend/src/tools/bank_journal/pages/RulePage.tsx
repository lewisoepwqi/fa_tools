import { PlusOutlined } from '@ant-design/icons';
import { Button, Input, InputNumber, Modal, Switch, Table, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createRule, listRules } from '../api/rules';
import {
  RuleEditor,
  ruleDataToBackend,
  type RuleEditorData
} from '../components/RuleEditor';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';
import type { Rule } from '../types/rules';

const ACTOR = 'user-1';

const EMPTY_RULE: RuleEditorData = { logic: 'all', conditions: [], actions: [] };

export function RulePage() {
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
    setCreating(true);
    try {
      const { conditions_json, actions_json } = ruleDataToBackend(ruleData);
      await createRule({
        company_id: 'company-1',
        name,
        version: {
          priority,
          conditions_json,
          actions_json,
          allow_auto_confirm: allowAutoConfirm,
          created_by: ACTOR
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
      <div className="toolbar" style={{ marginBottom: 16 }}>
        <h2 className="section-title">规则</h2>
        <div className="toolbar-spacer" />
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
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
        destroyOnClose
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
