import { apiClient } from '../../../api/client';
import type { JournalTemplate, JournalTemplateVersion } from '../types/templates';
import type { Page } from '../types/pagination';

export async function listJournalTemplates(
  params?: { limit?: number; offset?: number; company_id?: string }
): Promise<Page<JournalTemplate>> {
  const response = await apiClient.get<Page<JournalTemplate>>('/api/tools/bank-journal/journal-templates', { params });
  return response.data;
}

export async function getJournalTemplate(id: string): Promise<JournalTemplate> {
  const response = await apiClient.get<JournalTemplate>(`/api/tools/bank-journal/journal-templates/${id}`);
  return response.data;
}

export async function createJournalTemplate(payload: {
  company_id: string;
  name: string;
  version: Partial<JournalTemplateVersion> & { file_type: string };
}): Promise<JournalTemplate> {
  const response = await apiClient.post<JournalTemplate>('/api/tools/bank-journal/journal-templates', payload);
  return response.data;
}

export async function createJournalTemplateVersion(
  id: string,
  version: Partial<JournalTemplateVersion> & { file_type: string }
): Promise<JournalTemplate> {
  const response = await apiClient.post<JournalTemplate>(
    `/api/tools/bank-journal/journal-templates/${id}/versions`,
    version
  );
  return response.data;
}

export async function listJournalTemplateVersions(id: string): Promise<JournalTemplateVersion[]> {
  const response = await apiClient.get<JournalTemplateVersion[]>(
    `/api/tools/bank-journal/journal-templates/${id}/versions`
  );
  return response.data;
}

export async function setJournalTemplateStatus(
  id: string,
  status: 'active' | 'inactive'
): Promise<JournalTemplate> {
  const response = await apiClient.patch<JournalTemplate>(
    `/api/tools/bank-journal/journal-templates/${id}/status`,
    null,
    { params: { status } }
  );
  return response.data;
}

/** 软删除日记账模板（被批次引用时后端返回 409）。 */
export async function deleteJournalTemplate(id: string): Promise<void> {
  await apiClient.delete(`/api/tools/bank-journal/journal-templates/${id}`);
}

/** 日记账模板 detect 识别结果（表头行 + 列名）。 */
export interface JournalDetectResult {
  file_type: string;
  sheet_name: string;
  header_row_index: number;
  data_start_row_index: number;
  columns: string[];
  required_columns: string[];
}

/**
 * 从已上传的日记账样本识别表头行与列名（对齐银行模板 detect 体验）。
 *
 * 列名即输出列名本身，无需字段别名映射。识别后用户可核对调整。
 */
export async function detectJournalTemplate(
  sourceFileId: string,
  sheetName?: string
): Promise<JournalDetectResult> {
  const response = await apiClient.post<JournalDetectResult>(
    '/api/tools/bank-journal/journal-templates/detect',
    {
      source_file_id: sourceFileId,
      ...(sheetName ? { sheet_name: sheetName } : {})
    }
  );
  return response.data;
}
