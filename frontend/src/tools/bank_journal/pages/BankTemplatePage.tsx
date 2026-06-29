import { PlusOutlined } from '@ant-design/icons';
import { Button, Modal, Popconfirm, Space, Switch, Table, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../auth/useAuth';
import { message } from '../../../components/antdApp';
import {
  createBankTemplate,
  deleteBankTemplate,
  listBankTemplates,
  setBankTemplateStatus
} from '../api/bankTemplates';
import { BankTemplateWizard } from '../components/BankTemplateWizard';
import type { BankTemplateWizardValues } from '../components/BankTemplateWizard';
import { VersionBadge } from '../components/VersionBadge';
import type { BankTemplate } from '../types/templates';

export function BankTemplatePage() {
  const { currentCompanyId, hasPermission } = useAuth();
  const canManage = hasPermission('template_manage');
  const [rows, setRows] = useState<BankTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    listBankTemplates()
      .then(setRows)
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    let active = true;
    setLoading(true);
    listBankTemplates()
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

  const handleSubmit = async (values: BankTemplateWizardValues) => {
    setCreating(true);
    try {
      await createBankTemplate({
        company_id: currentCompanyId,
        name: values.name,
        bank_name: values.bank_name ?? null,
        version: {
          file_type: values.detect.file_type,
          sheet_selector_json: values.detect.sheet_name ? { sheet_name: values.detect.sheet_name } : null,
          header_row_index: values.detect.header_row_index,
          data_start_row_index: values.detect.data_start_row_index,
          field_aliases_json: values.detect.field_aliases,
          amount_mode: values.detect.amount_mode,
          amount_config_json: values.detect.amount_config,
          date_formats_json: values.detect.date_formats,
          sample_file_id: values.sample_file_id ?? null
        }
      });
      message.success('模板已创建');
      setWizardOpen(false);
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '创建失败');
    } finally {
      setCreating(false);
    }
  };

  const handleToggleStatus = async (id: string, next: 'active' | 'inactive') => {
    try {
      await setBankTemplateStatus(id, next);
      message.success(next === 'active' ? '已启用' : '已停用');
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteBankTemplate(id);
      message.success('已删除');
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败');
    }
  };

  const columns: ColumnsType<BankTemplate> = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    {
      title: '银行名称',
      dataIndex: 'bank_name',
      key: 'bank_name',
      render: (v) => v ?? '-'
    },
    {
      title: '银行账号',
      dataIndex: 'bank_account_id',
      key: 'bank_account_id',
      render: (v) => v ?? '-'
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
              navigate(`/bank-journal/templates/bank/${r.id}`);
            }}
          >
            详情
          </Button>
          <Popconfirm
            title="确定删除该银行模板？"
            description="被转换批次引用的模板无法删除。"
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
        <h2 className="section-title">银行流水模板</h2>
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
            onClick={() => setWizardOpen(true)}
          >
            新建
          </Button>
        </Tooltip>
      </div>
      <Table<BankTemplate>
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={loading}
        pagination={false}
        onRow={(record) => ({
          onClick: () => navigate(`/bank-journal/templates/bank/${record.id}`),
          style: { cursor: 'pointer' }
        })}
      />

      <Modal
        open={wizardOpen}
        title="新建银行流水模板"
        footer={null}
        onCancel={() => setWizardOpen(false)}
        destroyOnHidden
        width={680}
      >
        <div style={{ marginTop: 16 }}>
          <BankTemplateWizard
            onSubmit={handleSubmit}
            onCancel={() => setWizardOpen(false)}
            submitting={creating}
          />
        </div>
      </Modal>
    </div>
  );
}
