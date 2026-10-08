"""0102_estimator_spec: the customer specification master and its snapshot on each estimate (ADR-012 T9).

Three new tables: estimator_customer_spec (versioned customer-facing material specification, one ACTIVE per package),
estimator_customer_spec_item (its categories, flattened for staff review) and estimator_spec_event (load, activation,
retirement, rollback). Two nullable columns on budget_estimate record the specification version an estimate showed:
customer_spec_id and customer_spec_sha256. No rates, costs or personal data. No permission changes (specifications
are operator-loaded through the CLI, like rate cards).

Expand-only (02 §12.4): new tables and nullable columns, no data rewrite. The N-1 image never reads them, and rows it
writes carry NULLs (no specification shown), so a rollback runs unchanged (VEDA_SCHEMA_AHEAD_ACCEPTED).

Revision ID: 0102_estimator_spec
Revises: 0101_estimator
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel.base import guid_format_sql
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0102_estimator_spec"
down_revision = "0101_estimator"
branch_labels = None
depends_on = None


def _snapshot_columns(dialect: str) -> None:
    if dialect == "sqlite":
        fmt = guid_format_sql("customer_spec_id")
        op.execute(
            "ALTER TABLE budget_estimate ADD COLUMN customer_spec_id CHAR(32) "
            "CONSTRAINT fk_budget_estimate__customer_spec_id REFERENCES estimator_customer_spec (id) ON DELETE RESTRICT "
            f"CONSTRAINT ck_budget_estimate__customer_spec_id_format CHECK (customer_spec_id IS NULL OR ({fmt}))"
        )
        op.execute(
            "ALTER TABLE budget_estimate ADD COLUMN customer_spec_sha256 VARCHAR(64) "
            "CONSTRAINT ck_budget_estimate__customer_spec_sha256_len CHECK (length(customer_spec_sha256) <= 64)"
        )
        return
    op.add_column("budget_estimate", sa.Column("customer_spec_id", GUID(), nullable=True))
    op.add_column("budget_estimate", sa.Column("customer_spec_sha256", sa.String(64), nullable=True))
    op.create_foreign_key(
        "fk_budget_estimate__customer_spec_id",
        "budget_estimate",
        "estimator_customer_spec",
        ["customer_spec_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "estimator_customer_spec",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("spec_code", sa.String(40), nullable=False),
        sa.Column("spec_version", sa.String(20), nullable=False),
        sa.Column("package", sa.String(10), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("summary", sa.String(300), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="DRAFT"),
        sa.Column("effective_on", UTCDateTime(), nullable=False),
        sa.Column("document", JSONType(), nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.Column("approval_reference", sa.String(200), nullable=True),
        sa.Column("activated_on", UTCDateTime(), nullable=True),
        sa.Column("activated_by", GUID(), nullable=True),
        sa.Column("retired_on", UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_estimator_customer_spec"),
        sa.ForeignKeyConstraint(
            ["activated_by"], ["app_user.id"], name="fk_estimator_customer_spec__activated_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_estimator_customer_spec__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_estimator_customer_spec__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_estimator_customer_spec__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "activated_by IS NULL OR (length(activated_by) = 32 AND activated_by NOT GLOB '*[^0-9a-f]*' AND substr(activated_by, 13, 1) = '7' AND substr(activated_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_estimator_customer_spec__activated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(approval_reference) <= 200", name="ck_estimator_customer_spec__approval_reference_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_customer_spec__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_estimator_customer_spec__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "document IS NULL OR json_valid(document)", name="ck_estimator_customer_spec__document_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(document_sha256) <= 64", name="ck_estimator_customer_spec__document_sha256_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_customer_spec__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_estimator_customer_spec__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(name) <= 120", name="ck_estimator_customer_spec__name_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("package IN ('ESSENTIAL', 'PREMIUM', 'LUXURY')", name="ck_estimator_customer_spec__package"),
        sa.CheckConstraint("length(package) <= 10", name="ck_estimator_customer_spec__package_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(document_sha256) = 64", name="ck_estimator_customer_spec__sha_len"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_estimator_customer_spec__soft_delete_consistent",
        ),
        sa.CheckConstraint("length(spec_code) <= 40", name="ck_estimator_customer_spec__spec_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(spec_version) <= 20", name="ck_estimator_customer_spec__spec_version_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="ck_estimator_customer_spec__status"),
        sa.CheckConstraint("length(status) <= 10", name="ck_estimator_customer_spec__status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(summary) <= 300", name="ck_estimator_customer_spec__summary_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_estimator_customer_spec__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_customer_spec__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_estimator_customer_spec__version_positive"),
    )
    op.create_index(
        "ux_estimator_customer_spec__one_active",
        "estimator_customer_spec",
        ["package"],
        unique=True,
        sqlite_where=sa.text("status = 'ACTIVE' AND is_deleted = 0"),
        postgresql_where=sa.text("status = 'ACTIVE' AND is_deleted = false"),
    )
    op.create_index(
        "ux_estimator_customer_spec__spec_code",
        "estimator_customer_spec",
        ["spec_code"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "estimator_customer_spec_item",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("customer_spec_id", GUID(), nullable=False),
        sa.Column("category_code", sa.String(40), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("summary", sa.String(160), nullable=False),
        sa.Column("requirement", sa.String(300), nullable=False),
        sa.Column("grade", sa.String(160), nullable=True),
        sa.Column("thickness", sa.String(300), nullable=True),
        sa.Column("finish", sa.String(160), nullable=True),
        sa.Column("brand_examples", sa.String(400), nullable=True),
        sa.Column("equivalent_rule", sa.String(300), nullable=False),
        sa.Column("final_selection", sa.String(300), nullable=False),
        sa.Column("hardware_category", sa.String(80), nullable=True),
        sa.Column("warranty_summary", sa.String(300), nullable=False),
        sa.Column("applicability", JSONType(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_estimator_customer_spec_item"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_estimator_customer_spec_item__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["customer_spec_id"],
            ["estimator_customer_spec.id"],
            name="fk_estimator_customer_spec_item__customer_spec_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_estimator_customer_spec_item__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_estimator_customer_spec_item__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "applicability IS NULL OR json_valid(applicability)",
            name="ck_estimator_customer_spec_item__applicability_json",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(brand_examples) <= 400", name="ck_estimator_customer_spec_item__brand_examples_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(category_code) <= 40", name="ck_estimator_customer_spec_item__category_code_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_customer_spec_item__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(customer_spec_id) = 32 AND customer_spec_id NOT GLOB '*[^0-9a-f]*' AND substr(customer_spec_id, 13, 1) = '7' AND substr(customer_spec_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_customer_spec_item__customer_spec_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_estimator_customer_spec_item__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(equivalent_rule) <= 300", name="ck_estimator_customer_spec_item__equivalent_rule_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(final_selection) <= 300", name="ck_estimator_customer_spec_item__final_selection_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(finish) <= 160", name="ck_estimator_customer_spec_item__finish_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(grade) <= 160", name="ck_estimator_customer_spec_item__grade_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(hardware_category) <= 80", name="ck_estimator_customer_spec_item__hardware_category_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_customer_spec_item__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_estimator_customer_spec_item__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(label) <= 80", name="ck_estimator_customer_spec_item__label_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(requirement) <= 300", name="ck_estimator_customer_spec_item__requirement_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_estimator_customer_spec_item__soft_delete_consistent",
        ),
        sa.CheckConstraint("length(summary) <= 160", name="ck_estimator_customer_spec_item__summary_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(thickness) <= 300", name="ck_estimator_customer_spec_item__thickness_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_estimator_customer_spec_item__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_customer_spec_item__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_estimator_customer_spec_item__version_positive"),
        sa.CheckConstraint(
            "length(warranty_summary) <= 300", name="ck_estimator_customer_spec_item__warranty_summary_len"
        ).ddl_if(dialect="sqlite"),
    )
    op.create_index(
        "ux_estimator_customer_spec_item__spec_category",
        "estimator_customer_spec_item",
        ["customer_spec_id", "category_code"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "estimator_spec_event",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("customer_spec_id", GUID(), nullable=False),
        sa.Column("detail", JSONType(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_estimator_spec_event"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_estimator_spec_event__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["customer_spec_id"],
            ["estimator_customer_spec.id"],
            name="fk_estimator_spec_event__customer_spec_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_estimator_spec_event__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_estimator_spec_event__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_spec_event__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(customer_spec_id) = 32 AND customer_spec_id NOT GLOB '*[^0-9a-f]*' AND substr(customer_spec_id, 13, 1) = '7' AND substr(customer_spec_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_spec_event__customer_spec_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_estimator_spec_event__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("detail IS NULL OR json_valid(detail)", name="ck_estimator_spec_event__detail_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "event_type IN ('SPEC_LOADED', 'SPEC_ACTIVATED', 'SPEC_RETIRED', 'SPEC_ROLLED_BACK')",
            name="ck_estimator_spec_event__event_type",
        ),
        sa.CheckConstraint("length(event_type) <= 30", name="ck_estimator_spec_event__event_type_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_spec_event__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_estimator_spec_event__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_estimator_spec_event__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_estimator_spec_event__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_spec_event__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_estimator_spec_event__version_positive"),
    )
    op.create_index(
        "ix_estimator_spec_event__spec",
        "estimator_spec_event",
        ["customer_spec_id", "created_on"],
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    # --- end generated DDL ---
    _snapshot_columns(op.get_bind().dialect.name)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
