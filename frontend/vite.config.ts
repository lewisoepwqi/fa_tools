/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  // vitest 单元测试：只扫 src/ 下的 *.test/*.spec，
  // 排除 tests/（Playwright e2e，由 `npm run e2e` 运行）。
  // 暂无单测时不报错，待补充时直接在 src 下新增即可。
  // 写组件测试时需把 environment 改为 'jsdom' 并安装 jsdom。
  test: {
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['tests/**', 'node_modules/**', 'dist/**'],
    passWithNoTests: true,
  },
});
