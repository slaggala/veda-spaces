"""The permission code registry and seeded role matrix (06 §3, §6, RBAC-008).

Permissions are defined here, in code, and synchronized into ``permission``
by migration (06 §3). The API can never create, delete or reclassify them.
"""

from __future__ import annotations

from dataclasses import dataclass

from veda.modules.catalog import permissions as catalog_permissions
from veda.modules.crm.leads import permissions as lead_permissions
from veda.modules.estimator import permissions as estimate_permissions

from .registry_types import PermissionDef, RoleDef

FOUNDER_WORKFLOW_ONLY = "FOUNDER_WORKFLOW_ONLY"

PLATFORM_PERMISSIONS: tuple[PermissionDef, ...] = (
    # 6.1 self-service
    PermissionDef(
        "profile.read",
        "View own profile",
        "View own profile, MFA status and effective permissions",
        False,
        None,
        "USER-004",
    ),
    PermissionDef(
        "profile.update",
        "Edit own profile",
        "Edit own name, display name, phone, timezone and locale only",
        False,
        None,
        "USER-004",
    ),
    PermissionDef("session.read", "List own sessions", "List own sessions", True, None, "AUTH-016"),
    PermissionDef("session.revoke", "Revoke own sessions", "Revoke own sessions", True, None, "AUTH-016"),
    PermissionDef("notification.read", "Read notifications", "Own notifications", True, None, "NOTIF-001"),
    PermissionDef("lookup.read", "Read reference lists", "Reference lists", False, None, "PLAT-009"),
    # 6.2 users, access and security
    PermissionDef("user.read", "View users", "List and view users", False, None, "USER-001"),
    PermissionDef("user.create", "Invite users", "Invite users and resend invites", False, None, "USER-001"),
    PermissionDef(
        "user.profile.update", "Edit user profiles", "Edit another user's profile fields only", False, None, "RBAC-019"
    ),
    PermissionDef(
        "user.email.change",
        "Change user email",
        "Start the proposed-email workflow for another user",
        False,
        "ACCOUNT_CONTROL",
        "USER-007",
    ),
    PermissionDef(
        "user.status.manage",
        "Manage user status",
        "Deactivate, reactivate or unlock another user",
        False,
        "ACCOUNT_CONTROL",
        "RBAC-019",
    ),
    PermissionDef("user.delete", "Delete users", "Soft-delete a user", False, "ACCOUNT_CONTROL", "USER-001"),
    PermissionDef(
        "user.restore", "Restore users", "Restore a deleted user (returns as DISABLED)", False, None, "USER-001"
    ),
    PermissionDef(
        "user.password.reset",
        "Send password reset",
        "Send a reset link to the user's verified email",
        False,
        None,
        "AUTH-008",
    ),
    PermissionDef(
        "user.session.revoke",
        "Revoke user sessions",
        "Revoke another user's sessions",
        False,
        "ACCOUNT_CONTROL",
        "AUTH-016",
    ),
    PermissionDef(
        "user.role.manage", "Manage user roles", "Add or remove roles on users", False, "ACCESS_CONTROL", "RBAC-009"
    ),
    PermissionDef(
        "user.permission.manage",
        "Manage direct permissions",
        "Direct GRANT/DENY on users",
        False,
        "ACCESS_CONTROL",
        "RBAC-006",
    ),
    PermissionDef(
        "user.mfa.reset",
        "Reset user MFA",
        "Request, approve or execute another user's MFA reset",
        False,
        "ACCOUNT_CONTROL",
        "MFA-007",
    ),
    PermissionDef(
        "user.mfa.require",
        "Require MFA for a user",
        "Set or clear the per-user MFA requirement",
        False,
        "ACCOUNT_CONTROL",
        "MFA-003",
    ),
    PermissionDef(
        "user.founder.manage",
        "Founder governance",
        "Request or approve Founder-level actions",
        False,
        "ACCOUNT_CONTROL",
        "RBAC-021",
        grant_path=FOUNDER_WORKFLOW_ONLY,
    ),
    PermissionDef("role.read", "View roles", "View roles and grants", False, None, "RBAC-008"),
    PermissionDef(
        "role.manage",
        "Manage roles",
        "Create, edit or delete roles and role grants",
        False,
        "ACCESS_CONTROL",
        "RBAC-008",
    ),
    PermissionDef("permission.read", "View permissions", "View the catalog and holders", False, None, "RBAC-016"),
    PermissionDef(
        "permission.manage",
        "Edit permissions",
        "Edit permission name and description",
        False,
        "ACCESS_CONTROL",
        "RBAC-004",
    ),
    PermissionDef("audit.read", "View audit log", "View audit_log", False, "SECURITY_DATA", "AUDIT-008"),
    PermissionDef(
        "security_event.read",
        "View security events",
        "View security_event_log (ALL only)",
        False,
        "SECURITY_DATA",
        "SEVT-005",
    ),
    PermissionDef("lookup.manage", "Manage lookups", "Manage lookup values", False, None, "PLAT-009"),
)

PLATFORM_MATRIX: dict[str, dict[str, str]] = {
    "profile.read": {"FOUNDER": "✓", "ADMIN": "✓", "SALES": "✓"},
    "profile.update": {"FOUNDER": "✓", "ADMIN": "✓", "SALES": "✓"},
    "session.read": {"FOUNDER": "O", "ADMIN": "O", "SALES": "O"},
    "session.revoke": {"FOUNDER": "O", "ADMIN": "O", "SALES": "O"},
    "notification.read": {"FOUNDER": "O", "ADMIN": "O", "SALES": "O"},
    "lookup.read": {"FOUNDER": "✓", "ADMIN": "✓", "SALES": "✓"},
    "user.read": {"FOUNDER": "✓", "ADMIN": "✓"},
    "user.create": {"FOUNDER": "✓", "ADMIN": "✓"},
    "user.profile.update": {"FOUNDER": "✓", "ADMIN": "✓"},
    "user.email.change": {"FOUNDER": "✓", "ADMIN": "✓"},
    "user.status.manage": {"FOUNDER": "✓", "ADMIN": "✓"},
    "user.delete": {"FOUNDER": "✓"},
    "user.restore": {"FOUNDER": "✓"},
    "user.password.reset": {"FOUNDER": "✓", "ADMIN": "✓"},
    "user.session.revoke": {"FOUNDER": "✓", "ADMIN": "✓"},
    "user.role.manage": {"FOUNDER": "✓", "ADMIN": "✓"},
    "user.permission.manage": {"FOUNDER": "✓"},
    "user.mfa.reset": {"FOUNDER": "✓", "ADMIN": "✓"},
    "user.mfa.require": {"FOUNDER": "✓", "ADMIN": "✓"},
    "user.founder.manage": {"FOUNDER": "✓"},
    "role.read": {"FOUNDER": "✓", "ADMIN": "✓"},
    "role.manage": {"FOUNDER": "✓", "ADMIN": "✓"},
    "permission.read": {"FOUNDER": "✓", "ADMIN": "✓"},
    "permission.manage": {"FOUNDER": "✓"},
    "audit.read": {"FOUNDER": "✓", "ADMIN": "✓"},
    "security_event.read": {"FOUNDER": "✓", "ADMIN": "✓"},
    "lookup.manage": {"FOUNDER": "✓", "ADMIN": "✓"},
}

ROLES: tuple[RoleDef, ...] = (
    RoleDef(
        "FOUNDER",
        "Founder",
        "Business owner. Founder protection comes from protection_level, not this code.",
        mfa_required=True,
        is_assignable=False,
        grant_path=FOUNDER_WORKFLOW_ONLY,
        sort_order=10,
    ),
    RoleDef("ADMIN", "Admin", "Operations administrator", mfa_required=True, sort_order=20),
    RoleDef("SALES", "Sales", "Sales & design consultants", mfa_required=False, sort_order=30),
)


@dataclass(frozen=True)
class RegistryEntry:
    definition: PermissionDef
    module: str
    resource: str
    action: str

    @property
    def code(self) -> str:
        return self.definition.code


def _entries() -> tuple[RegistryEntry, ...]:
    out: list[RegistryEntry] = []
    for module, defs in (
        ("platform", PLATFORM_PERMISSIONS),
        ("crm", lead_permissions.PERMISSIONS),
        ("estimator", estimate_permissions.PERMISSIONS),
        ("catalog", catalog_permissions.PERMISSIONS),
    ):
        for d in defs:
            resource, _, action = d.code.partition(".")
            out.append(RegistryEntry(d, module, resource, action))
    return tuple(out)


REGISTRY: tuple[RegistryEntry, ...] = _entries()
BY_CODE: dict[str, RegistryEntry] = {e.code: e for e in REGISTRY}
MATRIX: dict[str, dict[str, str]] = {
    **PLATFORM_MATRIX,
    **lead_permissions.MATRIX,
    **estimate_permissions.MATRIX,
    **catalog_permissions.MATRIX,
}

SENSITIVE_CODES = frozenset(e.code for e in REGISTRY if e.definition.is_sensitive)
FOUNDER_WORKFLOW_ONLY_CODES = frozenset(e.code for e in REGISTRY if e.definition.grant_path == FOUNDER_WORKFLOW_ONLY)
STEP_UP_CLASSES = frozenset({"ACCOUNT_CONTROL", "ACCESS_CONTROL", "BULK_DATA"})
READ_RECORDED_CLASSES = frozenset({"SECURITY_DATA", "BULK_DATA"})
RECOVERY_ADMIN_CODES = ("user.role.manage", "role.manage", "user.mfa.reset", "user.status.manage")  # I2 (06 §7.3)


def sensitivity(code: str) -> str | None:
    entry = BY_CODE.get(code)
    return entry.definition.sensitivity_class if entry else None


def requires_step_up(code: str) -> bool:
    return sensitivity(code) in STEP_UP_CLASSES or code == "lead.erase"


def matrix_scope(symbol: str) -> str:
    return {"A": "ALL", "O": "OWN", "✓": "ALL"}[symbol]


def validate_registry() -> list[str]:
    """Registry rules 1–5 of 06 §3.1 (also asserted by the seed migration)."""
    problems: list[str] = []
    codes = [e.code for e in REGISTRY]
    if len(codes) != len(set(codes)):
        problems.append("duplicate permission codes")
    for code in MATRIX:
        if code not in BY_CODE:
            problems.append(f"matrix references unknown code {code}")
    for e in REGISTRY:
        if e.code not in MATRIX:
            problems.append(f"{e.code} missing from the role matrix")
    for code, grants in MATRIX.items():
        if "SALES" in grants and code in SENSITIVE_CODES:
            problems.append(f"SALES must hold no sensitive permission ({code})")
        if code in FOUNDER_WORKFLOW_ONLY_CODES and set(grants) != {"FOUNDER"}:
            problems.append(f"{code} (FOUNDER_WORKFLOW_ONLY) may appear only in the FOUNDER role")
        entry = BY_CODE.get(code)
        if entry:
            for role, symbol in grants.items():
                if symbol == "O" and not entry.definition.supports_scope:
                    problems.append(f"{code} does not support scope but {role} has OWN")
    account_control_markers = (
        "user.email.change",
        "user.status.manage",
        "user.delete",
        "user.session.revoke",
        "user.mfa.reset",
        "user.mfa.require",
        "user.founder.manage",
    )
    for code in account_control_markers:
        if sensitivity(code) != "ACCOUNT_CONTROL":
            problems.append(f"{code} must be ACCOUNT_CONTROL")
    for code in ("user.role.manage", "user.permission.manage", "role.manage", "permission.manage"):
        if sensitivity(code) != "ACCESS_CONTROL":
            problems.append(f"{code} must be ACCESS_CONTROL")
    for code in ("audit.read", "security_event.read"):
        if sensitivity(code) != "SECURITY_DATA":
            problems.append(f"{code} must be SECURITY_DATA")
    if sensitivity("security_event.read") and BY_CODE["security_event.read"].definition.supports_scope:
        problems.append("security_event.read must be ALL-only (supports_scope = false)")
    return problems
