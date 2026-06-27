import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons';
import {
  Button,
  Card,
  Descriptions,
  Form,
  InputNumber,
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
  createBankTemplateVersion,
  getBankTemplate,
  listBankTemplateVersions,
  setBankTemplateStatus
} from '../api/bankTemplates';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';
import type { BankTemplate, BankTemplateVersion } from '../types/templates';

const ACTOR = 'user-1';
const AMOUNT_MODES = [
  { value: 'income_expense_columns', label: '收入/支出双列' },
  { value: 'debit_credit_columns', label: '借方/贷方双列' },
  { value: 'single_amount_with_direction', label: '单金额+方向列' },
  { value: 'signed_amount', label: '带符号金额' }
];

function pretty(value: unknown): string {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

export function BankTemplateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<BankTemplate | null>(null);
  const [versions, setVersions] = useState<BankTemplateVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [form] = Form.useForm();

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

  const handleEdit = async () => {
    if (!id || !data) return;
    const values = await form.validateFields();
    setEditing(true);
    try {
      await createBankTemplateVersion(id, {
        file_type: values.file_type,
        header_row_index: values.header_row_index,
        data_start_row_index: values.data_start_row_index,
        amount_mode: values.amount_mode,
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

  const openEdit = () => {
    if (!data) return;
    const v = data.latest_version;
    form.setFieldsValue({
      file_type: v.file_type,
      header_row_index: v.header_row_index ?? 0,
      data_start_row_index: v.data_start_row_index ?? 1,
      amount_mode: v.amount_mode
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
    { title: '文件类型', dataIndex: 'file_type', key: 'file_type' },
    { title: '金额模式', dataIndex: 'amount_mode', key: 'amount_mode' },
    {
      title: '表头行',
      key: 'header_row_index',
      render: (_, r) => r.header_row_index ?? '-'
    },
    {
      title: '字段别名',
      key: 'field_aliases_json',
      render: (_, r) => (
        <pre style={{ margin: 0, maxHeight: 80, overflow: 'auto' }}>
          {pretty(r.field_aliases_json)}
        </pre>
      )
    }
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card className="work-card">
        <Space style={{ marginBottom: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/bank-journal/templates/bank')}>
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
      <Card className="work-card" title={`版本配置 · v${v.version_no}`}>
        <Descriptions size="small" column={1} bordered>
          <Descriptions.Item label="文件类型">{v.file_type}</Descriptions.Item>
          <Descriptions.Item label="表头行">{v.header_row_index ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="数据起始行">{v.data_start_row_index ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="金额模式">{v.amount_mode}</Descriptions.Item>
          <Descriptions.Item label="字段别名">
            <pre style={{ margin: 0 }}>{pretty(v.field_aliases_json)}</pre>
          </Descriptions.Item>
          <Descriptions.Item label="金额配置">
            <pre style={{ margin: 0 }}>{pretty(v.amount_config_json)}</pre>
          </Descriptions.Item>
          <Descriptions.Item label="日期格式">
            <pre style={{ margin: 0 }}>{pretty(v.date_formats_json)}</pre>
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
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="file_type" label="文件类型" rules={[{ required: true }]}>
            <Select options={[{ value: 'csv', label: 'CSV' }, { value: 'xlsx', label: 'XLSX' }]} />
          </Form.Item>
          <Form.Item name="amount_mode" label="金额模式" rules={[{ required: true }]}>
            <Select options={AMOUNT_MODES} />
          </Form.Item>
          <Form.Item name="header_row_index" label="表头行（0 基）">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="data_start_row_index" label="数据起始行（0 基）">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          编辑会创建新版本（旧版本不可变，历史批次仍引用旧版本）。
        </Typography.Text>
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
