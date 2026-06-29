import { Button, Card, Form, Input } from 'antd';
import { useNavigate } from 'react-router-dom';
import { message } from '../components/antdApp';
import { useAuth } from '../auth/useAuth';

interface LoginForm {
  email: string;
  password: string;
}

/** 登录页：不含 AppShell，独立全屏展示。 */
export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const onFinish = async (values: LoginForm) => {
    try {
      await login(values.email, values.password);
      // 登录成功后跳转主页（用 react-router navigate 而非 location.assign，避免整页刷新）
      navigate('/', { replace: true });
    } catch {
      void message.error('邮箱或密码错误，请重试');
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f5f5f5',
      }}
    >
      <Card
        title={
          <span style={{ fontWeight: 700, fontSize: 18 }}>
            登录 <span style={{ color: '#b5141d' }}>FA</span>·Tools
          </span>
        }
        style={{ width: 360, boxShadow: '0 4px 24px rgba(0,0,0,0.08)' }}
      >
        <Form<LoginForm> onFinish={onFinish} layout="vertical" autoComplete="on">
          <Form.Item
            name="email"
            label="邮箱"
            rules={[{ required: true, message: '请输入邮箱' }, { type: 'email', message: '邮箱格式不正确' }]}
          >
            <Input autoFocus placeholder="user@example.com" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password placeholder="••••••••" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block style={{ marginTop: 8 }}>
            登录
          </Button>
        </Form>
      </Card>
    </div>
  );
}
