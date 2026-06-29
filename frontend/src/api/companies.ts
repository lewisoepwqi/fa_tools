import { apiClient } from './client';

/** 拉取当前用户可访问的公司列表（平台共享接口）。 */
export async function listCompanies(): Promise<{ id: string; name: string }[]> {
  const res = await apiClient.get('/api/companies');
  return res.data;
}
