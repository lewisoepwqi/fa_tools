import { Tag } from 'antd';

/** 版本徽标 — 品牌红点睛，体现版本追溯。 */
export function VersionBadge({ version }: { version: number | string }) {
  return (
    <Tag color="#b5141d" style={{ marginInlineEnd: 0 }}>
      v{version}
    </Tag>
  );
}
