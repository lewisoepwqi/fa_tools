import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons';
import {
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  Modal,
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
  createMappingProfileVersion,
  getMappingProfile,
  listMappingProfileVersions,
  setMappingProfileStatus
} from '../api/mappingProfiles';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';
import type { MappingProfile, MappingProfileVersion } from '../types/mapping';

const ACTOR = 'user-1';

function pretty(value: unknown): string {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

export function MappingProfileDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<MappingProfile | null>(null);
  const [versions, setVersions] = useState<MappingProfileVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [form] = Form.useForm();

  const load = (profileId: string) => {
    setLoading(true);
    Promise.all([getMappingProfile(profileId), listMappingProfileVersions(profileId)])
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
      const patch: Partial<MappingProfileVersion> = { created_by: ACTOR };
      if (values.mappings_json) patch.mappings_json = JSON.parse(values.mappings_json);
      await createMappingProfileVersion(id, patch);
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
      await setMappingProfileStatus(id, next);
      message.success(next === 'active' ? '已启用' : '已停用');
      load(id);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败');
    }
  };

  const openEdit = () => {
    if (!data) return;
    form.setFieldsValue({
      mappings_json: data.latest_version.mappings_json
        ? JSON.stringify(data.latest_version.mappings_json)
        : ''
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
        <Typography.Text type="secondary">未找到该映射方案。</Typography.Text>
        <div style={{ marginTop: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/bank-journal/templates/mapping')}>
            返回
          </Button>
        </div>
      </Card>
    );
  }

  const v = data.latest_version;
  const versionColumns: ColumnsType<MappingProfileVersion> = [
    {
      title: '版本',
      key: 'version_no',
      render: (_, r) => <VersionBadge version={r.version_no} />
    },
    {
      title: '映射配置',
      key: 'mappings_json',
      render: (_, r) => (
        <pre style={{ margin: 0, maxHeight: 60, overflow: 'auto' }}>
          {pretty(r.mappings_json)}
        </pre>
      )
    }
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card className="work-card">
        <Space style={{ marginBottom: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/bank-journal/templates/mapping')}>
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
          <Descriptions.Item label="方案ID">{data.id}</Descriptions.Item>
          <Descriptions.Item label="公司">{data.company_id}</Descriptions.Item>
          <Descriptions.Item label="银行流水模板">{data.bank_template_id ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="日记账模板">{data.company_journal_template_id ?? '-'}</Descriptions.Item>
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
          <Descriptions.Item label="银行模板版本ID">{v.bank_template_version_id ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="日记账模板版本ID">
            {v.company_journal_template_version_id ?? '-'}
          </Descriptions.Item>
          <Descriptions.Item label="映射配置">
            <pre style={{ margin: 0 }}>{pretty(v.mappings_json)}</pre>
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
          <Form.Item
            name="mappings_json"
            label="映射配置（JSON）"
            extra='例：{"日期": "transaction_date", "摘要": "summary"}'
          >
            <Input.TextArea rows={4} />
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
        <Table<MappingProfileVersion>
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
