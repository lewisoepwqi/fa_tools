export interface PreviewRow {
  row_index: number;
  output_values: Record<string, unknown>;
  status: string;
  exception_codes: string[];
  matched_rule_version_ids: string[];
  rule_trace: Record<string, unknown>[];
}

export interface ConversionRunSummary {
  total_rows: number;
}

export interface ConversionRunResponse {
  id: string;
  status: string;
  summary: ConversionRunSummary;
  preview_rows: PreviewRow[];
}

export interface UploadedFile {
  id: string;
  original_filename: string;
  file_type: string;
  sha256: string;
  storage_key: string;
}
