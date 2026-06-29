/**
 * 镜像后端角色→权限映射（backend/app/core/enums.py Role → Permission）。
 * 权限值与后端 Permission enum value 完全一致，修改时需同步后端。
 */
const ROLE_PERMS: Record<string, string[]> = {
  admin: [
    'company_manage',
    'user_manage',
    'template_manage',
    'conversion_process',
    'conversion_confirm',
    'export_run',
    'rule_approve',
    'audit_view',
    'read',
  ],
  template_admin: ['read', 'template_manage'],
  processor: ['read', 'conversion_process', 'conversion_confirm', 'export_run'],
  reviewer: ['read', 'conversion_confirm', 'rule_approve', 'audit_view'],
  auditor: ['read', 'audit_view'],
};

/** 合并多个角色对应的权限集合。 */
export function permissionsForRoles(roles: string[]): Set<string> {
  const s = new Set<string>();
  roles.forEach((r) => (ROLE_PERMS[r] ?? []).forEach((p) => s.add(p)));
  return s;
}
