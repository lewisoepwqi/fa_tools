/** 规则类型（对齐后端 app/schemas/rule.py）。 */

export interface RuleVersion {
  version_no: number;
  priority?: number | null;
  conditions_json?: Record<string, unknown> | null;
  actions_json?: Record<string, unknown> | null;
  allow_auto_confirm: boolean;
  created_by?: string | null;
  /** 展示名（后端联表解析，供直接显示，避免裸 ID）。 */
  created_by_name?: string | null;
}

export interface Rule {
  id: string;
  company_id: string;
  company_name?: string | null;
  name: string;
  scope_type?: string | null;
  scope_id?: string | null;
  /** 作用域显示名（按 scope_type 联表解析，避免裸 ID）。 */
  scope_name?: string | null;
  status: string;
  latest_version: RuleVersion;
}
