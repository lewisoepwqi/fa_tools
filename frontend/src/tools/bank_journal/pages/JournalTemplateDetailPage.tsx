import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons';
import {
  Button,
  Card,
  Descriptions,
  Input,
  Modal,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  message
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  createJournalTemplateVersion,
  getJournalTemplate,
  listJournalTemplateVersions,
  setJournalTemplateStatus
} from '../api/journalTemplates';
import {
  JournalColumnsEditor,
  columnsFromBackend,
  columnsToBackend,
  type JournalColumn
} from '../components/JournalColumnsEditor';
import { FILE_TYPE_LABEL, FILE_TYPE_OPTIONS } from '../constants';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';
import type { JournalTemplate, JournalTemplateVersion } from '../types/templates';

const ACTOR = 'user-1';

export function JournalTemplateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<JournalTemplate | null>(null);
  const [versions, setVersions] = useState<JournalTemplateVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  // 编辑态
  const [editFileType, setEditFileType] = useState('xlsx');
  const [editSheetName, setEditSheetName] = useState('');
  const [editColumns, setEditColumns] = useState<JournalColumn[]>([]);

  const load = (templateId: string) => {
    setLoading(true);
    Promise.all([getJournalTemplate(templateId), listJournalTemplateVersions(templateId)])
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
    setEditFileType(v.file_type);
    setEditSheetName(v.sheet_name ?? '');
    setEditColumns(columnsFromBackend(v.columns_json, v.required_columns_json));
    setEditOpen(true);
  };

  const handleEdit = async () => {
    if (!id) return;
    setEditing(true);
    try {
      const { columns_json, required_columns_json } = columnsToBackend(editColumns);
      await createJournalTemplateVersion(id, {
        file_type: editFileType,
        sheet_name: editSheetName,
        columns_json,
        required_columns_json,
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
          <Descriptions.Item label="公司">{data.company_id}</Descriptions.Item>
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
        </Descriptions>
      </Card>
      <Card className="work-card" title={`输出列 · v${v.version_no}`}>
        <Space wrap size={[8, 8]}>
          {cols.length > 0 ? (
            cols.map((col) => (
              <Tag key={col} color={requiredSet.has(col) ? 'orange' : 'default'}>
                {col}
                {requiredSet.has(col) ? '（必填）' : ''}
              </Tag>
            ))
          ) : (
            <Typography.Text type="secondary">未配置列</Typography.Text>
          )}
        </Space>
      </Card>

      <Modal
        open={editOpen}
        title="编辑日记账模板（创建新版本）"
        okText="创建新版本"
        cancelText="取消"
        confirmLoading={editing}
        onOk={handleEdit}
        onCancel={() => setEditOpen(false)}
        destroyOnClose
        width={680}
      >
        <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
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
              <Input style={{ marginTop: 4 }} value={editSheetName} onChange={(e) => setEditSheetName(e.target.value)} />
            </div>
          </div>
          <div>
            <Typography.Text strong>输出列配置</Typography.Text>
            <div style={{ marginTop: 4 }}>
              <JournalColumnsEditor value={editColumns} onChange={setEditColumns} />
            </div>
          </div>
        </div>
      </Modal>

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
