"""0006_reference: lookup_category, lookup_value (+ seed), number_sequence (+ LEAD).

Revision ID: 0006_reference
Revises: 0005_audit
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms  # noqa: F401
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0006_reference"
down_revision = "0005_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "lookup_category",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id", name="pk_lookup_category"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_lookup_category__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_lookup_category__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_lookup_category__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("length(code) <= 50", name="ck_lookup_category__code_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_lookup_category__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_lookup_category__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(description) <= 500", name="ck_lookup_category__description_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_lookup_category__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_lookup_category__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_system IN (0, 1)", name="ck_lookup_category__is_system_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(module) <= 50", name="ck_lookup_category__module_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(name) <= 100", name="ck_lookup_category__name_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_lookup_category__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_lookup_category__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_lookup_category__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_lookup_category__version_positive"),
    )
    op.create_index(
        "ux_lookup_category__code",
        "lookup_category",
        ["code"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "lookup_value",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("category_id", GUID(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("attributes", JSONType(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_lookup_value"),
        sa.ForeignKeyConstraint(
            ["category_id"], ["lookup_category.id"], name="fk_lookup_value__category_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_lookup_value__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_lookup_value__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_lookup_value__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "attributes IS NULL OR json_valid(attributes)", name="ck_lookup_value__attributes_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(category_id) = 32 AND category_id NOT GLOB '*[^0-9a-f]*' AND substr(category_id, 13, 1) = '7' AND substr(category_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_lookup_value__category_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(code) <= 50", name="ck_lookup_value__code_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_lookup_value__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_lookup_value__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(description) <= 500", name="ck_lookup_value__description_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_lookup_value__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_active IN (0, 1)", name="ck_lookup_value__is_active_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_lookup_value__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(label) <= 120", name="ck_lookup_value__label_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_lookup_value__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_lookup_value__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_lookup_value__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_lookup_value__version_positive"),
    )
    op.create_index("ix_lookup_value__category_active", "lookup_value", ["category_id", "is_active", "sort_order"])
    op.create_index(
        "ux_lookup_value__category_code",
        "lookup_value",
        ["category_id", "code"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "number_sequence",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("sequence_key", sa.String(50), nullable=False),
        sa.Column("prefix", sa.String(20), nullable=False),
        sa.Column("reset_period", sa.String(10), nullable=False, server_default="YEAR"),
        sa.Column("current_period", sa.String(10), nullable=True),
        sa.Column("next_value", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("padding", sa.Integer(), nullable=False, server_default=sa.text("6")),
        sa.PrimaryKeyConstraint("id", name="pk_number_sequence"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_number_sequence__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_number_sequence__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_number_sequence__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_number_sequence__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(current_period) <= 10", name="ck_number_sequence__current_period_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_number_sequence__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_number_sequence__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_number_sequence__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("next_value >= 1", name="ck_number_sequence__next_value_positive"),
        sa.CheckConstraint("padding BETWEEN 1 AND 12", name="ck_number_sequence__padding_range"),
        sa.CheckConstraint("length(prefix) <= 20", name="ck_number_sequence__prefix_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("reset_period IN ('NONE', 'YEAR', 'MONTH')", name="ck_number_sequence__reset_period"),
        sa.CheckConstraint("length(reset_period) <= 10", name="ck_number_sequence__reset_period_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(sequence_key) <= 50", name="ck_number_sequence__sequence_key_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_number_sequence__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_number_sequence__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_number_sequence__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_number_sequence__version_positive"),
    )
    op.create_index(
        "ux_number_sequence__key",
        "number_sequence",
        ["sequence_key"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    # --- end generated DDL ---
    ms.seed_reference_data(op.get_bind())


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
