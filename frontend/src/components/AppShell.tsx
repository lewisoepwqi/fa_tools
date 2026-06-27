import { AuditOutlined } from '@ant-design/icons';
import { Layout, Menu, Typography } from 'antd';
import type { MenuProps } from 'antd';
import type { ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { registry } from '../tools/registry';

const { Header, Sider, Content } = Layout;

interface AppShellProps {
  children: ReactNode;
}

type MenuItem = Required<MenuProps>['items'][number];

/** 根据当前 URL 路径派生侧边栏选中项，使工具子路由（如 /bank-journal/runs/123）也高亮对应菜单。 */
function activeKeyFromPathname(pathname: string): string {
  const tool = registry.find((t) => pathname === t.basePath || pathname.startsWith(`${t.basePath}/`));
  if (tool) return tool.id;
  if (pathname.startsWith('/audit')) return 'audit';
  return registry[0]?.id ?? 'audit';
}

export function AppShell({ children }: AppShellProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const activeKey = activeKeyFromPathname(location.pathname);

  // 工具菜单项从 registry 动态生成 + 平台固定项（审计日志）。
  const items: MenuItem[] = [
    ...registry.map<MenuItem>((tool) => ({
      key: tool.id,
      icon: <tool.icon />,
      label: tool.label
    })),
    { key: 'audit', icon: <AuditOutlined />, label: '审计日志' }
  ];

  const handleClick: MenuProps['onClick'] = ({ key }) => {
    if (key === 'audit') {
      navigate('/audit');
      return;
    }
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
