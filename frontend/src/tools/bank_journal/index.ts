import { FileTextOutlined } from '@ant-design/icons';
import type { Tool } from '../registry';
import { BankJournalRoutes } from './routes';

/**
 * 银行流水转公司日记账工具的自描述注册项。
 * 平台 registry 据此动态挂载菜单与路由，新增工具时只需在 registry 注册一项。
 */
export const bankJournalTool: Tool = {
  id: 'bank-journal',
  label: '流水转日记账',
  icon: FileTextOutlined,
  /** 工具路由前缀，所有该工具的页面挂在此命名空间下。 */
  basePath: '/bank-journal',
  /** 工具落地页（菜单点击后跳转的第一个页面）。 */
  menuTarget: '/bank-journal',
  /** 该工具的路由树（以 basePath 为挂载点）。 */
  Routes: BankJournalRoutes
};
