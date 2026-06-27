import { apiClient } from '../../../api/client';
import type { MappingProfile, MappingProfileVersion } from '../types/mapping';

export async function listMappingProfiles(companyId?: string): Promise<MappingProfile[]> {
  const params = companyId ? { company_id: companyId } : undefined;
  const response = await apiClient.get<MappingProfile[]>('/api/tools/bank-journal/mapping-profiles', { params });
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
