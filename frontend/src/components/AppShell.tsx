import { AuditOutlined, FileTextOutlined, SettingOutlined, UploadOutlined } from '@ant-design/icons';
import { Layout, Menu, Typography } from 'antd';
import type { ReactNode } from 'react';

const { Header, Sider, Content } = Layout;

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <Layout className="app-shell">
      <Sider width={232} className="app-sider">
        <Typography.Title level={4} className="app-title">FA Tools</Typography.Title>
        <Menu
          theme="dark"
          mode="inline"
          defaultSelectedKeys={['upload']}
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
