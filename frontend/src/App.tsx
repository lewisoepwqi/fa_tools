import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { RequireAuth } from './auth/RequireAuth';
import { LoginPage } from './pages/LoginPage';
import { AuditLogPage } from './pages/AuditLogPage';
import { registry } from './tools/registry';

/**
 * 根路由。
 * - /login  → 登录页（无 AppShell，无鉴权守卫）
 * - /*      → RequireAuth 守卫 → AppShell → 工具路由 + 审计路由
 *
 * 第一个工具作为根路径 / 的默认落地页。
 */
export default function App() {
  const defaultTool = registry[0];
  return (
    <Routes>
      {/* 登录页：不走 AppShell，不需要鉴权 */}
      <Route path="/login" element={<LoginPage />} />

      {/* 受保护区域：未登录跳 /login */}
      <Route
        path="/*"
        element={
          <RequireAuth>
            <AppShell>
              <Routes>
                <Route path="/" element={<Navigate to={defaultTool.menuTarget} replace />} />
                {registry.map((tool) => (
                  <Route key={tool.id} path={`${tool.basePath}/*`} element={<tool.Routes />} />
                ))}
                <Route path="/audit" element={<AuditLogPage />} />
              </Routes>
            </AppShell>
          </RequireAuth>
        }
      />
    </Routes>
  );
}
