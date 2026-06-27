import { Button, Card, Space, Typography } from 'antd';
import { AppShell } from './components/AppShell';

export default function App() {
  return (
    <AppShell>
      <Card className="work-card">
        <Space direction="vertical" size={16}>
          <Typography.Title level={3}>流水上传</Typography.Title>
          <Typography.Text>上传银行流水，生成公司日记账预览。</Typography.Text>
          <Button type="primary">选择文件</Button>
        </Space>
      </Card>
    </AppShell>
  );
}
