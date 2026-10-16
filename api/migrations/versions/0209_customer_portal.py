"""0209_customer_portal: the Customer Project Portal (decision log 41).

Five tables (``veda.modules.portal.models``): ``portal_account`` (a customer, by normalised email; not an
``app_user``), ``portal_access`` (staff-granted access of an account to one enquiry), ``portal_sign_in`` (single-use
sign-in links; the token is derived from the row id and only its SHA-256 is stored), ``portal_session`` (signed-in
browsers; SHA-256 of the token only) and ``portal_event`` (the immutable record of access and sign-in: database
triggers refuse UPDATE and DELETE). The three ``portal.access.*`` staff permission codes and their default grants
(FOUNDER, ADMIN, SALES_MANAGER: ALL; SALES: OWN). No business content is seeded.

Expand-only and additive: no existing table, column or constraint changes. Inert while VEDA_CUSTOMER_PORTAL_ENABLED is
off (the default everywhere; production refuses it).

Revision ID: 0209_customer_portal
Revises: 0208_project_lifecycle
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0209_customer_portal"
down_revision = "0208_project_lifecycle"
branch_labels = None
depends_on = None

CODES = ("portal.access.view", "portal.access.grant", "portal.access.revoke")
IMMUTABLE = ("portal_event",)


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "portal_account",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("email_normalized", sa.String(254), nullable=False),
        sa.Column("email_hash", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(150), nullable=False),
        sa.Column("name_source_lead_id", GUID(), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("last_signed_in_on", UTCDateTime(), nullable=True),
        sa.Column("erased_on", UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_portal_account"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_portal_account__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_portal_account__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["name_source_lead_id"], ["lead.id"], name="fk_portal_account__name_source_lead_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_portal_account__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_account__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_portal_account__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(display_name) <= 150", name="ck_portal_account__display_name_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(email_hash) = 64", name="ck_portal_account__email_hash_len"),
        sa.CheckConstraint("length(email_normalized) <= 254", name="ck_portal_account__email_normalized_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("erased_on IS NULL OR status = 'DISABLED'", name="ck_portal_account__erased"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_account__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_portal_account__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "name_source_lead_id IS NULL OR (length(name_source_lead_id) = 32 AND name_source_lead_id NOT GLOB '*[^0-9a-f]*' AND substr(name_source_lead_id, 13, 1) = '7' AND substr(name_source_lead_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_portal_account__name_source_lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_portal_account__soft_delete_consistent",
        ),
        sa.CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name="ck_portal_account__status"),
        sa.CheckConstraint("length(status) <= 10", name="ck_portal_account__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_portal_account__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_account__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_portal_account__version_positive"),
    )
    op.create_index("ix_portal_account__name_source", "portal_account", ["name_source_lead_id"])
    op.create_index(
        "ux_portal_account__email",
        "portal_account",
        ["email_normalized"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_portal_account__email_hash",
        "portal_account",
        ["email_hash"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "portal_access",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("relationship", sa.String(20), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("revoked_on", UTCDateTime(), nullable=True),
        sa.Column("revoked_by", GUID(), nullable=True),
        sa.Column("revoke_reason_code", sa.String(16), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_portal_access"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["portal_account.id"], name="fk_portal_access__account_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_portal_access__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_portal_access__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_portal_access__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["revoked_by"], ["app_user.id"], name="fk_portal_access__revoked_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_portal_access__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(account_id) = 32 AND account_id NOT GLOB '*[^0-9a-f]*' AND substr(account_id, 13, 1) = '7' AND substr(account_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_access__account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_access__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_portal_access__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_access__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_portal_access__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_access__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "relationship IN ('PRIMARY_CUSTOMER', 'CO_OWNER', 'FAMILY_MEMBER', 'OTHER')",
            name="ck_portal_access__relationship",
        ),
        sa.CheckConstraint("length(relationship) <= 20", name="ck_portal_access__relationship_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "revoke_reason_code IS NULL OR revoke_reason_code IN ('STAFF_REVOKED', 'LEAD_ERASED')",
            name="ck_portal_access__revoke_reason_code",
        ),
        sa.CheckConstraint("length(revoke_reason_code) <= 16", name="ck_portal_access__revoke_reason_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(status = 'REVOKED') = (revoked_on IS NOT NULL AND revoke_reason_code IS NOT NULL)",
            name="ck_portal_access__revoked",
        ),
        sa.CheckConstraint(
            "revoked_by IS NULL OR (length(revoked_by) = 32 AND revoked_by NOT GLOB '*[^0-9a-f]*' AND substr(revoked_by, 13, 1) = '7' AND substr(revoked_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_portal_access__revoked_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_portal_access__soft_delete_consistent",
        ),
        sa.CheckConstraint("status IN ('ACTIVE', 'REVOKED')", name="ck_portal_access__status"),
        sa.CheckConstraint("length(status) <= 10", name="ck_portal_access__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_portal_access__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_access__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_portal_access__version_positive"),
    )
    op.create_index("ix_portal_access__account_id", "portal_access", ["account_id"])
    op.create_index("ix_portal_access__lead_id", "portal_access", ["lead_id"])
    op.create_index(
        "ux_portal_access__active",
        "portal_access",
        ["account_id", "lead_id"],
        unique=True,
        sqlite_where=sa.text("status = 'ACTIVE' AND is_deleted = 0"),
        postgresql_where=sa.text("status = 'ACTIVE' AND is_deleted = false"),
    )

    op.create_table(
        "portal_sign_in",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("purpose", sa.String(12), nullable=False),
        sa.Column("token_sha256", sa.String(64), nullable=False),
        sa.Column("expires_on", UTCDateTime(), nullable=False),
        sa.Column("used_on", UTCDateTime(), nullable=True),
        sa.Column("invalidated_on", UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_portal_sign_in"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["portal_account.id"], name="fk_portal_sign_in__account_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_portal_sign_in__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_portal_sign_in__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_portal_sign_in__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(account_id) = 32 AND account_id NOT GLOB '*[^0-9a-f]*' AND substr(account_id, 13, 1) = '7' AND substr(account_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_sign_in__account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_sign_in__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_portal_sign_in__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_sign_in__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_portal_sign_in__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("purpose IN ('INVITATION', 'SIGN_IN')", name="ck_portal_sign_in__purpose"),
        sa.CheckConstraint("length(purpose) <= 12", name="ck_portal_sign_in__purpose_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("used_on IS NULL OR invalidated_on IS NULL", name="ck_portal_sign_in__single_outcome"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_portal_sign_in__soft_delete_consistent",
        ),
        sa.CheckConstraint("length(token_sha256) = 64", name="ck_portal_sign_in__token_len"),
        sa.CheckConstraint("length(token_sha256) <= 64", name="ck_portal_sign_in__token_sha256_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_portal_sign_in__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_sign_in__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_portal_sign_in__version_positive"),
    )
    op.create_index("ix_portal_sign_in__account_id", "portal_sign_in", ["account_id", "expires_on"])
    op.create_index(
        "ux_portal_sign_in__token",
        "portal_sign_in",
        ["token_sha256"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "portal_session",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("sign_in_id", GUID(), nullable=False),
        sa.Column("token_sha256", sa.String(64), nullable=False),
        sa.Column("last_seen_on", UTCDateTime(), nullable=False),
        sa.Column("idle_expires_on", UTCDateTime(), nullable=False),
        sa.Column("absolute_expires_on", UTCDateTime(), nullable=False),
        sa.Column("ended_on", UTCDateTime(), nullable=True),
        sa.Column("end_reason_code", sa.String(16), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_portal_session"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["portal_account.id"], name="fk_portal_session__account_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_portal_session__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_portal_session__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["sign_in_id"], ["portal_sign_in.id"], name="fk_portal_session__sign_in_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_portal_session__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(account_id) = 32 AND account_id NOT GLOB '*[^0-9a-f]*' AND substr(account_id, 13, 1) = '7' AND substr(account_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_session__account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_session__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_portal_session__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "end_reason_code IS NULL OR end_reason_code IN ('SIGNED_OUT', 'ACCESS_REVOKED', 'LEAD_ERASED')",
            name="ck_portal_session__end_reason_code",
        ),
        sa.CheckConstraint("length(end_reason_code) <= 16", name="ck_portal_session__end_reason_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("(ended_on IS NULL) = (end_reason_code IS NULL)", name="ck_portal_session__ended"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_session__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_portal_session__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(sign_in_id) = 32 AND sign_in_id NOT GLOB '*[^0-9a-f]*' AND substr(sign_in_id, 13, 1) = '7' AND substr(sign_in_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_session__sign_in_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_portal_session__soft_delete_consistent",
        ),
        sa.CheckConstraint("length(token_sha256) = 64", name="ck_portal_session__token_len"),
        sa.CheckConstraint("length(token_sha256) <= 64", name="ck_portal_session__token_sha256_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_portal_session__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_session__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_portal_session__version_positive"),
    )
    op.create_index("ix_portal_session__account_id", "portal_session", ["account_id"])
    op.create_index(
        "ix_portal_session__sign_in_id",
        "portal_session",
        ["sign_in_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_portal_session__token",
        "portal_session",
        ["token_sha256"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "portal_event",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=True),
        sa.Column("event_code", sa.String(24), nullable=False),
        sa.Column("detail", JSONType(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_portal_event"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["portal_account.id"], name="fk_portal_event__account_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_portal_event__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_portal_event__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_portal_event__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_portal_event__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(account_id) = 32 AND account_id NOT GLOB '*[^0-9a-f]*' AND substr(account_id, 13, 1) = '7' AND substr(account_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_event__account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_event__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_portal_event__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("detail IS NULL OR json_valid(detail)", name="ck_portal_event__detail_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "event_code IN ('ACCESS_GRANTED', 'ACCESS_REVOKED', 'SIGN_IN_LINK_SENT', 'SIGNED_IN', 'SIGN_IN_REFUSED', 'SIGNED_OUT', 'ACCOUNT_ERASED')",
            name="ck_portal_event__event_code",
        ),
        sa.CheckConstraint("length(event_code) <= 24", name="ck_portal_event__event_code_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_event__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted = false AND version = 1", name="ck_portal_event__immutable_contract"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_portal_event__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "lead_id IS NULL OR (length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_portal_event__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_portal_event__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_portal_event__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_portal_event__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_portal_event__version_positive"),
    )
    op.create_index("ix_portal_event__account", "portal_event", ["account_id", "created_on"])
    op.create_index("ix_portal_event__lead_id", "portal_event", ["lead_id"])
    # --- end generated DDL ---
    bind = op.get_bind()
    for table in IMMUTABLE:
        ms.create_immutability_guards(bind, table)
    ms.sync_permissions(bind, audit=True)
    ms.grant_new_codes(bind, CODES, audit=True)
    ms.assert_rbac_seed(bind)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
