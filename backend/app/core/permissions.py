from __future__ import annotations

from enum import StrEnum


class Permission(StrEnum):
    COMPANY_MANAGE = "company_manage"
    USER_MANAGE = "user_manage"
    TEMPLATE_MANAGE = "template_manage"
    CONVERSION_PROCESS = "conversion_process"
    CONVERSION_CONFIRM = "conversion_confirm"
    EXPORT_RUN = "export_run"
    RULE_APPROVE = "rule_approve"
    AUDIT_VIEW = "audit_view"
    READ = "read"


ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "admin": set(Permission),
    "template_admin": {Permission.READ, Permission.TEMPLATE_MANAGE},
    "processor": {
        Permission.READ,
        Permission.CONVERSION_PROCESS,
        Permission.CONVERSION_CONFIRM,
        Permission.EXPORT_RUN,
    },
    "reviewer": {
        Permission.READ,
        Permission.CONVERSION_CONFIRM,
        Permission.RULE_APPROVE,
        Permission.AUDIT_VIEW,
    },
    "auditor": {Permission.READ, Permission.AUDIT_VIEW},
}

CROSS_COMPANY_ROLES: frozenset[str] = frozenset({"admin", "auditor"})


def permissions_for(roles: list[str]) -> set[Permission]:
    perms: set[Permission] = set()
    for role in roles:
        perms |= ROLE_PERMISSIONS.get(role, set())
    return perms
