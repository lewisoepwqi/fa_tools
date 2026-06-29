import { HolderOutlined, PlusOutlined } from '@ant-design/icons';
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import type { SyntheticListenerMap } from '@dnd-kit/core/dist/hooks/utilities';
import { SortableContext, arrayMove, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Button, Input, InputNumber, Modal, Popconfirm, Space, Switch, Table, Tag, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../auth/useAuth';
import { message } from '../../../components/antdApp';
import { createRule, deleteRule, listRules, reorderRules, setRuleStatus } from '../api/rules';
import {
  RuleEditor,
  ruleDataToBackend,
  type RuleEditorData
} from '../components/RuleEditor';
import { VersionBadge } from '../components/VersionBadge';
import type { Rule } from '../types/rules';

const EMPTY_RULE: RuleEditorData = { logic: 'all', conditions: [], actions: [] };

// ---- 拖拽手柄 Context（从行传给手柄列）----

interface DragHandleContextValue {
  setActivatorNodeRef?: (el: HTMLElement | null) => void;
  listeners?: SyntheticListenerMap;
  canDrag: boolean;
}

const DragHandleCtx = createContext<DragHandleContextValue>({ canDrag: false });

// ---- 可拖拽的表格行 ----

interface SortableRowProps extends React.HTMLAttributes<HTMLTableRowElement> {
  'data-row-key'?: string;
  canDrag: boolean;
}

function SortableRow({ canDrag, children, ...props }: SortableRowProps) {
  const id = props['data-row-key'] ?? '';
  const {
    setNodeRef,
    setActivatorNodeRef,
    listeners,
    transform,
    transition,
    isDragging,
  } = useSortable({ id, disabled: !canDrag });

  const style: React.CSSProperties = {
    ...props.style,
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const ctxValue = useMemo(
    () => ({ setActivatorNodeRef, listeners, canDrag }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [setActivatorNodeRef, listeners, canDrag]
  );

  return (
    <DragHandleCtx.Provider value={ctxValue}>
      <tr {...props} ref={setNodeRef} style={style}>
        {children}
      </tr>
    </DragHandleCtx.Provider>
  );
}

// ---- 拖拽手柄图标（在手柄列渲染）----

function DragHandle() {
  const { setActivatorNodeRef, listeners, canDrag } = useContext(DragHandleCtx);

  if (!canDrag) {
    return (
      <Tooltip title="权限不足">
        <HolderOutlined style={{ color: '#d9d9d9', cursor: 'not-allowed', fontSize: 16 }} />
      </Tooltip>
    );
  }

  return (
    <span
      ref={setActivatorNodeRef as ((el: HTMLSpanElement | null) => void) | undefined}
      {...listeners}
      onClick={(e) => e.stopPropagation()}
      style={{
        color: '#bfbfbf',
        cursor: 'grab',
        fontSize: 16,
        display: 'inline-flex',
        alignItems: 'center',
        padding: '0 4px',
        userSelect: 'none',
      }}
      title="拖拽调整优先级"
    >
      <HolderOutlined />
    </span>
  );
}

// ---- 主页面 ----

export function RulePage() {
  const { currentCompanyId, hasPermission } = useAuth();
  const canManage = hasPermission('template_manage');
  const [items, setItems] = useState<Rule[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
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
    listRules({
      limit: pageSize,
      offset: (page - 1) * pageSize,
      company_id: currentCompanyId ?? undefined
    })
      .then((p) => { setItems(p.items ?? []); setTotal(p.total ?? 0); })
      .catch(() => { setItems([]); setTotal(0); })
      .finally(() => setLoading(false));
  };

  // 切换公司时重置页码，避免旧 offset 查新公司导致空表
  useEffect(() => { setPage(1); }, [currentCompanyId]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    listRules({
      limit: pageSize,
      offset: (page - 1) * pageSize,
      company_id: currentCompanyId ?? undefined
    })
      .then((p) => {
        if (active) { setItems(p.items ?? []); setTotal(p.total ?? 0); }
      })
      .catch(() => {
        if (active) setItems([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [page, pageSize, currentCompanyId]);

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

  // dnd-kit sensors：需拖动 5px 才激活，防止误触点击
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  const handleDragEnd = async ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;

    const oldIndex = items.findIndex((r) => r.id === active.id);
    const newIndex = items.findIndex((r) => r.id === over.id);
    if (oldIndex === -1 || newIndex === -1) return;

    const snapshot = items; // 快照，失败时用于回滚
    const next = arrayMove(items, oldIndex, newIndex);
    setItems(next); // 乐观更新

    try {
      await reorderRules(next.map((r, i) => ({ rule_id: r.id, priority: i + 1 })));
      message.success('优先级已更新');
    } catch (err) {
      message.error(err instanceof Error ? err.message : '排序保存失败，已还原');
      setItems(snapshot); // 回滚到拖拽前快照
    }
  };

  const columns: ColumnsType<Rule> = [
    {
      title: '',
      key: 'drag',
      width: 40,
      render: () => <DragHandle />,
    },
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

  // antd Table 的自定义行渲染：注入 canManage 到 SortableRow
  const tableComponents = useMemo(() => ({
    body: {
      row: ({ children, ...rowProps }: React.HTMLAttributes<HTMLTableRowElement> & { 'data-row-key'?: string }) => (
        <SortableRow canDrag={canManage} {...rowProps}>
          {children}
        </SortableRow>
      ),
    },
  }), [canManage]);

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

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={items.map((r) => r.id)} strategy={verticalListSortingStrategy}>
          <Table<Rule>
            rowKey="id"
            columns={columns}
            dataSource={items}
            loading={loading}
            components={tableComponents}
            pagination={{
              current: page,
              pageSize,
              total,
              showSizeChanger: true,
              showTotal: (t) => `共 ${t} 条`,
              onChange: (p, ps) => { setPage(p); setPageSize(ps); }
            }}
            onRow={(record) => ({
              onClick: () => navigate(`/bank-journal/templates/rule/${record.id}`),
              style: { cursor: 'pointer' }
            })}
          />
        </SortableContext>
      </DndContext>

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
