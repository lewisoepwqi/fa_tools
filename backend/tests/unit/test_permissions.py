from app.core.permissions import (
    CROSS_COMPANY_ROLES,
    ROLE_PERMISSIONS,
    Permission,
    permissions_for,
)


def test_all_five_roles_present():
    assert set(ROLE_PERMISSIONS) == {
        "admin",
        "template_admin",
        "processor",
        "reviewer",
        "auditor",
    }


def test_admin_has_all_permissions():
    assert ROLE_PERMISSIONS["admin"] == set(Permission)


def test_auditor_is_read_only():
    assert ROLE_PERMISSIONS["auditor"] == {Permission.READ, Permission.AUDIT_VIEW}


def test_permissions_for_unions_roles():
    perms = permissions_for(["processor", "auditor"])
    assert Permission.CONVERSION_PROCESS in perms
    assert Permission.AUDIT_VIEW in perms


def test_permissions_for_ignores_unknown_role():
    assert permissions_for(["nope"]) == set()


def test_cross_company_roles():
    assert CROSS_COMPANY_ROLES == frozenset({"admin", "auditor"})
