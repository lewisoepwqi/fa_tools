import { ArrowLeftOutlined, EditOutlined, InboxOutlined } from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Input,
  Modal,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
  Upload
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { UploadProps } from 'antd';
import type { RcFile } from 'antd/es/upload';
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../../../auth/useAuth';
import { uploadBankStatement } from '../../../api/files';
import { message } from '../../../components/antdApp';
import {
  createJournalTemplateVersion,
  detectJournalTemplate,
  getJournalTemplate,
  listJournalTemplateVersions,
  setJournalTemplateStatus
} from '../api/journalTemplates';
import { listMappingProfiles } from '../api/mappingProfiles';
import {
  JournalColumnsEditor,
  columnsFromBackend,
  columnsToBackend,
  type JournalColumn
} from '../components/JournalColumnsEditor';
import { FILE_TYPE_LABEL, FILE_TYPE_OPTIONS, rowIndexOf } from '../constants';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';
import type { JournalTemplate, JournalTemplateVersion } from '../types/templates';
import type { MappingProfile } from '../types/mapping';

export function JournalTemplateDetailPage() {
  const { hasPermission, currentCompanyId } = useAuth();
  const canManage = hasPermission('template_manage');
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<JournalTemplate | null>(null);
  const [versions, setVersions] = useState<JournalTemplateVersion[]>([]);
  const [referencedBy, setReferencedBy] = useState<MappingProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [detecting, setDetecting] = useState(false);

  // 编辑态
  const [editFileType, setEditFileType] = useState('xlsx');
  const [editSheetName, setEditSheetName] = useState('');
  const [editHeaderRow, setEditHeaderRow] = useState<number | null>(null);
  const [editDataStartRow, setEditDataStartRow] = useState<number | null>(null);
  const [editSampleFileId, setEditSampleFileId] = useState<string | undefined>(undefined);
  const [editColumns, setEditColumns] = useState<JournalColumn[]>([]);

  const load = (templateId: string) => {
    setLoading(true);
    Promise.all([
      getJournalTemplate(templateId),
      listJournalTemplateVersions(templateId),
      listMappingProfiles({ company_journal_template_id: templateId, limit: 500 })
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
    const v = data.latest_version;
    setEditFileType(v.file_type);
    setEditSheetName(v.sheet_name ?? '');
    setEditHeaderRow(v.header_row_index ?? null);
    setEditDataStartRow(v.data_start_row_index ?? null);
    setEditSampleFileId(v.sample_file_id ?? undefined);
    setEditColumns(columnsFromBackend(v.columns_json, v.required_columns_json));
    setEditOpen(true);
  };

  /** 编辑态：上传新样本识别列名（回填列编辑器 + 表头/数据行位置）。 */
  const handleDetectFromSample = async (file: RcFile) => {
    if (!currentCompanyId) {
      message.error('请先在右上角选择公司');
      return false;
    }
    setDetecting(true);
    try {
      const uploaded = await uploadBankStatement(file, currentCompanyId);
      const result = await detectJournalTemplate(uploaded.id);
      setEditFileType(result.file_type);
      setEditSheetName(result.sheet_name);
      setEditHeaderRow(result.header_row_index);
      setEditDataStartRow(result.data_start_row_index);
      setEditSampleFileId(uploaded.id);
      setEditColumns(columnsFromBackend(result.columns, result.required_columns));
      message.success('已从样本识别列名，请核对');
    } catch (err) {
      message.error(err instanceof Error ? err.message : '识别失败');
    } finally {
      setDetecting(false);
    }
    return false;
  };

  const detectUploadProps: UploadProps = {
    accept: '.csv,.xlsx',
    multiple: false,
    showUploadList: false,
    beforeUpload: (file) => {
      void handleDetectFromSample(file as RcFile);
      return false;
    }
  };

  const handleEdit = async () => {
    if (!id) return;
    setEditing(true);
    try {
      const { columns_json, required_columns_json } = columnsToBackend(editColumns);
      await createJournalTemplateVersion(id, {
        file_type: editFileType,
        sheet_name: editSheetName || undefined,
        header_row_index: editHeaderRow ?? undefined,
        data_start_row_index: editDataStartRow ?? undefined,
        columns_json,
        required_columns_json,
        sample_file_id: editSampleFileId ?? undefined
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
      await setJournalTemplateStatus(id, next);
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
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/bank-journal/templates/journal')}>
            返回
          </Button>
        </div>
      </Card>
    );
  }

  const v = data.latest_version;
  const cols = (v.columns_json as string[]) ?? [];
  const requiredSet = new Set(((v.required_columns_json as string[]) ?? []).map(String));
  const formatRules = (v.format_rules_json as Record<string, unknown> | null) ?? null;
  const formatRuleEntries = formatRules ? Object.entries(formatRules) : [];

  const versionColumns: ColumnsType<JournalTemplateVersion> = [
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
      title: '输出列',
      key: 'columns',
      render: (_, r) => {
        const c = (r.columns_json as string[]) ?? [];
        return <Typography.Text style={{ fontSize: 12 }}>{c.join('、') || '-'}</Typography.Text>;
      }
    }
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card className="work-card">
        <div className="toolbar" style={{ marginBottom: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/bank-journal/templates/journal')}>
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
          <Descriptions.Item label="公司">{data.company_name ?? data.company_id}</Descriptions.Item>
          <Descriptions.Item label="文件类型">
            {FILE_TYPE_LABEL[v.file_type] ?? v.file_type}
          </Descriptions.Item>
          <Descriptions.Item label="工作表名">{v.sheet_name ?? '-'}</Descriptions.Item>
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
              <Button type="primary" loading={editing} onClick={handleEdit}>
                保存（创建新版本）
              </Button>
              <Button onClick={() => setEditOpen(false)}>取消</Button>
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
        {editOpen ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Alert type="warning" showIcon message="修改将创建新版本，旧版本保留用于历史追溯。" />
            {/* 从样本识别：上传日记账样本，自动回填列名与表头位置（替代逐个手敲列名）。 */}
            <Upload.Dragger {...detectUploadProps} disabled={detecting} style={{ padding: 8 }}>
              {detecting ? (
                <Spin tip="正在识别...">
                  <div style={{ padding: 12 }} />
                </Spin>
              ) : (
                <>
                  <p className="ant-upload-drag-icon" style={{ marginBottom: 4 }}>
                    <InboxOutlined />
                  </p>
                  <p className="ant-upload-text" style={{ fontSize: 13 }}>
                    上传日记账样本，自动识别列名
                  </p>
                  <p className="ant-upload-hint" style={{ fontSize: 12 }}>
                    支持 .xlsx / .csv（可选，不传则手动编辑列名）
                  </p>
                </>
              )}
            </Upload.Dragger>
            <div style={{ display: 'flex', gap: 16 }}>
              <div style={{ flex: 1 }}>
                <Typography.Text strong>文件类型</Typography.Text>
                <Select
                  style={{ width: '100%', marginTop: 4 }}
                  value={editFileType}
                  onChange={setEditFileType}
                  options={FILE_TYPE_OPTIONS}
                />
              </div>
              <div style={{ flex: 1 }}>
                <Typography.Text strong>工作表名</Typography.Text>
                <Input
                  style={{ marginTop: 4 }}
                  value={editSheetName}
                  onChange={(e) => setEditSheetName(e.target.value)}
                />
              </div>
            </div>
            <div>
              <Typography.Text strong>输出列配置</Typography.Text>
              <div style={{ marginTop: 4 }}>
                <JournalColumnsEditor value={editColumns} onChange={setEditColumns} />
              </div>
            </div>
          </Space>
        ) : (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label="文件类型">
                {FILE_TYPE_LABEL[v.file_type] ?? v.file_type}
              </Descriptions.Item>
              <Descriptions.Item label="工作表名">{v.sheet_name ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="表头位置">
                {rowIndexOf(v.header_row_index)}
              </Descriptions.Item>
              <Descriptions.Item label="数据起始位置">
                {rowIndexOf(v.data_start_row_index)}
              </Descriptions.Item>
            </Descriptions>

            {/* 输出列：从 Descriptions 抽出，用表格逐行展示（序号 | 列名 | 是否必填）。 */}
            <Typography.Text strong>输出列（{cols.length} 个）</Typography.Text>
            {cols.length > 0 ? (
              <Table
                rowKey={(row) => row.name}
                dataSource={cols.map((name) => ({ name, required: requiredSet.has(name) }))}
                pagination={false}
                size="small"
                columns={[
                  {
                    title: '#',
                    key: 'index',
                    width: 50,
                    render: (_v, _r, i) => i + 1
                  },
                  { title: '列名', dataIndex: 'name', key: 'name' },
                  {
                    title: '是否必填',
                    dataIndex: 'required',
                    key: 'required',
                    width: 100,
                    render: (required: boolean) =>
                      required ? <Tag color="orange">必填</Tag> : <Typography.Text type="secondary">否</Typography.Text>
                  }
                ]}
              />
            ) : (
              <Typography.Text type="secondary">未配置列</Typography.Text>
            )}
            {formatRuleEntries.length > 0 && (
              <Descriptions size="small" column={1} bordered title="列格式化规则">
                {formatRuleEntries.map(([col, rule]) => (
                  <Descriptions.Item key={col} label={col}>
                    <Typography.Text code>{String(rule)}</Typography.Text>
                  </Descriptions.Item>
                ))}
              </Descriptions>
            )}
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label="样本文件">
                {v.sample_file_id ? (
                  <Typography.Text>{v.sample_file_name ?? v.sample_file_id}</Typography.Text>
                ) : (
                  <Typography.Text type="secondary">无</Typography.Text>
                )}
              </Descriptions.Item>
            </Descriptions>
          </Space>
        )}
      </Card>

      <Card className="work-card" title="被引用情况">
        {referencedBy.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无映射方案引用此日记账模板"
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
        <Table<JournalTemplateVersion>
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
