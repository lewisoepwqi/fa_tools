import { AuditOutlined } from '@ant-design/icons';
import { Layout, Menu, Typography } from 'antd';
import type { MenuProps } from 'antd';
import type { ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { registry, type ToolMenuItem } from '../tools/registry';

const { Header, Sider, Content } = Layout;

interface AppShellProps {
  children: ReactNode;
}

type MenuItem = Required<MenuProps>['items'][number];

const AUDIT_KEY = 'audit';

/**
 * 把工具的 children 展平成 key→target 查找表，供菜单点击跳转用。
 */
function buildChildTargetMap(): Record<string, string> {
  const map: Record<string, string> = {};
  for (const tool of registry) {
    for (const child of tool.children ?? []) {
      map[child.key] = child.target;
    }
  }
  return map;
}

const CHILD_TARGETS = buildChildTargetMap();

/**
 * 收集所有子菜单项（key + target），用于按当前路径反查应高亮的 key。
 */
function collectAllChildren(): ToolMenuItem[] {
  return registry.flatMap((tool) => tool.children ?? []);
}

const ALL_CHILDREN = collectAllChildren();

/**
 * 根据当前 URL 路径派生侧边栏选中 key。
 * 规则：找 target 是 pathname 前缀的最长子菜单项（如 /bank-journal/runs/123 → bank-journal:runs）。
 * 平台审计页 → audit。无匹配 → 第一个子菜单（或第一个工具）。
 */
function activeKeyFromPathname(pathname: string): string {
  if (pathname.startsWith('/audit')) return AUDIT_KEY;

  // 优先精确匹配 target，其次前缀匹配（处理详情页等深层路径）
  const exact = ALL_CHILDREN.find((c) => pathname === c.target);
  if (exact) return exact.key;

  const prefixMatch = ALL_CHILDREN
    .filter((c) => pathname.startsWith(`${c.target}/`))
    .sort((a, b) => b.target.length - a.target.length)[0];
  if (prefixMatch) return prefixMatch.key;

  // 工具根路径（/bank-journal）且无 children 精确命中时，回落到首个子菜单
  return ALL_CHILDREN[0]?.key ?? registry[0]?.id ?? AUDIT_KEY;
}

export function AppShell({ children }: AppShellProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const activeKey = activeKeyFromPathname(location.pathname);

  // 工具菜单项从 registry 动态生成 + 平台固定项（审计日志）。
  const items: MenuItem[] = [
    ...registry.map<MenuItem>((tool) => {
      if (tool.children && tool.children.length > 0) {
        // 带子菜单：渲染为可展开父菜单
        return {
          key: tool.id,
          icon: <tool.icon />,
          label: tool.label,
          children: tool.children.map((child) => ({
            key: child.key,
            label: child.label
          }))
        };
      }
      // 无子菜单：单层叶子项
      return { key: tool.id, icon: <tool.icon />, label: tool.label };
    }),
    { key: AUDIT_KEY, icon: <AuditOutlined />, label: '审计日志' }
  ];

  const handleClick: MenuProps['onClick'] = ({ key }) => {
    if (key === AUDIT_KEY) {
      navigate('/audit');
      return;
    }
    // 子菜单项：按 key 查 target
    if (CHILD_TARGETS[key]) {
      navigate(CHILD_TARGETS[key]);
      return;
    }
    // 父菜单项：跳工具落地页
    const tool = registry.find((t) => t.id === key);
    if (tool) navigate(tool.menuTarget);
  };

  return (
    <Layout className="app-shell">
      <Sider width={232} className="app-sider">
        <Typography.Title level={4} className="app-title">FA Tools</Typography.Title>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[activeKey]}
          // 父菜单默认展开（子菜单选中时其父项也展开）
          defaultOpenKeys={registry.filter((t) => t.children).map((t) => t.id)}
          onClick={handleClick}
          items={items}
        />
      </Sider>
      <Layout>
        <Header className="app-header">财务自动化工具包</Header>
        <Content className="app-content">{children}</Content>
      </Layout>
    </Layout>
  );
}
