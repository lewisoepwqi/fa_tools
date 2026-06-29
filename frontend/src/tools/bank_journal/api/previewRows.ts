import { apiClient } from '../../../api/client';

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
