import { Tag } from 'antd';

export function VersionBadge({ version }: { version: number | string }) {
  return <Tag color="blue">v{version}</Tag>;
}
