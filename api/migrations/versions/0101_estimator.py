"""0101_estimator: the Budgetary Estimate tables and permissions (ADR-012).

Eight new tables (no change to existing ones): estimator_rate_card, estimator_rate_item, budget_estimate,
budget_estimate_line, budget_estimate_assumption, budget_estimate_project_item, budget_estimate_lead_link,
estimate_event. No table holds personal data. Adds the permission codes estimate.read and estimate.manage and grants
them per the matrix where missing (fresh databases already have them from 0003, which reads the live registry).

Expand-only (02 §12.4): the N-1 image never touches these tables, so it runs unchanged on this schema (declared
through VEDA_SCHEMA_AHEAD_ACCEPTED for a rollback).

Revision ID: 0101_estimator
Revises: 0010_consent_evidence_guard
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0101_estimator"
down_revision = "0010_consent_evidence_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "estimator_rate_card",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("card_version", sa.String(40), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="DRAFT"),
        sa.Column("effective_on", UTCDateTime(), nullable=False),
        sa.Column("calculation_version", sa.String(20), nullable=False),
        sa.Column("document", JSONType(), nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.Column("approval_reference", sa.String(200), nullable=True),
        sa.Column("activated_on", UTCDateTime(), nullable=True),
        sa.Column("activated_by", GUID(), nullable=True),
        sa.Column("retired_on", UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_estimator_rate_card"),
        sa.ForeignKeyConstraint(
            ["activated_by"], ["app_user.id"], name="fk_estimator_rate_card__activated_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_estimator_rate_card__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_estimator_rate_card__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_estimator_rate_card__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "activated_by IS NULL OR (length(activated_by) = 32 AND activated_by NOT GLOB '*[^0-9a-f]*' AND substr(activated_by, 13, 1) = '7' AND substr(activated_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_estimator_rate_card__activated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(approval_reference) <= 200", name="ck_estimator_rate_card__approval_reference_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(calculation_version) <= 20", name="ck_estimator_rate_card__calculation_version_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(card_version) <= 40", name="ck_estimator_rate_card__card_version_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_rate_card__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_estimator_rate_card__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "document IS NULL OR json_valid(document)", name="ck_estimator_rate_card__document_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(document_sha256) <= 64", name="ck_estimator_rate_card__document_sha256_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_rate_card__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_estimator_rate_card__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(document_sha256) = 64", name="ck_estimator_rate_card__sha_len"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_estimator_rate_card__soft_delete_consistent",
        ),
        sa.CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="ck_estimator_rate_card__status"),
        sa.CheckConstraint("length(status) <= 10", name="ck_estimator_rate_card__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_estimator_rate_card__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_rate_card__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_estimator_rate_card__version_positive"),
    )
    op.create_index(
        "ux_estimator_rate_card__card_version",
        "estimator_rate_card",
        ["card_version"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_estimator_rate_card__one_active",
        "estimator_rate_card",
        ["status"],
        unique=True,
        sqlite_where=sa.text("status = 'ACTIVE' AND is_deleted = 0"),
        postgresql_where=sa.text("status = 'ACTIVE' AND is_deleted = false"),
    )

    op.create_table(
        "estimator_rate_item",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("rate_card_id", GUID(), nullable=False),
        sa.Column("product_code", sa.String(40), nullable=False),
        sa.Column("line_code", sa.String(40), nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("uom", sa.String(4), nullable=False),
        sa.Column("rate_essential_minor", sa.BigInteger(), nullable=True),
        sa.Column("rate_premium_minor", sa.BigInteger(), nullable=True),
        sa.Column("rate_luxury_minor", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_estimator_rate_item"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_estimator_rate_item__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_estimator_rate_item__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["rate_card_id"],
            ["estimator_rate_card.id"],
            name="fk_estimator_rate_item__rate_card_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_estimator_rate_item__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_rate_item__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_estimator_rate_item__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_rate_item__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_estimator_rate_item__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(label) <= 300", name="ck_estimator_rate_item__label_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(line_code) <= 40", name="ck_estimator_rate_item__line_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(product_code) <= 40", name="ck_estimator_rate_item__product_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(rate_card_id) = 32 AND rate_card_id NOT GLOB '*[^0-9a-f]*' AND substr(rate_card_id, 13, 1) = '7' AND substr(rate_card_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_rate_item__rate_card_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "coalesce(rate_essential_minor, 0) >= 0 AND coalesce(rate_premium_minor, 0) >= 0 AND coalesce(rate_luxury_minor, 0) >= 0",
            name="ck_estimator_rate_item__rates_nonneg",
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_estimator_rate_item__soft_delete_consistent",
        ),
        sa.CheckConstraint("uom IN ('SFT', 'RFT', 'NOS', 'LUMP')", name="ck_estimator_rate_item__uom"),
        sa.CheckConstraint("length(uom) <= 4", name="ck_estimator_rate_item__uom_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_estimator_rate_item__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimator_rate_item__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_estimator_rate_item__version_positive"),
    )
    op.create_index(
        "ux_estimator_rate_item__card_line",
        "estimator_rate_item",
        ["rate_card_id", "product_code", "line_code"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "budget_estimate",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("public_reference", sa.String(9), nullable=False),
        sa.Column("rate_card_id", GUID(), nullable=False),
        sa.Column("rate_card_version", sa.String(40), nullable=False),
        sa.Column("calculation_version", sa.String(20), nullable=False),
        sa.Column("origin", sa.String(10), nullable=False),
        sa.Column("source_estimate_id", GUID(), nullable=True),
        sa.Column("package", sa.String(10), nullable=False),
        sa.Column("property_type", sa.String(10), nullable=False),
        sa.Column("home_size", sa.String(6), nullable=False),
        sa.Column("project_kind", sa.String(10), nullable=False),
        sa.Column("city", sa.String(60), nullable=True),
        sa.Column("inputs", JSONType(), nullable=False),
        sa.Column("result", JSONType(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("base_minor", sa.BigInteger(), nullable=False),
        sa.Column("range_low_minor", sa.BigInteger(), nullable=False),
        sa.Column("range_high_minor", sa.BigInteger(), nullable=False),
        sa.Column("preparation_minor", sa.BigInteger(), nullable=False),
        sa.Column("allowance_minor", sa.BigInteger(), nullable=False),
        sa.Column("allowance_low_minor", sa.BigInteger(), nullable=False),
        sa.Column("allowance_high_minor", sa.BigInteger(), nullable=False),
        sa.Column("optional_minor", sa.BigInteger(), nullable=False),
        sa.Column("gst_low_minor", sa.BigInteger(), nullable=False),
        sa.Column("gst_high_minor", sa.BigInteger(), nullable=False),
        sa.Column("timeline_min_days", sa.Integer(), nullable=False),
        sa.Column("timeline_max_days", sa.Integer(), nullable=False),
        sa.Column("budget_range_code", sa.String(20), nullable=False),
        sa.Column("project_type_code", sa.String(30), nullable=False),
        sa.Column("expires_on", UTCDateTime(), nullable=False),
        sa.Column("site_measurement_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("id", name="pk_budget_estimate"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_budget_estimate__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_budget_estimate__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["rate_card_id"], ["estimator_rate_card.id"], name="fk_budget_estimate__rate_card_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_estimate_id"],
            ["budget_estimate.id"],
            name="fk_budget_estimate__source_estimate_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_budget_estimate__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "base_minor >= 0 AND range_low_minor >= 0 AND range_low_minor <= base_minor AND base_minor <= range_high_minor AND preparation_minor >= 0 AND optional_minor >= 0 AND allowance_low_minor >= 0 AND allowance_low_minor <= allowance_minor AND allowance_minor <= allowance_high_minor AND gst_low_minor >= 0 AND gst_high_minor >= gst_low_minor",
            name="ck_budget_estimate__amounts",
        ),
        sa.CheckConstraint("length(budget_range_code) <= 20", name="ck_budget_estimate__budget_range_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(calculation_version) <= 20", name="ck_budget_estimate__calculation_version_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(city) <= 60", name="ck_budget_estimate__city_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(currency) <= 3", name="ck_budget_estimate__currency_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_budget_estimate__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "home_size IN ('1BHK', '2BHK', '3BHK', '4BHK', 'CUSTOM')", name="ck_budget_estimate__home_size"
        ),
        sa.CheckConstraint("length(home_size) <= 6", name="ck_budget_estimate__home_size_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("inputs IS NULL OR json_valid(inputs)", name="ck_budget_estimate__inputs_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_budget_estimate__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("origin IN ('PUBLIC', 'STAFF')", name="ck_budget_estimate__origin"),
        sa.CheckConstraint("length(origin) <= 10", name="ck_budget_estimate__origin_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("package IN ('ESSENTIAL', 'PREMIUM', 'LUXURY')", name="ck_budget_estimate__package"),
        sa.CheckConstraint("length(package) <= 10", name="ck_budget_estimate__package_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("project_kind IN ('NEW_HOME', 'RENOVATION')", name="ck_budget_estimate__project_kind"),
        sa.CheckConstraint("length(project_kind) <= 10", name="ck_budget_estimate__project_kind_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(project_type_code) <= 30", name="ck_budget_estimate__project_type_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("property_type IN ('APARTMENT', 'VILLA')", name="ck_budget_estimate__property_type"),
        sa.CheckConstraint("length(property_type) <= 10", name="ck_budget_estimate__property_type_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(public_reference) <= 9", name="ck_budget_estimate__public_reference_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(rate_card_id) = 32 AND rate_card_id NOT GLOB '*[^0-9a-f]*' AND substr(rate_card_id, 13, 1) = '7' AND substr(rate_card_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate__rate_card_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(rate_card_version) <= 40", name="ck_budget_estimate__rate_card_version_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("result IS NULL OR json_valid(result)", name="ck_budget_estimate__result_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "site_measurement_required IN (0, 1)", name="ck_budget_estimate__site_measurement_required_bool"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_budget_estimate__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "source_estimate_id IS NULL OR (length(source_estimate_id) = 32 AND source_estimate_id NOT GLOB '*[^0-9a-f]*' AND substr(source_estimate_id, 13, 1) = '7' AND substr(source_estimate_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_budget_estimate__source_estimate_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "timeline_min_days >= 1 AND timeline_max_days >= timeline_min_days", name="ck_budget_estimate__timeline"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_budget_estimate__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_budget_estimate__version_positive"),
    )
    op.create_index(
        "ix_budget_estimate__expires",
        "budget_estimate",
        ["expires_on"],
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_budget_estimate__source",
        "budget_estimate",
        ["source_estimate_id"],
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index("ux_budget_estimate__public_reference", "budget_estimate", ["public_reference"], unique=True)

    op.create_table(
        "budget_estimate_line",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("estimate_id", GUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("room", sa.String(20), nullable=False),
        sa.Column("instance", sa.Integer(), nullable=False),
        sa.Column("product_code", sa.String(40), nullable=False),
        sa.Column("line_code", sa.String(40), nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("uom", sa.String(4), nullable=False),
        sa.Column("quantity_centi", sa.BigInteger(), nullable=False),
        sa.Column("rate_minor", sa.BigInteger(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("is_typical", sa.Boolean(), nullable=False),
        sa.Column("is_optional", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_budget_estimate_line"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_budget_estimate_line__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_budget_estimate_line__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["estimate_id"], ["budget_estimate.id"], name="fk_budget_estimate_line__estimate_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_budget_estimate_line__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "quantity_centi > 0 AND rate_minor >= 0 AND amount_minor >= 0", name="ck_budget_estimate_line__amounts"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate_line__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_budget_estimate_line__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(estimate_id) = 32 AND estimate_id NOT GLOB '*[^0-9a-f]*' AND substr(estimate_id, 13, 1) = '7' AND substr(estimate_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate_line__estimate_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate_line__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_budget_estimate_line__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("is_optional IN (0, 1)", name="ck_budget_estimate_line__is_optional_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("is_typical IN (0, 1)", name="ck_budget_estimate_line__is_typical_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(label) <= 300", name="ck_budget_estimate_line__label_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(line_code) <= 40", name="ck_budget_estimate_line__line_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(product_code) <= 40", name="ck_budget_estimate_line__product_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(room) <= 20", name="ck_budget_estimate_line__room_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_budget_estimate_line__soft_delete_consistent",
        ),
        sa.CheckConstraint("uom IN ('SFT', 'RFT', 'NOS', 'LUMP')", name="ck_budget_estimate_line__uom"),
        sa.CheckConstraint("length(uom) <= 4", name="ck_budget_estimate_line__uom_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_budget_estimate_line__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate_line__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_budget_estimate_line__version_positive"),
    )
    op.create_index(
        "ux_budget_estimate_line__position",
        "budget_estimate_line",
        ["estimate_id", "position"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "budget_estimate_assumption",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("estimate_id", GUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("room", sa.String(20), nullable=False),
        sa.Column("instance", sa.Integer(), nullable=False),
        sa.Column("product_code", sa.String(40), nullable=False),
        sa.Column("input_code", sa.String(40), nullable=False),
        sa.Column("value_centi", sa.BigInteger(), nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
        sa.Column("text", sa.String(300), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_budget_estimate_assumption"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_budget_estimate_assumption__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_budget_estimate_assumption__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["estimate_id"],
            ["budget_estimate.id"],
            name="fk_budget_estimate_assumption__estimate_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_budget_estimate_assumption__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate_assumption__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_budget_estimate_assumption__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(estimate_id) = 32 AND estimate_id NOT GLOB '*[^0-9a-f]*' AND substr(estimate_id, 13, 1) = '7' AND substr(estimate_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate_assumption__estimate_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate_assumption__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(input_code) <= 40", name="ck_budget_estimate_assumption__input_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_budget_estimate_assumption__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(product_code) <= 40", name="ck_budget_estimate_assumption__product_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(room) <= 20", name="ck_budget_estimate_assumption__room_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_budget_estimate_assumption__soft_delete_consistent",
        ),
        sa.CheckConstraint("length(text) <= 300", name="ck_budget_estimate_assumption__text_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(unit) <= 10", name="ck_budget_estimate_assumption__unit_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_budget_estimate_assumption__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate_assumption__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_budget_estimate_assumption__version_positive"),
    )
    op.create_index(
        "ux_budget_estimate_assumption__position",
        "budget_estimate_assumption",
        ["estimate_id", "position"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "budget_estimate_project_item",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("estimate_id", GUID(), nullable=False),
        sa.Column("component_code", sa.String(40), nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("inclusion", sa.String(300), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_budget_estimate_project_item"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_budget_estimate_project_item__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_budget_estimate_project_item__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["estimate_id"],
            ["budget_estimate.id"],
            name="fk_budget_estimate_project_item__estimate_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_budget_estimate_project_item__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("amount_minor >= 0", name="ck_budget_estimate_project_item__amount"),
        sa.CheckConstraint(
            "length(component_code) <= 40", name="ck_budget_estimate_project_item__component_code_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate_project_item__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_budget_estimate_project_item__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(estimate_id) = 32 AND estimate_id NOT GLOB '*[^0-9a-f]*' AND substr(estimate_id, 13, 1) = '7' AND substr(estimate_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate_project_item__estimate_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate_project_item__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(inclusion) <= 300", name="ck_budget_estimate_project_item__inclusion_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_budget_estimate_project_item__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(label) <= 300", name="ck_budget_estimate_project_item__label_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_budget_estimate_project_item__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_budget_estimate_project_item__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate_project_item__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_budget_estimate_project_item__version_positive"),
    )
    op.create_index(
        "ux_budget_estimate_project_item__component",
        "budget_estimate_project_item",
        ["estimate_id", "component_code"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "budget_estimate_lead_link",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("estimate_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("consent_policy_version", sa.String(40), nullable=True),
        sa.Column("preferred_contact", sa.String(10), nullable=True),
        sa.Column("linked_on", UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_budget_estimate_lead_link"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_budget_estimate_lead_link__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_budget_estimate_lead_link__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["estimate_id"],
            ["budget_estimate.id"],
            name="fk_budget_estimate_lead_link__estimate_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["lead.id"], name="fk_budget_estimate_lead_link__lead_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_budget_estimate_lead_link__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(consent_policy_version) <= 40", name="ck_budget_estimate_lead_link__consent_policy_version_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate_lead_link__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_budget_estimate_lead_link__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(estimate_id) = 32 AND estimate_id NOT GLOB '*[^0-9a-f]*' AND substr(estimate_id, 13, 1) = '7' AND substr(estimate_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate_lead_link__estimate_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate_lead_link__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_budget_estimate_lead_link__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate_lead_link__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "preferred_contact IS NULL OR preferred_contact IN ('PHONE', 'WHATSAPP', 'EMAIL')",
            name="ck_budget_estimate_lead_link__preferred_contact",
        ),
        sa.CheckConstraint(
            "length(preferred_contact) <= 10", name="ck_budget_estimate_lead_link__preferred_contact_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_budget_estimate_lead_link__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_budget_estimate_lead_link__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_budget_estimate_lead_link__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_budget_estimate_lead_link__version_positive"),
    )
    op.create_index(
        "ix_budget_estimate_lead_link__lead",
        "budget_estimate_lead_link",
        ["lead_id"],
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_budget_estimate_lead_link__estimate",
        "budget_estimate_lead_link",
        ["estimate_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "estimate_event",
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
        sa.Column("estimate_id", GUID(), nullable=True),
        sa.Column("rate_card_id", GUID(), nullable=True),
        sa.Column("detail", JSONType(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_estimate_event"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_estimate_event__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_estimate_event__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["estimate_id"], ["budget_estimate.id"], name="fk_estimate_event__estimate_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["rate_card_id"], ["estimator_rate_card.id"], name="fk_estimate_event__rate_card_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_estimate_event__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimate_event__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_estimate_event__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("detail IS NULL OR json_valid(detail)", name="ck_estimate_event__detail_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "estimate_id IS NULL OR (length(estimate_id) = 32 AND estimate_id NOT GLOB '*[^0-9a-f]*' AND substr(estimate_id, 13, 1) = '7' AND substr(estimate_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_estimate_event__estimate_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "event_type IN ('CARD_LOADED', 'CARD_ACTIVATED', 'CARD_RETIRED', 'CARD_ROLLED_BACK', 'ESTIMATE_CREATED', 'ESTIMATE_LINKED', 'ESTIMATE_DUPLICATED', 'ESTIMATE_REVISED', 'CONSULTATION_COPY', 'SITE_MEASUREMENT_REQUIRED', 'QUOTATION_PROCESS_STARTED', 'ESTIMATE_EXPIRED')",
            name="ck_estimate_event__event_type",
        ),
        sa.CheckConstraint("length(event_type) <= 30", name="ck_estimate_event__event_type_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimate_event__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_estimate_event__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "rate_card_id IS NULL OR (length(rate_card_id) = 32 AND rate_card_id NOT GLOB '*[^0-9a-f]*' AND substr(rate_card_id, 13, 1) = '7' AND substr(rate_card_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_estimate_event__rate_card_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_estimate_event__soft_delete_consistent",
        ),
        sa.CheckConstraint("estimate_id IS NOT NULL OR rate_card_id IS NOT NULL", name="ck_estimate_event__subject"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_estimate_event__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_estimate_event__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_estimate_event__version_positive"),
    )
    op.create_index(
        "ix_estimate_event__card",
        "estimate_event",
        ["rate_card_id", "created_on"],
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_estimate_event__estimate",
        "estimate_event",
        ["estimate_id", "created_on"],
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    # --- end generated DDL ---
    bind = op.get_bind()
    ms.sync_permissions(bind, audit=True)
    ms.grant_new_codes(bind, ("estimate.read", "estimate.manage"), audit=True)
    ms.assert_rbac_seed(bind)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
