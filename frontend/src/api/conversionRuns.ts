import { apiClient } from './client';
import type {
  ConversionRunListItem,
  ConversionRunResponse
} from '../types/conversion';

export async function listConversionRuns(companyId?: string): Promise<ConversionRunListItem[]> {
  const params = companyId ? { company_id: companyId } : undefined;
  const response = await apiClient.get<ConversionRunListItem[]>('/api/conversion-runs', { params });
  return response.data;
}

export async function getConversionRun(runId: string): Promise<ConversionRunResponse> {
  const response = await apiClient.get<ConversionRunResponse>(`/api/conversion-runs/${runId}`);
  return response.data;
}

export async function createConversionRun(sourceFileIds: string[]) {
  const response = await apiClient.post('/api/conversion-runs', {
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
