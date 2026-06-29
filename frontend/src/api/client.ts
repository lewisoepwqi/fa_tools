import axios from 'axios';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
});

// ── Token 存取 ──────────────────────────────────────────────────────────────

const TOKEN_KEY = 'fa_token';

/** 读取本地存储的 JWT。 */
export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY);

/** 写入（传 null 则清除）JWT。 */
export const setToken = (t: string | null): void => {
  if (t) {
    localStorage.setItem(TOKEN_KEY, t);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
};

// ── 请求拦截：注入 Authorization ────────────────────────────────────────────

apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * 统一把后端错误转成可读文本，挂到 err.message。
 *
 * FastAPI 的 422 校验错误形如：
 *   { "detail": [ { "type": "missing", "loc": ["body","version","amount_mode"], "msg": "Field required" } ] }
 * 各页面 `message.error(err instanceof Error ? err.message : '...')` 即可显示真实原因，
 * 而不是一句笼统的"创建失败"，便于诊断字段缺失类问题。
 */
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // 401 未鉴权：清除 token 并跳转到登录页（避免无限重定向）
    if (error?.response?.status === 401) {
      setToken(null);
      if (window.location.pathname !== '/login') {
        window.location.assign('/login');
      }
    }

    // 把后端错误转成可读文本，挂到 err.message（保留原有逻辑）
    const detail = error?.response?.data?.detail;
    let message: string;
    if (Array.isArray(detail) && detail.length > 0) {
      // Pydantic 校验错误列表：拼成 "amount_mode: Field required" 这种可读形式
      message = detail
        .map((item: { loc?: unknown[]; msg?: string }) => {
          const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : 'field';
          return `${field}: ${item.msg ?? 'invalid'}`;
        })
        .join('；');
    } else if (typeof detail === 'string' && detail.length > 0) {
      message = detail;
    } else if (error?.response?.statusText) {
      message = `${error.response.status} ${error.response.statusText}`;
    } else {
      message = error?.message ?? '请求失败';
    }
    return Promise.reject(new Error(message));
  }
);
