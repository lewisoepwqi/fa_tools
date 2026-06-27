import { Tag } from 'antd';

const STATUS_MAP: Record<string, { color: string; label: string }> = {
  needs_confirmation: { color: 'orange', label: '待确认' },
  auto_confirmed: { color: 'green', label: '已自动确认' },
  manually_confirmed: { color: 'blue', label: '已人工确认' },
  conflict: { color: 'red', label: '有冲突' },
  parse_failed: { color: 'red', label: '解析失败' },
  ignored: { color: 'default', label: '已忽略' }
};

export function StatusTag({ status }: { status: string }) {
  const entry = STATUS_MAP[status] ?? { color: 'default', label: status };
  return <Tag color={entry.color}>{entry.label}</Tag>;
}
