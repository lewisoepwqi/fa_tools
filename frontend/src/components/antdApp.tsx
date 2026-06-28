import { App as AntdApp, message as staticMessage } from 'antd';
import type { MessageInstance } from 'antd/es/message/interface';
import { useLayoutEffect, type ReactNode } from 'react';

/**
 * 全局 message 实例代理。
 *
 * antd v5 中静态 `message.xxx()` 无法消费 ConfigProvider 的动态主题，会报警告：
 *   "Static function can not consume context like dynamic theme."
 * 正确做法是用 `App.useApp()` 拿到的实例。但项目里大量页面直接 `import { message } from 'antd'`，
 * 全量改造为 hook 成本高、且 message 多在事件回调里调用（不在渲染期）。
 *
 * 折中方案：在根挂一个 <AntdApp>，由内部的 MessageBridge 把 useApp() 拿到的实例
 * 写到模块级变量；本模块导出一个静态 `message`，转发到当前实例。调用点把
 * `import { message } from 'antd'` 改成 `import { message } from '../components/antdApp'`
 * 即可（API 完全一致），既消除警告又保留原有调用写法。
 *
 * provider 在 main.tsx 早于业务渲染挂载，故实例总会先于任何业务 message 调用就绪；
 * 极端情况下（provider 未就绪）退化为 antd 原生静态 message（仍可用，仅丢主题）。
 */
let messageInstance: MessageInstance | null = null;

/**
 * 兼容 antd `message` API 的静态代理：转发到 useApp() 实例；
 * 实例未就绪时退化为 antd 原生静态 message。
 */
export const message = new Proxy({} as MessageInstance, {
  get(_target, prop: string) {
    const target = messageInstance ?? staticMessage;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const fn = (target as any)[prop];
    return typeof fn === 'function' ? fn.bind(target) : fn;
  }
});

/** 在 <AntdApp> 内部把 useApp() 的 message 同步到模块级变量。 */
function MessageBridge() {
  const { message } = AntdApp.useApp();
  // 用 useLayoutEffect 在浏览器绘制前写入，确保业务回调触发时实例已就绪。
  useLayoutEffect(() => {
    messageInstance = message;
  }, [message]);
  return null;
}

export function AntdAppProvider({ children }: { children: ReactNode }) {
  return (
    <AntdApp>
      <MessageBridge />
      {children}
    </AntdApp>
  );
}
