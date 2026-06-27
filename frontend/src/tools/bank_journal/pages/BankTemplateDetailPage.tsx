import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons';
import { Button, Card, Descriptions, Modal, Space, Spin, Table, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  createBankTemplateVersion,
  getBankTemplate,
  listBankTemplateVersions,
  setBankTemplateStatus
} from '../api/bankTemplates';
import { AMOUNT_MODE_LABEL, FILE_TYPE_LABEL, rowIndexOf } from '../constants';
import { BankTemplateWizard } from '../components/BankTemplateWizard';
import type { BankTemplateWizardValues } from '../components/BankTemplateWizard';
import { DetectResultView } from '../components/DetectResultView';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';
import type { BankTemplate, BankTemplateVersion } from '../types/templates';

const ACTOR = 'user-1';

export function BankTemplateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<BankTemplate | null>(null);
  const [versions, setVersions] = useState<BankTemplateVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  const load = (templateId: string) => {
    setLoading(true);
    Promise.all([getBankTemplate(templateId), listBankTemplateVersions(templateId)])
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
    setEditOpen(true);
  };

  const handleEditSubmit = async (values: BankTemplateWizardValues) => {
    if (!id) return;
    setEditing(true);
    try {
      await createBankTemplateVersion(id, {
        file_type: values.detect.file_type,
        sheet_selector_json: values.detect.sheet_name ? { sheet_name: values.detect.sheet_name } : null,
        header_row_index: values.detect.header_row_index,
        data_start_row_index: values.detect.data_start_row_index,
        field_aliases_json: values.detect.field_aliases,
        amount_mode: values.detect.amount_mode,
        amount_config_json: values.detect.amount_config,
        date_formats_json: values.detect.date_formats,
        sample_file_id: values.sample_file_id ?? null,
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
      await setBankTemplateStatus(id, next);
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
        <Typography.Text type="secondary">未找到该模板。</Typography.Text>
        <div style={{ marginTop: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/bank-journal/templates/bank')}>
            返回
          </Button>
        </div>
      </Card>
    );
  }

  const v = data.latest_version;

  const versionColumns: ColumnsType<BankTemplateVersion> = [
    {
      title: '版本',
      key: 'version_no',
      render: (_, r) => <VersionBadge version={r.version_no} />
    },
    {
      title: '文件类型',
      key: 'file_type',
      render: (_, r) => FILE_TYPE_LABEL[r.file_type] ?? r.file_type
    },
    {
      title: '金额格式',
      key: 'amount_mode',
      render: (_, r) => AMOUNT_MODE_LABEL[r.amount_mode] ?? r.amount_mode
    },
    {
      title: '表头位置',
      key: 'header_row_index',
      render: (_, r) => rowIndexOf(r.header_row_index)
    },
    {
      title: '字段映射数',
      key: 'field_aliases',
      render: (_, r) => Object.keys(r.field_aliases_json ?? {}).length
    }
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card className="work-card">
        <div className="toolbar" style={{ marginBottom: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/bank-journal/templates/bank')}>
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
          <Descriptions.Item label="模板ID">{data.id}</Descriptions.Item>
          <Descriptions.Item label="公司">{data.company_id ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="银行名称">{data.bank_name ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="银行账号">{data.bank_account_id ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <StatusTag status={data.status} />
          </Descriptions.Item>
          <Descriptions.Item label="最新版本">
            <VersionBadge version={v.version_no} />
          </Descriptions.Item>
        </Descriptions>
      </Card>
      <Card className="work-card" title={`配置详情 · v${v.version_no}`}>
        <DetectResultView config={v} />
      </Card>

      {/* 编辑（创建新版本）：用向导，回填当前版本配置作为起点 */}
      <Modal
        open={editOpen}
        title="编辑模板（创建新版本）"
        footer={null}
        onCancel={() => setEditOpen(false)}
        destroyOnClose
        width={680}
      >
        <div style={{ marginTop: 16 }}>
          <BankTemplateWizard
            onSubmit={handleEditSubmit}
            onCancel={() => setEditOpen(false)}
            submitting={editing}
            skipUpload
            initialValues={{
              name: data.name,
              bank_name: data.bank_name ?? undefined,
              detect: {
                file_type: v.file_type,
                sheet_name: (v.sheet_selector_json as { sheet_name?: string } | null)?.sheet_name ?? '',
                header_row_index: v.header_row_index ?? 0,
                data_start_row_index: v.data_start_row_index ?? 1,
                field_aliases: (v.field_aliases_json ?? {}) as Record<string, string>,
                amount_mode: v.amount_mode,
                amount_config: (v.amount_config_json ?? {}) as Record<string, string>,
                date_formats: (v.date_formats_json ?? []) as string[]
              },
              sample_file_id: v.sample_file_id ?? undefined
            }}
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
        <Table<BankTemplateVersion>
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
