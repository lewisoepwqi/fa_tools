import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons';
import { Alert, Button, Card, Descriptions, Empty, Modal, Space, Spin, Table, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../../../auth/useAuth';
import { message } from '../../../components/antdApp';
import {
  createBankTemplateVersion,
  getBankTemplate,
  listBankTemplateVersions,
  setBankTemplateStatus
} from '../api/bankTemplates';
import { listMappingProfiles } from '../api/mappingProfiles';
import { AMOUNT_MODE_LABEL, FILE_TYPE_LABEL, rowIndexOf } from '../constants';
import { DetectResultView, type BankTemplateConfigView } from '../components/DetectResultView';
import { useStandardFields } from '../components/useStandardFields';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';
import type { BankTemplate, BankTemplateVersion } from '../types/templates';
import type { MappingProfile } from '../types/mapping';

/**
 * 把后端版本对象（字段带 _json 后缀）适配成 DetectResultView 期望的 config
 * （无后缀）。detect API 返回的就是无后缀形态，故 DetectResultView 同时服务
 * detect 结果与版本详情，但版本对象的字段名带 _json，需在此映射。
 */
function versionToConfigView(v: BankTemplateVersion): BankTemplateConfigView {
  return {
    file_type: v.file_type,
    sheet_name:
      (v.sheet_selector_json as { sheet_name?: string } | null)?.sheet_name ?? '',
    header_row_index: v.header_row_index,
    data_start_row_index: v.data_start_row_index,
    field_aliases: (v.field_aliases_json ?? {}) as Record<string, string>,
    amount_mode: v.amount_mode,
    amount_config: (v.amount_config_json ?? {}) as Record<string, string>,
    date_formats: (v.date_formats_json ?? []) as string[],
    unique_key_config: v.unique_key_config_json,
    sample_file_id: v.sample_file_id,
    sample_file_name: v.sample_file_name
  };
}

export function BankTemplateDetailPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission('template_manage');
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const standardFields = useStandardFields();
  const [data, setData] = useState<BankTemplate | null>(null);
  const [versions, setVersions] = useState<BankTemplateVersion[]>([]);
  const [referencedBy, setReferencedBy] = useState<MappingProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  // 编辑态：回填当前版本配置，DetectResultView 可编辑模式直接修改 field_aliases。
  const [editDetect, setEditDetect] = useState<BankTemplateConfigView | null>(null);

  const load = (templateId: string) => {
    setLoading(true);
    Promise.all([
      getBankTemplate(templateId),
      listBankTemplateVersions(templateId),
      listMappingProfiles({ bank_template_id: templateId, limit: 500 })
    ])
      .then(([d, vs, refs]) => {
        setData(d);
        setVersions(vs);
        setReferencedBy(refs.items);
      })
      .catch(() => {
        setData(null);
        setVersions([]);
        setReferencedBy([]);
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
    setEditDetect(versionToConfigView(data.latest_version));
    setEditOpen(true);
  };

  const handleEditSubmit = async () => {
    if (!id || !editDetect) return;
    setEditing(true);
    try {
      await createBankTemplateVersion(id, {
        file_type: editDetect.file_type,
        sheet_selector_json: editDetect.sheet_name ? { sheet_name: editDetect.sheet_name } : null,
        header_row_index: editDetect.header_row_index,
        data_start_row_index: editDetect.data_start_row_index,
        field_aliases_json: editDetect.field_aliases as Record<string, string>,
        amount_mode: editDetect.amount_mode,
        amount_config_json: editDetect.amount_config as Record<string, string>,
        date_formats_json: editDetect.date_formats as string[],
        sample_file_id: data?.latest_version.sample_file_id ?? null
      });
      message.success('已创建新版本');
      setEditOpen(false);
      setEditDetect(null);
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
          <Button onClick={() => setHistoryOpen(true)}>版本历史</Button>
          <Tooltip title={!canManage ? '权限不足' : undefined}>
            <Button onClick={handleToggleStatus} disabled={!canManage}>
              {data.status === 'active' ? '停用' : '启用'}
            </Button>
          </Tooltip>
        </div>
        <Descriptions size="small" column={2} bordered>
          <Descriptions.Item label="公司">{data.company_name ?? data.company_id ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="银行名称">{data.bank_name ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="银行账号">{data.bank_account_id ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <StatusTag status={data.status} />
          </Descriptions.Item>
          <Descriptions.Item label="最新版本">
            <VersionBadge version={v.version_no} />
          </Descriptions.Item>
          <Descriptions.Item label="版本创建者">{v.created_by_name ?? v.created_by ?? '-'}</Descriptions.Item>
        </Descriptions>
      </Card>
      <Card
        className="work-card"
        title={`配置详情 · v${v.version_no}`}
        extra={
          editOpen ? (
            <Space>
              <Button type="primary" loading={editing} onClick={handleEditSubmit}>
                保存（创建新版本）
              </Button>
              <Button onClick={() => { setEditOpen(false); setEditDetect(null); }}>
                取消
              </Button>
            </Space>
          ) : (
            <Tooltip title={!canManage ? '权限不足' : undefined}>
              <Button icon={<EditOutlined />} onClick={openEdit} disabled={!canManage}>
                编辑
              </Button>
            </Tooltip>
          )
        }
      >
        {editOpen && editDetect ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Alert type="warning" showIcon message="修改将创建新版本，旧版本保留用于历史追溯。" />
            <DetectResultView
              config={editDetect}
              onFieldAliasesChange={(next) =>
                setEditDetect((prev) => (prev ? { ...prev, field_aliases: next } : prev))
              }
              standardFieldOptions={standardFields.options}
            />
          </Space>
        ) : (
          <DetectResultView
            config={versionToConfigView(v)}
            standardFieldOptions={standardFields.options}
          />
        )}
      </Card>

      <Card className="work-card" title="被引用情况">
        {referencedBy.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无映射方案引用此银行模板"
          >
            <Button type="primary" onClick={() => navigate('/bank-journal/templates/mapping')}>
              去新建映射方案
            </Button>
          </Empty>
        ) : (
          <Table<MappingProfile>
            rowKey="id"
            dataSource={referencedBy}
            pagination={false}
            size="small"
            onRow={(record) => ({
              onClick: () => navigate(`/bank-journal/templates/mapping/${record.id}`),
              style: { cursor: 'pointer' }
            })}
            columns={[
              { title: '映射方案名称', dataIndex: 'name', key: 'name' },
              {
                title: '最新版本',
                key: 'latest_version',
                render: (_, r) => <VersionBadge version={r.latest_version.version_no} />
              },
              {
                title: '状态',
                key: 'status',
                width: 80,
                render: (_, r) => <StatusTag status={r.status} />
              }
            ]}
          />
        )}
      </Card>

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
