import { AuditOutlined, FileTextOutlined, SettingOutlined, UploadOutlined } from '@ant-design/icons';
import { Layout, Menu, Typography } from 'antd';
import type { ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

const { Header, Sider, Content } = Layout;

interface AppShellProps {
  children: ReactNode;
}

/** 根据当前 URL 路径派生侧边栏选中项，使详情页（如 /runs/:id）也高亮对应菜单。 */
function activeKeyFromPathname(pathname: string): string {
  if (pathname.startsWith('/runs')) return 'runs';
  if (pathname.startsWith('/templates')) return 'templates';
  if (pathname.startsWith('/audit')) return 'audit';
  return 'upload';
}

const MENU_TARGETS: Record<string, string> = {
  upload: '/',
  runs: '/runs',
  templates: '/templates',
  audit: '/audit'
};

export function AppShell({ children }: AppShellProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const activeKey = activeKeyFromPathname(location.pathname);

  return (
    <Layout className="app-shell">
      <Sider width={232} className="app-sider">
        <Typography.Title level={4} className="app-title">FA Tools</Typography.Title>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[activeKey]}
          onClick={({ key }) => navigate(MENU_TARGETS[key] ?? '/')}
          items={[
            { key: 'upload', icon: <UploadOutlined />, label: '流水上传' },
            { key: 'runs', icon: <FileTextOutlined />, label: '处理批次' },
            { key: 'templates', icon: <SettingOutlined />, label: '模板规则' },
            { key: 'audit', icon: <AuditOutlined />, label: '审计日志' }
          ]}
        />
      </Sider>
      <Layout>
        <Header className="app-header">银行流水转日记账</Header>
        <Content className="app-content">{children}</Content>
      </Layout>
    </Layout>
  );
}
