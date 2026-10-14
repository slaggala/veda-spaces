"""0202_mtq_commercial: MTQ B4 quotations and variations (blueprint §4.3, §16 B4; decision log 31).

Tables: ``quotation`` (versions and variations, frozen from ISSUED with the customer document and its digest),
``quotation_section``, ``quotation_line``, ``quotation_event`` (lifecycle). Number sequence ``QUOTATION``
(``VS-Q-YYYY-NNNNNN``, yearly, allocated under the sequence row lock). The quotation permission codes for the existing
roles. Expand-only; inert while VEDA_MTQ_QUOTATION_ENABLED is off (the default everywhere; production refuses it).
Terms, exclusions and decisions live on the quotation (a terms snapshot and decision columns) rather than in separate
tables: the owner has decided none of their content yet (OI-MTQ-08…11), so no structure is frozen around it.

Revision ID: 0202_mtq_commercial
Revises: 0201_mtq_estimation
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0202_mtq_commercial"
down_revision = "0201_mtq_estimation"
branch_labels = None
depends_on = None

SEQUENCES = (("QUOTATION", "VS-Q-"),)
CODES = (
    "quotation.read",
    "quotation.create",
    "quotation.approve",
    "quotation.issue",
    "quotation.decision.record",
    "quotation.variation.create",
    "quotation.lineage.read",
)


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "quotation",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("quotation_number", sa.String(24), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("quotation_kind", sa.String(10), nullable=False),
        sa.Column("variation_no", sa.Integer(), nullable=False),
        sa.Column("variation_of_quotation_id", GUID(), nullable=True),
        sa.Column("baseline_quotation_id", GUID(), nullable=True),
        sa.Column("supersedes_quotation_id", GUID(), nullable=True),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("property_id", GUID(), nullable=False),
        sa.Column("measurement_set_id", GUID(), nullable=False),
        sa.Column("measurement_revision_no", sa.Integer(), nullable=False),
        sa.Column("scope_id", GUID(), nullable=False),
        sa.Column("scope_revision_no", sa.Integer(), nullable=False),
        sa.Column("boq_id", GUID(), nullable=False),
        sa.Column("boq_revision_no", sa.Integer(), nullable=False),
        sa.Column("cost_estimate_id", GUID(), nullable=False),
        sa.Column("estimate_revision_no", sa.Integer(), nullable=False),
        sa.Column("estimate_snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("cover_note", sa.Text(), nullable=True),
        sa.Column("tier_code", sa.String(10), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("policy_sha256", sa.String(64), nullable=False),
        sa.Column("terms", JSONType(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("base_total_minor", sa.BigInteger(), nullable=False),
        sa.Column("optional_minor", sa.BigInteger(), nullable=False),
        sa.Column("discount_minor", sa.BigInteger(), nullable=False),
        sa.Column("taxable_minor", sa.BigInteger(), nullable=False),
        sa.Column("tax_status", sa.String(20), nullable=False),
        sa.Column("tax_minor", sa.BigInteger(), nullable=True),
        sa.Column("total_minor", sa.BigInteger(), nullable=True),
        sa.Column("blockers", JSONType(), nullable=False),
        sa.Column("submitted_on", UTCDateTime(), nullable=True),
        sa.Column("approved_on", UTCDateTime(), nullable=True),
        sa.Column("approved_by", GUID(), nullable=True),
        sa.Column("issued_on", UTCDateTime(), nullable=True),
        sa.Column("issued_by", GUID(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("snapshot", JSONType(), nullable=True),
        sa.Column("snapshot_sha256", sa.String(64), nullable=True),
        sa.Column("template_version", sa.String(40), nullable=True),
        sa.Column("issued_html", sa.Text(), nullable=True),
        sa.Column("issued_html_sha256", sa.String(64), nullable=True),
        sa.Column("decision_method", sa.String(16), nullable=True),
        sa.Column("decided_on", UTCDateTime(), nullable=True),
        sa.Column("decision_recorded_by", GUID(), nullable=True),
        sa.Column("selected_optional_line_ids", JSONType(), nullable=False),
        sa.Column("accepted_total_minor", sa.BigInteger(), nullable=True),
        sa.Column("accepted_baseline", JSONType(), nullable=True),
        sa.Column("accepted_baseline_sha256", sa.String(64), nullable=True),
        sa.Column("decision_note", sa.String(1000), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_quotation"),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["app_user.id"], name="fk_quotation__approved_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["baseline_quotation_id"], ["quotation.id"], name="fk_quotation__baseline_quotation_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["boq_id"], ["boq.id"], name="fk_quotation__boq_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["cost_estimate_id"], ["cost_estimate.id"], name="fk_quotation__cost_estimate_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], name="fk_quotation__created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["decision_recorded_by"], ["app_user.id"], name="fk_quotation__decision_recorded_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["deleted_by"], ["app_user.id"], name="fk_quotation__deleted_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["issued_by"], ["app_user.id"], name="fk_quotation__issued_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_quotation__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["measurement_set_id"], ["measurement_set.id"], name="fk_quotation__measurement_set_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["property.id"], name="fk_quotation__property_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["scope_id"], ["scope.id"], name="fk_quotation__scope_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["supersedes_quotation_id"],
            ["quotation.id"],
            name="fk_quotation__supersedes_quotation_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], name="fk_quotation__updated_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["variation_of_quotation_id"],
            ["quotation.id"],
            name="fk_quotation__variation_of_quotation_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status <> 'ACCEPTED' OR (accepted_total_minor IS NOT NULL AND accepted_baseline_sha256 IS NOT NULL)",
            name="ck_quotation__accepted",
        ),
        sa.CheckConstraint(
            "accepted_baseline IS NULL OR json_valid(accepted_baseline)", name="ck_quotation__accepted_baseline_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "accepted_baseline_sha256 IS NULL OR length(accepted_baseline_sha256) = 64",
            name="ck_quotation__accepted_baseline_sha256_len",
        ),
        sa.CheckConstraint(
            "optional_minor >= 0 AND discount_minor >= 0 AND taxable_minor = base_total_minor - discount_minor AND (quotation_kind = 'VARIATION' OR base_total_minor >= 0)",
            name="ck_quotation__amounts",
        ),
        sa.CheckConstraint(
            "approved_by IS NULL OR (length(approved_by) = 32 AND approved_by NOT GLOB '*[^0-9a-f]*' AND substr(approved_by, 13, 1) = '7' AND substr(approved_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_quotation__approved_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "baseline_quotation_id IS NULL OR (length(baseline_quotation_id) = 32 AND baseline_quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(baseline_quotation_id, 13, 1) = '7' AND substr(baseline_quotation_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_quotation__baseline_quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("blockers IS NULL OR json_valid(blockers)", name="ck_quotation__blockers_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(boq_id) = 32 AND boq_id NOT GLOB '*[^0-9a-f]*' AND substr(boq_id, 13, 1) = '7' AND substr(boq_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation__boq_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(cost_estimate_id) = 32 AND cost_estimate_id NOT GLOB '*[^0-9a-f]*' AND substr(cost_estimate_id, 13, 1) = '7' AND substr(cost_estimate_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation__cost_estimate_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(currency) <= 3", name="ck_quotation__currency_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status NOT IN ('ACCEPTED', 'REJECTED') OR (decided_on IS NOT NULL AND decision_recorded_by IS NOT NULL AND decision_method IS NOT NULL)",
            name="ck_quotation__decided",
        ),
        sa.CheckConstraint(
            "decision_method IS NULL OR decision_method IN ('STAFF_RECORDED', 'SIGNED_COPY')",
            name="ck_quotation__decision_method",
        ),
        sa.CheckConstraint("length(decision_method) <= 16", name="ck_quotation__decision_method_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(decision_note) <= 1000", name="ck_quotation__decision_note_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "decision_recorded_by IS NULL OR (length(decision_recorded_by) = 32 AND decision_recorded_by NOT GLOB '*[^0-9a-f]*' AND substr(decision_recorded_by, 13, 1) = '7' AND substr(decision_recorded_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_quotation__decision_recorded_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_quotation__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(estimate_snapshot_sha256) <= 64", name="ck_quotation__estimate_snapshot_sha256_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_quotation__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "issued_by IS NULL OR (length(issued_by) = 32 AND issued_by NOT GLOB '*[^0-9a-f]*' AND substr(issued_by, 13, 1) = '7' AND substr(issued_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_quotation__issued_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'INTERNAL_REVIEW', 'APPROVED') OR status = 'SUPERSEDED' OR (issued_on IS NOT NULL AND snapshot_sha256 IS NOT NULL AND total_minor IS NOT NULL AND issued_html_sha256 IS NOT NULL AND template_version IS NOT NULL)",
            name="ck_quotation__issued_frozen",
        ),
        sa.CheckConstraint(
            "issued_html_sha256 IS NULL OR length(issued_html_sha256) = 64", name="ck_quotation__issued_html_sha256_len"
        ),
        sa.CheckConstraint(
            "(quotation_kind = 'BASE') = (variation_no = 0) AND (quotation_kind = 'BASE') = (variation_of_quotation_id IS NULL)",
            name="ck_quotation__kind",
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(measurement_set_id) = 32 AND measurement_set_id NOT GLOB '*[^0-9a-f]*' AND substr(measurement_set_id, 13, 1) = '7' AND substr(measurement_set_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation__measurement_set_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version_no >= 1 AND variation_no >= 0", name="ck_quotation__numbers"),
        sa.CheckConstraint("length(policy_sha256) <= 64", name="ck_quotation__policy_sha256_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(policy_version) <= 40", name="ck_quotation__policy_version_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(property_id) = 32 AND property_id NOT GLOB '*[^0-9a-f]*' AND substr(property_id, 13, 1) = '7' AND substr(property_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation__property_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("quotation_kind IN ('BASE', 'VARIATION')", name="ck_quotation__quotation_kind"),
        sa.CheckConstraint("length(quotation_kind) <= 10", name="ck_quotation__quotation_kind_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(quotation_number) <= 24", name="ck_quotation__quotation_number_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(scope_id) = 32 AND scope_id NOT GLOB '*[^0-9a-f]*' AND substr(scope_id, 13, 1) = '7' AND substr(scope_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation__scope_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "selected_optional_line_ids IS NULL OR json_valid(selected_optional_line_ids)",
            name="ck_quotation__selected_optional_line_ids_json",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("snapshot IS NULL OR json_valid(snapshot)", name="ck_quotation__snapshot_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "snapshot_sha256 IS NULL OR length(snapshot_sha256) = 64", name="ck_quotation__snapshot_sha256_len"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_quotation__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'INTERNAL_REVIEW', 'APPROVED', 'ISSUED', 'ACCEPTED', 'REJECTED', 'EXPIRED', 'SUPERSEDED')",
            name="ck_quotation__status",
        ),
        sa.CheckConstraint("length(status) <= 16", name="ck_quotation__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "supersedes_quotation_id IS NULL OR (length(supersedes_quotation_id) = 32 AND supersedes_quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(supersedes_quotation_id, 13, 1) = '7' AND substr(supersedes_quotation_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_quotation__supersedes_quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("tax_status IN ('GST_POLICY_REQUIRED', 'APPLIED')", name="ck_quotation__tax_status"),
        sa.CheckConstraint("length(tax_status) <= 20", name="ck_quotation__tax_status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(template_version) <= 40", name="ck_quotation__template_version_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("terms IS NULL OR json_valid(terms)", name="ck_quotation__terms_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("tier_code IN ('ESSENTIAL', 'PREMIUM', 'LUXURY')", name="ck_quotation__tier_code"),
        sa.CheckConstraint("length(tier_code) <= 10", name="ck_quotation__tier_code_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(title) <= 160", name="ck_quotation__title_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_quotation__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "variation_of_quotation_id IS NULL OR (length(variation_of_quotation_id) = 32 AND variation_of_quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(variation_of_quotation_id, 13, 1) = '7' AND substr(variation_of_quotation_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_quotation__variation_of_quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_quotation__version_positive"),
    )
    op.create_index("ix_quotation__baseline", "quotation", ["baseline_quotation_id"])
    op.create_index("ix_quotation__boq_id", "quotation", ["boq_id"])
    op.create_index("ix_quotation__cost_estimate_id", "quotation", ["cost_estimate_id"])
    op.create_index("ix_quotation__lead_id", "quotation", ["lead_id"])
    op.create_index("ix_quotation__measurement_set_id", "quotation", ["measurement_set_id"])
    op.create_index("ix_quotation__property_id", "quotation", ["property_id"])
    op.create_index("ix_quotation__scope_id", "quotation", ["scope_id"])
    op.create_index("ix_quotation__status_valid_until", "quotation", ["status", "valid_until"])
    op.create_index("ix_quotation__supersedes", "quotation", ["supersedes_quotation_id"])
    op.create_index("ix_quotation__variation_of", "quotation", ["variation_of_quotation_id"])
    op.create_index(
        "ux_quotation__number_variation_version",
        "quotation",
        ["quotation_number", "variation_no", "version_no"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_quotation__one_open",
        "quotation",
        ["quotation_number", "variation_no"],
        unique=True,
        sqlite_where=sa.text("status IN ('DRAFT', 'INTERNAL_REVIEW', 'APPROVED') AND is_deleted = 0"),
        postgresql_where=sa.text("status IN ('DRAFT', 'INTERNAL_REVIEW', 'APPROVED') AND is_deleted = false"),
    )

    op.create_table(
        "quotation_section",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("quotation_id", GUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("section_code", sa.String(10), nullable=False),
        sa.Column("space_id", GUID(), nullable=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("subtotal_minor", sa.BigInteger(), nullable=False),
        sa.Column("optional_minor", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_quotation_section"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_quotation_section__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_quotation_section__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id"], ["quotation.id"], name="fk_quotation_section__quotation_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["space_id"], ["property_space.id"], name="fk_quotation_section__space_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_quotation_section__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_section__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_quotation_section__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_section__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_quotation_section__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(quotation_id) = 32 AND quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(quotation_id, 13, 1) = '7' AND substr(quotation_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_section__quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "section_code IN ('SPACE', 'PROJECT', 'OPTIONAL', 'VARIATION')", name="ck_quotation_section__section_code"
        ),
        sa.CheckConstraint("length(section_code) <= 10", name="ck_quotation_section__section_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_quotation_section__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "space_id IS NULL OR (length(space_id) = 32 AND space_id NOT GLOB '*[^0-9a-f]*' AND substr(space_id, 13, 1) = '7' AND substr(space_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_quotation_section__space_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(title) <= 120", name="ck_quotation_section__title_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_quotation_section__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_section__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_quotation_section__version_positive"),
    )
    op.create_index("ix_quotation_section__space_id", "quotation_section", ["space_id"])
    op.create_index(
        "ux_quotation_section__position",
        "quotation_section",
        ["quotation_id", "position"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "quotation_line",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("quotation_id", GUID(), nullable=False),
        sa.Column("section_id", GUID(), nullable=False),
        sa.Column("cost_estimate_line_id", GUID(), nullable=True),
        sa.Column("requirement_id", GUID(), nullable=True),
        sa.Column("space_id", GUID(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("line_key", sa.String(200), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("detail", sa.String(300), nullable=True),
        sa.Column("uom_code", sa.String(4), nullable=True),
        sa.Column("quantity_centi", sa.BigInteger(), nullable=True),
        sa.Column("finish_code", sa.String(20), nullable=True),
        sa.Column("rate_minor", sa.BigInteger(), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("discount_minor", sa.BigInteger(), nullable=False),
        sa.Column("tax_minor", sa.BigInteger(), nullable=True),
        sa.Column("is_priced", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("change_code", sa.String(16), nullable=False),
        sa.Column("baseline_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("delta_amount_minor", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_quotation_line"),
        sa.ForeignKeyConstraint(
            ["cost_estimate_line_id"],
            ["cost_estimate_line.id"],
            name="fk_quotation_line__cost_estimate_line_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_quotation_line__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_quotation_line__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id"], ["quotation.id"], name="fk_quotation_line__quotation_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"], ["requirement.id"], name="fk_quotation_line__requirement_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["section_id"], ["quotation_section.id"], name="fk_quotation_line__section_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["space_id"], ["property_space.id"], name="fk_quotation_line__space_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_quotation_line__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "change_code IN ('NONE', 'ADD', 'OMIT', 'CHANGE_QUANTITY', 'CHANGE_MATERIAL', 'CHANGE_FINISH', 'CHANGE_RATE')",
            name="ck_quotation_line__change_code",
        ),
        sa.CheckConstraint("length(change_code) <= 16", name="ck_quotation_line__change_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "cost_estimate_line_id IS NULL OR (length(cost_estimate_line_id) = 32 AND cost_estimate_line_id NOT GLOB '*[^0-9a-f]*' AND substr(cost_estimate_line_id, 13, 1) = '7' AND substr(cost_estimate_line_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_quotation_line__cost_estimate_line_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_line__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_quotation_line__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(description) <= 300", name="ck_quotation_line__description_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(detail) <= 300", name="ck_quotation_line__detail_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(finish_code) <= 20", name="ck_quotation_line__finish_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_line__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_quotation_line__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_mandatory IN (0, 1)", name="ck_quotation_line__is_mandatory_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("is_optional IN (0, 1)", name="ck_quotation_line__is_optional_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("is_priced IN (0, 1)", name="ck_quotation_line__is_priced_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(line_key) <= 200", name="ck_quotation_line__line_key_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(quotation_id) = 32 AND quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(quotation_id, 13, 1) = '7' AND substr(quotation_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_line__quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "requirement_id IS NULL OR (length(requirement_id) = 32 AND requirement_id NOT GLOB '*[^0-9a-f]*' AND substr(requirement_id, 13, 1) = '7' AND substr(requirement_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_quotation_line__requirement_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(section_id) = 32 AND section_id NOT GLOB '*[^0-9a-f]*' AND substr(section_id, 13, 1) = '7' AND substr(section_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_line__section_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_quotation_line__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "space_id IS NULL OR (length(space_id) = 32 AND space_id NOT GLOB '*[^0-9a-f]*' AND substr(space_id, 13, 1) = '7' AND substr(space_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_quotation_line__space_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_priced OR amount_minor IS NULL", name="ck_quotation_line__unpriced"),
        sa.CheckConstraint(
            "uom_code IS NULL OR uom_code IN ('SFT', 'RFT', 'NOS', 'LUMP')", name="ck_quotation_line__uom_code"
        ),
        sa.CheckConstraint("length(uom_code) <= 4", name="ck_quotation_line__uom_code_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_quotation_line__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_line__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_quotation_line__version_positive"),
    )
    op.create_index("ix_quotation_line__cost_estimate_line_id", "quotation_line", ["cost_estimate_line_id"])
    op.create_index("ix_quotation_line__requirement_id", "quotation_line", ["requirement_id"])
    op.create_index("ix_quotation_line__section_id", "quotation_line", ["section_id"])
    op.create_index("ix_quotation_line__space_id", "quotation_line", ["space_id"])
    op.create_index(
        "ux_quotation_line__position",
        "quotation_line",
        ["quotation_id", "position"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "quotation_event",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("quotation_id", GUID(), nullable=False),
        sa.Column("event_code", sa.String(24), nullable=False),
        sa.Column("from_status", sa.String(16), nullable=True),
        sa.Column("to_status", sa.String(16), nullable=True),
        sa.Column("detail", JSONType(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_quotation_event"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_quotation_event__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_quotation_event__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id"], ["quotation.id"], name="fk_quotation_event__quotation_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_quotation_event__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_event__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_quotation_event__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("detail IS NULL OR json_valid(detail)", name="ck_quotation_event__detail_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "event_code IN ('CREATED', 'VERSION_CREATED', 'VARIATION_CREATED', 'EDITED', 'SUBMITTED_FOR_REVIEW', 'RETURNED_TO_DRAFT', 'APPROVED', 'ISSUED', 'ACCEPTED', 'REJECTED', 'EXPIRED', 'SUPERSEDED', 'SNAPSHOT_REDACTED')",
            name="ck_quotation_event__event_code",
        ),
        sa.CheckConstraint("length(event_code) <= 24", name="ck_quotation_event__event_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(from_status) <= 16", name="ck_quotation_event__from_status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_event__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_quotation_event__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(quotation_id) = 32 AND quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(quotation_id, 13, 1) = '7' AND substr(quotation_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_event__quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_quotation_event__soft_delete_consistent",
        ),
        sa.CheckConstraint("length(to_status) <= 16", name="ck_quotation_event__to_status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_quotation_event__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_event__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_quotation_event__version_positive"),
    )
    op.create_index("ix_quotation_event__quotation", "quotation_event", ["quotation_id", "created_on"])
    # --- end generated DDL ---
    bind = op.get_bind()
    for key, prefix in SEQUENCES:
        ms.seed_sequence(bind, key, prefix)
    ms.sync_permissions(bind, audit=True)
    ms.grant_new_codes(bind, CODES, audit=True)
    ms.assert_rbac_seed(bind)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
