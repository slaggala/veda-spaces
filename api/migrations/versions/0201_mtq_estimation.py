"""0201_mtq_estimation: MTQ B2 scope and BOQ, B3 estimates, and the commercial roles (blueprint §4.2, §16 B2-B3;
decision log 31).

Tables: ``requirement``, ``scope``, ``scope_item``, ``boq``, ``boq_line`` (B2); ``cost_estimate``,
``cost_estimate_line``, ``cost_estimate_adjustment`` (B3). No rate table is added: estimates price with the
estimator's existing versioned rate card and pin it. Roles ``ESTIMATOR`` and ``SALES_MANAGER``
with the B2/B3 permission codes, plus the read grants they need on the B1 site records and the workspace self-service
rows. Expand-only (02 §12.4): new tables and rows only; no existing table is altered. The tables are inert while
VEDA_MTQ_ESTIMATION_ENABLED is off (the default everywhere; production refuses it).

The revision takes the number reserved for it by the B1 blocker closure (§4); it follows 0204, the corrective B1
revision that took the next free number.

Revision ID: 0201_mtq_estimation
Revises: 0204_mtq_self_service
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0201_mtq_estimation"
down_revision = "0204_mtq_self_service"
branch_labels = None
depends_on = None

ROLES = ("ESTIMATOR", "SALES_MANAGER")
CODES = (
    "scope.read",
    "scope.edit",
    "scope.confirm",
    "boq.read",
    "boq.generate",
    "boq.override",
    "boq.review",
    "cost_estimate.read",
    "cost_estimate.rate.view",
    "cost_estimate.create",
    "cost_estimate.approve",
    "cost_estimate.discount.apply",
    "cost_estimate.discount.approve",
    # existing codes the new roles need: the B1 site records, the lead (sales manager) and the workspace shell
    "property.read",
    "measurement.visit.read",
    "measurement.read",
    "attachment.read",
    "lead.read",
    "profile.read",
    "lookup.read",
    "notification.read",
)


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "requirement",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("property_id", GUID(), nullable=False),
        sa.Column("space_id", GUID(), nullable=True),
        sa.Column("requirement_type_code", sa.String(40), nullable=False),
        sa.Column("custom_label", sa.String(120), nullable=True),
        sa.Column("necessity_code", sa.String(12), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source_code", sa.String(20), nullable=False),
        sa.Column("source_ref", JSONType(), nullable=False),
        sa.Column("anchor_wall_index", sa.Integer(), nullable=True),
        sa.Column("instance_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("dedupe_key", sa.String(120), nullable=False),
        sa.Column("preferences", JSONType(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("decided_by", GUID(), nullable=True),
        sa.Column("decided_on", UTCDateTime(), nullable=True),
        sa.Column("decision_reason", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_requirement"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_requirement__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["app_user.id"], name="fk_requirement__decided_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_requirement__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_requirement__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["property_id"], ["property.id"], name="fk_requirement__property_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["space_id"], ["property_space.id"], name="fk_requirement__space_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_requirement__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_requirement__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "requirement_type_code <> 'CUSTOM' OR custom_label IS NOT NULL", name="ck_requirement__custom_label"
        ),
        sa.CheckConstraint("length(custom_label) <= 120", name="ck_requirement__custom_label_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "status = 'PROPOSED' OR (decided_by IS NOT NULL AND decided_on IS NOT NULL)", name="ck_requirement__decided"
        ),
        sa.CheckConstraint(
            "decided_by IS NULL OR (length(decided_by) = 32 AND decided_by NOT GLOB '*[^0-9a-f]*' AND substr(decided_by, 13, 1) = '7' AND substr(decided_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_requirement__decided_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(decision_reason) <= 500", name="ck_requirement__decision_reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(dedupe_key) <= 120", name="ck_requirement__dedupe_key_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_requirement__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_requirement__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("instance_no >= 1", name="ck_requirement__instance_no"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_requirement__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_requirement__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "necessity_code IN ('MANDATORY', 'RECOMMENDED', 'OPTIONAL')", name="ck_requirement__necessity_code"
        ),
        sa.CheckConstraint("length(necessity_code) <= 12", name="ck_requirement__necessity_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "preferences IS NULL OR json_valid(preferences)", name="ck_requirement__preferences_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(property_id) = 32 AND property_id NOT GLOB '*[^0-9a-f]*' AND substr(property_id, 13, 1) = '7' AND substr(property_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_requirement__property_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "requirement_type_code IN ('WARDROBE', 'TV_UNIT', 'CROCKERY_UNIT', 'STUDY_UNIT', 'VANITY', 'DRESSER', 'KITCHEN', 'KITCHEN_TALL_UNIT', 'UTILITY_UNIT', 'BED', 'SIDE_TABLE', 'STORAGE_UNIT', 'FALSE_CEILING', 'PROFILE_LIGHTING', 'WALL_PANELLING', 'MIRROR_PANEL', 'CURTAIN_PELMET', 'PARTITION', 'POOJA_UNIT', 'WINDOW_SEATING', 'PAINTING', 'ELECTRICAL', 'ELECTRICAL_SHIFTING', 'SENSOR_LIGHTING', 'CUSTOM')",
            name="ck_requirement__requirement_type_code",
        ),
        sa.CheckConstraint(
            "length(requirement_type_code) <= 40", name="ck_requirement__requirement_type_code_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_requirement__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "source_code IN ('SURVEY_TEMPLATE', 'MEASUREMENT_RULE', 'STAFF_SELECTION', 'CUSTOMER_REQUEST', 'MANUAL')",
            name="ck_requirement__source_code",
        ),
        sa.CheckConstraint("length(source_code) <= 20", name="ck_requirement__source_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "source_ref IS NULL OR json_valid(source_ref)", name="ck_requirement__source_ref_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "space_id IS NULL OR (length(space_id) = 32 AND space_id NOT GLOB '*[^0-9a-f]*' AND substr(space_id, 13, 1) = '7' AND substr(space_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_requirement__space_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status IN ('PROPOSED', 'ACCEPTED', 'EXCLUDED', 'NOT_APPLICABLE')", name="ck_requirement__status"
        ),
        sa.CheckConstraint("length(status) <= 16", name="ck_requirement__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_requirement__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_requirement__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_requirement__version_positive"),
    )
    op.create_index("ix_requirement__lead_id", "requirement", ["lead_id"])
    op.create_index("ix_requirement__space_id", "requirement", ["space_id"])
    op.create_index(
        "ux_requirement__property_dedupe",
        "requirement",
        ["property_id", "dedupe_key"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "scope",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("property_id", GUID(), nullable=False),
        sa.Column("measurement_set_id", GUID(), nullable=False),
        sa.Column("measurement_revision_no", sa.Integer(), nullable=False),
        sa.Column("measurement_snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("supersedes_scope_id", GUID(), nullable=True),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("tier_code", sa.String(10), nullable=False),
        sa.Column("ruleset_version", sa.String(20), nullable=False),
        sa.Column("ruleset_sha256", sa.String(64), nullable=False),
        sa.Column("ruleset_status", sa.String(30), nullable=False),
        sa.Column("generation_run", JSONType(), nullable=False),
        sa.Column("exclusions", JSONType(), nullable=False),
        sa.Column("confirmed_on", UTCDateTime(), nullable=True),
        sa.Column("confirmed_by", GUID(), nullable=True),
        sa.Column("snapshot_sha256", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_scope"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["app_user.id"], name="fk_scope__confirmed_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], name="fk_scope__created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["app_user.id"], name="fk_scope__deleted_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_scope__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["measurement_set_id"], ["measurement_set.id"], name="fk_scope__measurement_set_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["property_id"], ["property.id"], name="fk_scope__property_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["supersedes_scope_id"], ["scope.id"], name="fk_scope__supersedes_scope_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], name="fk_scope__updated_by", ondelete="RESTRICT"),
        sa.CheckConstraint(
            "confirmed_by IS NULL OR (length(confirmed_by) = 32 AND confirmed_by NOT GLOB '*[^0-9a-f]*' AND substr(confirmed_by, 13, 1) = '7' AND substr(confirmed_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_scope__confirmed_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status = 'DRAFT' OR (confirmed_on IS NOT NULL AND confirmed_by IS NOT NULL AND snapshot_sha256 IS NOT NULL)",
            name="ck_scope__confirmed_sealed",
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_scope__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_scope__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("exclusions IS NULL OR json_valid(exclusions)", name="ck_scope__exclusions_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "generation_run IS NULL OR json_valid(generation_run)", name="ck_scope__generation_run_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_scope__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_scope__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_scope__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(measurement_set_id) = 32 AND measurement_set_id NOT GLOB '*[^0-9a-f]*' AND substr(measurement_set_id, 13, 1) = '7' AND substr(measurement_set_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_scope__measurement_set_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(measurement_snapshot_sha256) <= 64", name="ck_scope__measurement_snapshot_sha256_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("supersedes_scope_id IS NULL OR supersedes_scope_id <> id", name="ck_scope__not_self"),
        sa.CheckConstraint(
            "length(property_id) = 32 AND property_id NOT GLOB '*[^0-9a-f]*' AND substr(property_id, 13, 1) = '7' AND substr(property_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_scope__property_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("revision_no >= 1", name="ck_scope__revision_no"),
        sa.CheckConstraint("length(ruleset_sha256) <= 64", name="ck_scope__ruleset_sha256_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(ruleset_status) <= 30", name="ck_scope__ruleset_status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(ruleset_version) <= 20", name="ck_scope__ruleset_version_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "snapshot_sha256 IS NULL OR length(snapshot_sha256) = 64", name="ck_scope__snapshot_sha256_len"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_scope__soft_delete_consistent",
        ),
        sa.CheckConstraint("status IN ('DRAFT', 'CONFIRMED', 'SUPERSEDED')", name="ck_scope__status"),
        sa.CheckConstraint("length(status) <= 12", name="ck_scope__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "supersedes_scope_id IS NULL OR (length(supersedes_scope_id) = 32 AND supersedes_scope_id NOT GLOB '*[^0-9a-f]*' AND substr(supersedes_scope_id, 13, 1) = '7' AND substr(supersedes_scope_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_scope__supersedes_scope_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("tier_code IN ('ESSENTIAL', 'PREMIUM', 'LUXURY')", name="ck_scope__tier_code"),
        sa.CheckConstraint("length(tier_code) <= 10", name="ck_scope__tier_code_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_scope__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_scope__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_scope__version_positive"),
    )
    op.create_index("ix_scope__lead_id", "scope", ["lead_id"])
    op.create_index("ix_scope__measurement_set_id", "scope", ["measurement_set_id"])
    op.create_index("ix_scope__supersedes_scope_id", "scope", ["supersedes_scope_id"])
    op.create_index(
        "ux_scope__one_confirmed",
        "scope",
        ["property_id"],
        unique=True,
        sqlite_where=sa.text("status = 'CONFIRMED' AND is_deleted = 0"),
        postgresql_where=sa.text("status = 'CONFIRMED' AND is_deleted = false"),
    )
    op.create_index(
        "ux_scope__one_draft",
        "scope",
        ["property_id"],
        unique=True,
        sqlite_where=sa.text("status = 'DRAFT' AND is_deleted = 0"),
        postgresql_where=sa.text("status = 'DRAFT' AND is_deleted = false"),
    )
    op.create_index(
        "ux_scope__property_revision",
        "scope",
        ["property_id", "revision_no"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "scope_item",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("scope_id", GUID(), nullable=False),
        sa.Column("requirement_id", GUID(), nullable=False),
        sa.Column("space_id", GUID(), nullable=True),
        sa.Column("item_type_code", sa.String(40), nullable=False),
        sa.Column("card_product_code", sa.String(40), nullable=True),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("origin_code", sa.String(20), nullable=False),
        sa.Column("necessity_code", sa.String(12), nullable=False),
        sa.Column("inclusion_code", sa.String(10), nullable=False),
        sa.Column("rule_key", sa.String(80), nullable=True),
        sa.Column("anchor_wall_index", sa.Integer(), nullable=True),
        sa.Column("options", JSONType(), nullable=False),
        sa.Column("finish_code", sa.String(20), nullable=True),
        sa.Column("material_key", sa.String(80), nullable=True),
        sa.Column("dimensions", JSONType(), nullable=False),
        sa.Column("dimension_overrides", JSONType(), nullable=False),
        sa.Column("override_reason", sa.String(500), nullable=True),
        sa.Column("dimension_source_code", sa.String(10), nullable=False),
        sa.Column("carried_from_item_id", GUID(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_scope_item"),
        sa.ForeignKeyConstraint(
            ["carried_from_item_id"], ["scope_item.id"], name="fk_scope_item__carried_from_item_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], name="fk_scope_item__created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["app_user.id"], name="fk_scope_item__deleted_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["requirement_id"], ["requirement.id"], name="fk_scope_item__requirement_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["scope_id"], ["scope.id"], name="fk_scope_item__scope_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["space_id"], ["property_space.id"], name="fk_scope_item__space_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], name="fk_scope_item__updated_by", ondelete="RESTRICT"),
        sa.CheckConstraint("length(card_product_code) <= 40", name="ck_scope_item__card_product_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "carried_from_item_id IS NULL OR (length(carried_from_item_id) = 32 AND carried_from_item_id NOT GLOB '*[^0-9a-f]*' AND substr(carried_from_item_id, 13, 1) = '7' AND substr(carried_from_item_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_scope_item__carried_from_item_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_scope_item__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_scope_item__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "dimension_overrides IS NULL OR json_valid(dimension_overrides)",
            name="ck_scope_item__dimension_overrides_json",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "dimension_source_code IN ('MEASURED', 'DERIVED', 'ASSUMED', 'STAFF')",
            name="ck_scope_item__dimension_source_code",
        ),
        sa.CheckConstraint(
            "length(dimension_source_code) <= 10", name="ck_scope_item__dimension_source_code_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "dimensions IS NULL OR json_valid(dimensions)", name="ck_scope_item__dimensions_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "finish_code IS NULL OR finish_code IN ('LAMINATE', 'ACRYLIC', 'VENEER', 'PU', 'GLASS', 'MEMBRANE', 'CUSTOM')",
            name="ck_scope_item__finish_code",
        ),
        sa.CheckConstraint("length(finish_code) <= 20", name="ck_scope_item__finish_code_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_scope_item__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "inclusion_code IN ('INCLUDED', 'OPTIONAL', 'EXCLUDED')", name="ck_scope_item__inclusion_code"
        ),
        sa.CheckConstraint("length(inclusion_code) <= 10", name="ck_scope_item__inclusion_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_scope_item__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "item_type_code IN ('WARDROBE', 'TV_UNIT', 'CROCKERY_UNIT', 'STUDY_UNIT', 'VANITY', 'DRESSER', 'KITCHEN', 'KITCHEN_TALL_UNIT', 'UTILITY_UNIT', 'BED', 'SIDE_TABLE', 'STORAGE_UNIT', 'FALSE_CEILING', 'PROFILE_LIGHTING', 'WALL_PANELLING', 'MIRROR_PANEL', 'CURTAIN_PELMET', 'PARTITION', 'POOJA_UNIT', 'WINDOW_SEATING', 'PAINTING', 'ELECTRICAL', 'ELECTRICAL_SHIFTING', 'SENSOR_LIGHTING', 'CUSTOM')",
            name="ck_scope_item__item_type_code",
        ),
        sa.CheckConstraint("length(item_type_code) <= 40", name="ck_scope_item__item_type_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(label) <= 120", name="ck_scope_item__label_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(material_key) <= 80", name="ck_scope_item__material_key_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "necessity_code IN ('MANDATORY', 'RECOMMENDED', 'OPTIONAL')", name="ck_scope_item__necessity_code"
        ),
        sa.CheckConstraint("length(necessity_code) <= 12", name="ck_scope_item__necessity_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("options IS NULL OR json_valid(options)", name="ck_scope_item__options_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "origin_code IN ('AUTO', 'RECOMMENDED', 'CUSTOMER_REQUESTED', 'MANUAL')", name="ck_scope_item__origin_code"
        ),
        sa.CheckConstraint("length(origin_code) <= 20", name="ck_scope_item__origin_code_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(override_reason) <= 500", name="ck_scope_item__override_reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(requirement_id) = 32 AND requirement_id NOT GLOB '*[^0-9a-f]*' AND substr(requirement_id, 13, 1) = '7' AND substr(requirement_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_scope_item__requirement_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(rule_key) <= 80", name="ck_scope_item__rule_key_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(scope_id) = 32 AND scope_id NOT GLOB '*[^0-9a-f]*' AND substr(scope_id, 13, 1) = '7' AND substr(scope_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_scope_item__scope_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_scope_item__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "space_id IS NULL OR (length(space_id) = 32 AND space_id NOT GLOB '*[^0-9a-f]*' AND substr(space_id, 13, 1) = '7' AND substr(space_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_scope_item__space_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_scope_item__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_scope_item__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_scope_item__version_positive"),
    )
    op.create_index("ix_scope_item__carried_from_item_id", "scope_item", ["carried_from_item_id"])
    op.create_index("ix_scope_item__requirement_id", "scope_item", ["requirement_id"])
    op.create_index("ix_scope_item__space_id", "scope_item", ["space_id"])
    op.create_index(
        "ux_scope_item__scope_requirement",
        "scope_item",
        ["scope_id", "requirement_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "boq",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("property_id", GUID(), nullable=False),
        sa.Column("scope_id", GUID(), nullable=False),
        sa.Column("scope_revision_no", sa.Integer(), nullable=False),
        sa.Column("scope_snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("measurement_set_id", GUID(), nullable=False),
        sa.Column("measurement_revision_no", sa.Integer(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("supersedes_boq_id", GUID(), nullable=True),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("quantity_engine_version", sa.String(20), nullable=False),
        sa.Column("ruleset_version", sa.String(20), nullable=False),
        sa.Column("catalogue_card_id", GUID(), nullable=False),
        sa.Column("catalogue_card_version", sa.String(40), nullable=False),
        sa.Column("catalogue_card_sha256", sa.String(64), nullable=False),
        sa.Column("rounding_policy", JSONType(), nullable=False),
        sa.Column("summary", JSONType(), nullable=False),
        sa.Column("issues", JSONType(), nullable=False),
        sa.Column("reviewed_on", UTCDateTime(), nullable=True),
        sa.Column("reviewed_by", GUID(), nullable=True),
        sa.Column("snapshot_sha256", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_boq"),
        sa.ForeignKeyConstraint(
            ["catalogue_card_id"], ["estimator_rate_card.id"], name="fk_boq__catalogue_card_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], name="fk_boq__created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["app_user.id"], name="fk_boq__deleted_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_boq__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["measurement_set_id"], ["measurement_set.id"], name="fk_boq__measurement_set_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["property_id"], ["property.id"], name="fk_boq__property_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["app_user.id"], name="fk_boq__reviewed_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["scope_id"], ["scope.id"], name="fk_boq__scope_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["supersedes_boq_id"], ["boq.id"], name="fk_boq__supersedes_boq_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], name="fk_boq__updated_by", ondelete="RESTRICT"),
        sa.CheckConstraint(
            "length(catalogue_card_id) = 32 AND catalogue_card_id NOT GLOB '*[^0-9a-f]*' AND substr(catalogue_card_id, 13, 1) = '7' AND substr(catalogue_card_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_boq__catalogue_card_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(catalogue_card_sha256) <= 64", name="ck_boq__catalogue_card_sha256_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(catalogue_card_version) <= 40", name="ck_boq__catalogue_card_version_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_boq__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_boq__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_boq__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_boq__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("issues IS NULL OR json_valid(issues)", name="ck_boq__issues_json").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_boq__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(measurement_set_id) = 32 AND measurement_set_id NOT GLOB '*[^0-9a-f]*' AND substr(measurement_set_id, 13, 1) = '7' AND substr(measurement_set_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_boq__measurement_set_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("supersedes_boq_id IS NULL OR supersedes_boq_id <> id", name="ck_boq__not_self"),
        sa.CheckConstraint(
            "length(property_id) = 32 AND property_id NOT GLOB '*[^0-9a-f]*' AND substr(property_id, 13, 1) = '7' AND substr(property_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_boq__property_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(quantity_engine_version) <= 20", name="ck_boq__quantity_engine_version_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "reviewed_by IS NULL OR (length(reviewed_by) = 32 AND reviewed_by NOT GLOB '*[^0-9a-f]*' AND substr(reviewed_by, 13, 1) = '7' AND substr(reviewed_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_boq__reviewed_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status <> 'REVIEWED' OR (reviewed_on IS NOT NULL AND reviewed_by IS NOT NULL AND snapshot_sha256 IS NOT NULL)",
            name="ck_boq__reviewed_sealed",
        ),
        sa.CheckConstraint("revision_no >= 1", name="ck_boq__revision_no"),
        sa.CheckConstraint(
            "rounding_policy IS NULL OR json_valid(rounding_policy)", name="ck_boq__rounding_policy_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(ruleset_version) <= 20", name="ck_boq__ruleset_version_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(scope_id) = 32 AND scope_id NOT GLOB '*[^0-9a-f]*' AND substr(scope_id, 13, 1) = '7' AND substr(scope_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_boq__scope_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(scope_snapshot_sha256) <= 64", name="ck_boq__scope_snapshot_sha256_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "snapshot_sha256 IS NULL OR length(snapshot_sha256) = 64", name="ck_boq__snapshot_sha256_len"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_boq__soft_delete_consistent",
        ),
        sa.CheckConstraint("status IN ('GENERATED', 'REVIEWED', 'SUPERSEDED')", name="ck_boq__status"),
        sa.CheckConstraint("length(status) <= 12", name="ck_boq__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("summary IS NULL OR json_valid(summary)", name="ck_boq__summary_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "supersedes_boq_id IS NULL OR (length(supersedes_boq_id) = 32 AND supersedes_boq_id NOT GLOB '*[^0-9a-f]*' AND substr(supersedes_boq_id, 13, 1) = '7' AND substr(supersedes_boq_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_boq__supersedes_boq_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_boq__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_boq__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_boq__version_positive"),
    )
    op.create_index("ix_boq__catalogue_card_id", "boq", ["catalogue_card_id"])
    op.create_index("ix_boq__lead_id", "boq", ["lead_id"])
    op.create_index("ix_boq__measurement_set_id", "boq", ["measurement_set_id"])
    op.create_index("ix_boq__scope_id", "boq", ["scope_id"])
    op.create_index("ix_boq__supersedes_boq_id", "boq", ["supersedes_boq_id"])
    op.create_index(
        "ux_boq__one_generated",
        "boq",
        ["property_id"],
        unique=True,
        sqlite_where=sa.text("status = 'GENERATED' AND is_deleted = 0"),
        postgresql_where=sa.text("status = 'GENERATED' AND is_deleted = false"),
    )
    op.create_index(
        "ux_boq__property_revision",
        "boq",
        ["property_id", "revision_no"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "boq_line",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("boq_id", GUID(), nullable=False),
        sa.Column("scope_item_id", GUID(), nullable=False),
        sa.Column("requirement_id", GUID(), nullable=False),
        sa.Column("space_id", GUID(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("item_type_code", sa.String(40), nullable=False),
        sa.Column("card_product_code", sa.String(40), nullable=True),
        sa.Column("card_line_code", sa.String(40), nullable=True),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("uom_code", sa.String(4), nullable=True),
        sa.Column("formula_kind", sa.String(20), nullable=False),
        sa.Column("formula_inputs", JSONType(), nullable=False),
        sa.Column("derivation", sa.String(500), nullable=False),
        sa.Column("measurement_source", JSONType(), nullable=False),
        sa.Column("calculated_quantity_centi", sa.BigInteger(), nullable=True),
        sa.Column("override_quantity_centi", sa.BigInteger(), nullable=True),
        sa.Column("override_reason", sa.String(500), nullable=True),
        sa.Column("override_by", GUID(), nullable=True),
        sa.Column("override_on", UTCDateTime(), nullable=True),
        sa.Column("final_quantity_centi", sa.BigInteger(), nullable=True),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dimension_source_code", sa.String(10), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("issue_codes", JSONType(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_boq_line"),
        sa.ForeignKeyConstraint(["boq_id"], ["boq.id"], name="fk_boq_line__boq_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], name="fk_boq_line__created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["app_user.id"], name="fk_boq_line__deleted_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["override_by"], ["app_user.id"], name="fk_boq_line__override_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["requirement_id"], ["requirement.id"], name="fk_boq_line__requirement_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["scope_item_id"], ["scope_item.id"], name="fk_boq_line__scope_item_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["space_id"], ["property_space.id"], name="fk_boq_line__space_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], name="fk_boq_line__updated_by", ondelete="RESTRICT"),
        sa.CheckConstraint(
            "length(boq_id) = 32 AND boq_id NOT GLOB '*[^0-9a-f]*' AND substr(boq_id, 13, 1) = '7' AND substr(boq_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_boq_line__boq_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "calculated_quantity_centi IS NULL OR calculated_quantity_centi >= 0", name="ck_boq_line__calculated_nn"
        ),
        sa.CheckConstraint("length(card_line_code) <= 40", name="ck_boq_line__card_line_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(card_product_code) <= 40", name="ck_boq_line__card_product_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_boq_line__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_boq_line__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(derivation) <= 500", name="ck_boq_line__derivation_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "dimension_source_code IN ('MEASURED', 'DERIVED', 'ASSUMED', 'STAFF')",
            name="ck_boq_line__dimension_source_code",
        ),
        sa.CheckConstraint("length(dimension_source_code) <= 10", name="ck_boq_line__dimension_source_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "final_quantity_centi IS NULL OR final_quantity_centi = coalesce(override_quantity_centi, calculated_quantity_centi)",
            name="ck_boq_line__final",
        ),
        sa.CheckConstraint(
            "formula_inputs IS NULL OR json_valid(formula_inputs)", name="ck_boq_line__formula_inputs_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "formula_kind IN ('CARD_AREA', 'CARD_DIRECT', 'CARD_COUNT', 'CARD_LUMP', 'MEASURED_COUNT', 'UNMAPPED')",
            name="ck_boq_line__formula_kind",
        ),
        sa.CheckConstraint("length(formula_kind) <= 20", name="ck_boq_line__formula_kind_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_boq_line__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_boq_line__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_optional IN (0, 1)", name="ck_boq_line__is_optional_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "issue_codes IS NULL OR json_valid(issue_codes)", name="ck_boq_line__issue_codes_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(item_type_code) <= 40", name="ck_boq_line__item_type_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(label) <= 300", name="ck_boq_line__label_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "measurement_source IS NULL OR json_valid(measurement_source)", name="ck_boq_line__measurement_source_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "override_by IS NULL OR (length(override_by) = 32 AND override_by NOT GLOB '*[^0-9a-f]*' AND substr(override_by, 13, 1) = '7' AND substr(override_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_boq_line__override_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "override_quantity_centi IS NULL OR (override_reason IS NOT NULL AND override_by IS NOT NULL AND override_on IS NOT NULL)",
            name="ck_boq_line__override_explained",
        ),
        sa.CheckConstraint(
            "override_quantity_centi IS NULL OR override_quantity_centi >= 0", name="ck_boq_line__override_nn"
        ),
        sa.CheckConstraint("length(override_reason) <= 500", name="ck_boq_line__override_reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(requirement_id) = 32 AND requirement_id NOT GLOB '*[^0-9a-f]*' AND substr(requirement_id, 13, 1) = '7' AND substr(requirement_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_boq_line__requirement_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(scope_item_id) = 32 AND scope_item_id NOT GLOB '*[^0-9a-f]*' AND substr(scope_item_id, 13, 1) = '7' AND substr(scope_item_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_boq_line__scope_item_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_boq_line__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "space_id IS NULL OR (length(space_id) = 32 AND space_id NOT GLOB '*[^0-9a-f]*' AND substr(space_id, 13, 1) = '7' AND substr(space_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_boq_line__space_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("status IN ('OK', 'ISSUE')", name="ck_boq_line__status"),
        sa.CheckConstraint("length(status) <= 8", name="ck_boq_line__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "uom_code IS NULL OR uom_code IN ('SFT', 'RFT', 'NOS', 'LUMP')", name="ck_boq_line__uom_code"
        ),
        sa.CheckConstraint("length(uom_code) <= 4", name="ck_boq_line__uom_code_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_boq_line__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_boq_line__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_boq_line__version_positive"),
    )
    op.create_index("ix_boq_line__requirement_id", "boq_line", ["requirement_id"])
    op.create_index("ix_boq_line__scope_item_id", "boq_line", ["scope_item_id"])
    op.create_index("ix_boq_line__space_id", "boq_line", ["space_id"])
    op.create_index(
        "ux_boq_line__boq_position",
        "boq_line",
        ["boq_id", "position"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "cost_estimate",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("property_id", GUID(), nullable=False),
        sa.Column("boq_id", GUID(), nullable=False),
        sa.Column("boq_revision_no", sa.Integer(), nullable=False),
        sa.Column("boq_snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("scope_id", GUID(), nullable=False),
        sa.Column("scope_revision_no", sa.Integer(), nullable=False),
        sa.Column("measurement_set_id", GUID(), nullable=False),
        sa.Column("measurement_revision_no", sa.Integer(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("supersedes_estimate_id", GUID(), nullable=True),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("tier_code", sa.String(10), nullable=False),
        sa.Column("rate_card_id", GUID(), nullable=False),
        sa.Column("rate_card_version", sa.String(40), nullable=False),
        sa.Column("rate_card_sha256", sa.String(64), nullable=False),
        sa.Column("calculation_version", sa.String(20), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("policy_sha256", sa.String(64), nullable=False),
        sa.Column("pricing_basis_code", sa.String(10), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("subtotal_minor", sa.BigInteger(), nullable=False),
        sa.Column("optional_minor", sa.BigInteger(), nullable=False),
        sa.Column("discount_minor", sa.BigInteger(), nullable=False),
        sa.Column("taxable_minor", sa.BigInteger(), nullable=False),
        sa.Column("tax_status", sa.String(20), nullable=False),
        sa.Column("tax_minor", sa.BigInteger(), nullable=True),
        sa.Column("total_minor", sa.BigInteger(), nullable=True),
        sa.Column("unpriced_lines", sa.Integer(), nullable=False),
        sa.Column("blockers", JSONType(), nullable=False),
        sa.Column("approved_on", UTCDateTime(), nullable=True),
        sa.Column("approved_by", GUID(), nullable=True),
        sa.Column("snapshot_sha256", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_cost_estimate"),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["app_user.id"], name="fk_cost_estimate__approved_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["boq_id"], ["boq.id"], name="fk_cost_estimate__boq_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_cost_estimate__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_cost_estimate__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_cost_estimate__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["measurement_set_id"],
            ["measurement_set.id"],
            name="fk_cost_estimate__measurement_set_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["property.id"], name="fk_cost_estimate__property_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["rate_card_id"], ["estimator_rate_card.id"], name="fk_cost_estimate__rate_card_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["scope_id"], ["scope.id"], name="fk_cost_estimate__scope_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["supersedes_estimate_id"],
            ["cost_estimate.id"],
            name="fk_cost_estimate__supersedes_estimate_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_cost_estimate__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "subtotal_minor >= 0 AND optional_minor >= 0 AND discount_minor >= 0 AND discount_minor <= subtotal_minor AND taxable_minor = subtotal_minor - discount_minor",
            name="ck_cost_estimate__amounts",
        ),
        sa.CheckConstraint(
            "approved_by IS NULL OR (length(approved_by) = 32 AND approved_by NOT GLOB '*[^0-9a-f]*' AND substr(approved_by, 13, 1) = '7' AND substr(approved_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_cost_estimate__approved_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status <> 'APPROVED' OR (approved_on IS NOT NULL AND approved_by IS NOT NULL AND snapshot_sha256 IS NOT NULL)",
            name="ck_cost_estimate__approved_sealed",
        ),
        sa.CheckConstraint("blockers IS NULL OR json_valid(blockers)", name="ck_cost_estimate__blockers_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(boq_id) = 32 AND boq_id NOT GLOB '*[^0-9a-f]*' AND substr(boq_id, 13, 1) = '7' AND substr(boq_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_cost_estimate__boq_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(boq_snapshot_sha256) <= 64", name="ck_cost_estimate__boq_snapshot_sha256_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(calculation_version) <= 20", name="ck_cost_estimate__calculation_version_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_cost_estimate__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(currency) <= 3", name="ck_cost_estimate__currency_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_cost_estimate__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_cost_estimate__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_cost_estimate__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_cost_estimate__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(measurement_set_id) = 32 AND measurement_set_id NOT GLOB '*[^0-9a-f]*' AND substr(measurement_set_id, 13, 1) = '7' AND substr(measurement_set_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_cost_estimate__measurement_set_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "supersedes_estimate_id IS NULL OR supersedes_estimate_id <> id", name="ck_cost_estimate__not_self"
        ),
        sa.CheckConstraint("length(policy_sha256) <= 64", name="ck_cost_estimate__policy_sha256_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(policy_version) <= 40", name="ck_cost_estimate__policy_version_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("pricing_basis_code IN ('MEASURED', 'MIXED')", name="ck_cost_estimate__pricing_basis_code"),
        sa.CheckConstraint("length(pricing_basis_code) <= 10", name="ck_cost_estimate__pricing_basis_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(property_id) = 32 AND property_id NOT GLOB '*[^0-9a-f]*' AND substr(property_id, 13, 1) = '7' AND substr(property_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_cost_estimate__property_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(rate_card_id) = 32 AND rate_card_id NOT GLOB '*[^0-9a-f]*' AND substr(rate_card_id, 13, 1) = '7' AND substr(rate_card_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_cost_estimate__rate_card_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(rate_card_sha256) <= 64", name="ck_cost_estimate__rate_card_sha256_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(rate_card_version) <= 40", name="ck_cost_estimate__rate_card_version_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("revision_no >= 1", name="ck_cost_estimate__revision_no"),
        sa.CheckConstraint(
            "length(scope_id) = 32 AND scope_id NOT GLOB '*[^0-9a-f]*' AND substr(scope_id, 13, 1) = '7' AND substr(scope_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_cost_estimate__scope_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "snapshot_sha256 IS NULL OR length(snapshot_sha256) = 64", name="ck_cost_estimate__snapshot_sha256_len"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_cost_estimate__soft_delete_consistent",
        ),
        sa.CheckConstraint("status IN ('DRAFT', 'APPROVED', 'SUPERSEDED')", name="ck_cost_estimate__status"),
        sa.CheckConstraint("length(status) <= 12", name="ck_cost_estimate__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "supersedes_estimate_id IS NULL OR (length(supersedes_estimate_id) = 32 AND supersedes_estimate_id NOT GLOB '*[^0-9a-f]*' AND substr(supersedes_estimate_id, 13, 1) = '7' AND substr(supersedes_estimate_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_cost_estimate__supersedes_estimate_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(tax_status = 'APPLIED' AND tax_minor IS NOT NULL AND total_minor = taxable_minor + tax_minor) OR (tax_status = 'GST_POLICY_REQUIRED' AND tax_minor IS NULL AND total_minor IS NULL)",
            name="ck_cost_estimate__tax",
        ),
        sa.CheckConstraint("tax_status IN ('GST_POLICY_REQUIRED', 'APPLIED')", name="ck_cost_estimate__tax_status"),
        sa.CheckConstraint("length(tax_status) <= 20", name="ck_cost_estimate__tax_status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("tier_code IN ('ESSENTIAL', 'PREMIUM', 'LUXURY')", name="ck_cost_estimate__tier_code"),
        sa.CheckConstraint("length(tier_code) <= 10", name="ck_cost_estimate__tier_code_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_cost_estimate__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_cost_estimate__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_cost_estimate__version_positive"),
    )
    op.create_index("ix_cost_estimate__boq_id", "cost_estimate", ["boq_id"])
    op.create_index("ix_cost_estimate__lead_id", "cost_estimate", ["lead_id"])
    op.create_index("ix_cost_estimate__measurement_set_id", "cost_estimate", ["measurement_set_id"])
    op.create_index("ix_cost_estimate__rate_card_id", "cost_estimate", ["rate_card_id"])
    op.create_index("ix_cost_estimate__scope_id", "cost_estimate", ["scope_id"])
    op.create_index("ix_cost_estimate__supersedes_estimate_id", "cost_estimate", ["supersedes_estimate_id"])
    op.create_index(
        "ux_cost_estimate__one_approved",
        "cost_estimate",
        ["property_id"],
        unique=True,
        sqlite_where=sa.text("status = 'APPROVED' AND is_deleted = 0"),
        postgresql_where=sa.text("status = 'APPROVED' AND is_deleted = false"),
    )
    op.create_index(
        "ux_cost_estimate__one_draft",
        "cost_estimate",
        ["property_id"],
        unique=True,
        sqlite_where=sa.text("status = 'DRAFT' AND is_deleted = 0"),
        postgresql_where=sa.text("status = 'DRAFT' AND is_deleted = false"),
    )
    op.create_index(
        "ux_cost_estimate__property_revision",
        "cost_estimate",
        ["property_id", "revision_no"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "cost_estimate_line",
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
        sa.Column("boq_line_id", GUID(), nullable=True),
        sa.Column("scope_item_id", GUID(), nullable=True),
        sa.Column("requirement_id", GUID(), nullable=True),
        sa.Column("space_id", GUID(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("component_code", sa.String(20), nullable=False),
        sa.Column("category_code", sa.String(20), nullable=False),
        sa.Column("card_product_code", sa.String(40), nullable=True),
        sa.Column("card_line_code", sa.String(40), nullable=True),
        sa.Column("prep_component_code", sa.String(40), nullable=True),
        sa.Column("item_type_code", sa.String(40), nullable=True),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("uom_code", sa.String(4), nullable=True),
        sa.Column("quantity_centi", sa.BigInteger(), nullable=True),
        sa.Column("tier_code", sa.String(10), nullable=False),
        sa.Column("finish_code", sa.String(20), nullable=True),
        sa.Column("rate_minor", sa.BigInteger(), nullable=True),
        sa.Column("rate_status", sa.String(30), nullable=False),
        sa.Column("rate_note", sa.String(500), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("discount_minor", sa.BigInteger(), nullable=False),
        sa.Column("taxable_minor", sa.BigInteger(), nullable=True),
        sa.Column("tax_rate_bp", sa.Integer(), nullable=True),
        sa.Column("tax_minor", sa.BigInteger(), nullable=True),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dimension_source_code", sa.String(10), nullable=False),
        sa.Column("provenance", JSONType(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_cost_estimate_line"),
        sa.ForeignKeyConstraint(
            ["boq_line_id"], ["boq_line.id"], name="fk_cost_estimate_line__boq_line_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_cost_estimate_line__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_cost_estimate_line__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["estimate_id"], ["cost_estimate.id"], name="fk_cost_estimate_line__estimate_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"], ["requirement.id"], name="fk_cost_estimate_line__requirement_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["scope_item_id"], ["scope_item.id"], name="fk_cost_estimate_line__scope_item_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["space_id"], ["property_space.id"], name="fk_cost_estimate_line__space_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_cost_estimate_line__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "coalesce(rate_minor, 0) >= 0 AND coalesce(amount_minor, 0) >= 0 AND discount_minor >= 0 AND discount_minor <= coalesce(amount_minor, 0)",
            name="ck_cost_estimate_line__amounts",
        ),
        sa.CheckConstraint(
            "boq_line_id IS NULL OR (length(boq_line_id) = 32 AND boq_line_id NOT GLOB '*[^0-9a-f]*' AND substr(boq_line_id, 13, 1) = '7' AND substr(boq_line_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_cost_estimate_line__boq_line_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(card_line_code) <= 40", name="ck_cost_estimate_line__card_line_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(card_product_code) <= 40", name="ck_cost_estimate_line__card_product_code_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(category_code) <= 20", name="ck_cost_estimate_line__category_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "component_code IN ('PRODUCT', 'LABOUR', 'INSTALLATION', 'TRANSPORT', 'SITE_PROTECTION', 'ELECTRICAL_SHIFTING', 'OTHER_SERVICE')",
            name="ck_cost_estimate_line__component_code",
        ),
        sa.CheckConstraint("length(component_code) <= 20", name="ck_cost_estimate_line__component_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_cost_estimate_line__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_cost_estimate_line__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "dimension_source_code IN ('MEASURED', 'DERIVED', 'ASSUMED', 'STAFF')",
            name="ck_cost_estimate_line__dimension_source_code",
        ),
        sa.CheckConstraint(
            "length(dimension_source_code) <= 10", name="ck_cost_estimate_line__dimension_source_code_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(estimate_id) = 32 AND estimate_id NOT GLOB '*[^0-9a-f]*' AND substr(estimate_id, 13, 1) = '7' AND substr(estimate_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_cost_estimate_line__estimate_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "finish_code IS NULL OR finish_code IN ('LAMINATE', 'ACRYLIC', 'VENEER', 'PU', 'GLASS', 'MEMBRANE', 'CUSTOM')",
            name="ck_cost_estimate_line__finish_code",
        ),
        sa.CheckConstraint("length(finish_code) <= 20", name="ck_cost_estimate_line__finish_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_cost_estimate_line__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_cost_estimate_line__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("is_optional IN (0, 1)", name="ck_cost_estimate_line__is_optional_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(item_type_code) <= 40", name="ck_cost_estimate_line__item_type_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(label) <= 300", name="ck_cost_estimate_line__label_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(prep_component_code) <= 40", name="ck_cost_estimate_line__prep_component_code_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(rate_status = 'PRICED' AND rate_minor IS NOT NULL AND amount_minor IS NOT NULL) OR (rate_status <> 'PRICED' AND amount_minor IS NULL)",
            name="ck_cost_estimate_line__priced",
        ),
        sa.CheckConstraint(
            "provenance IS NULL OR json_valid(provenance)", name="ck_cost_estimate_line__provenance_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(rate_note) <= 500", name="ck_cost_estimate_line__rate_note_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "rate_status IN ('PRICED', 'RATE_CARD_NOT_APPROVED', 'FINISH_RATE_NOT_APPROVED', 'CATALOGUE_MAPPING_MISSING', 'OWNER_DECISION_REQUIRED', 'RATE_MISSING', 'QUANTITY_MISSING', 'QUANTITY_BASIS_CHANGED')",
            name="ck_cost_estimate_line__rate_status",
        ),
        sa.CheckConstraint("length(rate_status) <= 30", name="ck_cost_estimate_line__rate_status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "requirement_id IS NULL OR (length(requirement_id) = 32 AND requirement_id NOT GLOB '*[^0-9a-f]*' AND substr(requirement_id, 13, 1) = '7' AND substr(requirement_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_cost_estimate_line__requirement_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "scope_item_id IS NULL OR (length(scope_item_id) = 32 AND scope_item_id NOT GLOB '*[^0-9a-f]*' AND substr(scope_item_id, 13, 1) = '7' AND substr(scope_item_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_cost_estimate_line__scope_item_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_cost_estimate_line__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "space_id IS NULL OR (length(space_id) = 32 AND space_id NOT GLOB '*[^0-9a-f]*' AND substr(space_id, 13, 1) = '7' AND substr(space_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_cost_estimate_line__space_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("tier_code IN ('ESSENTIAL', 'PREMIUM', 'LUXURY')", name="ck_cost_estimate_line__tier_code"),
        sa.CheckConstraint("length(tier_code) <= 10", name="ck_cost_estimate_line__tier_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "uom_code IS NULL OR uom_code IN ('SFT', 'RFT', 'NOS', 'LUMP')", name="ck_cost_estimate_line__uom_code"
        ),
        sa.CheckConstraint("length(uom_code) <= 4", name="ck_cost_estimate_line__uom_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_cost_estimate_line__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_cost_estimate_line__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_cost_estimate_line__version_positive"),
    )
    op.create_index("ix_cost_estimate_line__boq_line_id", "cost_estimate_line", ["boq_line_id"])
    op.create_index("ix_cost_estimate_line__requirement_id", "cost_estimate_line", ["requirement_id"])
    op.create_index("ix_cost_estimate_line__scope_item_id", "cost_estimate_line", ["scope_item_id"])
    op.create_index("ix_cost_estimate_line__space_id", "cost_estimate_line", ["space_id"])
    op.create_index(
        "ux_cost_estimate_line__position",
        "cost_estimate_line",
        ["estimate_id", "position"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "cost_estimate_adjustment",
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
        sa.Column("scope_code", sa.String(10), nullable=False),
        sa.Column("target_line_id", GUID(), nullable=True),
        sa.Column("target_category", sa.String(20), nullable=True),
        sa.Column("kind_code", sa.String(10), nullable=False),
        sa.Column("value_bp", sa.Integer(), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("base_minor", sa.BigInteger(), nullable=False),
        sa.Column("discount_minor", sa.BigInteger(), nullable=False),
        sa.Column("post_minor", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("authority_code", sa.String(15), nullable=True),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("decided_by", GUID(), nullable=True),
        sa.Column("decided_on", UTCDateTime(), nullable=True),
        sa.Column("decision_note", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_cost_estimate_adjustment"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_cost_estimate_adjustment__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["app_user.id"], name="fk_cost_estimate_adjustment__decided_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_cost_estimate_adjustment__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["estimate_id"], ["cost_estimate.id"], name="fk_cost_estimate_adjustment__estimate_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["target_line_id"],
            ["cost_estimate_line.id"],
            name="fk_cost_estimate_adjustment__target_line_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_cost_estimate_adjustment__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "discount_minor >= 0 AND discount_minor <= base_minor AND post_minor = base_minor - discount_minor",
            name="ck_cost_estimate_adjustment__amounts",
        ),
        sa.CheckConstraint(
            "authority_code IS NULL OR authority_code IN ('WITHIN_LIMIT', 'APPROVER')",
            name="ck_cost_estimate_adjustment__authority_code",
        ),
        sa.CheckConstraint(
            "length(authority_code) <= 15", name="ck_cost_estimate_adjustment__authority_code_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_cost_estimate_adjustment__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status = 'PROPOSED' OR (decided_by IS NOT NULL AND decided_on IS NOT NULL)",
            name="ck_cost_estimate_adjustment__decided",
        ),
        sa.CheckConstraint(
            "decided_by IS NULL OR (length(decided_by) = 32 AND decided_by NOT GLOB '*[^0-9a-f]*' AND substr(decided_by, 13, 1) = '7' AND substr(decided_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_cost_estimate_adjustment__decided_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(decision_note) <= 500", name="ck_cost_estimate_adjustment__decision_note_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_cost_estimate_adjustment__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(estimate_id) = 32 AND estimate_id NOT GLOB '*[^0-9a-f]*' AND substr(estimate_id, 13, 1) = '7' AND substr(estimate_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_cost_estimate_adjustment__estimate_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_cost_estimate_adjustment__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_cost_estimate_adjustment__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("kind_code IN ('PERCENT', 'AMOUNT')", name="ck_cost_estimate_adjustment__kind_code"),
        sa.CheckConstraint("length(kind_code) <= 10", name="ck_cost_estimate_adjustment__kind_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(policy_version) <= 40", name="ck_cost_estimate_adjustment__policy_version_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(reason) <= 500", name="ck_cost_estimate_adjustment__reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "scope_code IN ('LINE', 'CATEGORY', 'PROJECT')", name="ck_cost_estimate_adjustment__scope_code"
        ),
        sa.CheckConstraint("length(scope_code) <= 10", name="ck_cost_estimate_adjustment__scope_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_cost_estimate_adjustment__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "status IN ('PROPOSED', 'APPROVED', 'REJECTED', 'WITHDRAWN')", name="ck_cost_estimate_adjustment__status"
        ),
        sa.CheckConstraint("length(status) <= 10", name="ck_cost_estimate_adjustment__status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(scope_code = 'LINE') = (target_line_id IS NOT NULL) AND (scope_code = 'CATEGORY') = (target_category IS NOT NULL)",
            name="ck_cost_estimate_adjustment__target",
        ),
        sa.CheckConstraint(
            "length(target_category) <= 20", name="ck_cost_estimate_adjustment__target_category_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "target_line_id IS NULL OR (length(target_line_id) = 32 AND target_line_id NOT GLOB '*[^0-9a-f]*' AND substr(target_line_id, 13, 1) = '7' AND substr(target_line_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_cost_estimate_adjustment__target_line_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_cost_estimate_adjustment__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_cost_estimate_adjustment__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(kind_code = 'PERCENT' AND value_bp BETWEEN 1 AND 10000 AND amount_minor IS NULL) OR (kind_code = 'AMOUNT' AND amount_minor > 0 AND value_bp IS NULL)",
            name="ck_cost_estimate_adjustment__value",
        ),
        sa.CheckConstraint("version >= 1", name="ck_cost_estimate_adjustment__version_positive"),
    )
    op.create_index("ix_cost_estimate_adjustment__estimate_id", "cost_estimate_adjustment", ["estimate_id"])
    op.create_index("ix_cost_estimate_adjustment__target_line_id", "cost_estimate_adjustment", ["target_line_id"])
    # --- end generated DDL ---
    bind = op.get_bind()
    ms.sync_permissions(bind, audit=True)
    ms.seed_missing_roles(bind, ROLES, audit=True)
    ms.grant_new_codes(bind, CODES, audit=True)
    ms.assert_rbac_seed(bind)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
