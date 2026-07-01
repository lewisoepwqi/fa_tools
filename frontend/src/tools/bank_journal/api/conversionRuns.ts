import { apiClient } from '../../../api/client';
import type {
  ConversionRunListItem,
  ConversionRunResponse
} from '../types/conversion';
import type { Page } from '../types/pagination';

export async function listConversionRuns(
  params?: { limit?: number; offset?: number; company_id?: string }
): Promise<Page<ConversionRunListItem>> {
  const response = await apiClient.get<Page<ConversionRunListItem>>(
    '/api/tools/bank-journal/conversion-runs',
    { params }
  );
  return response.data;
}

export async function getConversionRun(runId: string): Promise<ConversionRunResponse> {
  const response = await apiClient.get<ConversionRunResponse>(`/api/tools/bank-journal/conversion-runs/${runId}`);
  return response.data;
}

/**
 * P0：用已配置的版本化模板/映射/规则驱动转换（真正读取用户配置）。
 */
export interface SourceFileRef {
  /** 源文件 ID。 */
  file_id: string;
  /** 该文件本次使用的工作表名（xlsx 多 sheet 时由用户逐文件选择）。 */
  sheet_name: string;
}

export interface ConversionRunFromConfigPayload {
  company_id: string;
  source_file_ids: string[];
  bank_template_id?: string;
  company_journal_template_id?: string;
  mapping_profile_id?: string;
  rule_ids?: string[];
  /** 每文件可选的工作表覆盖。缺省时由后端按模板默认/文件首个 sheet 解析。 */
  source_files?: SourceFileRef[];
}

export async function createConversionRunFromConfig(
  payload: ConversionRunFromConfigPayload
): Promise<ConversionRunResponse> {
  const response = await apiClient.post<ConversionRunResponse>(
    '/api/tools/bank-journal/conversion-runs/from-config',
    {
      company_id: payload.company_id,
      bank_account_id: 'bank-account-1',
      source_file_ids: payload.source_file_ids,
      bank_template_id: payload.bank_template_id,
      company_journal_template_id: payload.company_journal_template_id,
      mapping_profile_id: payload.mapping_profile_id,
      rule_ids: payload.rule_ids ?? [],
      ...(payload.source_files && payload.source_files.length > 0
        ? { source_files: payload.source_files }
        : {})
    }
  );
  return response.data;
}

/** P3：试跑结果（不落库）。 */
export interface DryRunResponse {
  summary: { total_rows: number; parse_failed_rows: number };
  preview_rows: Array<{
    row_index: number;
    output_values: Record<string, unknown>;
    status: string;
    exception_codes: string[];
    matched_rule_version_ids: string[];
  }>;
}

/**
 * P3：试跑——用配置解析样本文件并返回前 N 行预览，但不创建批次。
 * 供保存配置前即时验证效果。
 */
export async function dryRunConversion(
  payload: ConversionRunFromConfigPayload & { limit?: number }
): Promise<DryRunResponse> {
  const response = await apiClient.post<DryRunResponse>(
    '/api/tools/bank-journal/conversion-runs/dry-run',
    {
      company_id: payload.company_id,
      bank_account_id: 'bank-account-1',
      source_file_ids: payload.source_file_ids,
      bank_template_id: payload.bank_template_id,
      company_journal_template_id: payload.company_journal_template_id,
      mapping_profile_id: payload.mapping_profile_id,
      rule_ids: payload.rule_ids ?? [],
      limit: payload.limit ?? 20,
      ...(payload.source_files && payload.source_files.length > 0
        ? { source_files: payload.source_files }
        : {})
    }
  );
  return response.data;
}
