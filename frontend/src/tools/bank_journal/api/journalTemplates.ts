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
