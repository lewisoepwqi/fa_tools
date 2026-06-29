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
  Routes: BankJournalRoutes,
  /** 有 read 权限的登录用户均可见工具入口。 */
  requiredPermission: 'read',
  /** 子菜单：覆盖工具内部主要功能区，侧边栏可展开直达。 */
  children: [
    /** 流水上传属于转换动作入口，需 conversion_process 权限。 */
    { key: 'bank-journal:upload', label: '流水上传', target: '/bank-journal', requiredPermission: 'conversion_process' },
    /** 批次列表为只读浏览，reviewer/auditor 均可查看，用 read 权限。 */
    { key: 'bank-journal:runs', label: '处理批次', target: '/bank-journal/runs', requiredPermission: 'read' },
    /** 模板/映射/规则配置入口，需 template_manage 权限。 */
    { key: 'bank-journal:templates', label: '模板规则', target: '/bank-journal/templates', requiredPermission: 'template_manage' }
  ]
};
