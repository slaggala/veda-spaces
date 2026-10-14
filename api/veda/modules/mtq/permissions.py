"""Permission registry entries owned by MTQ B1 (blueprint §15.2, the B1 subset).

Scope (blueprint §15.3): a property, its spaces and its measurement sets are OWN to an actor who owns the parent lead
(assigned to or created by them) or who is assigned a measurement visit on the property; a visit is OWN to its
assignee. Visit start and completion are part of capture (``measurement.capture``); scheduling, cancelling and
no-shows need ``measurement.visit.schedule``. Nothing here is sensitive and no B1 surface shows a price.
"""

from veda.platform.rbac.registry_types import PermissionDef

PERMISSIONS: tuple[PermissionDef, ...] = (
    PermissionDef(
        "property.read",
        "View properties",
        "View properties and their space trees, within scope",
        True,
        None,
        "PROP-001",
    ),  # fmt: skip
    PermissionDef(
        "property.create",
        "Create properties",
        "Create a property for a lead, within the lead scope",
        True,
        None,
        "PROP-002",
    ),  # fmt: skip
    PermissionDef(
        "property.update", "Edit properties", "Edit a property and its spaces, within scope", True, None, "PROP-003"
    ),  # fmt: skip
    PermissionDef(
        "measurement.visit.read",
        "View measurement visits",
        "View site measurement visits, within scope",
        True,
        None,
        "MEAS-001",
    ),  # fmt: skip
    PermissionDef(
        "measurement.visit.create",
        "Request measurement visits",
        "Request a site measurement visit for a property, within scope",
        True,
        None,
        "MEAS-002",
    ),  # fmt: skip
    PermissionDef(
        "measurement.visit.schedule",
        "Schedule measurement visits",
        "Schedule, reassign, cancel or mark a no-show for a measurement visit, within scope",
        True,
        None,
        "MEAS-003",
    ),  # fmt: skip
    PermissionDef(
        "measurement.capture",
        "Capture measurements",
        "Start a visit and capture, sync and submit measurement sets, within scope",
        True,
        None,
        "MEAS-004",
    ),  # fmt: skip
    PermissionDef(
        "measurement.read",
        "View measurements",
        "View measurement sets and their revisions, within scope",
        True,
        None,
        "MEAS-005",
    ),  # fmt: skip
    PermissionDef(
        "measurement.verify",
        "Verify measurements",
        "Verify or reject a submitted measurement set (never one you captured), within scope",
        True,
        None,
        "MEAS-006",
    ),  # fmt: skip
)

MATRIX: dict[str, dict[str, str]] = {
    "property.read": {
        "FOUNDER": "A",
        "ADMIN": "A",
        "SALES": "O",
        "DESIGNER": "O",
        "SURVEYOR": "O",
        "ESTIMATOR": "A",
        "SALES_MANAGER": "A",
    },
    "property.create": {"FOUNDER": "A", "ADMIN": "A", "SALES": "O", "DESIGNER": "O"},
    "property.update": {"FOUNDER": "A", "ADMIN": "A", "SALES": "O", "DESIGNER": "O"},
    "measurement.visit.read": {
        "FOUNDER": "A",
        "ADMIN": "A",
        "SALES": "O",
        "DESIGNER": "O",
        "SURVEYOR": "O",
        "ESTIMATOR": "A",
        "SALES_MANAGER": "A",
    },
    "measurement.visit.create": {"FOUNDER": "A", "ADMIN": "A", "SALES": "O", "DESIGNER": "O"},
    "measurement.visit.schedule": {"FOUNDER": "A", "ADMIN": "A", "SALES": "O", "DESIGNER": "O"},
    "measurement.capture": {"FOUNDER": "A", "ADMIN": "A", "DESIGNER": "O", "SURVEYOR": "O"},
    "measurement.read": {
        "FOUNDER": "A",
        "ADMIN": "A",
        "SALES": "O",
        "DESIGNER": "O",
        "SURVEYOR": "O",
        "ESTIMATOR": "A",
        "SALES_MANAGER": "A",
    },
    "measurement.verify": {"FOUNDER": "A", "ADMIN": "A", "DESIGNER": "O"},
}
