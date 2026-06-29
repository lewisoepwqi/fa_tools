import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from './useAuth';

/** 路由守卫：未登录跳转 /login；初始化中返回 null 避免闪烁。 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { me, ready } = useAuth();

  // 正在从 token 恢复会话，等待完成再决策（避免未认证跳转闪烁）
  if (!ready) return null;

  if (!me) return <Navigate to="/login" replace />;

  return <>{children}</>;
}
