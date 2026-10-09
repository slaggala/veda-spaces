"""Permission registry entries owned by the catalog module (ADR-013 D10).

Least privilege: pricing is separate from content, media editing grants no pricing access, editing never permits
approving one's own work (four-eyes, enforced in the service), and release activation and rollback need
`catalog.admin`. The default matrix grants everything to the Founder and only viewing to Admin; anyone else is
granted individually. No employee is assigned automatically. Pricing, approval and release administration are
sensitive: they require MFA before they take effect (ADR-006).
"""

from veda.platform.rbac.registry_types import PermissionDef

PERMISSIONS: tuple[PermissionDef, ...] = (
    PermissionDef("catalog.view", "View the estimator catalog", "See catalog records, releases and previews (no rates)", False, None, "CAT-001"),
    PermissionDef("catalog.edit", "Edit catalog content", "Create, clone and edit DRAFT homes, rooms, products, extras, materials, hardware, packages, rules and copy, and submit them for review", False, None, "CAT-002"),
    PermissionDef("catalog.pricing.view", "View catalog pricing", "Read private pricing records (rates, formulas, minimums)", False, "BULK_DATA", "CAT-003"),
    PermissionDef("catalog.pricing.edit", "Edit catalog pricing", "Create and edit DRAFT pricing records and submit them for review", False, "BULK_DATA", "CAT-003"),
    PermissionDef("catalog.media.edit", "Manage catalog media", "Upload images, galleries, video, 360-degree and 3D references, and edit media records", False, None, "CAT-004"),
    PermissionDef("catalog.spec.edit", "Edit catalog specifications", "Edit materials, hardware and governed customer statements", False, None, "CAT-005"),
    PermissionDef("catalog.review", "Review catalog changes", "Approve or reject submitted catalog records (never one's own)", False, None, "CAT-006"),
    PermissionDef("catalog.approve", "Approve catalog releases", "Approve the customer preview and the release (never one's own release)", False, "ACCESS_CONTROL", "CAT-007"),
    PermissionDef("catalog.admin", "Administer catalog releases", "Create, validate, schedule, activate and roll back catalog releases; import and export", False, "ACCESS_CONTROL", "CAT-008"),
)  # fmt: skip

MATRIX: dict[str, dict[str, str]] = {
    "catalog.view": {"FOUNDER": "✓", "ADMIN": "✓"},
    "catalog.edit": {"FOUNDER": "✓"},
    "catalog.pricing.view": {"FOUNDER": "✓"},
    "catalog.pricing.edit": {"FOUNDER": "✓"},
    "catalog.media.edit": {"FOUNDER": "✓"},
    "catalog.spec.edit": {"FOUNDER": "✓"},
    "catalog.review": {"FOUNDER": "✓"},
    "catalog.approve": {"FOUNDER": "✓"},
    "catalog.admin": {"FOUNDER": "✓"},
}

# Which permission edits which record kind (content, pricing, media and specifications are separate duties).
EDIT_PERMISSION = {
    "pricing": "catalog.pricing.edit",
    "media": "catalog.media.edit",
    "material": "catalog.spec.edit",
    "hardware": "catalog.spec.edit",
    "copy": "catalog.spec.edit",
}
DEFAULT_EDIT = "catalog.edit"


def edit_permission(kind: str) -> str:
    return EDIT_PERMISSION.get(kind, DEFAULT_EDIT)
