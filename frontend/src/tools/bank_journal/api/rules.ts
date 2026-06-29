import { apiClient } from '../../../api/client';
import type { Rule, RuleVersion } from '../types/rules';
import type { Page } from '../types/pagination';

/** 过滤参数：用于模板详情页展示"绑定了哪些规则"等反向关联查询。 */
export interface RuleFilter {
  company_id?: string;
  scope_type?: string;
  scope_id?: string;
  limit?: number;
  offset?: number;
}

export async function listRules(filter: RuleFilter = {}): Promise<Page<Rule>> {
  const params: Record<string, string | number> = {};
  if (filter.company_id) params.company_id = filter.company_id;
  if (filter.scope_type) params.scope_type = filter.scope_type;
  if (filter.scope_id) params.scope_id = filter.scope_id;
  if (filter.limit !== undefined) params.limit = filter.limit;
  if (filter.offset !== undefined) params.offset = filter.offset;
  const response = await apiClient.get<Page<Rule>>('/api/tools/bank-journal/rules', { params });
  return response.data;
}

export async function getRule(id: string): Promise<Rule> {
  const response = await apiClient.get<Rule>(`/api/tools/bank-journal/rules/${id}`);
  return response.data;
}

export async function createRule(payload: {
  company_id: string;
  name: string;
  scope_type?: string | null;
  scope_id?: string | null;
  version: Partial<RuleVersion>;
}): Promise<Rule> {
  const response = await apiClient.post<Rule>('/api/tools/bank-journal/rules', payload);
  return response.data;
}

export async function createRuleVersion(
  id: string,
  version: Partial<RuleVersion>
): Promise<Rule> {
  const response = await apiClient.post<Rule>(`/api/tools/bank-journal/rules/${id}/versions`, version);
  return response.data;
}

export async function listRuleVersions(id: string): Promise<RuleVersion[]> {
  const response = await apiClient.get<RuleVersion[]>(`/api/tools/bank-journal/rules/${id}/versions`);
  return response.data;
}

export async function setRuleStatus(
  id: string,
  status: 'active' | 'inactive'
): Promise<Rule> {
  const response = await apiClient.patch<Rule>(`/api/tools/bank-journal/rules/${id}/status`, null, {
    params: { status }
  });
  return response.data;
}

/** 软删除规则（被批次引用时后端返回 409）。 */
export async function deleteRule(id: string): Promise<void> {
  await apiClient.delete(`/api/tools/bank-journal/rules/${id}`);
}

export async function reorderRules(
  items: Array<{ rule_id: string; priority: number }>
): Promise<{ updated: Array<{ rule_id: string; priority: number }> }> {
  const response = await apiClient.post('/api/tools/bank-journal/rules/reorder', { items });
  return response.data;
}
