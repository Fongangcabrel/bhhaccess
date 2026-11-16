"""RBAC catalogue: the 23 atomic actions and the default role bundles.

Roles are *templates*; a user's effective rights = role bundle + per-user overrides.
"""
from enum import StrEnum


class Permission(StrEnum):
    EMPLOYEES_VIEW = "employees.view"
    EMPLOYEES_EDIT = "employees.edit"
    EMPLOYEES_IMPORT = "employees.import"
    EMPLOYEES_ARCHIVE = "employees.archive"
    BADGES_ISSUE = "badges.issue"
    BADGES_REVOKE = "badges.revoke"
    ZONES_VIEW = "zones.view"
    ZONES_MANAGE = "zones.manage"
    ZONES_ANTIPASSBACK = "zones.antipassback"
    AUTHORIZATIONS_MANAGE = "authorizations.manage"
    SCAN_PERFORM = "scan.perform"
    SCAN_MANUAL = "scan.manual"
    SCAN_HISTORY = "scan.history"
    PRESENCE_UNBLOCK = "presence.unblock"
    LOGS_VIEW = "logs.view"
    REPORTS_VIEW = "reports.view"
    AUDIT_VIEW = "audit.view"
    DATA_EXPORT = "data.export"
    DATA_PURGE = "data.purge"
    USERS_MANAGE = "users.manage"
    ROLES_ASSIGN = "roles.assign"
    ROLES_MANAGE = "roles.manage"
    SYSTEM_CONFIG = "system.config"


# Only the super admin holds these four by default.
ADMIN_ONLY: frozenset[Permission] = frozenset(
    {Permission.USERS_MANAGE, Permission.ROLES_ASSIGN, Permission.ROLES_MANAGE, Permission.SYSTEM_CONFIG}
)

_ALL = frozenset(Permission)

DEFAULT_ROLES: dict[str, dict] = {
    "super_admin": {"label": "Super admin", "permissions": _ALL},
    "super_user": {"label": "Super user", "permissions": _ALL - ADMIN_ONLY},
    "rh": {
        "label": "RH",
        "permissions": frozenset(
            {
                Permission.EMPLOYEES_VIEW,
                Permission.EMPLOYEES_EDIT,
                Permission.EMPLOYEES_IMPORT,
                Permission.BADGES_ISSUE,
                Permission.BADGES_REVOKE,
                Permission.ZONES_VIEW,
                Permission.AUTHORIZATIONS_MANAGE,
                Permission.LOGS_VIEW,
                Permission.REPORTS_VIEW,
                Permission.AUDIT_VIEW,
                Permission.DATA_EXPORT,
                Permission.DATA_PURGE,
            }
        ),
    },
    "agent": {
        "label": "Agent",
        "permissions": frozenset(
            {Permission.ZONES_VIEW, Permission.SCAN_PERFORM, Permission.SCAN_MANUAL, Permission.SCAN_HISTORY}
        ),
    },
}
