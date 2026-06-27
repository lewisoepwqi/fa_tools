import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { AuditLogPage } from './pages/AuditLogPage';
import { registry } from './tools/registry';

/**
 * 根路由。每个工具的路由树挂在各自 basePath 下；平台共享路由（审计日志）单独挂载。
 * 第一个工具作为根路径 / 的默认落地页。
 */
export default function App() {
  const defaultTool = registry[0];
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to={defaultTool.menuTarget} replace />} />
        {registry.map((tool) => (
          <Route key={tool.id} path={`${tool.basePath}/*`} element={<tool.Routes />} />
        ))}
        <Route path="/audit" element={<AuditLogPage />} />
      </Routes>
    </AppShell>
  );
}
