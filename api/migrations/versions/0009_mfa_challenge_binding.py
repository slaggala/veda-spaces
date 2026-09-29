"""0009_mfa_challenge_binding: bind ENROLLMENT challenges to their factor and enrollment path (IR-01).

Adds two nullable columns to mfa_challenge:

* ``factor_id``: the PENDING factor an enrollment transaction may promote (FK user_mfa_factor).
* ``enrollment_path``: INVITE_CONTEXT (the path-B proof, never confirmable) or PATH_A..PATH_D.

Expand-only (02 §12.4): nullable columns, no data rewrite. Rows written by the N-1 image carry NULLs,
and the N image refuses an ENROLLMENT challenge without a binding (fail closed), so an enrollment
started just before the upgrade has to be restarted.

The revision follows 0100_crm_leads because the chain is linear; it depends only on platform tables.
Proposed amendment: docs/proposals/amendments/AM-11 (deviation DEV-006).

Revision ID: 0009_mfa_challenge_binding
Revises: 0100_crm_leads
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel.base import guid_format_sql
from veda.kernel.types import GUID

revision = "0009_mfa_challenge_binding"
down_revision = "0100_crm_leads"
branch_labels = None
depends_on = None

PATHS = "'INVITE_CONTEXT', 'PATH_A', 'PATH_B', 'PATH_C', 'PATH_D'"
CONFIRMABLE = "'PATH_A', 'PATH_B', 'PATH_C', 'PATH_D'"


def _sqlite() -> None:
    fmt = guid_format_sql("factor_id")
    op.execute(
        "ALTER TABLE mfa_challenge ADD COLUMN factor_id CHAR(32) "
        "CONSTRAINT fk_mfa_challenge__factor_id REFERENCES user_mfa_factor (id) ON DELETE RESTRICT "
        f"CONSTRAINT ck_mfa_challenge__factor_id_format CHECK (factor_id IS NULL OR ({fmt}))"
    )
    op.execute(
        "ALTER TABLE mfa_challenge ADD COLUMN enrollment_path VARCHAR(14) "
        f"CONSTRAINT ck_mfa_challenge__enrollment_path CHECK (enrollment_path IS NULL OR enrollment_path IN ({PATHS})) "
        "CONSTRAINT ck_mfa_challenge__enrollment_path_len CHECK (length(enrollment_path) <= 14) "
        "CONSTRAINT ck_mfa_challenge__path_purpose CHECK (enrollment_path IS NULL OR purpose = 'ENROLLMENT') "
        f"CONSTRAINT ck_mfa_challenge__factor_path CHECK (factor_id IS NULL OR enrollment_path IN ({CONFIRMABLE}))"
    )


def _postgresql() -> None:
    op.add_column("mfa_challenge", sa.Column("factor_id", GUID(), nullable=True))
    op.add_column("mfa_challenge", sa.Column("enrollment_path", sa.String(14), nullable=True))
    op.create_foreign_key(
        "fk_mfa_challenge__factor_id", "mfa_challenge", "user_mfa_factor", ["factor_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_check_constraint(
        "ck_mfa_challenge__enrollment_path", "mfa_challenge", f"enrollment_path IS NULL OR enrollment_path IN ({PATHS})"
    )
    op.create_check_constraint(
        "ck_mfa_challenge__path_purpose", "mfa_challenge", "enrollment_path IS NULL OR purpose = 'ENROLLMENT'"
    )
    op.create_check_constraint(
        "ck_mfa_challenge__factor_path", "mfa_challenge", f"factor_id IS NULL OR enrollment_path IN ({CONFIRMABLE})"
    )


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        _sqlite()
    else:
        _postgresql()


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
