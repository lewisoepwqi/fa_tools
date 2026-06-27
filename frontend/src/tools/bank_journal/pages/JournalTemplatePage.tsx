import { PlusOutlined } from '@ant-design/icons';
import { Button, Input, Modal, Select, Table, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createJournalTemplate, listJournalTemplates } from '../api/journalTemplates';
import {
  JournalColumnsEditor,
  columnsFromBackend,
  columnsToBackend,
  type JournalColumn
} from '../components/JournalColumnsEditor';
import { StatusTag } from '../components/StatusTag';
import { VersionBadge } from '../components/VersionBadge';
import { FILE_TYPE_OPTIONS } from '../constants';
import type { JournalTemplate } from '../types/templates';

const ACTOR = 'user-1';

export function JournalTemplatePage() {
  const [rows, setRows] = useState<JournalTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [fileType, setFileType] = useState('xlsx');
  const [sheetName, setSheetName] = useState('日记账');
  const [columns, setColumns] = useState<JournalColumn[]>(
    columnsFromBackend(['日期', '摘要', '科目', '金额'], ['日期', '科目', '金额'])
  );

  const load = () => {
    setLoading(true);
    listJournalTemplates()
      .then(setRows)
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    let active = true;
    setLoading(true);
    listJournalTemplates()
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

  const openCreate = () => {
    setName('');
    setFileType('xlsx');
    setSheetName('日记账');
    setColumns(columnsFromBackend(['日期', '摘要', '科目', '金额'], ['日期', '科目', '金额']));
    setModalOpen(true);
  };

  const handleCreate = async () => {
    if (!name.trim()) {
      message.error('请输入模板名称');
      return;
    }
    setCreating(true);
    try {
      const { columns_json, required_columns_json } = columnsToBackend(columns);
      await createJournalTemplate({
        company_id: 'company-1',
        name,
        version: {
          file_type: fileType,
          sheet_name: sheetName,
          columns_json,
          required_columns_json,
          created_by: ACTOR
        }
      });
      message.success('模板已创建');
      setModalOpen(false);
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '创建失败');
    } finally {
      setCreating(false);
    }
  };

  const columnsDef: ColumnsType<JournalTemplate> = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    {
      title: '输出列',
      key: 'columns',
      render: (_, r) => {
        const cols = (r.latest_version.columns_json as string[]) ?? [];
        return <Typography.Text>{cols.join('、') || '-'}</Typography.Text>;
      }
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
        <h2 className="section-title">日记账模板</h2>
        <div className="toolbar-spacer" />
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新建
        </Button>
      </div>
      <Table<JournalTemplate>
        rowKey="id"
        columns={columnsDef}
        dataSource={rows}
        loading={loading}
        pagination={false}
        onRow={(record) => ({
          onClick: () => navigate(`/bank-journal/templates/journal/${record.id}`),
          style: { cursor: 'pointer' }
        })}
      />

      <Modal
        open={modalOpen}
        title="新建日记账模板"
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
            <Typography.Text strong>模板名称</Typography.Text>
            <Input style={{ marginTop: 4 }} value={name} onChange={(e) => setName(e.target.value)} placeholder="如：标准日记账模板" />
          </div>
          <div style={{ display: 'flex', gap: 16 }}>
            <div style={{ flex: 1 }}>
              <Typography.Text strong>文件类型</Typography.Text>
              <Select
                style={{ width: '100%', marginTop: 4 }}
                value={fileType}
                onChange={setFileType}
                options={FILE_TYPE_OPTIONS}
              />
            </div>
            <div style={{ flex: 1 }}>
              <Typography.Text strong>工作表名</Typography.Text>
              <Input style={{ marginTop: 4 }} value={sheetName} onChange={(e) => setSheetName(e.target.value)} placeholder="如：日记账" />
            </div>
          </div>
          <div>
            <Typography.Text strong>输出列配置</Typography.Text>
            <div style={{ marginTop: 4 }}>
              <JournalColumnsEditor value={columns} onChange={setColumns} />
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
