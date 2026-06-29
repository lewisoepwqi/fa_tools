import { LinkOutlined, PlusOutlined } from '@ant-design/icons';
import {
  Alert,
  Button,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tooltip,
  Typography
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../auth/useAuth';
import { message } from '../../../components/antdApp';
import { listBankTemplates } from '../api/bankTemplates';
import { createJournalTemplate, listJournalTemplates } from '../api/journalTemplates';
import {
  createMappingProfile,
  deleteMappingProfile,
  listMappingProfiles,
  setMappingProfileStatus
} from '../api/mappingProfiles';
import {
  JournalColumnsEditor,
  columnsFromBackend,
  columnsToBackend,
  type JournalColumn
} from '../components/JournalColumnsEditor';
import {
  MappingEditor,
  mappingToBackend,
  type MappingEntry
} from '../components/MappingEditor';
import { RULE_ACTION_FIELD_OPTIONS } from '../constants';
import { VersionBadge } from '../components/VersionBadge';
import { useStandardFields } from '../components/useStandardFields';
import type { BankTemplate, JournalTemplate } from '../types/templates';
import type { MappingProfile } from '../types/mapping';

export function MappingProfilePage() {
  const { currentCompanyId, hasPermission } = useAuth();
  const canManage = hasPermission('template_manage');
  const [items, setItems] = useState<MappingProfile[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const navigate = useNavigate();
  const standardFields = useStandardFields();

  // 模板下拉选项
  const [bankTemplates, setBankTemplates] = useState<BankTemplate[]>([]);
  const [journalTemplates, setJournalTemplates] = useState<JournalTemplate[]>([]);
  // 表单态
  const [name, setName] = useState('');
  const [bankTemplateId, setBankTemplateId] = useState<string | undefined>();
  const [journalTemplateId, setJournalTemplateId] = useState<string | undefined>();
  const [journalColumns, setJournalColumns] = useState<string[]>([]);
  const [mappings, setMappings] = useState<MappingEntry[]>([]);

  // 就近创建日记账模板：映射方案新建弹窗内直接补建一个简单日记账模板（NN/g 渐进披露）
  const [journalCreateOpen, setJournalCreateOpen] = useState(false);
  const [journalCreating, setJournalCreating] = useState(false);
  const [journalFormName, setJournalFormName] = useState('');
  const [journalFormColumns, setJournalFormColumns] = useState<JournalColumn[]>(
    columnsFromBackend(['日期', '摘要', '科目', '金额'], ['日期', '科目', '金额'])
  );

  const load = () => {
    setLoading(true);
    listMappingProfiles({
      limit: pageSize,
      offset: (page - 1) * pageSize,
      company_id: currentCompanyId ?? undefined
    })
      .then((p) => { setItems(p.items); setTotal(p.total); })
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    let active = true;
    setLoading(true);
    // 同时加载映射方案 + 银行/日记账模板，用于列表中解析模板名（修复首渲染显示 -）
    Promise.all([
      listMappingProfiles({
        limit: pageSize,
        offset: (page - 1) * pageSize,
        company_id: currentCompanyId ?? undefined
      }),
      listBankTemplates({ limit: 500 }),
      listJournalTemplates({ limit: 500 })
    ])
      .then(([data, banks, journals]) => {
        if (!active) return;
        setItems(data.items);
        setTotal(data.total);
        setBankTemplates(banks.items);
        setJournalTemplates(journals.items);
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

  // 打开弹窗时加载可选模板
  const openCreate = async () => {
    setName('');
    setBankTemplateId(undefined);
    setJournalTemplateId(undefined);
    setJournalColumns([]);
    setMappings([]);
    setModalOpen(true);
    try {
      const [banks, journals] = await Promise.all([
        listBankTemplates({ limit: 500 }),
        listJournalTemplates({ limit: 500 })
      ]);
      setBankTemplates(banks.items);
      setJournalTemplates(journals.items);
    } catch {
      // 加载失败不阻塞，允许手动输入列名
    }
  };

  // 选择日记账模板时，加载其输出列作为目标列候选
  const handleSelectJournal = (id: string) => {
    setJournalTemplateId(id);
    const tpl = journalTemplates.find((t) => t.id === id);
    const cols = ((tpl?.latest_version.columns_json as string[]) ?? []).map(String);
    setJournalColumns(cols);
  };

  // 就近创建：在映射新建弹窗里直接补建一个日记账模板，建完自动选中。
  // 银行模板涉及上传识别较重，不内嵌，改用提示跳转。
  const openJournalCreate = () => {
    setJournalFormName('');
    setJournalFormColumns(columnsFromBackend(['日期', '摘要', '科目', '金额'], ['日期', '科目', '金额']));
    setJournalCreateOpen(true);
  };

  const handleJournalCreate = async () => {
    if (!journalFormName.trim()) {
      message.error('请输入日记账模板名称');
      return;
    }
    if (!currentCompanyId) {
      message.error('请先在右上角选择公司');
      return;
    }
    setJournalCreating(true);
    try {
      const { columns_json, required_columns_json } = columnsToBackend(journalFormColumns);
      const created = await createJournalTemplate({
        company_id: currentCompanyId,
        name: journalFormName.trim(),
        version: {
          file_type: 'xlsx',
          columns_json,
          required_columns_json
        }
      });
      setJournalTemplates((prev) => [...prev, created]);
      setJournalTemplateId(created.id);
      setJournalColumns((created.latest_version.columns_json as string[]) ?? []);
      message.success('日记账模板已创建并选中');
      setJournalCreateOpen(false);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '创建失败');
    } finally {
      setJournalCreating(false);
    }
  };

  const handleCreate = async () => {
    if (!name.trim()) {
      message.error('请输入方案名称');
      return;
    }
    if (!currentCompanyId) {
      message.error('请先在右上角选择公司');
      return;
    }
    setCreating(true);
    try {
      await createMappingProfile({
        company_id: currentCompanyId,
        name,
        bank_template_id: bankTemplateId ?? null,
        company_journal_template_id: journalTemplateId ?? null,
        version: {
          mappings_json: mappingToBackend(mappings)
        }
      });
      message.success('映射方案已创建');
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
      await setMappingProfileStatus(id, next);
      message.success(next === 'active' ? '已启用' : '已停用');
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteMappingProfile(id);
      message.success('已删除');
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败');
    }
  };

  const columns: ColumnsType<MappingProfile> = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    {
      title: '银行流水模板',
      key: 'bank_template',
      render: (_, r) => bankTemplates.find((t) => t.id === r.bank_template_id)?.name ?? '-'
    },
    {
      title: '日记账模板',
      key: 'journal_template',
      render: (_, r) => journalTemplates.find((t) => t.id === r.company_journal_template_id)?.name ?? '-'
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
              navigate(`/bank-journal/templates/mapping/${r.id}`);
            }}
          >
            详情
          </Button>
          <Popconfirm
            title="确定删除该映射方案？"
            description="被转换批次引用的方案无法删除。"
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
        <h2 className="section-title">映射方案</h2>
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
      <Table<MappingProfile>
        rowKey="id"
        columns={columns}
        dataSource={items}
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); }
        }}
        onRow={(record) => ({
          onClick: () => navigate(`/bank-journal/templates/mapping/${record.id}`),
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
        destroyOnHidden
        width={680}
      >
        <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <Typography.Text strong>方案名称</Typography.Text>
            <Input
              style={{ marginTop: 4 }}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="如：中行流水 → 标准日记账"
            />
          </div>
          <div style={{ display: 'flex', gap: 16 }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Typography.Text strong>银行流水模板</Typography.Text>
                <Button
                  size="small"
                  type="link"
                  icon={<LinkOutlined />}
                  onClick={() => navigate('/bank-journal/templates/bank')}
                >
                  去新建
                </Button>
              </div>
              <Select
                style={{ width: '100%', marginTop: 4 }}
                placeholder="选择银行模板（可选）"
                allowClear
                value={bankTemplateId}
                onChange={setBankTemplateId}
                options={bankTemplates.map((t) => ({ value: t.id, label: t.name }))}
                notFoundContent="暂无银行模板，可点上方「去新建」"
              />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Typography.Text strong>日记账模板</Typography.Text>
                <Button size="small" type="link" icon={<PlusOutlined />} onClick={openJournalCreate}>
                  就近新建
                </Button>
              </div>
              <Select
                style={{ width: '100%', marginTop: 4 }}
                placeholder="选择日记账模板（可选）"
                allowClear
                value={journalTemplateId}
                onChange={handleSelectJournal}
                options={journalTemplates.map((t) => ({ value: t.id, label: t.name }))}
                notFoundContent="暂无日记账模板，可点上方「就近新建」"
              />
            </div>
          </div>
          {bankTemplates.length === 0 && journalTemplates.length === 0 && (
            <Alert
              type="info"
              showIcon
              message="尚未配置任何模板"
              description="映射方案用来把银行模板字段对应到日记账模板列。建议先在「模板规则」里配好两个模板，再回到这里建映射。"
            />
          )}
          <MappingEditor
            value={mappings}
            onChange={setMappings}
            targetOptions={journalColumns.length > 0 ? journalColumns : undefined}
            ruleOutputOptions={RULE_ACTION_FIELD_OPTIONS}
            standardFieldOptions={standardFields.options}
          />
        </div>
      </Modal>

      {/* 就近创建日记账模板（二级弹窗）：建完自动选中并加载其输出列 */}
      <Modal
        open={journalCreateOpen}
        title="就近新建日记账模板"
        okText="创建并选中"
        cancelText="取消"
        confirmLoading={journalCreating}
        onOk={handleJournalCreate}
        onCancel={() => setJournalCreateOpen(false)}
        destroyOnHidden
        width={680}
      >
        <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <Typography.Text strong>模板名称</Typography.Text>
            <Input
              style={{ marginTop: 4 }}
              value={journalFormName}
              onChange={(e) => setJournalFormName(e.target.value)}
              placeholder="如：标准日记账模板"
            />
          </div>
          <div>
            <Typography.Text strong>输出列配置</Typography.Text>
            <div style={{ marginTop: 4 }}>
              <JournalColumnsEditor value={journalFormColumns} onChange={setJournalFormColumns} />
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
