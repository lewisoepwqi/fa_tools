import { CheckCircleFilled, DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { Alert, Button, Descriptions, Input, Select, Space, Table, Tag, Typography } from 'antd';
import {
  AMOUNT_MODE_LABEL,
  FIELD_LABEL,
  FILE_TYPE_LABEL,
  STANDARD_FIELD_OPTIONS,
  rowIndexOf
} from '../constants';

/** 银行模板识别/配置的可视化字段集合（与 detect 返回、版本存储一致）。 */
export interface BankTemplateConfigView {
  file_type: string;
  sheet_name?: string | null;
  header_row_index?: number | null;
  data_start_row_index?: number | null;
  field_aliases?: Record<string, unknown> | null;
  amount_mode: string;
  amount_config?: Record<string, unknown> | null;
  date_formats?: unknown[] | null;
  /** 去重唯一键配置：{ fields: ["transaction_date", "amount", ...] }。 */
  unique_key_config?: Record<string, unknown> | null;
  /** 识别所用的样本文件 ID（追溯用）。 */
  sample_file_id?: string | null;
  /** 样本文件名（后端联表解析，优先显示）。 */
  sample_file_name?: string | null;
}

interface DetectResultViewProps {
  config: BankTemplateConfigView;
  /**
   * 传入即开启「字段映射就地编辑」：识别结果认错时可改标准字段、删除、新增。
   * detect 是启发式自动识别，会认错列名；可编辑让财务就地纠正，无需重传样本。
   * 不传则保持只读展示（详情页等纯展示场景）。
   */
  onFieldAliasesChange?: (next: Record<string, string>) => void;
  /** 流水标准字段下拉（含公司扩展字段）。默认用构建期内置字段；页面注入运行时全集。 */
  standardFieldOptions?: { value: string; label: string }[];
}

/**
 * 生成识别结果的自然语言摘要（P1）。
 * 把技术字段转成财务看得懂的一句话，降低「识别结果对不对」的认知负担。
 */
/** 关键标准字段 key 集合（用于识别摘要高亮）。按 key 判断，使 label 可被自定义后仍正确高亮。 */
const KEY_FIELD_KEYS = new Set([
  'transaction_date',
  'income_amount',
  'expense_amount',
  'debit_amount',
  'credit_amount',
  'amount',
  'summary',
  'counterparty_name'
]);

/** amount_config 的角色 key → 中文（金额模式参数展示用）。 */
const AMOUNT_CONFIG_ROLE_LABEL: Record<string, string> = {
  income: '收入列',
  expense: '支出列',
  debit: '借方列',
  credit: '贷方列',
  amount: '金额列',
  direction: '方向列'
};

function describeConfig(config: BankTemplateConfigView): string {
  const aliases = config.field_aliases ?? {};
  const aliasKeys = Object.values(aliases).map((f) => String(f));
  const keyFields = aliasKeys
    .filter((k) => KEY_FIELD_KEYS.has(k))
    .map((k) => FIELD_LABEL[k] ?? k);
  const amountMode = AMOUNT_MODE_LABEL[config.amount_mode] ?? config.amount_mode;
  const parts: string[] = [];
  parts.push(`这份流水将从第 ${rowIndexOf(config.data_start_row_index)} 行开始读取`);
  parts.push(`按「${amountMode}」识别金额`);
  if (keyFields.length > 0) {
    parts.push(`已识别关键字段：${keyFields.join('、')}`);
  }
  return parts.join('，') + '。';
}

/**
 * 银行模板配置的结构化展示（替代裸 JSON `<pre>`）。
 * 把技术字段全部转成财务看得懂的中文标签，供详情页、版本历史、向导复用。
 */
export function DetectResultView({
  config,
  onFieldAliasesChange,
  standardFieldOptions
}: DetectResultViewProps) {
  const aliases = config.field_aliases ?? {};
  const aliasEntries = Object.entries(aliases);
  const dateFormats = (config.date_formats ?? []) as string[];
  const amountConfigEntries = Object.entries(config.amount_config ?? {});
  const uniqueKeyFields = ((config.unique_key_config?.fields as string[] | undefined) ?? []).map(
    (f) => FIELD_LABEL[f] ?? f
  );
  const summary = describeConfig(config);
  const editable = !!onFieldAliasesChange;
  const fieldOptions = standardFieldOptions ?? STANDARD_FIELD_OPTIONS;

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Alert type="info" showIcon message="识别摘要" description={summary} />
      <Descriptions bordered size="small" column={1} styles={{ label: { width: 140 } }}>
        <Descriptions.Item label="文件类型">
          <Tag color="blue">{FILE_TYPE_LABEL[config.file_type] ?? config.file_type}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="工作表">{config.sheet_name || '-'}</Descriptions.Item>
        <Descriptions.Item label="表头位置">
          {rowIndexOf(config.header_row_index)}
        </Descriptions.Item>
        <Descriptions.Item label="数据起始位置">
          {rowIndexOf(config.data_start_row_index)}
        </Descriptions.Item>
        <Descriptions.Item label="金额格式">
          <Space direction="vertical" size={4} style={{ lineHeight: 1.4 }}>
            <Tag color="blue">{AMOUNT_MODE_LABEL[config.amount_mode] ?? config.amount_mode}</Tag>
            {amountConfigEntries.length > 0 && (
              <Space wrap size={[4, 4]}>
                {amountConfigEntries.map(([role, field]) => (
                  <Typography.Text key={role} type="secondary" style={{ fontSize: 12 }}>
                    {AMOUNT_CONFIG_ROLE_LABEL[role] ?? role}：
                    <Typography.Text code style={{ marginLeft: 2 }}>
                      {FIELD_LABEL[String(field)] ?? String(field)}
                    </Typography.Text>
                  </Typography.Text>
                ))}
              </Space>
            )}
          </Space>
        </Descriptions.Item>
        <Descriptions.Item label="日期格式">
          {dateFormats.length > 0 ? (
            dateFormats.map((f) => <Tag key={f}>{f}</Tag>)
          ) : (
            <Typography.Text type="secondary">未识别（将按默认格式尝试）</Typography.Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="去重唯一键">
          {uniqueKeyFields.length > 0 ? (
            <Space wrap size={[4, 4]}>
              {uniqueKeyFields.map((f) => (
                <Tag key={f} color="purple">{f}</Tag>
              ))}
            </Space>
          ) : (
            <Typography.Text type="secondary">默认（日期+金额+对方户名）</Typography.Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="样本文件">
          {config.sample_file_id ? (
            <Typography.Text>{config.sample_file_name ?? config.sample_file_id}</Typography.Text>
          ) : (
            <Typography.Text type="secondary">无</Typography.Text>
          )}
        </Descriptions.Item>
      </Descriptions>

      {/* 字段映射：从 Descriptions 抽出，用表格逐行展示（流水表头列 → 标准字段）。 */}
      <Typography.Text strong>字段映射（{aliasEntries.length} 个）</Typography.Text>
      {editable ? (
        <FieldAliasesEditor
          entries={aliasEntries.map(([col, field]) => [col, String(field ?? '')])}
          fieldOptions={fieldOptions}
          onChange={(next) => onFieldAliasesChange?.(next)}
        />
      ) : aliasEntries.length > 0 ? (
        <Table
          rowKey={(row: { col: string }) => row.col}
          dataSource={aliasEntries.map(([col, field]) => ({ col, field: String(field ?? '') }))}
          pagination={false}
          size="small"
          columns={[
            { title: '流水表头列', dataIndex: 'col', key: 'col', width: '45%' },
            {
              title: '标准字段',
              dataIndex: 'field',
              key: 'field',
              render: (field: string) => (
                <Space size={4}>
                  <Typography.Text type="secondary">→</Typography.Text>
                  <Tag color="blue" icon={<CheckCircleFilled className="ok-mark" />}>
                    {FIELD_LABEL[field] ?? field}
                  </Tag>
                </Space>
              )
            }
          ]}
        />
      ) : (
        <Typography.Text type="secondary">无</Typography.Text>
      )}
    </Space>
  );
}

/**
 * 字段别名就地编辑器：每行 = 流水表头列名 → 标准字段（下拉）。
 *
 * detect 自动识别会认错列名（启发式匹配中文关键词），这里让财务纠正：
 * - 改某列对应的标准字段
 * - 删除错误的映射
 * - 手动新增一条（识别漏掉的列）
 * 用 [col, field] 元组数组承载，Col 重复时以最后一条为准（与扁平 Record 语义一致）。
 */
function FieldAliasesEditor({
  entries,
  fieldOptions,
  onChange
}: {
  entries: Array<[string, string]>;
  fieldOptions: { value: string; label: string }[];
  onChange: (next: Record<string, string>) => void;
}) {
  const emit = (next: Array<[string, string]>) => {
    const obj: Record<string, string> = {};
    for (const [col, field] of next) {
      if (col.trim() && field) obj[col.trim()] = field;
    }
    onChange(obj);
  };

  const updateCol = (i: number, col: string) =>
    emit(entries.map((e, idx) => (idx === i ? [col, e[1]] : e)));
  const updateField = (i: number, field: string) =>
    emit(entries.map((e, idx) => (idx === i ? [e[0], field] : e)));
  const remove = (i: number) => emit(entries.filter((_, idx) => idx !== i));
  const add = () => emit([...entries, ['', '']]);

  return (
    <Space direction="vertical" size={8} style={{ width: '100%' }}>
      {entries.map(([col, field], i) => (
        <Space.Compact key={i} style={{ width: '100%' }}>
          <Input
            style={{ width: '45%' }}
            value={col}
            placeholder="流水表头列名（如：交易日期）"
            onChange={(e) => updateCol(i, e.target.value)}
          />
          <Typography.Text type="secondary" style={{ alignSelf: 'center', padding: '0 6px' }}>
            →
          </Typography.Text>
          <Select
            style={{ width: '45%' }}
            value={field || undefined}
            placeholder="对应的标准字段"
            allowClear
            showSearch
            optionFilterProp="label"
            options={fieldOptions}
            onChange={(v) => updateField(i, v ?? '')}
          />
          <Button
            icon={<DeleteOutlined />}
            onClick={() => remove(i)}
            danger
            style={{ width: '10%' }}
          />
        </Space.Compact>
      ))}
      <Button type="dashed" icon={<PlusOutlined />} onClick={add} block size="small">
        添加字段映射
      </Button>
      {entries.length === 0 && (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          尚无字段映射，可点上方添加；否则该模板无法解析流水。
        </Typography.Text>
      )}
    </Space>
  );
}
