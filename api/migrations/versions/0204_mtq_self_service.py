"""0204_mtq_self_service: the MTQ site roles can load the workspace (B1-PE-08).

0200_mtq_site seeded DESIGNER and SURVEYOR with the property, measurement and attachment grants only. A user holding
just one of them could not load ``/auth/me`` (``profile.read``), so the workspace never opened for them. This revision
grants the platform self-service rows the shell needs, and nothing more:

- ``profile.read`` (ALL = self): ``GET /auth/me`` and ``GET /auth/mfa``.
- ``lookup.read`` (ALL): the reference lists the shell loads after every sign-in.
- ``notification.read`` (OWN): the notification tray polls the user's own notifications.

``profile.update`` and ``session.read``/``session.revoke`` stay with the V1 roles (not needed to load; an owner
decision). MFA self-enrolment needs no permission (authenticated-only routes).

Data only, expand-only (02 §12.4): no table changes. The rows come from the live registry (``grant_new_codes`` inserts
only what is missing and bumps authz_version so live sessions pick them up); fresh databases already hold them from
0003. Numbered 0204 because ``0201``–``0203`` are reserved for B2–B4 (MTQ B1 blocker closure §4: a corrective B1
migration takes 0204 onward).

Revision ID: 0204_mtq_self_service
Revises: 0200_mtq_site
"""

from alembic import op

from veda.kernel import migration_support as ms

revision = "0204_mtq_self_service"
down_revision = "0200_mtq_site"
branch_labels = None
depends_on = None

ROLES = ("DESIGNER", "SURVEYOR")
CODES = ("profile.read", "lookup.read", "notification.read")


def upgrade() -> None:
    bind = op.get_bind()
    ms.sync_permissions(bind, audit=True)
    ms.grant_new_codes(bind, CODES, audit=True)
    ms.assert_rbac_seed(bind)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
