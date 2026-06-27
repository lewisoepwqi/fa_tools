import type { ComponentType } from 'react';

import { bankJournalTool } from './bank_journal';

/**
 * 工具内子菜单项（侧边栏父菜单展开后的叶子项）。
 */
export interface ToolMenuItem {
  /** 全局唯一 key（建议形如 <toolId>:<segment>）。 */
  key: string;
  /** 显示名。 */
  label: string;
  /** 点击后跳转的路径。 */
  target: string;
}

/**
 * 一个财务工具的自描述注册项。
 *
 * 平台 AppShell 据此动态渲染侧边栏菜单，App 据此动态挂载路由。
 * 新增工具：在 src/tools/<name>/index.ts 导出一个 Tool，并加入下方 registry 数组。
 */
export interface Tool {
  /** 工具唯一标识（用于菜单 key 等）。 */
  id: string;
  /** 侧边栏菜单显示名。 */
  label: string;
  /** 菜单图标。 */
  icon: ComponentType;
  /** 工具路由前缀，所有该工具的页面挂在此命名空间下（如 /bank-journal）。 */
  basePath: string;
  /** 点击父菜单项后跳转的目标路径。 */
  menuTarget: string;
  /** 该工具的路由树（挂载在 basePath 下）。 */
  Routes: ComponentType;
  /**
   * 可选子菜单。提供时侧边栏渲染为可展开的父菜单 + 叶子项；
   * 不提供则渲染为单层叶子菜单项。
   */
  children?: ToolMenuItem[];
}

/**
 * 已注册的工具列表。新增工具时在此追加。
 * 第一个工具作为根路径 / 的默认重定向目标。
 */
export const registry: Tool[] = [bankJournalTool];
