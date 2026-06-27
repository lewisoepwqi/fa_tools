/** 规则类型（对齐后端 app/schemas/rule.py）。 */

export interface RuleVersion {
  version_no: number;
  priority?: number | null;
  conditions_json?: Record<string, unknown> | null;
  actions_json?: Record<string, unknown> | null;
  allow_auto_confirm: boolean;
  created_by?: string | null;
}

export interface Rule {
  id: string;
  company_id: string;
  name: string;
  scope_type?: string | null;
  scope_id?: string | null;
  status: string;
  latest_version: RuleVersion;
}
