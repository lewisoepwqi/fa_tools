import { apiClient } from '../../../api/client';
import type { BankTemplate, BankTemplateVersion } from '../types/templates';

export async function listBankTemplates(companyId?: string): Promise<BankTemplate[]> {
  const params = companyId ? { company_id: companyId } : undefined;
  const response = await apiClient.get<BankTemplate[]>('/api/tools/bank-journal/bank-templates', { params });
  return response.data;
}

export async function getBankTemplate(id: string): Promise<BankTemplate> {
  const response = await apiClient.get<BankTemplate>(`/api/tools/bank-journal/bank-templates/${id}`);
  return response.data;
}

export async function createBankTemplate(payload: {
  company_id?: string | null;
  name: string;
  bank_name?: string | null;
  bank_account_id?: string | null;
  version: Partial<BankTemplateVersion> & { file_type: string; amount_mode: string };
}): Promise<BankTemplate> {
  const response = await apiClient.post<BankTemplate>('/api/tools/bank-journal/bank-templates', payload);
  return response.data;
}

export async function createBankTemplateVersion(
  id: string,
  version: Partial<BankTemplateVersion> & { file_type: string; amount_mode: string }
): Promise<BankTemplate> {
  const response = await apiClient.post<BankTemplate>(`/api/tools/bank-journal/bank-templates/${id}/versions`, version);
  return response.data;
}

export async function listBankTemplateVersions(id: string): Promise<BankTemplateVersion[]> {
  const response = await apiClient.get<BankTemplateVersion[]>(`/api/tools/bank-journal/bank-templates/${id}/versions`);
  return response.data;
}

export async function setBankTemplateStatus(id: string, status: 'active' | 'inactive'): Promise<BankTemplate> {
  const response = await apiClient.patch<BankTemplate>(
    `/api/tools/bank-journal/bank-templates/${id}/status`,
    null,
    { params: { status } }
  );
  return response.data;
}

export interface DetectResult {
  file_type: string;
  sheet_name: string;
  header_row_index: number;
  data_start_row_index: number;
  field_aliases: Record<string, string>;
  amount_mode: string;
  amount_config: Record<string, string>;
  date_formats: string[];
}

export async function detectBankTemplate(sourceFileId: string): Promise<DetectResult> {
  const response = await apiClient.post<DetectResult>('/api/tools/bank-journal/bank-templates/detect', {
    source_file_id: sourceFileId
  });
  return response.data;
}
