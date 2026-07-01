import { apiClient } from '../../../api/client';
import type { BankTemplate, BankTemplateVersion } from '../types/templates';
import type { Page } from '../types/pagination';

export async function listBankTemplates(
  params?: { limit?: number; offset?: number; company_id?: string }
): Promise<Page<BankTemplate>> {
  const response = await apiClient.get<Page<BankTemplate>>('/api/tools/bank-journal/bank-templates', { params });
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

/** 软删除银行模板（被批次引用时后端返回 409，拦截器会透传 detail）。 */
export async function deleteBankTemplate(id: string): Promise<void> {
  await apiClient.delete(`/api/tools/bank-journal/bank-templates/${id}`);
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

export async function detectBankTemplate(
  sourceFileId: string,
  companyId?: string
): Promise<DetectResult> {
  const response = await apiClient.post<DetectResult>(
    '/api/tools/bank-journal/bank-templates/detect',
    {
      source_file_id: sourceFileId,
      ...(companyId ? { company_id: companyId } : {})
    }
  );
  return response.data;
}

/** 已上传文件的工作表列表（供「上传后选 sheet」能力使用）。CSV/XLS 返回空数组。 */
export interface SourceFileSheetsResponse {
  file_id: string;
  sheets: string[];
}

/**
 * 列出已上传文件的工作表名。
 *
 * 每个文件的 sheet 名不同（"明细"/"交易流水"/"Sheet1"），转换前需让用户
 * 看到该文件有哪些 sheet 可选。CSV / XLS 等无工作表概念的文件返回空数组，
 * 前端据此隐藏选择器。
 */
export async function listSourceFileSheets(fileId: string): Promise<SourceFileSheetsResponse> {
  const response = await apiClient.get<SourceFileSheetsResponse>(
    `/api/tools/bank-journal/bank-templates/source-files/${fileId}/sheets`
  );
  return response.data;
}
