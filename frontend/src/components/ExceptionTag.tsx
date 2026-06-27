import { Tag } from 'antd';

const EXCEPTION_LABELS: Record<string, string> = {
  MISSING_REQUIRED_FIELD: '缺少必填字段',
  NO_RULE_MATCH: '无规则匹配',
  RULE_CONFLICT: '规则冲突'
};

export function ExceptionTag({ code }: { code: string }) {
  return <Tag color="red">{EXCEPTION_LABELS[code] ?? code}</Tag>;
}
