export interface PreviewRow {
  id: string | null;
  row_index: number;
  output_values: Record<string, unknown>;
  status: string;
  exception_codes: string[];
  matched_rule_version_ids: string[];
  rule_trace: Record<string, unknown>[];
}

export interface ConversionRunSummary {
  total_rows: number;
  parse_failed_rows?: number;
}

/** 批次详情（含预览行）。 */
export interface ConversionRunResponse {
  id: string;
  status: string;
  summary: ConversionRunSummary;
  preview_rows: PreviewRow[];
  company_id?: string | null;
  bank_account_id?: string | null;
  created_at?: string | null;
  completed_at?: string | null;
}

/** 批次列表项（不含预览行）。 */
export interface ConversionRunListItem {
  id: string;
  company_id: string;
  bank_account_id?: string | null;
  status: string;
  summary: ConversionRunSummary;
  created_at?: string | null;
  completed_at?: string | null;
}

export interface UploadedFile {
  id: string;
  original_filename: string;
  file_type: string;
  sha256: string;
  storage_key: string;
}
