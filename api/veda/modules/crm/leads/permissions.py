"""Permission registry entries owned by the CRM leads module (06 §6.3)."""

from veda.platform.rbac.registry_types import PermissionDef

PERMISSIONS: tuple[PermissionDef, ...] = (
    PermissionDef("lead.create", "Create leads", "Create leads manually", False, None, "LEAD-003"),
    PermissionDef("lead.read", "View leads", "View leads, dashboard, duplicates, spam queue", True, None, "LEAD-013"),
    PermissionDef("lead.update", "Edit leads", "Edit and enrich fields, resolve duplicate and spam flags, record consent withdrawal", True, None, "LEAD-024"),
    PermissionDef("lead.status.change", "Change lead status", "Move leads through the pipeline, including WON/LOST.", True, None, "LEAD-005"),
    PermissionDef("lead.reopen", "Reopen leads", "Reopen WON/LOST", True, None, "LEAD-005"),
    PermissionDef("lead.assign", "Assign leads", "Assign, reassign or unassign", True, None, "LEAD-007"),
    PermissionDef("lead.delete", "Delete leads", "Soft-delete", True, "DESTRUCTIVE", "LEAD-016"),
    PermissionDef("lead.restore", "Restore leads", "Restore, view deleted", False, None, "LEAD-016"),
    PermissionDef("lead.erase", "Erase lead personal data", "Execute a personal-data erasure request (07 §8.2)", False, "DESTRUCTIVE", "LEAD-029"),
    PermissionDef("lead.export", "Export leads", "CSV export (P1)", False, "BULK_DATA", "LEAD-017"),
    PermissionDef("lead_note.create", "Add lead notes", "Add a note to a visible lead", False, None, "NOTE-001"),
    PermissionDef("lead_note.read", "Read lead notes", "Read notes on visible leads", True, None, "NOTE-001"),
    PermissionDef("lead_note.update", "Edit lead notes", "Edit notes", True, None, "NOTE-002"),
    PermissionDef("lead_note.delete", "Delete lead notes", "Delete notes", True, None, "NOTE-002"),
    PermissionDef("lead_activity.create", "Log lead activities", "Log or plan an activity on a visible lead", False, None, "ACT-001"),
    PermissionDef("lead_activity.read", "Read lead timeline", "Read the timeline", True, None, "ACT-001"),
    PermissionDef("lead_activity.update", "Edit lead activities", "Edit, complete, cancel or reschedule", True, None, "ACT-002"),
    PermissionDef("lead_activity.delete", "Delete lead activities", "Delete non-system activities", True, None, "ACT-002"),
)

# Default role matrix (06 §6.3). "A" = ALL, "O" = OWN, "✓" = granted without scope.
MATRIX: dict[str, dict[str, str]] = {
    "lead.create": {"FOUNDER": "✓", "ADMIN": "✓", "SALES": "✓"},
    "lead.read": {"FOUNDER": "A", "ADMIN": "A", "SALES": "O"},
    "lead.update": {"FOUNDER": "A", "ADMIN": "A", "SALES": "O"},
    "lead.status.change": {"FOUNDER": "A", "ADMIN": "A", "SALES": "O"},
    "lead.reopen": {"FOUNDER": "A", "ADMIN": "A"},
    "lead.assign": {"FOUNDER": "A", "ADMIN": "A"},
    "lead.delete": {"FOUNDER": "A", "ADMIN": "A"},
    "lead.restore": {"FOUNDER": "✓", "ADMIN": "✓"},
    "lead.erase": {"FOUNDER": "✓"},
    "lead.export": {"FOUNDER": "✓"},
    "lead_note.create": {"FOUNDER": "✓", "ADMIN": "✓", "SALES": "✓"},
    "lead_note.read": {"FOUNDER": "A", "ADMIN": "A", "SALES": "A"},
    "lead_note.update": {"FOUNDER": "A", "ADMIN": "A", "SALES": "O"},
    "lead_note.delete": {"FOUNDER": "A", "ADMIN": "A", "SALES": "O"},
    "lead_activity.create": {"FOUNDER": "✓", "ADMIN": "✓", "SALES": "✓"},
    "lead_activity.read": {"FOUNDER": "A", "ADMIN": "A", "SALES": "A"},
    "lead_activity.update": {"FOUNDER": "A", "ADMIN": "A", "SALES": "O"},
    "lead_activity.delete": {"FOUNDER": "A", "ADMIN": "A", "SALES": "O"},
}
