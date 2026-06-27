import { apiClient } from './client';
import type { Rule, RuleVersion } from '../types/rules';

export async function listRules(companyId?: string): Promise<Rule[]> {
  const params = companyId ? { company_id: companyId } : undefined;
  const response = await apiClient.get<Rule[]>('/api/rules', { params });
  return response.data;
}

export async function getRule(id: string): Promise<Rule> {
  const response = await apiClient.get<Rule>(`/api/rules/${id}`);
  return response.data;
}

export async function createRule(payload: {
  company_id: string;
  name: string;
  scope_type?: string | null;
  scope_id?: string | null;
  version: Partial<RuleVersion>;
}): Promise<Rule> {
  const response = await apiClient.post<Rule>('/api/rules', payload);
  return response.data;
}

export async function createRuleVersion(
  id: string,
  version: Partial<RuleVersion>
): Promise<Rule> {
  const response = await apiClient.post<Rule>(`/api/rules/${id}/versions`, version);
  return response.data;
}

export async function listRuleVersions(id: string): Promise<RuleVersion[]> {
  const response = await apiClient.get<RuleVersion[]>(`/api/rules/${id}/versions`);
  return response.data;
}

export async function setRuleStatus(
  id: string,
  status: 'active' | 'inactive'
): Promise<Rule> {
  const response = await apiClient.patch<Rule>(`/api/rules/${id}/status`, null, {
    params: { status }
  });
  return response.data;
}

export async function reorderRules(
  items: Array<{ rule_id: string; priority: number }>
): Promise<{ updated: Array<{ rule_id: string; priority: number }> }> {
  const response = await apiClient.post('/api/rules/reorder', { items });
  return response.data;
}
