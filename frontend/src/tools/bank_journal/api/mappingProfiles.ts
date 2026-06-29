import { apiClient } from '../../../api/client';
import type { MappingProfile, MappingProfileVersion } from '../types/mapping';
import type { Page } from '../types/pagination';

/** 过滤参数：用于模板详情页展示"被哪些映射方案引用"等反向关联查询。 */
export interface MappingProfileFilter {
  company_id?: string;
  bank_template_id?: string;
  company_journal_template_id?: string;
  limit?: number;
  offset?: number;
}

export async function listMappingProfiles(
  filter: MappingProfileFilter = {}
): Promise<Page<MappingProfile>> {
  const params: Record<string, string | number> = {};
  if (filter.company_id) params.company_id = filter.company_id;
  if (filter.bank_template_id) params.bank_template_id = filter.bank_template_id;
  if (filter.company_journal_template_id) {
    params.company_journal_template_id = filter.company_journal_template_id;
  }
  if (filter.limit !== undefined) params.limit = filter.limit;
  if (filter.offset !== undefined) params.offset = filter.offset;
  const response = await apiClient.get<Page<MappingProfile>>(
    '/api/tools/bank-journal/mapping-profiles',
    { params }
  );
  return response.data;
}

export async function getMappingProfile(id: string): Promise<MappingProfile> {
  const response = await apiClient.get<MappingProfile>(`/api/tools/bank-journal/mapping-profiles/${id}`);
  return response.data;
}

export async function createMappingProfile(payload: {
  company_id: string;
  name: string;
  bank_template_id?: string | null;
  company_journal_template_id?: string | null;
  version: Partial<MappingProfileVersion>;
}): Promise<MappingProfile> {
  const response = await apiClient.post<MappingProfile>('/api/tools/bank-journal/mapping-profiles', payload);
  return response.data;
}

export async function createMappingProfileVersion(
  id: string,
  version: Partial<MappingProfileVersion>
): Promise<MappingProfile> {
  const response = await apiClient.post<MappingProfile>(
    `/api/tools/bank-journal/mapping-profiles/${id}/versions`,
    version
  );
  return response.data;
}

export async function listMappingProfileVersions(
  id: string
): Promise<MappingProfileVersion[]> {
  const response = await apiClient.get<MappingProfileVersion[]>(
    `/api/tools/bank-journal/mapping-profiles/${id}/versions`
  );
  return response.data;
}

export async function setMappingProfileStatus(
  id: string,
  status: 'active' | 'inactive'
): Promise<MappingProfile> {
  const response = await apiClient.patch<MappingProfile>(
    `/api/tools/bank-journal/mapping-profiles/${id}/status`,
    null,
    { params: { status } }
  );
  return response.data;
}

/** 软删除映射方案（被批次引用时后端返回 409）。 */
export async function deleteMappingProfile(id: string): Promise<void> {
  await apiClient.delete(`/api/tools/bank-journal/mapping-profiles/${id}`);
}
