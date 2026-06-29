import { createContext, useCallback, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { fetchMe, login as apiLogin } from '../api/auth';
import type { Me } from '../api/auth';
import { getToken, setToken } from '../api/client';
import { permissionsForRoles } from './permissions';

/** 鉴权上下文接口。 */
export interface AuthCtx {
  me: Me | null;
  /** 初始化完成（已尝试从 token 恢复会话）。 */
  ready: boolean;
  login: (email: string, pw: string) => Promise<void>;
  logout: () => void;
  hasPermission: (p: string) => boolean;
  /** 当前操作公司 ID（多公司时用户手动切换）。 */
  currentCompanyId: string | null;
  setCurrentCompanyId: (id: string | null) => void;
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthCtx>(null as never);

/** 在应用根部挂载，提供登录态与用户信息。 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);
  const [currentCompanyId, setCurrentCompanyId] = useState<string | null>(null);

  /** 尝试用当前 token 加载用户信息。 */
  const loadMe = useCallback(async () => {
    if (!getToken()) {
      setReady(true);
      return;
    }
    try {
      setMe(await fetchMe());
    } catch {
      // token 失效或网络错误：清空，401 拦截器会跳转 /login
      setMe(null);
    }
    setReady(true);
  }, []);

  // 应用启动时恢复会话
  useEffect(() => {
    void loadMe();
  }, [loadMe]);

  const login = async (email: string, pw: string): Promise<void> => {
    const token = await apiLogin(email, pw);
    setToken(token);
    await loadMe();
  };

  const logout = (): void => {
    setToken(null);
    setMe(null);
    window.location.assign('/login');
  };

  const hasPermission = (p: string): boolean =>
    permissionsForRoles(me?.roles ?? []).has(p);

  return (
    <AuthContext.Provider
      value={{ me, ready, login, logout, hasPermission, currentCompanyId, setCurrentCompanyId }}
    >
      {children}
    </AuthContext.Provider>
  );
}
