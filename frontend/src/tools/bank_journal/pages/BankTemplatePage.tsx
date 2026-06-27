import { PlusOutlined } from '@ant-design/icons';
import { Button, Modal, Table, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createBankTemplate, listBankTemplates } from '../api/bankTemplates';
import { BankTemplateWizard } from '../components/BankTemplateWizard';
import type { BankTemplateWizardValues } from '../components/BankTemplateWizard';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';
import type { BankTemplate } from '../types/templates';

const ACTOR = 'user-1';

export function BankTemplatePage() {
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
        company_id: 'company-1',
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
          sample_file_id: values.sample_file_id ?? null,
          created_by: ACTOR
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
    { title: '状态', dataIndex: 'status', key: 'status', render: (_, r) => <StatusTag status={r.status} /> },
    {
      title: '最新版本',
      key: 'latest_version',
      render: (_, r) => <VersionBadge version={r.latest_version.version_no} />
    }
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          银行流水模板
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setWizardOpen(true)}>
          新建
        </Button>
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
        destroyOnClose
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
