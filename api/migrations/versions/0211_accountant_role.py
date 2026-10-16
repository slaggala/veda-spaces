"""0211_accountant_role: the ACCOUNTANT role (owner decision PCM-D01, decision log 45).

Seeds the system role ACCOUNTANT (MFA required) with every ``commercials.*`` code at ALL scope and the workspace shell's
self-service codes (``profile.read``, ``notification.read``, ``lookup.read``), as the role matrix in
``veda.platform.rbac.registry`` and ``veda.modules.commercials.permissions`` now lists them. Withdraws from
SALES_MANAGER the five commercial mutation codes the temporary mapping of decision log 44 gave it
(``commercials.schedule.manage``, ``.payment.record``, ``.payment.reverse``, ``.invoice.issue``, ``.audit.view``); it
keeps ``commercials.view``. Each withdrawal is a soft delete with its own audit row, and every account's authz_version
moves so sessions lose the codes at once. No user is given the role: the founder assigns it.

Additive for the schema (no DDL). Fresh databases already have the role and the current matrix from 0003, which reads
the live registry; on them every step below finds nothing to do.

Revision ID: 0211_accountant_role
Revises: 0210_project_commercials
"""

from alembic import op

from veda.kernel import migration_support as ms

revision = "0211_accountant_role"
down_revision = "0210_project_commercials"
branch_labels = None
depends_on = None

ROLES = ("ACCOUNTANT",)
CODES = (
    "commercials.view",
    "commercials.schedule.manage",
    "commercials.payment.record",
    "commercials.payment.reverse",
    "commercials.invoice.issue",
    "commercials.audit.view",
    "profile.read",
    "notification.read",
    "lookup.read",
)
WITHDRAWN = (
    "commercials.schedule.manage",
    "commercials.payment.record",
    "commercials.payment.reverse",
    "commercials.invoice.issue",
    "commercials.audit.view",
)


def upgrade() -> None:
    bind = op.get_bind()
    ms.refuse_role_collisions(bind, ROLES)  # before any change: a custom role must not be taken over
    ms.sync_permissions(bind, audit=True)
    ms.seed_missing_roles(bind, ROLES, audit=True)
    ms.grant_new_codes(bind, CODES, audit=True)
    ms.withdraw_role_grants(bind, "SALES_MANAGER", WITHDRAWN, audit=True)
    ms.assert_rbac_seed(bind)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
