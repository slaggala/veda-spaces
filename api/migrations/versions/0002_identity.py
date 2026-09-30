"""0002_identity: app_user (+ SYSTEM, WEB_INTAKE, ANONYMOUS), user_credential.

No table named user (ADR-001). No human users are seeded (AUTH-014).

Revision ID: 0002_identity
Revises: 0001_kernel
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms  # noqa: F401
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0002_identity"
down_revision = "0001_kernel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "app_user",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("email_normalized", sa.String(254), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=True),
        sa.Column("phone_e164", sa.String(16), nullable=True),
        sa.Column("user_type", sa.String(20), nullable=False, server_default="HUMAN"),
        sa.Column("status", sa.String(20), nullable=False, server_default="INVITED"),
        sa.Column("status_changed_on", UTCDateTime(), nullable=False),
        sa.Column("timezone", sa.String(40), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("locale", sa.String(10), nullable=False, server_default="en-IN"),
        sa.Column("email_verified_on", UTCDateTime(), nullable=True),
        sa.Column("mfa_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("authz_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_login_on", UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_app_user"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], name="fk_app_user__created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["app_user.id"], name="fk_app_user__deleted_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], name="fk_app_user__updated_by", ondelete="RESTRICT"),
        sa.CheckConstraint("authz_version >= 1", name="ck_app_user__authz_version_positive"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_app_user__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_app_user__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(display_name) <= 80", name="ck_app_user__display_name_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(email) <= 254", name="ck_app_user__email_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(email_normalized) <= 254", name="ck_app_user__email_normalized_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("email_normalized = lower(email_normalized)", name="ck_app_user__email_normalized_lower"),
        sa.CheckConstraint("length(full_name) <= 150", name="ck_app_user__full_name_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_app_user__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_app_user__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(locale) <= 10", name="ck_app_user__locale_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("mfa_required IN (0, 1)", name="ck_app_user__mfa_required_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(phone_e164) <= 16", name="ck_app_user__phone_e164_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_app_user__soft_delete_consistent",
        ),
        sa.CheckConstraint("status IN ('INVITED', 'ACTIVE', 'LOCKED', 'DISABLED')", name="ck_app_user__status"),
        sa.CheckConstraint("length(status) <= 20", name="ck_app_user__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(timezone) <= 40", name="ck_app_user__timezone_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_app_user__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_app_user__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("user_type IN ('HUMAN', 'SYSTEM')", name="ck_app_user__user_type"),
        sa.CheckConstraint("length(user_type) <= 20", name="ck_app_user__user_type_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_app_user__version_positive"),
    )
    op.create_index("ix_app_user__full_name", "app_user", ["full_name"])
    op.create_index(
        "ix_app_user__status",
        "app_user",
        ["status"],
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_app_user__email_normalized",
        "app_user",
        ["email_normalized"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "user_credential",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("password_changed_on", UTCDateTime(), nullable=True),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_window_started_on", UTCDateTime(), nullable=True),
        sa.Column("locked_until", UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_user_credential"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_user_credential__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_user_credential__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_user_credential__updated_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], name="fk_user_credential__user_id", ondelete="RESTRICT"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_user_credential__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_user_credential__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("failed_login_count >= 0", name="ck_user_credential__failed_login_count"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_user_credential__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_user_credential__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "must_change_password IN (0, 1)", name="ck_user_credential__must_change_password_bool"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(password_hash) <= 255", name="ck_user_credential__password_hash_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_user_credential__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_user_credential__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_user_credential__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(user_id) = 32 AND user_id NOT GLOB '*[^0-9a-f]*' AND substr(user_id, 13, 1) = '7' AND substr(user_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_user_credential__user_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_user_credential__version_positive"),
    )
    op.create_index(
        "ux_user_credential__user_id",
        "user_credential",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    # --- end generated DDL ---
    ms.seed_system_users(op.get_bind())


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
