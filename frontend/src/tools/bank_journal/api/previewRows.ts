import { apiClient } from '../../../api/client';
import type { PreviewRow } from '../types/conversion';
import type { Page } from '../types/pagination';

export interface AdjustResult {
  row_id: string;
  field_name: string;
  new_value: string;
  status: string;
}

export interface ConfirmResult {
  row_id: string;
  status: string;
}

/** 人工修改单个字段（PATCH /api/tools/bank-journal/preview-rows/{id}）。 */
export async function adjustPreviewRow(
  rowId: string,
  fieldName: string,
  newValue: string,
  reason: string | null
): Promise<AdjustResult> {
  const response = await apiClient.patch<AdjustResult>(`/api/tools/bank-journal/preview-rows/${rowId}`, {
    field_name: fieldName,
    new_value: newValue,
    reason
  });
  return response.data;
}

/** 分页拉取批次预览行（GET /api/tools/bank-journal/conversion-runs/{runId}/preview-rows）。 */
export async function listPreviewRows(
  runId: string,
  params?: { limit?: number; offset?: number; status?: string }
): Promise<Page<PreviewRow>> {
  const res = await apiClient.get<Page<PreviewRow>>(
    `/api/tools/bank-journal/conversion-runs/${runId}/preview-rows`,
    { params }
  );
  return res.data;
}

/** 确认单行（POST /api/tools/bank-journal/preview-rows/{id}/confirm）。 */
export async function confirmPreviewRow(
  rowId: string,
  comment: string | null = null
): Promise<ConfirmResult> {
  const response = await apiClient.post<ConfirmResult>(`/api/tools/bank-journal/preview-rows/${rowId}/confirm`, {
    comment
  });
  return response.data;
}
