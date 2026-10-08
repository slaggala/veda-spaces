"""Permission registry entries owned by the estimator module (ADR-012). Rate cards have no API permission: they are
loaded, activated and rolled back only through the operator CLI."""

from veda.platform.rbac.registry_types import PermissionDef

PERMISSIONS: tuple[PermissionDef, ...] = (
    PermissionDef(
        "estimate.read",
        "View budgetary estimates",
        "View estimates, their assumptions and internal lines, within the lead scope of the viewer",
        False,
        None,
        "EST-005",
    ),
    PermissionDef(
        "estimate.manage",
        "Work with budgetary estimates",
        "Duplicate or revise an estimate, generate a consultation copy, mark site measurement required and start the "
        "official quotation process, within the lead scope",
        False,
        None,
        "EST-005",
    ),
)

# Default role matrix. The linked lead's scope still applies (a SALES user acts only on leads they may read).
MATRIX: dict[str, dict[str, str]] = {
    "estimate.read": {"FOUNDER": "✓", "ADMIN": "✓", "SALES": "✓"},
    "estimate.manage": {"FOUNDER": "✓", "ADMIN": "✓", "SALES": "✓"},
}
