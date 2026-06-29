import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useAuth } from '../../../auth/useAuth';
import { message } from '../../../components/antdApp';
import {
  createCustomField,
  deleteBuiltinOverride,
  deleteCustomField,
  listCustomFields,
  upsertBuiltinOverride,
  updateCustomField,
  type CustomField,
  type StandardFieldDef
} from '../api/customFields';
import { getStandardSchema } from '../api/customFields';
import { StatusTag } from '../components/StatusTag';

const DATA_TYPE_LABEL: Record<string, string> = { text: '文本', amount: '金额', date: '日期', enum: '枚举' };
const DATA_TYPE_COLOR: Record<string, string> = {
  text: 'blue',
  amount: 'gold',
  date: 'green',
  enum: 'purple'
};

interface ExtFormState {
  field_key: string;
  name: string;
  data_type: 'text' | 'amount' | 'date';
  header_keywords: string[];
}

const EMPTY_EXT_FORM: ExtFormState = {
  field_key: '',
  name: '',
  data_type: 'text',
  header_keywords: []
};

interface BuiltinFormState {
  field_key: string;
  label: string;
  type: 'text' | 'amount' | 'date' | 'enum';
  header_keywords: string[];
}

export function CustomFieldPage() {
  const { currentCompanyId, hasPermission } = useAuth();
  const canManage = hasPermission('template_manage');
  const companyId = currentCompanyId ?? '';

  // 扩展字段
  const [extData, setExtData] = useState<CustomField[]>([]);
  const [loading, setLoading] = useState(true);
  const [extModalOpen, setExtModalOpen] = useState(false);
  const [editingExt, setEditingExt] = useState<CustomField | null>(null);
  const [extSaving, setExtSaving] = useState(false);
  const [extForm, setExtForm] = useState<ExtFormState>(EMPTY_EXT_FORM);
  const [extKwInput, setExtKwInput] = useState('');

  // 内置字段（来自 standard-schema）
  const [standardFields, setStandardFields] = useState<StandardFieldDef[]>([]);
  const [builtinModalOpen, setBuiltinModalOpen] = useState(false);
  const [builtinForm, setBuiltinForm] = useState<BuiltinFormState | null>(null);
  const [builtinKwInput, setBuiltinKwInput] = useState('');
  const [builtinSaving, setBuiltinSaving] = useState(false);

  const load = () => {
    setLoading(true);
    Promise.all([listCustomFields(companyId), getStandardSchema(companyId)])
      .then(([ext, schema]) => {
        setExtData(ext);
        setStandardFields(schema.fields);
      })
      .catch(() => {
        setExtData([]);
        setStandardFields([]);
      })
      .finally(() => setLoading(false));
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [companyId]);

  // ============ 内置字段覆盖 ============
  const openBuiltinEdit = (f: StandardFieldDef) => {
    setBuiltinForm({
      field_key: f.key,
      label: f.label,
      type: f.type,
      header_keywords: f.keywords.filter((k) => k !== '')
    });
    setBuiltinKwInput(f.keywords.join('，'));
    setBuiltinModalOpen(true);
  };

  const commitBuiltinKw = (raw: string) => {
    setBuiltinKwInput(raw);
    const kws = raw
      .split(/[，,\n]/)
      .map((s) => s.trim())
      .filter(Boolean);
    setBuiltinForm((f) => (f ? { ...f, header_keywords: kws } : f));
  };

  const handleBuiltinSave = async () => {
    if (!builtinForm) return;
    setBuiltinSaving(true);
    try {
      await upsertBuiltinOverride({
        company_id: companyId,
        field_key: builtinForm.field_key,
        label_override: builtinForm.label.trim() || null,
        header_keywords_override: builtinForm.header_keywords.length
          ? builtinForm.header_keywords
          : null,
        type_override: builtinForm.type
      });
      message.success('已保存');
      setBuiltinModalOpen(false);
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败');
    } finally {
      setBuiltinSaving(false);
    }
  };

  const handleRestoreBuiltin = async (fieldKey: string) => {
    try {
      await deleteBuiltinOverride(fieldKey, companyId);
      message.success('已恢复默认');
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '恢复失败');
    }
  };

  // ============ 扩展字段 CRUD ============
  const openExtCreate = () => {
    setEditingExt(null);
    setExtForm(EMPTY_EXT_FORM);
    setExtKwInput('');
    setExtModalOpen(true);
  };

  const openExtEdit = (record: CustomField) => {
    setEditingExt(record);
    setExtForm({
      field_key: record.field_key,
      name: record.name,
      data_type: record.data_type,
      header_keywords: record.header_keywords
    });
    setExtKwInput(record.header_keywords.join('，'));
    setExtModalOpen(true);
  };

  const commitExtKw = (raw: string) => {
    setExtKwInput(raw);
    const kws = raw
      .split(/[，,\n]/)
      .map((s) => s.trim())
      .filter(Boolean);
    setExtForm((f) => ({ ...f, header_keywords: kws }));
  };

  const handleExtSave = async () => {
    if (!extForm.field_key.trim() || !extForm.name.trim()) {
      message.error('请填写字段标识和名称');
      return;
    }
    if (extForm.header_keywords.length === 0) {
      message.error('至少需要一个识别关键词');
      return;
    }
    if (!/^[a-z][a-z0-9_]{0,62}$/.test(extForm.field_key.trim())) {
      message.error('字段标识需为蛇形（小写字母/数字/下划线，字母开头）');
      return;
    }
    setExtSaving(true);
    try {
      if (editingExt) {
        await updateCustomField(editingExt.id, {
          name: extForm.name.trim(),
          header_keywords: extForm.header_keywords
        });
        message.success('已保存');
      } else {
        await createCustomField({
          company_id: companyId,
          field_key: extForm.field_key.trim(),
          name: extForm.name.trim(),
          data_type: extForm.data_type,
          header_keywords: extForm.header_keywords
        });
        message.success('已创建');
      }
      setExtModalOpen(false);
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败');
    } finally {
      setExtSaving(false);
    }
  };

  const handleExtDelete = async (id: string) => {
    try {
      await deleteCustomField(id);
      message.success('已删除');
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败');
    }
  };

  const builtinFields = standardFields.filter((f) => f.builtin);
  const usedByType = (t: string) => extData.filter((d) => d.data_type === t).length;
  const QUOTA = { text: 8, amount: 4, date: 2 };

  // ============ 内置字段列 ============
  const builtinColumns: ColumnsType<StandardFieldDef> = [
    {
      title: '显示名称',
      dataIndex: 'label',
      key: 'label',
      width: 140,
      render: (v: string, r) => (
        <Space size={4}>
          <span>{v}</span>
          {r.overridden && <Tag color="orange">已自定义</Tag>}
        </Space>
      )
    },
    {
      title: '字段标识',
      dataIndex: 'key',
      key: 'key',
      width: 170,
      render: (v: string) => (
        <Tooltip title="字段标识是系统内部契约，不可修改">
          <code style={{ color: '#999' }}>{v}</code>
        </Tooltip>
      )
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 80,
      render: (v: string) => <Tag color={DATA_TYPE_COLOR[v]}>{DATA_TYPE_LABEL[v]}</Tag>
    },
    {
      title: '识别关键词',
      dataIndex: 'keywords',
      key: 'keywords',
      render: (v: string[]) =>
        v?.length ? (
          <Space wrap size={[4, 4]}>
            {v.map((k) => (
              <Tag key={k}>{k}</Tag>
            ))}
          </Space>
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        )
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_, r) => (
        <Space>
          <Button size="small" onClick={() => openBuiltinEdit(r)}>
            {r.overridden ? '编辑' : '自定义'}
          </Button>
          {r.overridden && (
            <Popconfirm
              title="恢复为系统默认？"
              onConfirm={() => handleRestoreBuiltin(r.key)}
            >
              <Button size="small" type="link" icon={<ReloadOutlined />}>
                恢复默认
              </Button>
            </Popconfirm>
          )}
        </Space>
      )
    }
  ];

  // ============ 扩展字段列 ============
  const extColumns: ColumnsType<CustomField> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 160 },
    {
      title: '字段标识',
      dataIndex: 'field_key',
      key: 'field_key',
      width: 160,
      render: (v: string) => <code>{v}</code>
    },
    {
      title: '类型',
      dataIndex: 'data_type',
      key: 'data_type',
      width: 90,
      render: (v: string) => <Tag color={DATA_TYPE_COLOR[v]}>{DATA_TYPE_LABEL[v]}</Tag>
    },
    {
      title: '识别关键词',
      dataIndex: 'header_keywords',
      key: 'header_keywords',
      render: (v: string[]) =>
        v?.length ? (
          <Space wrap size={[4, 4]}>
            {v.map((k) => (
              <Tag key={k}>{k}</Tag>
            ))}
          </Space>
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        )
    },
    {
      title: '槽位',
      dataIndex: 'slot_key',
      key: 'slot_key',
      width: 120,
      render: (v: string) => <code>{v}</code>
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (v: string) => <StatusTag status={v} />
    },
    {
      title: '操作',
      key: 'actions',
      width: 140,
      render: (_, r) => (
        <Space>
          <Button size="small" onClick={() => openExtEdit(r)}>
            编辑
          </Button>
          <Popconfirm
            title="删除该扩展字段？"
            description="被规则/映射引用时会被拦截。删除后字段标识不可复用。"
            onConfirm={() => handleExtDelete(r.id)}
          >
            <Button size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ];

  return (
    <div>
      <Typography.Title level={5}>标准字段</Typography.Title>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        管理系统用于解析银行流水、构建规则和映射的标准字段。内置字段可自定义名称/关键词/类型（公司级），扩展字段可增删。
      </Typography.Text>

      {/* 内置字段区 */}
      <Card
        className="work-card"
        size="small"
        title="内置标准字段"
        extra={<Typography.Text type="secondary" style={{ fontSize: 12 }}>字段标识不可改</Typography.Text>}
        style={{ marginTop: 16, marginBottom: 16 }}
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="内置字段是系统内置的标准字段，可自定义显示名称、识别关键词、规则类型"
          description={
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12 }}>
              <li>显示名称：仅影响界面展示，不影响实际解析</li>
              <li>识别关键词：上传流水时按这些词识别表头列（与系统默认合并，不会丢失默认词）</li>
              <li>
                类型：仅影响规则条件的操作符过滤，不影响该字段的实际解析方式（解析由字段标识决定，不可改）
              </li>
            </ul>
          }
        />
        <Table<StandardFieldDef>
          rowKey="key"
          loading={loading}
          dataSource={builtinFields}
          columns={builtinColumns}
          pagination={false}
          size="small"
        />
      </Card>

      {/* 扩展字段区 */}
      <Card
        className="work-card"
        size="small"
        title="扩展字段"
        extra={
          <Space>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              槽位配额：文本 {usedByType('text')}/{QUOTA.text}、金额 {usedByType('amount')}/
              {QUOTA.amount}、日期 {usedByType('date')}/{QUOTA.date}
            </Typography.Text>
            <Tooltip title={!canManage ? '权限不足' : !currentCompanyId ? '请先在右上角选择公司' : undefined}>
              <Button
                type="primary"
                size="small"
                icon={<PlusOutlined />}
                disabled={!canManage || !currentCompanyId}
                onClick={openExtCreate}
              >
                新建扩展字段
              </Button>
            </Tooltip>
          </Space>
        }
      >
        <Table<CustomField>
          rowKey="id"
          dataSource={extData}
          columns={extColumns}
          pagination={false}
          size="small"
        />
      </Card>

      {/* 内置字段覆盖编辑 Modal */}
      <Modal
        open={builtinModalOpen}
        title={`自定义内置字段：${builtinForm?.field_key ?? ''}`}
        okText="保存"
        cancelText="取消"
        confirmLoading={builtinSaving}
        onOk={handleBuiltinSave}
        onCancel={() => setBuiltinModalOpen(false)}
        destroyOnHidden
        width={560}
      >
        {builtinForm && (
          <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <Typography.Text strong>显示名称</Typography.Text>
              <Input
                style={{ marginTop: 4 }}
                value={builtinForm.label}
                onChange={(e) => setBuiltinForm((f) => (f ? { ...f, label: e.target.value } : f))}
                placeholder="如：业务日期"
              />
            </div>
            <div>
              <Typography.Text strong>类型</Typography.Text>
              <Typography.Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
                仅影响规则操作符过滤，不影响实际解析
              </Typography.Text>
              <Select
                style={{ width: '100%', marginTop: 4 }}
                value={builtinForm.type}
                onChange={(v) =>
                  setBuiltinForm((f) => (f ? { ...f, type: v } : f))
                }
                options={[
                  { value: 'text', label: '文本' },
                  { value: 'amount', label: '金额' },
                  { value: 'date', label: '日期' },
                  { value: 'enum', label: '枚举' }
                ]}
              />
            </div>
            <div>
              <Typography.Text strong>识别关键词</Typography.Text>
              <Typography.Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
                与系统默认词合并，用逗号分隔
              </Typography.Text>
              <Input
                style={{ marginTop: 4 }}
                value={builtinKwInput}
                onChange={(e) => commitBuiltinKw(e.target.value)}
                placeholder="如：业务日期，记账日"
              />
            </div>
          </div>
        )}
      </Modal>

      {/* 扩展字段编辑 Modal */}
      <Modal
        open={extModalOpen}
        title={editingExt ? '编辑扩展字段' : '新建扩展字段'}
        okText="保存"
        cancelText="取消"
        confirmLoading={extSaving}
        onOk={handleExtSave}
        onCancel={() => setExtModalOpen(false)}
        destroyOnHidden
        width={560}
      >
        <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Alert
            type="info"
            showIcon
            message="扩展字段用于补充系统内置标准字段没有的业务列"
            description="创建后，该字段会出现在「字段映射」「规则」的字段下拉中；上传含其关键词列头的流水时会被自动识别。"
          />
          <div>
            <Typography.Text strong>名称 *</Typography.Text>
            <Input
              style={{ marginTop: 4 }}
              value={extForm.name}
              onChange={(e) => setExtForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="如：成本中心"
            />
          </div>
          <div>
            <Typography.Text strong>字段标识 *</Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
              蛇形小写，创建后不可改、不可复用
            </Typography.Text>
            <Input
              style={{ marginTop: 4 }}
              value={extForm.field_key}
              disabled={!!editingExt}
              onChange={(e) => setExtForm((f) => ({ ...f, field_key: e.target.value }))}
              placeholder="如：cost_center"
            />
          </div>
          <div>
            <Typography.Text strong>数据类型 *</Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
              决定槽位类型，创建后不可改
            </Typography.Text>
            <Select
              style={{ width: '100%', marginTop: 4 }}
              disabled={!!editingExt}
              value={extForm.data_type}
              onChange={(v) => setExtForm((f) => ({ ...f, data_type: v }))}
              options={[
                { value: 'text', label: '文本（如成本中心、项目代号）' },
                { value: 'amount', label: '金额' },
                { value: 'date', label: '日期' }
              ]}
            />
          </div>
          <div>
            <Typography.Text strong>识别关键词 *</Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
              流水表头包含这些词时自动识别为该字段，用逗号分隔
            </Typography.Text>
            <Input
              style={{ marginTop: 4 }}
              value={extKwInput}
              onChange={(e) => commitExtKw(e.target.value)}
              placeholder="如：成本中心，部门"
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}
