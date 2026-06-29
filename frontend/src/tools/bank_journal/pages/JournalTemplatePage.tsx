import { PlusOutlined } from '@ant-design/icons';
import { Button, Input, Modal, Popconfirm, Select, Space, Switch, Table, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../auth/useAuth';
import { message } from '../../../components/antdApp';
import {
  createJournalTemplate,
  deleteJournalTemplate,
  listJournalTemplates,
  setJournalTemplateStatus
} from '../api/journalTemplates';
import {
  JournalColumnsEditor,
  columnsFromBackend,
  columnsToBackend,
  type JournalColumn
} from '../components/JournalColumnsEditor';
import { VersionBadge } from '../components/VersionBadge';
import { FILE_TYPE_OPTIONS } from '../constants';
import type { JournalTemplate } from '../types/templates';

export function JournalTemplatePage() {
  const { currentCompanyId, hasPermission } = useAuth();
  const canManage = hasPermission('template_manage');
  const [items, setItems] = useState<JournalTemplate[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
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
    listJournalTemplates({
      limit: pageSize,
      offset: (page - 1) * pageSize,
      company_id: currentCompanyId ?? undefined
    })
      .then((p) => { setItems(p.items ?? []); setTotal(p.total ?? 0); })
      .catch(() => { setItems([]); setTotal(0); })
      .finally(() => setLoading(false));
  };

  // 切换公司时重置页码，避免旧 offset 查新公司导致空表
  useEffect(() => { setPage(1); }, [currentCompanyId]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    listJournalTemplates({
      limit: pageSize,
      offset: (page - 1) * pageSize,
      company_id: currentCompanyId ?? undefined
    })
      .then((p) => {
        if (active) { setItems(p.items ?? []); setTotal(p.total ?? 0); }
      })
      .catch(() => {
        if (active) setItems([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [page, pageSize, currentCompanyId]);

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
    if (!currentCompanyId) {
      message.error('请先在右上角选择公司');
      return;
    }
    setCreating(true);
    try {
      const { columns_json, required_columns_json } = columnsToBackend(columns);
      await createJournalTemplate({
        company_id: currentCompanyId,
        name,
        version: {
          file_type: fileType,
          sheet_name: sheetName,
          columns_json,
          required_columns_json
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

  const handleToggleStatus = async (id: string, next: 'active' | 'inactive') => {
    try {
      await setJournalTemplateStatus(id, next);
      message.success(next === 'active' ? '已启用' : '已停用');
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteJournalTemplate(id);
      message.success('已删除');
      load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败');
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
              navigate(`/bank-journal/templates/journal/${r.id}`);
            }}
          >
            详情
          </Button>
          <Popconfirm
            title="确定删除该日记账模板？"
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
        <h2 className="section-title">日记账模板</h2>
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
            onClick={openCreate}
          >
            新建
          </Button>
        </Tooltip>
      </div>
      <Table<JournalTemplate>
        rowKey="id"
        columns={columnsDef}
        dataSource={items}
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); }
        }}
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
        destroyOnHidden
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
