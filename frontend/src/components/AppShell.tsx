import { AuditOutlined, MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons';
import { Button, Layout, Menu } from 'antd';
import type { MenuProps } from 'antd';
import { useState, type ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { registry, type ToolMenuItem } from '../tools/registry';

const { Header, Sider, Content } = Layout;

interface AppShellProps {
  children: ReactNode;
}

type MenuItem = Required<MenuProps>['items'][number];

const AUDIT_KEY = 'audit';

/** 展平工具 children 为 key→target 查找表。 */
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
const ALL_CHILDREN: ToolMenuItem[] = registry.flatMap((t) => t.children ?? []);

/** 选中态：精确匹配优先，其次最长前缀匹配（详情页也能高亮父级）。 */
function activeKeyFromPathname(pathname: string): string {
  if (pathname.startsWith('/audit')) return AUDIT_KEY;
  const exact = ALL_CHILDREN.find((c) => pathname === c.target);
  if (exact) return exact.key;
  const prefix = ALL_CHILDREN
    .filter((c) => pathname.startsWith(`${c.target}/`))
    .sort((a, b) => b.target.length - a.target.length)[0];
  if (prefix) return prefix.key;
  return ALL_CHILDREN[0]?.key ?? registry[0]?.id ?? AUDIT_KEY;
}

/** 派生面包屑：工具名 / 子页名（用于 Header 上下文栏）。 */
function breadcrumbs(pathname: string): { tool: string; crumb: string } {
  if (pathname.startsWith('/audit')) return { tool: '审计', crumb: '审计日志' };
  const tool = registry.find(
    (t) => pathname === t.basePath || pathname.startsWith(`${t.basePath}/`)
  );
  if (!tool) return { tool: '', crumb: '' };
  const child = ALL_CHILDREN.find(
    (c) => pathname === c.target || pathname.startsWith(`${c.target}/`)
  );
  return { tool: tool.label, crumb: child?.label ?? '' };
}

export function AppShell({ children }: AppShellProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const activeKey = activeKeyFromPathname(location.pathname);
  const { tool, crumb } = breadcrumbs(location.pathname);

  const items: MenuItem[] = [
    ...registry.map<MenuItem>((t) =>
      t.children && t.children.length > 0
        ? {
            key: t.id,
            icon: <t.icon />,
            label: t.label,
            children: t.children.map((c) => ({ key: c.key, label: c.label }))
          }
        : { key: t.id, icon: <t.icon />, label: t.label }
    ),
    { key: AUDIT_KEY, icon: <AuditOutlined />, label: '审计日志' }
  ];

  const handleClick: MenuProps['onClick'] = ({ key }) => {
    if (key === AUDIT_KEY) return navigate('/audit');
    if (CHILD_TARGETS[key]) return navigate(CHILD_TARGETS[key]);
    const tool = registry.find((t) => t.id === key);
    if (tool) navigate(tool.menuTarget);
  };

  return (
    <Layout className="app-shell">
      <Sider
        className="app-sider"
        width={232}
        collapsible
        collapsed={collapsed}
        trigger={null}
      >
        <div className="app-brand">
          <span className="app-brand-mark">
            FA<span className="accent">·</span>Tools
          </span>
          {!collapsed && <span className="app-brand-sub">财务自动化</span>}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[activeKey]}
          defaultOpenKeys={registry.filter((t) => t.children).map((t) => t.id)}
          onClick={handleClick}
          items={items}
        />
      </Sider>
      <Layout>
        <Header className="app-header">
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed((c) => !c)}
            style={{ marginRight: 16 }}
          />
          <span className="app-header-bread">
            {tool && (
              <>
                <span className="crumb-muted">{tool}</span>
                {crumb && <span className="sep">/</span>}
              </>
            )}
            {crumb && <span>{crumb}</span>}
          </span>
        </Header>
        <Content className="app-content">{children}</Content>
      </Layout>
    </Layout>
  );
}
