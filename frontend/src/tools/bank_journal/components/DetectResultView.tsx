import { CheckCircleFilled } from '@ant-design/icons';
import { Descriptions, Space, Tag, Typography } from 'antd';
import {
  AMOUNT_MODE_LABEL,
  FIELD_LABEL,
  FILE_TYPE_LABEL,
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
}

/**
 * 银行模板配置的结构化展示（替代裸 JSON `<pre>`）。
 * 把技术字段全部转成财务看得懂的中文标签，供详情页、版本历史、向导复用。
 */
export function DetectResultView({ config }: { config: BankTemplateConfigView }) {
  const aliases = config.field_aliases ?? {};
  const aliasEntries = Object.entries(aliases);
  const dateFormats = (config.date_formats ?? []) as string[];

  return (
    <Descriptions bordered size="small" column={1} labelStyle={{ width: 140 }}>
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
        <Tag color="blue">{AMOUNT_MODE_LABEL[config.amount_mode] ?? config.amount_mode}</Tag>
      </Descriptions.Item>
      <Descriptions.Item label="日期格式">
        {dateFormats.length > 0 ? (
          dateFormats.map((f) => <Tag key={f}>{f}</Tag>)
        ) : (
          <Typography.Text type="secondary">未识别（将按默认格式尝试）</Typography.Text>
        )}
      </Descriptions.Item>
      <Descriptions.Item label={`字段映射（${aliasEntries.length} 个）`}>
        {aliasEntries.length > 0 ? (
          <Space wrap size={[8, 8]}>
            {aliasEntries.map(([col, field]) => (
              <Tag key={col} icon={<CheckCircleFilled className="ok-mark" />}>
                {col} → {FIELD_LABEL[String(field)] ?? String(field)}
              </Tag>
            ))}
          </Space>
        ) : (
          <Typography.Text type="secondary">无</Typography.Text>
        )}
      </Descriptions.Item>
    </Descriptions>
  );
}
