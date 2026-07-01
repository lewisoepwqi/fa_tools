/** 银行流水模板 / 公司日记账模板类型（对齐后端 app/schemas/template.py）。 */

export interface BankTemplateVersion {
  version_no: number;
  file_type: string;
  sheet_selector_json?: Record<string, unknown> | null;
  header_row_index?: number | null;
  data_start_row_index?: number | null;
  field_aliases_json?: Record<string, unknown> | null;
  date_formats_json?: unknown[] | null;
  amount_mode: string;
  amount_config_json?: Record<string, unknown> | null;
  unique_key_config_json?: Record<string, unknown> | null;
  sample_file_id?: string | null;
  created_by?: string | null;
  /** 展示名（后端联表解析，供直接显示，避免裸 ID）。 */
  created_by_name?: string | null;
  sample_file_name?: string | null;
}

export interface BankTemplate {
  id: string;
  company_id?: string | null;
  company_name?: string | null;
  name: string;
  bank_name?: string | null;
  bank_account_id?: string | null;
  status: string;
  latest_version: BankTemplateVersion;
}

export interface JournalTemplateVersion {
  version_no: number;
  file_type: string;
  sheet_name?: string | null;
  header_row_index?: number | null;
  data_start_row_index?: number | null;
  columns_json?: unknown[] | null;
  required_columns_json?: unknown[] | null;
  format_rules_json?: Record<string, unknown> | null;
  sample_file_id?: string | null;
  created_by?: string | null;
  /** 展示名（后端联表解析，供直接显示，避免裸 ID）。 */
  created_by_name?: string | null;
  sample_file_name?: string | null;
}

export interface JournalTemplate {
  id: string;
  company_id: string;
  company_name?: string | null;
  name: string;
  status: string;
  latest_version: JournalTemplateVersion;
}
