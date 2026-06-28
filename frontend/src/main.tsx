import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App';
import { AntdAppProvider } from './components/antdApp';
import { themeConfig } from './theme';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider theme={themeConfig} locale={zhCN}>
      <AntdAppProvider>
        <BrowserRouter
          // 提前 opt-in v7 行为，消除两条升级警告：
          // - v7_startTransition: v7 会把状态更新包进 React.startTransition
          // - v7_relativeSplatPath: v7 改变 splat 路由内相对路径解析规则
          // 本应用路由均为绝对路径（/bank-journal/...），不受 relativeSplatPath 行为影响。
          future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        >
          <App />
        </BrowserRouter>
      </AntdAppProvider>
    </ConfigProvider>
  </React.StrictMode>
);
