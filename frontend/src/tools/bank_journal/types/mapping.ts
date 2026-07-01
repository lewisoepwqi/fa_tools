/** 映射方案类型（对齐后端 app/schemas/mapping.py）。 */

export interface MappingProfileVersion {
  version_no: number;
  bank_template_version_id?: string | null;
  company_journal_template_version_id?: string | null;
  mappings_json?: Record<string, unknown> | null;
  created_by?: string | null;
  /** 展示名（后端联表解析，供直接显示，避免裸 ID）。 */
  created_by_name?: string | null;
  bank_template_version_no?: number | null;
  company_journal_template_version_no?: number | null;
}

export interface MappingProfile {
  id: string;
  company_id: string;
  company_name?: string | null;
  name: string;
  bank_template_id?: string | null;
  company_journal_template_id?: string | null;
  status: string;
  latest_version: MappingProfileVersion;
}
