import { PlusOutlined } from '@ant-design/icons';
import { Button, Input, Modal, Select, Table, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listBankTemplates } from '../api/bankTemplates';
import { listJournalTemplates } from '../api/journalTemplates';
import { createMappingProfile, listMappingProfiles } from '../api/mappingProfiles';
import {
  MappingEditor,
  mappingToBackend,
  type MappingEntry
} from '../components/MappingEditor';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';
import type { BankTemplate, JournalTemplate } from '../types/templates';
import type { MappingProfile } from '../types/mapping';

const ACTOR = 'user-1';

export function MappingProfilePage() {
  const [rows, setRows] = useState<MappingProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const navigate = useNavigate();

  // 模板下拉选项
  const [bankTemplates, setBankTemplates] = useState<BankTemplate[]>([]);
  const [journalTemplates, setJournalTemplates] = useState<JournalTemplate[]>([]);
  // 表单态
  const [name, setName] = useState('');
  const [bankTemplateId, setBankTemplateId] = useState<string | undefined>();
  const [journalTemplateId, setJournalTemplateId] = useState<string | undefined>();
  const [journalColumns, setJournalColumns] = useState<string[]>([]);
  const [mappings, setMappings] = useState<MappingEntry[]>([]);

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

  // 打开弹窗时加载可选模板
  const openCreate = async () => {
    setName('');
    setBankTemplateId(undefined);
    setJournalTemplateId(undefined);
    setJournalColumns([]);
    setMappings([]);
    setModalOpen(true);
    try {
      const [banks, journals] = await Promise.all([listBankTemplates(), listJournalTemplates()]);
      setBankTemplates(banks);
      setJournalTemplates(journals);
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

  const handleCreate = async () => {
    if (!name.trim()) {
      message.error('请输入方案名称');
      return;
    }
    setCreating(true);
    try {
      await createMappingProfile({
        company_id: 'company-1',
        name,
        bank_template_id: bankTemplateId ?? null,
        company_journal_template_id: journalTemplateId ?? null,
        version: {
          mappings_json: mappingToBackend(mappings),
          created_by: ACTOR
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
    { title: '状态', dataIndex: 'status', key: 'status', render: (_, r) => <StatusTag status={r.status} /> },
    {
      title: '最新版本',
      key: 'latest_version',
      render: (_, r) => <VersionBadge version={r.latest_version.version_no} />
    }
  ];

  return (
    <div>
      <div className="toolbar" style={{ marginBottom: 16 }}>
        <h2 className="section-title">映射方案</h2>
        <div className="toolbar-spacer" />
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
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
        destroyOnClose
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
              <Typography.Text strong>银行流水模板</Typography.Text>
              <Select
                style={{ width: '100%', marginTop: 4 }}
                placeholder="选择银行模板（可选）"
                allowClear
                value={bankTemplateId}
                onChange={setBankTemplateId}
                options={bankTemplates.map((t) => ({ value: t.id, label: t.name }))}
              />
            </div>
            <div style={{ flex: 1 }}>
              <Typography.Text strong>日记账模板</Typography.Text>
              <Select
                style={{ width: '100%', marginTop: 4 }}
                placeholder="选择日记账模板（可选）"
                allowClear
                value={journalTemplateId}
                onChange={handleSelectJournal}
                options={journalTemplates.map((t) => ({ value: t.id, label: t.name }))}
              />
            </div>
          </div>
          <MappingEditor
            value={mappings}
            onChange={setMappings}
            targetOptions={journalColumns.length > 0 ? journalColumns : undefined}
          />
        </div>
      </Modal>
    </div>
  );
}
