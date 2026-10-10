"""0105_catalog_claim_control: the standing of released claims after activation (B1-B3 policy closure, B3).

One new table, catalog_claim_control: append-only rows that withdraw a released claim, remove or reassign its
accountable owner, narrow its applicability, or reinstate it. Every public V3 serve applies the latest row per claim
(fail closed), so a claim stops being shown without waiting for a new release. No change to any existing table, no
personal data, no rates.

Expand-only (02 §12.4): a new table, no data rewrite. The N-1 image never reads it, so a rollback runs unchanged
(VEDA_SCHEMA_AHEAD_ACCEPTED).

Revision ID: 0105_catalog_claim_control
Revises: 0104_catalog_idempotency
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0105_catalog_claim_control"
down_revision = "0104_catalog_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "catalog_claim_control",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("copy_key", sa.String(100), nullable=False),
        sa.Column("action", sa.String(25), nullable=False),
        sa.Column("owner", sa.String(120), nullable=True),
        sa.Column("scope", JSONType(), nullable=True),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_claim_control"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_catalog_claim_control__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_catalog_claim_control__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_catalog_claim_control__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "action IN ('WITHDRAW', 'UNASSIGN_OWNER', 'ASSIGN_OWNER', 'RESTRICT_APPLICABILITY', 'REINSTATE')",
            name="ck_catalog_claim_control__action",
        ),
        sa.CheckConstraint("length(action) <= 25", name="ck_catalog_claim_control__action_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(copy_key) <= 100", name="ck_catalog_claim_control__copy_key_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_claim_control__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_claim_control__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_claim_control__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_catalog_claim_control__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(owner) <= 120", name="ck_catalog_claim_control__owner_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(reason) <= 300", name="ck_catalog_claim_control__reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("scope IS NULL OR json_valid(scope)", name="ck_catalog_claim_control__scope_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_catalog_claim_control__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_catalog_claim_control__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_claim_control__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_catalog_claim_control__version_positive"),
    )
    op.create_index(
        "ix_catalog_claim_control__key",
        "catalog_claim_control",
        ["copy_key", "created_on"],
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    # --- end generated DDL ---


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
