/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  build: {
    // antd 全量引入后其 vendor chunk gzip ≈ 306KB（原始 ≈ 984KB），属该库的固有
    // 体积而非业务代码膨胀。把警告阈值提到 1000kB：仅在业务代码或异常组合
    // 超出时才告警，避免对稳定的第三方 vendor 产生持续噪音。
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        // 把体积大的第三方依赖拆成独立 chunk，避免单个 bundle 超过 500kB
        // 警告（antd 体积大但稳定，单列一 chunk 利于浏览器长缓存）。
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          antd: ['antd', '@ant-design/icons'],
        },
      },
    },
  },
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
