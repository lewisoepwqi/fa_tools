import { apiClient } from '../../../api/client';

/** 标准字段定义（内置 + 公司扩展合并视图）。 */
export interface StandardFieldDef {
  key: string;
  label: string;
  type: 'text' | 'amount' | 'date' | 'enum';
  /** True=内置字段，False=公司扩展字段 */
  builtin: boolean;
  /** 当前生效识别关键词（内置默认 ∪ 公司覆盖） */
  keywords: string[];
  /** 内置字段是否有公司覆盖（前端用于显示「恢复默认」） */
  overridden: boolean;
}

export interface SlotQuota {
  text: { used: number; total: number };
  amount: { used: number; total: number };
  date: { used: number; total: number };
}

export interface StandardSchema {
  fields: StandardFieldDef[];
  slot_quota: SlotQuota;
}

export interface CustomField {
  id: string;
  company_id: string;
  field_key: string;
  name: string;
  slot_key: string;
  data_type: 'text' | 'amount' | 'date';
  header_keywords: string[];
  status: string;
}

export interface CustomFieldCreate {
  company_id: string;
  field_key: string;
  name: string;
  data_type: 'text' | 'amount' | 'date';
  header_keywords: string[];
  created_by?: string;
}

export interface CustomFieldUpdate {
  name?: string;
  header_keywords?: string[];
  status?: 'active' | 'inactive';
}

const BASE = '/api/tools/bank-journal/custom-fields';

/** 合并后的标准字段全集（内置 + 该公司扩展），供所有字段下拉运行时拉取。 */
export async function getStandardSchema(companyId: string): Promise<StandardSchema> {
  const response = await apiClient.get<StandardSchema>(`${BASE}/standard-schema`, {
    params: { company_id: companyId }
  });
  return response.data;
}

export async function listCustomFields(companyId?: string): Promise<CustomField[]> {
  const params = companyId ? { company_id: companyId } : undefined;
  const response = await apiClient.get<CustomField[]>(BASE, { params });
  return response.data;
}

export async function createCustomField(payload: CustomFieldCreate): Promise<CustomField> {
  const response = await apiClient.post<CustomField>(BASE, payload);
  return response.data;
}

export async function updateCustomField(
  id: string,
  payload: CustomFieldUpdate
): Promise<CustomField> {
  const response = await apiClient.patch<CustomField>(`${BASE}/${id}`, payload);
  return response.data;
}

export async function deleteCustomField(id: string): Promise<void> {
  await apiClient.delete(`${BASE}/${id}`);
}

// ---------------------------------------------------------------------------
// 内置字段覆盖（公司级：label / 识别关键词 / 规则类型）
// ---------------------------------------------------------------------------

export interface BuiltinFieldOverride {
  id: string;
  company_id: string;
  field_key: string;
  label_override: string | null;
  header_keywords_override: string[] | null;
  type_override: 'text' | 'amount' | 'date' | 'enum' | null;
}

export interface BuiltinOverrideUpsert {
  company_id: string;
  field_key: string;
  label_override?: string | null;
  header_keywords_override?: string[] | null;
  type_override?: 'text' | 'amount' | 'date' | 'enum' | null;
}

/** upsert 内置字段覆盖（field_key 必须是内置字段）。返回公司级覆盖列表。 */
export async function listBuiltinOverrides(companyId: string): Promise<BuiltinFieldOverride[]> {
  const response = await apiClient.get<BuiltinFieldOverride[]>(`${BASE}/builtin-overrides`, {
    params: { company_id: companyId }
  });
  return response.data;
}

export async function upsertBuiltinOverride(
  payload: BuiltinOverrideUpsert
): Promise<BuiltinFieldOverride> {
  const response = await apiClient.put<BuiltinFieldOverride>(
    `${BASE}/builtin-overrides/${payload.field_key}`,
    payload
  );
  return response.data;
}

/** 删除覆盖即恢复内置默认。 */
export async function deleteBuiltinOverride(
  fieldKey: string,
  companyId: string
): Promise<void> {
  await apiClient.delete(`${BASE}/builtin-overrides/${fieldKey}`, {
    params: { company_id: companyId }
  });
}

/**
 * 供编辑器下拉使用的字段选项 + 类型映射，运行时从后端拉取（含公司扩展字段）。
 *
 * 返回 {
 *   options:  [{value,label}]  —— 注入 MappingEditor/RuleEditor/DetectResultView 的 standardFieldOptions
 *   typeMap:  {key→type}       —— 注入 RuleEditor 的 fieldTypeMap（条件操作符智能过滤）
 *   loading
 * }
 * 失败时回退到内置字段（由组件自身默认值兜底），不阻断页面。
 */
export interface StandardFieldOptionsState {
  options: { value: string; label: string }[];
  typeMap: Record<string, string>;
  loading: boolean;
}

export function standardFieldOptionsFromSchema(
  schema: StandardSchema | null
): { options: { value: string; label: string }[]; typeMap: Record<string, string> } {
  if (!schema) return { options: [], typeMap: {} };
  const options = schema.fields.map((f) => ({ value: f.key, label: f.label }));
  const typeMap: Record<string, string> = {};
  for (const f of schema.fields) typeMap[f.key] = f.type;
  return { options, typeMap };
}

