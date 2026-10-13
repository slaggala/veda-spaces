"""Permission registry entries owned by the attachment module (ATT; MTQ B1-SCOPE §2.1, blueprint §15).

Scope (06 §4): OWN means the attachment's lead is one the actor owns (assigned to or created by them), the actor
uploaded the attachment, or another module grants the actor access to the lead (MTQ: the surveyor assigned to a
measurement visit on it). Nothing here is sensitive; no role sees prices through an attachment."""

from veda.platform.rbac.registry_types import PermissionDef

PERMISSIONS: tuple[PermissionDef, ...] = (
    PermissionDef(
        "attachment.read",
        "View attachments",
        "View photos, sketches and floor-plan images attached to site records, within the lead scope",
        True,
        None,
        "ATT-001",
    ),
    PermissionDef(
        "attachment.create",
        "Upload attachments",
        "Upload photos, sketches and floor-plan images to site records, within the lead scope",
        True,
        None,
        "ATT-002",
    ),
    PermissionDef(
        "attachment.delete",
        "Withdraw attachments",
        "Withdraw an attachment: its bytes are deleted, its record and hashes are kept, within the lead scope",
        True,
        None,
        "ATT-003",
    ),
)

# Blueprint §15.2 pattern: FOUNDER/ADMIN ALL, SALES OWN. The SURVEYOR and DESIGNER roles and their grants arrive with
# 0200_mtq_site (B1-T03); the fresh-database seed (0003) reads this live matrix, so a role must exist before it is named.
MATRIX: dict[str, dict[str, str]] = {
    "attachment.read": {"FOUNDER": "A", "ADMIN": "A", "SALES": "O"},
    "attachment.create": {"FOUNDER": "A", "ADMIN": "A", "SALES": "O"},
    "attachment.delete": {"FOUNDER": "A", "ADMIN": "A", "SALES": "O"},
}
