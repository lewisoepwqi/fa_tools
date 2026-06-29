import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons';
import {
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  Modal,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../../../auth/useAuth';
import { message } from '../../../components/antdApp';
import { getConversionRun } from '../api/conversionRuns';
import { createExport, downloadExport } from '../api/exports';
import { adjustPreviewRow, confirmPreviewRow } from '../api/previewRows';
import { ExceptionTag } from '../components/ExceptionTag';
import { StatusTag } from '../components/StatusTag';
import type { ConversionRunResponse, PreviewRow } from '../types/conversion';

const JOURNAL_COLUMNS = ['日期', '摘要', '科目', '金额'];

function renderValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '-';
  }
  return String(value);
}

/**
 * 批次详情。
 * - 独立路由页：根据 URL :runId 自取数据。
 * - 上传页转换完成后内联展示：传入 run prop 跳过拉取。
 * 支持：按状态/异常筛选、单行编辑、单行确认、批量确认、导出。
 */
export function ConversionRunDetailPage({ run: runProp }: { run?: ConversionRunResponse }) {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const canProcess = hasPermission('conversion_process');
  const canConfirm = hasPermission('conversion_confirm');
  const canExport = hasPermission('export_run');
  const [run, setRun] = useState<ConversionRunResponse | null>(runProp ?? null);
  const [loading, setLoading] = useState(!runProp && !!runId);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [exceptionFilter, setExceptionFilter] = useState<string | undefined>(undefined);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [acting, setActing] = useState(false);
  const [editingRow, setEditingRow] = useState<PreviewRow | null>(null);
  const [editForm] = Form.useForm();

  const reload = (id: string) => {
    setLoading(true);
    getConversionRun(id)
      .then((data) => setRun(data))
      .catch(() => setRun(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (runProp) {
      setRun(runProp);
      return;
    }
    if (!runId) return;
    reload(runId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, runProp]);

  const stats = useMemo(() => {
    if (!run) return { total: 0, auto: 0, needs: 0, conflict: 0, parseFailed: 0 };
    const rows = run.preview_rows;
    return {
      total: rows.length,
      auto: rows.filter((r) => r.status === 'auto_confirmed').length,
      needs: rows.filter((r) => r.status === 'needs_confirmation').length,
      conflict: rows.filter((r) => r.status === 'conflict').length,
      parseFailed: rows.filter((r) => r.status === 'parse_failed').length
    };
  }, [run]);

  // 收集本批次出现过的异常码，用于筛选下拉
  const exceptionOptions = useMemo(() => {
    if (!run) return [];
    const codes = new Set<string>();
    run.preview_rows.forEach((r) => r.exception_codes.forEach((c) => codes.add(c)));
    return Array.from(codes);
  }, [run]);

  const filteredRows = useMemo(() => {
    if (!run) return [];
    return run.preview_rows.filter((r) => {
      if (statusFilter && r.status !== statusFilter) return false;
      if (exceptionFilter && !r.exception_codes.includes(exceptionFilter)) return false;
      return true;
    });
  }, [run, statusFilter, exceptionFilter]);

  const patchRowLocally = (rowId: string, patch: Partial<PreviewRow>) => {
    setRun((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        preview_rows: prev.preview_rows.map((r) =>
          r.id === rowId ? { ...r, ...patch } : r
        )
      };
    });
  };

  const handleConfirmOne = async (row: PreviewRow) => {
    if (!row.id) return;
    setActing(true);
    try {
      const result = await confirmPreviewRow(row.id);
      patchRowLocally(row.id, { status: result.status });
      message.success('已确认');
    } catch (err) {
      message.error(err instanceof Error ? err.message : '确认失败');
    } finally {
      setActing(false);
    }
  };

  const handleBatchConfirm = async () => {
    const targets = filteredRows.filter(
      (r) => r.id && selectedRowKeys.includes(r.row_index) && r.status !== 'manually_confirmed'
    );
    if (targets.length === 0) {
      message.warning('未选中可确认的行');
      return;
    }
    setActing(true);
    let ok = 0;
    for (const row of targets) {
      if (!row.id) continue;
      try {
        const result = await confirmPreviewRow(row.id);
        patchRowLocally(row.id, { status: result.status });
        ok += 1;
      } catch {
        /* 继续处理其余行 */
      }
    }
    setActing(false);
    setSelectedRowKeys([]);
    message.success(`已批量确认 ${ok} 行`);
  };

  const openEdit = (row: PreviewRow) => {
    setEditingRow(row);
    editForm.setFieldsValue({
      field_name: '科目',
      new_value: renderValue(row.output_values['科目']),
      reason: ''
    });
  };

  const handleEditSubmit = async () => {
    if (!editingRow?.id) return;
    const values = await editForm.validateFields();
    setActing(true);
    try {
      await adjustPreviewRow(
        editingRow.id,
        values.field_name,
        values.new_value,
        values.reason || null
      );
      patchRowLocally(editingRow.id, {
        output_values: { ...editingRow.output_values, [values.field_name]: values.new_value }
      });
      message.success('已修改');
      setEditingRow(null);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '修改失败');
    } finally {
      setActing(false);
    }
  };

  const handleExport = async (onlyConfirmed: boolean) => {
    if (!run) return;
    setActing(true);
    try {
      const result = await createExport(run.id, {
        file_type: 'xlsx',
        columns: JOURNAL_COLUMNS,
        only_confirmed: onlyConfirmed
      });
      message.success(`已生成导出（${result.row_count} 行）`);
      downloadExport(result.export_id);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '导出失败');
    } finally {
      setActing(false);
    }
  };

  const columns: ColumnsType<PreviewRow> = [
    {
      title: '行号',
      dataIndex: 'row_index',
      key: 'row_index',
      width: 64,
      render: (v) => <span className="num num-right">{renderValue(v)}</span>
    },
    {
      title: '日期',
      key: '日期',
      render: (_, record) => renderValue(record.output_values['日期'])
    },
    {
      title: '摘要',
      key: '摘要',
      render: (_, record) => renderValue(record.output_values['摘要'])
    },
    {
      title: '科目',
      key: '科目',
      render: (_, record) => renderValue(record.output_values['科目'])
    },
    {
      title: '金额',
      key: '金额',
      align: 'right',
      render: (_, record) => (
        <span className="num num-right">{renderValue(record.output_values['金额'])}</span>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: '状态',
      render: (_, record) => <StatusTag status={record.status} />
    },
    {
      title: '异常',
      dataIndex: 'exception_codes',
      key: '异常',
      render: (_, record) =>
        record.exception_codes.length > 0 ? (
          <Space size={4}>
            {record.exception_codes.map((code) => (
              <ExceptionTag key={code} code={code} />
            ))}
          </Space>
        ) : (
          '-'
        )
    },
    {
      title: '操作',
      key: '操作',
      width: 160,
      render: (_, record) => (
        <Space size={4}>
          <Tooltip title={!canProcess ? '权限不足' : undefined}>
            <Button
              size="small"
              icon={<EditOutlined />}
              disabled={!canProcess || !record.id || record.status === 'parse_failed'}
              onClick={() => openEdit(record)}
            />
          </Tooltip>
          <Tooltip title={!canConfirm ? '权限不足' : undefined}>
            <Button
              size="small"
              type="link"
              disabled={!canConfirm || !record.id || record.status === 'manually_confirmed'}
              loading={acting}
              onClick={() => handleConfirmOne(record)}
            >
              确认
            </Button>
          </Tooltip>
        </Space>
      )
    }
  ];

  if (loading) {
    return (
      <Card className="work-card">
        <Spin />
      </Card>
    );
  }

  if (!run) {
    return (
      <Card className="work-card">
        <Typography.Text type="secondary">未找到该批次。</Typography.Text>
        <div style={{ marginTop: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/bank-journal/runs')}>
            返回批次列表
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      {/* 第一段：页头 + 概览 */}
      <Card className="work-card">
        <div className="toolbar" style={{ marginBottom: 16 }}>
          {!runProp && (
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/bank-journal/runs')}>
              返回
            </Button>
          )}
          <h2 className="section-title">批次详情 · {run.id}</h2>
        </div>
        <Descriptions size="small" column={2} bordered>
          <Descriptions.Item label="公司">{run.company_id ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="银行账号">{run.bank_account_id ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="批次状态">
            <StatusTag status={run.status} />
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {run.created_at ? new Date(run.created_at).toLocaleString() : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="银行模板版本" span={2}>
            {run.bank_template_version_id ?? '内联配置（未绑定模板）'}
          </Descriptions.Item>
          <Descriptions.Item label="日记账模板版本">
            {run.company_journal_template_version_id ?? '-'}
          </Descriptions.Item>
          <Descriptions.Item label="映射方案版本">
            {run.mapping_profile_version_id ?? '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 第二段：统计数字卡片（关键数据点睛） */}
      <Row gutter={16}>
        <Col span={6}>
          <Card className="work-card">
            <div className="stat-value num">{stats.total}</div>
            <div className="stat-label">总行数</div>
          </Card>
        </Col>
        <Col span={6}>
          <Card className="work-card">
            <div className="stat-value num">{stats.auto}</div>
            <div className="stat-label">已自动确认</div>
          </Card>
        </Col>
        <Col span={6}>
          <Card className="work-card">
            <div className="stat-value num is-accent">{stats.needs}</div>
            <div className="stat-label">待确认</div>
          </Card>
        </Col>
        <Col span={6}>
          <Card className="work-card">
            <div className="stat-value num">{stats.conflict + stats.parseFailed}</div>
            <div className="stat-label">冲突 / 解析失败</div>
          </Card>
        </Col>
      </Row>

      {/* 第三段：预览工作台 */}
      <Card className="work-card">
        <div className="toolbar" style={{ marginBottom: 16 }}>
          <h3 className="section-title">转换结果 · 共 {run.summary.total_rows} 行</h3>
          <div className="toolbar-spacer" />
          <Select
            allowClear
            placeholder="按状态筛选"
            style={{ width: 150 }}
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: 'needs_confirmation', label: '待确认' },
              { value: 'auto_confirmed', label: '已自动确认' },
              { value: 'manually_confirmed', label: '已人工确认' },
              { value: 'conflict', label: '有冲突' },
              { value: 'parse_failed', label: '解析失败' }
            ]}
          />
          {exceptionOptions.length > 0 && (
            <Select
              allowClear
              placeholder="按异常筛选"
              style={{ width: 210 }}
              value={exceptionFilter}
              onChange={setExceptionFilter}
              options={exceptionOptions.map((c) => ({ value: c, label: c }))}
            />
          )}
          <Tooltip title={!canConfirm ? '权限不足' : undefined}>
            <Button
              disabled={!canConfirm || selectedRowKeys.length === 0}
              loading={acting}
              onClick={handleBatchConfirm}
            >
              批量确认（{selectedRowKeys.length}）
            </Button>
          </Tooltip>
        </div>
        <Table<PreviewRow>
          rowKey="row_index"
          columns={columns}
          dataSource={filteredRows}
          pagination={false}
          scroll={{ x: 'max-content' }}
          rowSelection={{
            selectedRowKeys,
            onChange: setSelectedRowKeys,
            getCheckboxProps: (r) => ({ disabled: !r.id || r.status === 'parse_failed' })
          }}
        />
        <div className="toolbar" style={{ marginTop: 16 }}>
          <div className="toolbar-spacer" />
          <Tooltip title={!canExport ? '权限不足' : undefined}>
            <Button disabled={!canExport} loading={acting} onClick={() => handleExport(true)}>
              仅导出已确认
            </Button>
          </Tooltip>
          <Tooltip title={!canExport ? '权限不足' : undefined}>
            <Button type="primary" disabled={!canExport} loading={acting} onClick={() => handleExport(false)}>
              导出全部
            </Button>
          </Tooltip>
        </div>
        {filteredRows.length === 0 && (
          <div className="empty-teach" style={{ marginTop: 12 }}>
            <strong>当前筛选条件下无数据</strong>
            清除筛选条件以查看全部转换结果
          </div>
        )}
      </Card>

      <Modal
        open={!!editingRow}
        title="人工修改字段"
        okText="保存"
        cancelText="取消"
        confirmLoading={acting}
        onCancel={() => setEditingRow(null)}
        onOk={handleEditSubmit}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="field_name" label="字段" rules={[{ required: true }]}>
            <Select
              options={JOURNAL_COLUMNS.map((c) => ({ value: c, label: c }))}
            />
          </Form.Item>
          <Form.Item name="new_value" label="新值" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="reason" label="修改原因">
            <Input.TextArea rows={2} />
          </Form.Item>
          {editingRow?.status !== 'manually_confirmed' && (
            <Tag color="#cc4f58">提示：修改后该行仍需确认才会变为已确认状态</Tag>
          )}
        </Form>
      </Modal>
    </Space>
  );
}
