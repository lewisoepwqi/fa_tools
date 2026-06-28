import axios from 'axios';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
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
