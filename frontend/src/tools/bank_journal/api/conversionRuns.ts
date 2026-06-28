import { apiClient } from '../../../api/client';
import type {
  ConversionRunListItem,
  ConversionRunResponse
} from '../types/conversion';

export async function listConversionRuns(companyId?: string): Promise<ConversionRunListItem[]> {
  const params = companyId ? { company_id: companyId } : undefined;
  const response = await apiClient.get<ConversionRunListItem[]>('/api/tools/bank-journal/conversion-runs', { params });
  return response.data;
}

export async function getConversionRun(runId: string): Promise<ConversionRunResponse> {
  const response = await apiClient.get<ConversionRunResponse>(`/api/tools/bank-journal/conversion-runs/${runId}`);
  return response.data;
}

export async function createConversionRun(sourceFileIds: string[]) {
  const response = await apiClient.post('/api/tools/bank-journal/conversion-runs', {
    company_id: 'company-1',
    bank_account_id: 'bank-account-1',
    source_file_ids: sourceFileIds,
    bank_parse_config: {
      file_type: 'csv',
      sheet_name: 'Sheet1',
      header_row_index: 0,
      data_start_row_index: 1,
      field_aliases: {
        交易日期: 'transaction_date',
        入账日期: 'posting_date',
        收入: 'income_amount',
        支出: 'expense_amount',
        余额: 'balance',
        对方户名: 'counterparty_name',
        对方账号: 'counterparty_account_no',
        摘要: 'summary',
        用途: 'purpose',
        流水号: 'bank_transaction_id'
      },
      amount_mode: 'income_expense_columns',
      amount_config: { income: 'income_amount', expense: 'expense_amount' },
      date_formats: ['%Y-%m-%d']
    },
    mappings: [
      { target: '日期', type: 'field', source: 'transaction_date' },
      { target: '摘要', type: 'rule_output', source: 'journal_summary' },
      { target: '科目', type: 'rule_output', source: 'account_subject' },
      { target: '金额', type: 'field', source: 'net_amount' }
    ],
    rules: [
      {
        id: 'rule-1',
        version_id: 'rule-version-1',
        priority: 10,
        conditions: { all: [{ field: 'summary', op: 'contains', value: '货款' }] },
        actions: [
          { field: 'journal_summary', value: '收到客户款项' },
          { field: 'account_subject', value: '银行存款' }
        ],
        allow_auto_confirm: false
      }
    ],
    required_columns: ['日期', '摘要', '科目', '金额']
  });
  return response.data;
}

/**
 * P0：用已配置的版本化模板/映射/规则驱动转换（真正读取用户配置）。
 * 与 createConversionRun（硬编码内联参数）相对——后者保留仅为兼容历史入口。
 */
export interface ConversionRunFromConfigPayload {
  source_file_ids: string[];
  bank_template_id?: string;
  company_journal_template_id?: string;
  mapping_profile_id?: string;
  rule_ids?: string[];
}

export async function createConversionRunFromConfig(
  payload: ConversionRunFromConfigPayload
): Promise<ConversionRunResponse> {
  const response = await apiClient.post<ConversionRunResponse>(
    '/api/tools/bank-journal/conversion-runs/from-config',
    {
      company_id: 'company-1',
      bank_account_id: 'bank-account-1',
      source_file_ids: payload.source_file_ids,
      bank_template_id: payload.bank_template_id,
      company_journal_template_id: payload.company_journal_template_id,
      mapping_profile_id: payload.mapping_profile_id,
      rule_ids: payload.rule_ids ?? []
    }
  );
  return response.data;
}

/** P3：试跑结果（不落库）。 */
export interface DryRunResponse {
  summary: { total_rows: number; parse_failed_rows: number };
  preview_rows: Array<{
    row_index: number;
    output_values: Record<string, unknown>;
    status: string;
    exception_codes: string[];
    matched_rule_version_ids: string[];
  }>;
}

/**
 * P3：试跑——用配置解析样本文件并返回前 N 行预览，但不创建批次。
 * 供保存配置前即时验证效果。
 */
export async function dryRunConversion(
  payload: ConversionRunFromConfigPayload & { limit?: number }
): Promise<DryRunResponse> {
  const response = await apiClient.post<DryRunResponse>(
    '/api/tools/bank-journal/conversion-runs/dry-run',
    {
      company_id: 'company-1',
      bank_account_id: 'bank-account-1',
      source_file_ids: payload.source_file_ids,
      bank_template_id: payload.bank_template_id,
      company_journal_template_id: payload.company_journal_template_id,
      mapping_profile_id: payload.mapping_profile_id,
      rule_ids: payload.rule_ids ?? [],
      limit: payload.limit ?? 20
    }
  );
  return response.data;
}
