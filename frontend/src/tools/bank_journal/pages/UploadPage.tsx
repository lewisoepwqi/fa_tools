import { InboxOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { Alert, Button, Card, Select, Space, Table, Tag, Typography, Upload } from 'antd';
import type { UploadFile } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadBankStatement } from '../../../api/files';
import { message } from '../../../components/antdApp';
import { listBankTemplates } from '../api/bankTemplates';
import { createConversionRunFromConfig, dryRunConversion, type DryRunResponse } from '../api/conversionRuns';
import { listJournalTemplates } from '../api/journalTemplates';
import { listMappingProfiles } from '../api/mappingProfiles';
import { listRules } from '../api/rules';
import { ConversionRunDetailPage } from './ConversionRunDetailPage';
import type { BankTemplate } from '../types/templates';
import type { JournalTemplate } from '../types/templates';
import type { MappingProfile } from '../types/mapping';
import type { Rule } from '../types/rules';
import type { ConversionRunResponse } from '../types/conversion';

/**
 * 流水上传 + 配置选择转换页（P0 改造）。
 *
 * 旧实现直接用硬编码参数跑转换，用户在四个配置模块里配的内容完全被无视。
 * 现改为：上传文件 → 选择本次使用的银行模板/日记账模板/映射方案/规则 → 转换，
 * 让配置真正生效。
 */
export function UploadPage() {
  const navigate = useNavigate();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [loading, setLoading] = useState(false);

  // 已上传的源文件 ID（beforeUpload 里逐个上传，转换时用这些 ID）
  const [sourceFileIds, setSourceFileIds] = useState<string[]>([]);

  // 配置选择
  const [bankTemplates, setBankTemplates] = useState<BankTemplate[]>([]);
  const [journalTemplates, setJournalTemplates] = useState<JournalTemplate[]>([]);
  const [mappingProfiles, setMappingProfiles] = useState<MappingProfile[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [bankTemplateId, setBankTemplateId] = useState<string>();
  const [journalTemplateId, setJournalTemplateId] = useState<string>();
  const [mappingProfileId, setMappingProfileId] = useState<string>();
  const [ruleIds, setRuleIds] = useState<string[]>([]);

  const [run, setRun] = useState<ConversionRunResponse | null>(null);
  const [dryRunResult, setDryRunResult] = useState<DryRunResponse | null>(null);
  const [dryRunning, setDryRunning] = useState(false);

  // 加载所有 active 配置供下拉选择
  useEffect(() => {
    let active = true;
    Promise.all([listBankTemplates(), listJournalTemplates(), listMappingProfiles(), listRules()])
      .then(([b, j, m, r]) => {
        if (!active) return;
        // 仅展示启用中的配置（status === 'active'）
        setBankTemplates(b.filter((t) => t.status === 'active'));
        setJournalTemplates(j.filter((t) => t.status === 'active'));
        setMappingProfiles(m.filter((t) => t.status === 'active'));
        setRules(r.filter((t) => t.status === 'active'));
      })
      .catch(() => {
        /* 加载失败时不阻塞上传，下拉为空即可 */
      });
    return () => {
      active = false;
    };
  }, []);

  // 映射方案按已选银行+日记账模板过滤，避免选到不相关的方案
  const filteredMappings = mappingProfiles.filter(
    (m) =>
      (!bankTemplateId || m.bank_template_id === bankTemplateId) &&
      (!journalTemplateId || m.company_journal_template_id === journalTemplateId)
  );

  const handleBeforeUpload = async (file: File) => {
    try {
      const uploaded = await uploadBankStatement(file);
      setSourceFileIds((prev) => [...prev, uploaded.id]);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '上传失败');
    }
    return false; // 阻止 antd 自动上传
  };

  const handleStart = async () => {
    if (sourceFileIds.length === 0) {
      message.error('请先上传流水文件');
      return;
    }
    if (!bankTemplateId || !journalTemplateId) {
      message.error('请选择银行流水模板和日记账模板');
      return;
    }
    setLoading(true);
    try {
      const result = await createConversionRunFromConfig({
        source_file_ids: sourceFileIds,
        bank_template_id: bankTemplateId,
        company_journal_template_id: journalTemplateId,
        mapping_profile_id: mappingProfileId,
        rule_ids: ruleIds
      });
      setRun(result);
      message.success('转换完成');
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败');
    } finally {
      setLoading(false);
    }
  };

  /** P3：试跑——用所选配置解析样本，预览前 N 行但不创建批次。 */
  const handleDryRun = async () => {
    if (sourceFileIds.length === 0 || !bankTemplateId) {
      message.error('请先上传文件并选择银行流水模板');
      return;
    }
    setDryRunning(true);
    try {
      const result = await dryRunConversion({
        source_file_ids: sourceFileIds,
        bank_template_id: bankTemplateId,
        company_journal_template_id: journalTemplateId,
        mapping_profile_id: mappingProfileId,
        rule_ids: ruleIds,
        limit: 10
      });
      setDryRunResult(result);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '试跑失败');
    } finally {
      setDryRunning(false);
    }
  };

  // 银行/日记账模板切换时，重置可能已失效的下游选择
  const onBankTemplateChange = (v: string) => {
    setBankTemplateId(v);
    setMappingProfileId(undefined);
  };
  const onJournalTemplateChange = (v: string) => {
    setJournalTemplateId(v);
    setMappingProfileId(undefined);
  };

  const canStart = sourceFileIds.length > 0 && !!bankTemplateId && !!journalTemplateId;

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card className="work-card">
        <div style={{ marginBottom: 16 }}>
          <h2 className="section-title">流水上传</h2>
        </div>
        <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 20 }}>
          上传银行流水 CSV / XLSX 文件，然后选择本次转换使用的模板与规则，系统将按你的配置
          自动解析并生成公司日记账预览，供你确认与导出。
        </Typography.Paragraph>
        <Upload.Dragger
          multiple
          accept=".csv,.xlsx"
          fileList={fileList}
          beforeUpload={(file) => {
            void handleBeforeUpload(file as File);
            return false;
          }}
          onChange={({ fileList: nextFileList }) => setFileList(nextFileList)}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
          <p className="ant-upload-hint">支持 .csv / .xlsx，可多选</p>
        </Upload.Dragger>

        {/* 配置选择区：上传后引导用户挑选本次使用的版本化配置 */}
        <div style={{ marginTop: 24 }}>
          <Typography.Title level={5}>选择本次转换使用的配置</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 0 }}>
            这些配置来自「模板规则」菜单。若下拉为空，请先去配置好对应模板。
          </Typography.Paragraph>
          {/* 任一必选模板为空时，就近给出快捷入口，避免用户来回切菜单 */}
          {bankTemplates.length === 0 || journalTemplates.length === 0 ? (
            <Alert
              style={{ marginBottom: 12 }}
              type="warning"
              showIcon
              message="部分必要配置尚未创建"
              description={
                <Space size={[8, 4]} wrap>
                  {bankTemplates.length === 0 && (
                    <Button size="small" onClick={() => navigate('/bank-journal/templates/bank')}>
                      去新建银行流水模板
                    </Button>
                  )}
                  {journalTemplates.length === 0 && (
                    <Button size="small" onClick={() => navigate('/bank-journal/templates/journal')}>
                      去新建日记账模板
                    </Button>
                  )}
                  {mappingProfiles.length === 0 && (
                    <Button size="small" onClick={() => navigate('/bank-journal/templates/mapping')}>
                      去新建映射方案
                    </Button>
                  )}
                  {rules.length === 0 && (
                    <Button size="small" onClick={() => navigate('/bank-journal/templates/rule')}>
                      去新建记账规则
                    </Button>
                  )}
                </Space>
              }
            />
          ) : null}
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <ConfigRow label="银行流水模板" required>
              <Select
                style={{ width: '100%' }}
                placeholder="选择该银行流水的解析模板"
                value={bankTemplateId}
                onChange={onBankTemplateChange}
                allowClear
                options={bankTemplates.map((t) => ({ value: t.id, label: t.name }))}
                notFoundContent="尚未配置银行流水模板"
              />
            </ConfigRow>
            <ConfigRow label="日记账模板" required>
              <Select
                style={{ width: '100%' }}
                placeholder="选择目标日记账格式"
                value={journalTemplateId}
                onChange={onJournalTemplateChange}
                allowClear
                options={journalTemplates.map((t) => ({ value: t.id, label: t.name }))}
                notFoundContent="尚未配置日记账模板"
              />
            </ConfigRow>
            <ConfigRow label="映射方案（可选）">
              <Select
                style={{ width: '100%' }}
                placeholder={
                  bankTemplateId && journalTemplateId
                    ? '选择字段映射方案'
                    : '请先选择银行/日记账模板'
                }
                value={mappingProfileId}
                onChange={setMappingProfileId}
                allowClear
                disabled={!bankTemplateId || !journalTemplateId}
                options={filteredMappings.map((t) => ({ value: t.id, label: t.name }))}
                notFoundContent="无可用的映射方案"
              />
            </ConfigRow>
            <ConfigRow label="应用规则（可选）">
              <Select
                style={{ width: '100%' }}
                mode="multiple"
                placeholder="选择要应用的自动记账规则"
                value={ruleIds}
                onChange={setRuleIds}
                allowClear
                options={rules.map((t) => ({ value: t.id, label: t.name }))}
                notFoundContent="尚未配置规则"
              />
            </ConfigRow>
          </Space>
        </div>

        <div className="toolbar" style={{ marginTop: 20 }}>
          <div className="toolbar-spacer" />
          <Button
            icon={<PlayCircleOutlined />}
            loading={dryRunning}
            disabled={!canStart}
            onClick={handleDryRun}
            style={{ marginRight: 8 }}
          >
            试跑预览（不保存）
          </Button>
          <Button type="primary" loading={loading} disabled={!canStart} onClick={handleStart}>
            开始转换
          </Button>
        </div>
      </Card>
      {dryRunResult && (
        <Card
          className="work-card"
          title={<span className="section-title">试跑预览（前 10 行，未保存）</span>}
        >
          <DryRunResultTable result={dryRunResult} />
        </Card>
      )}
      {run && (
        <Card className="work-card" title={<span className="section-title">转换结果</span>}>
          <ConversionRunDetailPage run={run} />
        </Card>
      )}
    </Space>
  );
}

/** 试跑结果表格：展示每行的输出值与状态/异常。 */
function DryRunResultTable({ result }: { result: DryRunResponse }) {
  const columns: ColumnsType<DryRunResponse['preview_rows'][number]> = [
    { title: '#', dataIndex: 'row_index', key: 'row_index', width: 50 },
    {
      title: '解析状态',
      key: 'status',
      width: 110,
      render: (_, r) => {
        const color =
          r.status === 'parse_failed'
            ? 'red'
            : r.status === 'auto_confirmed'
              ? 'green'
              : 'orange';
        const text =
          r.status === 'parse_failed'
            ? '解析失败'
            : r.status === 'auto_confirmed'
              ? '自动确认'
              : '待确认';
        return <Tag color={color}>{text}</Tag>;
      }
    },
    {
      title: '输出值',
      key: 'output',
      render: (_, r) => {
        const entries = Object.entries(r.output_values).filter(([k]) => !k.startsWith('_'));
        if (entries.length === 0) {
          const errMsg = String(r.output_values._parse_error ?? '无输出');
          return <Typography.Text type="danger">{errMsg}</Typography.Text>;
        }
        return (
          <Space wrap size={[4, 4]}>
            {entries.map(([k, v]) => (
              <Tag key={k}>
                {k}: {String(v)}
              </Tag>
            ))}
          </Space>
        );
      }
    },
    {
      title: '异常',
      key: 'exceptions',
      width: 160,
      render: (_, r) =>
        r.exception_codes.length > 0 ? (
          <Typography.Text type="danger" style={{ fontSize: 12 }}>
            {r.exception_codes.join('、')}
          </Typography.Text>
        ) : (
          <Typography.Text type="secondary">-</Typography.Text>
        )
    }
  ];
  return (
    <>
      <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
        共 {result.summary.total_rows} 行（其中 {result.summary.parse_failed_rows} 行解析失败）
      </Typography.Text>
      <Table
        rowKey="row_index"
        columns={columns}
        dataSource={result.preview_rows}
        pagination={false}
        size="small"
      />
    </>
  );
}

function ConfigRow({
  label,
  required,
  children
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
      <div style={{ width: 140, flexShrink: 0 }}>
        <Typography.Text strong>
          {label}
          {required && <span style={{ color: '#ff4d4f', marginLeft: 4 }}>*</span>}
        </Typography.Text>
      </div>
      <div style={{ flex: 1 }}>{children}</div>
    </div>
  );
}
