import { Tag } from 'antd';

/**
 * 状态标签 — 统一品牌色语义。
 * 品牌红/蓝来自集团 VI，正向状态（已确认/启用）用蓝，警示（待确认）用红浅，
 * 异常（冲突/失败）用红，停用/忽略用中性。
 */
const STATUS_MAP: Record<string, { color: string; label: string }> = {
  // 转换预览行状态
  needs_confirmation: { color: '#cc4f58', label: '待确认' },
  auto_confirmed: { color: '#133f8e', label: '已自动确认' },
  manually_confirmed: { color: '#133f8e', label: '已人工确认' },
  conflict: { color: '#b5141d', label: '有冲突' },
  parse_failed: { color: '#b5141d', label: '解析失败' },
  ignored: { color: 'default', label: '已忽略' },
  // 模板 / 规则 / 映射 生命周期状态
  active: { color: '#133f8e', label: '启用' },
  inactive: { color: 'default', label: '停用' },
  draft: { color: '#cc4f58', label: '草稿' }
};

export function StatusTag({ status }: { status: string }) {
  const entry = STATUS_MAP[status] ?? { color: 'default', label: status };
  return <Tag color={entry.color}>{entry.label}</Tag>;
}
