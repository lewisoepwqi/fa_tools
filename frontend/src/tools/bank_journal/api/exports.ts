import { apiClient } from '../../../api/client';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export interface ExportResponse {
  export_id: string;
  file_type: 'csv' | 'xlsx';
  row_count: number;
  download_url: string;
  report_url: string;
}

export interface CreateExportParams {
  file_type: 'csv' | 'xlsx';
  columns: string[];
  only_confirmed?: boolean;
  required_columns?: string[] | null;
  rows?: Record<string, unknown>[] | null;
}

/** 发起导出（POST /api/tools/bank-journal/conversion-runs/{run_id}/exports）。 */
export async function createExport(runId: string, params: CreateExportParams): Promise<ExportResponse> {
  const response = await apiClient.post<ExportResponse>(
    `/api/tools/bank-journal/conversion-runs/${runId}/exports`,
    params
  );
  return response.data;
}

/** 触发浏览器下载导出文件。 */
export function downloadExport(exportId: string): void {
  window.open(`${API_BASE}/api/tools/bank-journal/exports/${exportId}/download`, '_blank');
}

/** 触发浏览器下载处理报告。 */
export function downloadExportReport(exportId: string): void {
  window.open(`${API_BASE}/api/tools/bank-journal/exports/${exportId}/report`, '_blank');
}
