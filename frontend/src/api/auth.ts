import { apiClient } from './client';

/** 当前登录用户信息，与后端 /api/auth/me 响应一致。 */
export interface Me {
  id: string;
  email: string;
  name?: string;
  roles: string[];
  accessible_companies: { id: string; name: string }[] | 'all';
}

/** 登录：返回 JWT access_token。 */
export async function login(email: string, password: string): Promise<string> {
  const { data } = await apiClient.post('/api/auth/login', { email, password });
  return data.access_token as string;
}

/** 拉取当前用户信息。 */
export async function fetchMe(): Promise<Me> {
  const { data } = await apiClient.get('/api/auth/me');
  return data as Me;
}
