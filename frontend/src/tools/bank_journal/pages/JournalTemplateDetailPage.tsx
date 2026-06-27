import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons';
import {
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Spin,
  Table,
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
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';
import type { JournalTemplate, JournalTemplateVersion } from '../types/templates';

const ACTOR = 'user-1';

function pretty(value: unknown): string {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

export function JournalTemplateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<JournalTemplate | null>(null);
  const [versions, setVersions] = useState<JournalTemplateVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [form] = Form.useForm();

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

  const handleEdit = async () => {
    if (!id || !data) return;
    const values = await form.validateFields();
    setEditing(true);
    try {
      const patch: Partial<JournalTemplateVersion> & { file_type: string } = {
        file_type: values.file_type,
        sheet_name: values.sheet_name,
        created_by: ACTOR
      };
      if (values.columns_json) patch.columns_json = JSON.parse(values.columns_json);
      if (values.required_columns_json)
        patch.required_columns_json = JSON.parse(values.required_columns_json);
      await createJournalTemplateVersion(id, patch);
      message.success('已创建新版本');
      setEditOpen(false);
      load(id);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '创建失败（检查 JSON）');
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

  const openEdit = () => {
    if (!data) return;
    const v = data.latest_version;
    form.setFieldsValue({
      file_type: v.file_type,
      sheet_name: v.sheet_name,
      columns_json: v.columns_json ? JSON.stringify(v.columns_json) : '',
      required_columns_json: v.required_columns_json ? JSON.stringify(v.required_columns_json) : ''
    });
    setEditOpen(true);
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
  const versionColumns: ColumnsType<JournalTemplateVersion> = [
    {
      title: '版本',
      key: 'version_no',
      render: (_, r) => <VersionBadge version={r.version_no} />
    },
    { title: '文件类型', dataIndex: 'file_type', key: 'file_type' },
    {
      title: '列定义',
      key: 'columns_json',
      render: (_, r) => (
        <pre style={{ margin: 0, maxHeight: 60, overflow: 'auto' }}>
          {pretty(r.columns_json)}
        </pre>
      )
    }
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card className="work-card">
        <Space style={{ marginBottom: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/bank-journal/templates/journal')}>
            返回
          </Button>
          <Typography.Title level={4} style={{ margin: 0 }}>
            {data.name}
          </Typography.Title>
          <Button icon={<EditOutlined />} onClick={openEdit}>
            编辑（新版本）
          </Button>
          <Button onClick={() => setHistoryOpen(true)}>版本历史</Button>
          <Button onClick={handleToggleStatus}>
            {data.status === 'active' ? '停用' : '启用'}
          </Button>
        </Space>
        <Descriptions size="small" column={2} bordered>
          <Descriptions.Item label="模板ID">{data.id}</Descriptions.Item>
          <Descriptions.Item label="公司">{data.company_id}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <StatusTag status={data.status} />
          </Descriptions.Item>
          <Descriptions.Item label="最新版本">
            <VersionBadge version={v.version_no} />
          </Descriptions.Item>
        </Descriptions>
      </Card>
      <Card className="work-card" title={`版本配置 · v${v.version_no}`}>
        <Descriptions size="small" column={1} bordered>
          <Descriptions.Item label="文件类型">{v.file_type}</Descriptions.Item>
          <Descriptions.Item label="工作表名">{v.sheet_name ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="列定义">
            <pre style={{ margin: 0 }}>{pretty(v.columns_json)}</pre>
          </Descriptions.Item>
          <Descriptions.Item label="必填列">
            <pre style={{ margin: 0 }}>{pretty(v.required_columns_json)}</pre>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Modal
        open={editOpen}
        title="编辑（创建新版本）"
        okText="创建新版本"
        cancelText="取消"
        confirmLoading={editing}
        onOk={handleEdit}
        onCancel={() => setEditOpen(false)}
        destroyOnClose
        width={520}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="file_type" label="文件类型" rules={[{ required: true }]}>
            <Select options={[{ value: 'csv', label: 'CSV' }, { value: 'xlsx', label: 'XLSX' }]} />
          </Form.Item>
          <Form.Item name="sheet_name" label="Sheet 名">
            <Input />
          </Form.Item>
          <Form.Item name="columns_json" label="列定义（JSON 数组）" extra='例：["日期","摘要","科目","金额"]'>
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="required_columns_json" label="必填列（JSON 数组）" extra='例：["日期","科目"]'>
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
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
