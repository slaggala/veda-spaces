"""0208_project_lifecycle: the Project Lifecycle Backbone (decision log 39).

Twelve tables (``veda.modules.project.models``): ``project`` (VS-P-… reference, the accepted chain it executes, stage,
pinned lifecycle definition), ``project_baseline`` (the append-only commercial-baseline lineage), ``project_stage``,
``project_member``, ``project_transition`` (every transition request with its recorded gate evaluation, independent
approval and handover evidence), ``project_checklist_item``, ``project_milestone``, ``project_site_readiness``,
``project_blocker``, ``project_qc_check``, ``project_snag`` and ``project_event`` (the timeline: database triggers
refuse UPDATE and DELETE). Number sequence ``PROJECT`` (``VS-P-``). The sixteen ``project.*`` permission codes and
their default grants (FOUNDER every code; SALES_MANAGER booking, team, baseline, history, blockers; ADMIN view;
DESIGNER, SURVEYOR, SALES and ESTIMATOR on projects they are a member of). No business content is seeded.

Expand-only and additive: no existing table, column or constraint changes. Inert while VEDA_PROJECT_LIFECYCLE_ENABLED is
off (the default everywhere; production refuses it).

Numbered 0208: 0207 is the head (Customer Promise); 0203 stays reserved.

Revision ID: 0208_project_lifecycle
Revises: 0207_customer_promise
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0208_project_lifecycle"
down_revision = "0207_customer_promise"
branch_labels = None
depends_on = None

SEQUENCES = (("PROJECT", "VS-P-"),)
CODES = (
    "project.view",
    "project.create_from_acceptance",
    "project.assign_team",
    "project.manage_stage",
    "project.approve_transition",
    "project.complete_checklist",
    "project.checklist.not_applicable",
    "project.manage_milestone",
    "project.raise_blocker",
    "project.resolve_blocker",
    "project.manage_site_readiness",
    "project.manage_qc",
    "project.manage_snag",
    "project.complete_handover",
    "project.view_commercial_baseline",
    "project.view_audit",
)
IMMUTABLE = ("project_event",)


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "project",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("project_number", sa.String(24), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("property_id", GUID(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("source_quotation_id", GUID(), nullable=False),
        sa.Column("quotation_number", sa.String(24), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("stage_code", sa.String(24), nullable=False),
        sa.Column("stage_entered_on", UTCDateTime(), nullable=False),
        sa.Column("lifecycle_version", sa.String(20), nullable=False),
        sa.Column("lifecycle_sha256", sa.String(64), nullable=False),
        sa.Column("baseline_seq", sa.Integer(), nullable=False),
        sa.Column("handed_over_on", UTCDateTime(), nullable=True),
        sa.Column("handed_over_by", GUID(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_project"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], name="fk_project__created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["app_user.id"], name="fk_project__deleted_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["handed_over_by"], ["app_user.id"], name="fk_project__handed_over_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_project__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["property_id"], ["property.id"], name="fk_project__property_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_quotation_id"], ["quotation.id"], name="fk_project__source_quotation_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], name="fk_project__updated_by", ondelete="RESTRICT"),
        sa.CheckConstraint("baseline_seq >= 1", name="ck_project__baseline_seq"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(status = 'HANDED_OVER') = (stage_code = 'HANDED_OVER') AND (status = 'HANDED_OVER') = (handed_over_on IS NOT NULL AND handed_over_by IS NOT NULL)",
            name="ck_project__handed_over",
        ),
        sa.CheckConstraint(
            "handed_over_by IS NULL OR (length(handed_over_by) = 32 AND handed_over_by NOT GLOB '*[^0-9a-f]*' AND substr(handed_over_by, 13, 1) = '7' AND substr(handed_over_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project__handed_over_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_project__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(lifecycle_sha256) = 64", name="ck_project__lifecycle_sha256_len"),
        sa.CheckConstraint("length(lifecycle_version) <= 20", name="ck_project__lifecycle_version_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(project_number) <= 24", name="ck_project__project_number_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(property_id) = 32 AND property_id NOT GLOB '*[^0-9a-f]*' AND substr(property_id, 13, 1) = '7' AND substr(property_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project__property_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(quotation_number) <= 24", name="ck_project__quotation_number_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_project__soft_delete_consistent",
        ),
        sa.CheckConstraint("source IN ('ACCEPTED_QUOTATION')", name="ck_project__source"),
        sa.CheckConstraint("length(source) <= 20", name="ck_project__source_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(source_quotation_id) = 32 AND source_quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(source_quotation_id, 13, 1) = '7' AND substr(source_quotation_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project__source_quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "stage_code IN ('BOOKED', 'DESIGN_FINALISATION', 'SCOPE_FROZEN', 'SITE_READINESS', 'PRODUCTION_READINESS', 'IN_PRODUCTION', 'READY_FOR_INSTALLATION', 'INSTALLATION', 'QUALITY_CHECK', 'SNAGGING', 'READY_FOR_HANDOVER', 'HANDED_OVER')",
            name="ck_project__stage_code",
        ),
        sa.CheckConstraint("length(stage_code) <= 24", name="ck_project__stage_code_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("status IN ('ACTIVE', 'HANDED_OVER')", name="ck_project__status"),
        sa.CheckConstraint("length(status) <= 12", name="ck_project__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_project__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_project__version_positive"),
    )
    op.create_index("ix_project__lead_id", "project", ["lead_id"])
    op.create_index("ix_project__property_id", "project", ["property_id"])
    op.create_index("ix_project__stage", "project", ["status", "stage_code"])
    op.create_index(
        "ux_project__project_number",
        "project",
        ["project_number"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_project__quotation_number",
        "project",
        ["quotation_number"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_project__source_quotation",
        "project",
        ["source_quotation_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "project_baseline",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("previous_baseline_id", GUID(), nullable=True),
        sa.Column("quotation_id", GUID(), nullable=False),
        sa.Column("quotation_number", sa.String(24), nullable=False),
        sa.Column("variation_no", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("accepted_baseline_sha256", sa.String(64), nullable=False),
        sa.Column("accepted_total_minor", sa.BigInteger(), nullable=False),
        sa.Column("cumulative_value_minor", sa.BigInteger(), nullable=False),
        sa.Column("decision_method", sa.String(16), nullable=False),
        sa.Column("decided_on", UTCDateTime(), nullable=False),
        sa.Column("selected_optional_count", sa.Integer(), nullable=False),
        sa.Column("measurement_set_id", GUID(), nullable=False),
        sa.Column("measurement_revision_no", sa.Integer(), nullable=False),
        sa.Column("scope_id", GUID(), nullable=False),
        sa.Column("scope_revision_no", sa.Integer(), nullable=False),
        sa.Column("boq_id", GUID(), nullable=False),
        sa.Column("boq_revision_no", sa.Integer(), nullable=False),
        sa.Column("cost_estimate_id", GUID(), nullable=False),
        sa.Column("estimate_revision_no", sa.Integer(), nullable=False),
        sa.Column("estimate_snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("customer_promise", JSONType(), nullable=True),
        sa.Column("baseline_sha256", sa.String(64), nullable=False),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_project_baseline"),
        sa.ForeignKeyConstraint(["boq_id"], ["boq.id"], name="fk_project_baseline__boq_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["cost_estimate_id"],
            ["cost_estimate.id"],
            name="fk_project_baseline__cost_estimate_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_project_baseline__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_project_baseline__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_project_baseline__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["measurement_set_id"],
            ["measurement_set.id"],
            name="fk_project_baseline__measurement_set_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_baseline_id"],
            ["project_baseline.id"],
            name="fk_project_baseline__previous_baseline_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_project_baseline__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id"], ["quotation.id"], name="fk_project_baseline__quotation_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["scope_id"], ["scope.id"], name="fk_project_baseline__scope_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_project_baseline__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(accepted_baseline_sha256) = 64", name="ck_project_baseline__accepted_baseline_sha256_len"
        ),
        sa.CheckConstraint("length(baseline_sha256) = 64", name="ck_project_baseline__baseline_sha256_len"),
        sa.CheckConstraint(
            "length(boq_id) = 32 AND boq_id NOT GLOB '*[^0-9a-f]*' AND substr(boq_id, 13, 1) = '7' AND substr(boq_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_baseline__boq_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(cost_estimate_id) = 32 AND cost_estimate_id NOT GLOB '*[^0-9a-f]*' AND substr(cost_estimate_id, 13, 1) = '7' AND substr(cost_estimate_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_baseline__cost_estimate_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_baseline__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "customer_promise IS NULL OR json_valid(customer_promise)",
            name="ck_project_baseline__customer_promise_json",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(decision_method) <= 16", name="ck_project_baseline__decision_method_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_baseline__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(estimate_snapshot_sha256) = 64", name="ck_project_baseline__estimate_snapshot_sha256_len"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_baseline__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_project_baseline__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("kind IN ('ORIGINAL', 'VARIATION')", name="ck_project_baseline__kind"),
        sa.CheckConstraint("length(kind) <= 10", name="ck_project_baseline__kind_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_baseline__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(kind = 'ORIGINAL') = (variation_no = 0) AND (sequence_no = 1) = (previous_baseline_id IS NULL)",
            name="ck_project_baseline__lineage",
        ),
        sa.CheckConstraint(
            "length(measurement_set_id) = 32 AND measurement_set_id NOT GLOB '*[^0-9a-f]*' AND substr(measurement_set_id, 13, 1) = '7' AND substr(measurement_set_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_baseline__measurement_set_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "previous_baseline_id IS NULL OR (length(previous_baseline_id) = 32 AND previous_baseline_id NOT GLOB '*[^0-9a-f]*' AND substr(previous_baseline_id, 13, 1) = '7' AND substr(previous_baseline_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_baseline__previous_baseline_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_baseline__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(quotation_id) = 32 AND quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(quotation_id, 13, 1) = '7' AND substr(quotation_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_baseline__quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(quotation_number) <= 24", name="ck_project_baseline__quotation_number_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(scope_id) = 32 AND scope_id NOT GLOB '*[^0-9a-f]*' AND substr(scope_id, 13, 1) = '7' AND substr(scope_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_baseline__scope_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "sequence_no >= 1 AND (kind = 'ORIGINAL') = (sequence_no = 1)", name="ck_project_baseline__sequence"
        ),
        sa.CheckConstraint("length(snapshot_sha256) = 64", name="ck_project_baseline__snapshot_sha256_len"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_project_baseline__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_project_baseline__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_baseline__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_project_baseline__version_positive"),
    )
    op.create_index("ix_project_baseline__boq_id", "project_baseline", ["boq_id"])
    op.create_index("ix_project_baseline__cost_estimate_id", "project_baseline", ["cost_estimate_id"])
    op.create_index("ix_project_baseline__lead_id", "project_baseline", ["lead_id"])
    op.create_index("ix_project_baseline__measurement_set_id", "project_baseline", ["measurement_set_id"])
    op.create_index("ix_project_baseline__previous", "project_baseline", ["previous_baseline_id"])
    op.create_index("ix_project_baseline__scope_id", "project_baseline", ["scope_id"])
    op.create_index(
        "ux_project_baseline__quotation",
        "project_baseline",
        ["quotation_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_project_baseline__sequence",
        "project_baseline",
        ["project_id", "sequence_no"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "project_stage",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("stage_code", sa.String(24), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("entered_on", UTCDateTime(), nullable=True),
        sa.Column("entered_by", GUID(), nullable=True),
        sa.Column("completed_on", UTCDateTime(), nullable=True),
        sa.Column("completed_by", GUID(), nullable=True),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_project_stage"),
        sa.ForeignKeyConstraint(
            ["completed_by"], ["app_user.id"], name="fk_project_stage__completed_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_project_stage__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_project_stage__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["entered_by"], ["app_user.id"], name="fk_project_stage__entered_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_project_stage__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_project_stage__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_project_stage__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("(status = 'COMPLETED') = (completed_on IS NOT NULL)", name="ck_project_stage__completed"),
        sa.CheckConstraint(
            "completed_by IS NULL OR (length(completed_by) = 32 AND completed_by NOT GLOB '*[^0-9a-f]*' AND substr(completed_by, 13, 1) = '7' AND substr(completed_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_stage__completed_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_stage__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_stage__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("status = 'NOT_STARTED' OR entered_on IS NOT NULL", name="ck_project_stage__entered"),
        sa.CheckConstraint(
            "entered_by IS NULL OR (length(entered_by) = 32 AND entered_by NOT GLOB '*[^0-9a-f]*' AND substr(entered_by, 13, 1) = '7' AND substr(entered_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_stage__entered_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_stage__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_project_stage__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_stage__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_stage__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_project_stage__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "stage_code IN ('BOOKED', 'DESIGN_FINALISATION', 'SCOPE_FROZEN', 'SITE_READINESS', 'PRODUCTION_READINESS', 'IN_PRODUCTION', 'READY_FOR_INSTALLATION', 'INSTALLATION', 'QUALITY_CHECK', 'SNAGGING', 'READY_FOR_HANDOVER', 'HANDED_OVER')",
            name="ck_project_stage__stage_code",
        ),
        sa.CheckConstraint("length(stage_code) <= 24", name="ck_project_stage__stage_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("status IN ('NOT_STARTED', 'ACTIVE', 'COMPLETED')", name="ck_project_stage__status"),
        sa.CheckConstraint("length(status) <= 12", name="ck_project_stage__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_project_stage__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_stage__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_project_stage__version_positive"),
    )
    op.create_index("ix_project_stage__lead_id", "project_stage", ["lead_id"])
    op.create_index(
        "ux_project_stage__code",
        "project_stage",
        ["project_id", "stage_code"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_project_stage__one_active",
        "project_stage",
        ["project_id"],
        unique=True,
        sqlite_where=sa.text("status = 'ACTIVE' AND is_deleted = 0"),
        postgresql_where=sa.text("status = 'ACTIVE' AND is_deleted = false"),
    )

    op.create_table(
        "project_member",
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
        sa.Column("responsibility", sa.String(12), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("removed_on", UTCDateTime(), nullable=True),
        sa.Column("removed_by", GUID(), nullable=True),
        sa.Column("removal_reason", sa.String(500), nullable=True),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_project_member"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_project_member__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_project_member__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_project_member__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_project_member__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["removed_by"], ["app_user.id"], name="fk_project_member__removed_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_project_member__updated_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], name="fk_project_member__user_id", ondelete="RESTRICT"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_member__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_member__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_member__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_active IN (0, 1)", name="ck_project_member__is_active_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_project_member__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_member__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_member__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(removal_reason) <= 500", name="ck_project_member__removal_reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "is_active = (removed_on IS NULL) AND (removed_on IS NULL) = (removed_by IS NULL)",
            name="ck_project_member__removed",
        ),
        sa.CheckConstraint(
            "removed_by IS NULL OR (length(removed_by) = 32 AND removed_by NOT GLOB '*[^0-9a-f]*' AND substr(removed_by, 13, 1) = '7' AND substr(removed_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_member__removed_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "responsibility IN ('COMMERCIAL', 'DESIGN', 'PROJECT', 'SITE', 'QUALITY', 'HANDOVER', 'MEMBER')",
            name="ck_project_member__responsibility",
        ),
        sa.CheckConstraint("length(responsibility) <= 12", name="ck_project_member__responsibility_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_project_member__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_project_member__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_member__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(user_id) = 32 AND user_id NOT GLOB '*[^0-9a-f]*' AND substr(user_id, 13, 1) = '7' AND substr(user_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_member__user_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_project_member__version_positive"),
    )
    op.create_index("ix_project_member__lead_id", "project_member", ["lead_id"])
    op.create_index("ix_project_member__user", "project_member", ["user_id", "is_active"])
    op.create_index(
        "ux_project_member__owner",
        "project_member",
        ["project_id", "responsibility"],
        unique=True,
        sqlite_where=sa.text("is_active = 1 AND is_deleted = 0 AND responsibility <> 'MEMBER'"),
        postgresql_where=sa.text("is_active = true AND is_deleted = false AND responsibility <> 'MEMBER'"),
    )
    op.create_index(
        "ux_project_member__user_responsibility",
        "project_member",
        ["project_id", "user_id", "responsibility"],
        unique=True,
        sqlite_where=sa.text("is_active = 1 AND is_deleted = 0"),
        postgresql_where=sa.text("is_active = true AND is_deleted = false"),
    )

    op.create_table(
        "project_transition",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("from_stage", sa.String(24), nullable=False),
        sa.Column("to_stage", sa.String(24), nullable=False),
        sa.Column("lifecycle_version", sa.String(20), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("evaluation", JSONType(), nullable=False),
        sa.Column("evaluation_sha256", sa.String(64), nullable=False),
        sa.Column("independent_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.String(1000), nullable=True),
        sa.Column("decided_by", GUID(), nullable=True),
        sa.Column("decided_on", UTCDateTime(), nullable=True),
        sa.Column("decision_reason", sa.String(1000), nullable=True),
        sa.Column("handover_on", sa.Date(), nullable=True),
        sa.Column("acknowledgement_reference", sa.String(200), nullable=True),
        sa.Column("evidence_attachment_id", GUID(), nullable=True),
        sa.Column("observations", sa.String(2000), nullable=True),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_project_transition"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_project_transition__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["app_user.id"], name="fk_project_transition__decided_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_project_transition__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["evidence_attachment_id"],
            ["attachment.id"],
            name="fk_project_transition__evidence_attachment_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_project_transition__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_project_transition__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_project_transition__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(acknowledgement_reference) <= 200", name="ck_project_transition__acknowledgement_reference_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_transition__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "outcome IN ('REFUSED', 'AWAITING_APPROVAL') OR (decided_by IS NOT NULL AND decided_on IS NOT NULL)",
            name="ck_project_transition__decided",
        ),
        sa.CheckConstraint(
            "decided_by IS NULL OR (length(decided_by) = 32 AND decided_by NOT GLOB '*[^0-9a-f]*' AND substr(decided_by, 13, 1) = '7' AND substr(decided_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_transition__decided_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(decision_reason) <= 1000", name="ck_project_transition__decision_reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_transition__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "evaluation IS NULL OR json_valid(evaluation)", name="ck_project_transition__evaluation_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(evaluation_sha256) = 64", name="ck_project_transition__evaluation_sha256_len"),
        sa.CheckConstraint(
            "evidence_attachment_id IS NULL OR (length(evidence_attachment_id) = 32 AND evidence_attachment_id NOT GLOB '*[^0-9a-f]*' AND substr(evidence_attachment_id, 13, 1) = '7' AND substr(evidence_attachment_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_transition__evidence_attachment_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "from_stage IN ('BOOKED', 'DESIGN_FINALISATION', 'SCOPE_FROZEN', 'SITE_READINESS', 'PRODUCTION_READINESS', 'IN_PRODUCTION', 'READY_FOR_INSTALLATION', 'INSTALLATION', 'QUALITY_CHECK', 'SNAGGING', 'READY_FOR_HANDOVER', 'HANDED_OVER')",
            name="ck_project_transition__from_stage",
        ),
        sa.CheckConstraint("length(from_stage) <= 24", name="ck_project_transition__from_stage_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("kind <> 'HANDOVER' OR handover_on IS NOT NULL", name="ck_project_transition__handover_on"),
        sa.CheckConstraint(
            "kind = 'HANDOVER' OR (handover_on IS NULL AND acknowledgement_reference IS NULL AND evidence_attachment_id IS NULL AND observations IS NULL)",
            name="ck_project_transition__handover_only",
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_transition__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "independent_approval IN (0, 1)", name="ck_project_transition__independent_approval_bool"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_project_transition__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("kind IN ('STAGE', 'HANDOVER')", name="ck_project_transition__kind"),
        sa.CheckConstraint("length(kind) <= 10", name="ck_project_transition__kind_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_transition__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lifecycle_version) <= 20", name="ck_project_transition__lifecycle_version_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(observations) <= 2000", name="ck_project_transition__observations_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "outcome IN ('REFUSED', 'AWAITING_APPROVAL', 'COMPLETED', 'REJECTED', 'WITHDRAWN')",
            name="ck_project_transition__outcome",
        ),
        sa.CheckConstraint("length(outcome) <= 20", name="ck_project_transition__outcome_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_transition__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(reason) <= 1000", name="ck_project_transition__reason_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_project_transition__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "to_stage IN ('BOOKED', 'DESIGN_FINALISATION', 'SCOPE_FROZEN', 'SITE_READINESS', 'PRODUCTION_READINESS', 'IN_PRODUCTION', 'READY_FOR_INSTALLATION', 'INSTALLATION', 'QUALITY_CHECK', 'SNAGGING', 'READY_FOR_HANDOVER', 'HANDED_OVER')",
            name="ck_project_transition__to_stage",
        ),
        sa.CheckConstraint("length(to_stage) <= 24", name="ck_project_transition__to_stage_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_project_transition__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_transition__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_project_transition__version_positive"),
    )
    op.create_index("ix_project_transition__evidence", "project_transition", ["evidence_attachment_id"])
    op.create_index("ix_project_transition__lead_id", "project_transition", ["lead_id"])
    op.create_index("ix_project_transition__project", "project_transition", ["project_id", "created_on"])
    op.create_index(
        "ux_project_transition__one_pending",
        "project_transition",
        ["project_id"],
        unique=True,
        sqlite_where=sa.text("outcome = 'AWAITING_APPROVAL' AND is_deleted = 0"),
        postgresql_where=sa.text("outcome = 'AWAITING_APPROVAL' AND is_deleted = false"),
    )

    op.create_table(
        "project_checklist_item",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("stage_code", sa.String(24), nullable=False),
        sa.Column("item_code", sa.String(40), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("completed_by", GUID(), nullable=True),
        sa.Column("completed_on", UTCDateTime(), nullable=True),
        sa.Column("note", sa.String(1000), nullable=True),
        sa.Column("not_applicable_reason", sa.String(1000), nullable=True),
        sa.Column("reopen_reason", sa.String(1000), nullable=True),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("evidence_attachment_id", GUID(), nullable=True),
        sa.Column("evidence_reference", sa.String(200), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_project_checklist_item"),
        sa.ForeignKeyConstraint(
            ["completed_by"], ["app_user.id"], name="fk_project_checklist_item__completed_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_project_checklist_item__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_project_checklist_item__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["evidence_attachment_id"],
            ["attachment.id"],
            name="fk_project_checklist_item__evidence_attachment_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["lead.id"], name="fk_project_checklist_item__lead_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_project_checklist_item__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_project_checklist_item__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "(state = 'OPEN') = (completed_on IS NULL) AND (completed_on IS NULL) = (completed_by IS NULL)",
            name="ck_project_checklist_item__completed",
        ),
        sa.CheckConstraint(
            "completed_by IS NULL OR (length(completed_by) = 32 AND completed_by NOT GLOB '*[^0-9a-f]*' AND substr(completed_by, 13, 1) = '7' AND substr(completed_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_checklist_item__completed_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_checklist_item__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_checklist_item__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "evidence_attachment_id IS NULL OR (length(evidence_attachment_id) = 32 AND evidence_attachment_id NOT GLOB '*[^0-9a-f]*' AND substr(evidence_attachment_id, 13, 1) = '7' AND substr(evidence_attachment_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_checklist_item__evidence_attachment_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(evidence_reference) <= 200", name="ck_project_checklist_item__evidence_reference_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_checklist_item__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_project_checklist_item__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(item_code) <= 40", name="ck_project_checklist_item__item_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_checklist_item__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(state = 'NOT_APPLICABLE') = (not_applicable_reason IS NOT NULL)",
            name="ck_project_checklist_item__na_reason",
        ),
        sa.CheckConstraint(
            "length(not_applicable_reason) <= 1000", name="ck_project_checklist_item__not_applicable_reason_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(note) <= 1000", name="ck_project_checklist_item__note_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_checklist_item__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(reopen_reason) <= 1000", name="ck_project_checklist_item__reopen_reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_project_checklist_item__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "stage_code IN ('BOOKED', 'DESIGN_FINALISATION', 'SCOPE_FROZEN', 'SITE_READINESS', 'PRODUCTION_READINESS', 'IN_PRODUCTION', 'READY_FOR_INSTALLATION', 'INSTALLATION', 'QUALITY_CHECK', 'SNAGGING', 'READY_FOR_HANDOVER', 'HANDED_OVER')",
            name="ck_project_checklist_item__stage_code",
        ),
        sa.CheckConstraint("length(stage_code) <= 24", name="ck_project_checklist_item__stage_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("state IN ('OPEN', 'DONE', 'NOT_APPLICABLE')", name="ck_project_checklist_item__state"),
        sa.CheckConstraint("length(state) <= 16", name="ck_project_checklist_item__state_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_project_checklist_item__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_checklist_item__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_project_checklist_item__version_positive"),
    )
    op.create_index("ix_project_checklist_item__evidence", "project_checklist_item", ["evidence_attachment_id"])
    op.create_index("ix_project_checklist_item__lead_id", "project_checklist_item", ["lead_id"])
    op.create_index(
        "ux_project_checklist_item__code",
        "project_checklist_item",
        ["project_id", "stage_code", "item_code"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "project_milestone",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("milestone_code", sa.String(24), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("customer_label", sa.String(120), nullable=True),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("stage_code", sa.String(24), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=True),
        sa.Column("actual_date", sa.Date(), nullable=True),
        sa.Column("customer_promised_date", sa.Date(), nullable=True),
        sa.Column("depends_on_milestone_id", GUID(), nullable=True),
        sa.Column("owner_responsibility", sa.String(12), nullable=True),
        sa.Column("status_reason", sa.String(500), nullable=True),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("evidence_attachment_id", GUID(), nullable=True),
        sa.Column("evidence_reference", sa.String(200), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_project_milestone"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_project_milestone__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_project_milestone__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["depends_on_milestone_id"],
            ["project_milestone.id"],
            name="fk_project_milestone__depends_on_milestone_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_attachment_id"],
            ["attachment.id"],
            name="fk_project_milestone__evidence_attachment_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_project_milestone__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_project_milestone__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_project_milestone__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "(status = 'COMPLETED') = (actual_date IS NOT NULL)", name="ck_project_milestone__actual_date"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_milestone__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(customer_label) <= 120", name="ck_project_milestone__customer_label_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_milestone__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "depends_on_milestone_id IS NULL OR (length(depends_on_milestone_id) = 32 AND depends_on_milestone_id NOT GLOB '*[^0-9a-f]*' AND substr(depends_on_milestone_id, 13, 1) = '7' AND substr(depends_on_milestone_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_milestone__depends_on_milestone_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(description) <= 1000", name="ck_project_milestone__description_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "evidence_attachment_id IS NULL OR (length(evidence_attachment_id) = 32 AND evidence_attachment_id NOT GLOB '*[^0-9a-f]*' AND substr(evidence_attachment_id, 13, 1) = '7' AND substr(evidence_attachment_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_milestone__evidence_attachment_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(evidence_reference) <= 200", name="ck_project_milestone__evidence_reference_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_milestone__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_project_milestone__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(label) <= 120", name="ck_project_milestone__label_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_milestone__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "milestone_code IN ('DESIGN_SIGN_OFF', 'SCOPE_FREEZE', 'SITE_READY', 'PRODUCTION_RELEASE', 'PRODUCTION_COMPLETE', 'DELIVERY_TO_SITE', 'INSTALLATION_START', 'INSTALLATION_COMPLETE', 'QUALITY_CHECK_COMPLETE', 'HANDOVER', 'OTHER')",
            name="ck_project_milestone__milestone_code",
        ),
        sa.CheckConstraint("length(milestone_code) <= 24", name="ck_project_milestone__milestone_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "owner_responsibility IS NULL OR owner_responsibility IN ('COMMERCIAL', 'DESIGN', 'PROJECT', 'SITE', 'QUALITY', 'HANDOVER', 'MEMBER')",
            name="ck_project_milestone__owner_responsibility",
        ),
        sa.CheckConstraint(
            "length(owner_responsibility) <= 12", name="ck_project_milestone__owner_responsibility_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_milestone__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_project_milestone__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "stage_code IN ('BOOKED', 'DESIGN_FINALISATION', 'SCOPE_FROZEN', 'SITE_READINESS', 'PRODUCTION_READINESS', 'IN_PRODUCTION', 'READY_FOR_INSTALLATION', 'INSTALLATION', 'QUALITY_CHECK', 'SNAGGING', 'READY_FOR_HANDOVER', 'HANDED_OVER')",
            name="ck_project_milestone__stage_code",
        ),
        sa.CheckConstraint("length(stage_code) <= 24", name="ck_project_milestone__stage_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "status IN ('NOT_STARTED', 'PLANNED', 'IN_PROGRESS', 'BLOCKED', 'COMPLETED', 'CANCELLED', 'NOT_APPLICABLE')",
            name="ck_project_milestone__status",
        ),
        sa.CheckConstraint("length(status) <= 16", name="ck_project_milestone__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status NOT IN ('CANCELLED', 'NOT_APPLICABLE') OR status_reason IS NOT NULL",
            name="ck_project_milestone__status_reason",
        ),
        sa.CheckConstraint("length(status_reason) <= 500", name="ck_project_milestone__status_reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_project_milestone__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_milestone__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_project_milestone__version_positive"),
    )
    op.create_index("ix_project_milestone__depends_on", "project_milestone", ["depends_on_milestone_id"])
    op.create_index("ix_project_milestone__evidence", "project_milestone", ["evidence_attachment_id"])
    op.create_index("ix_project_milestone__lead_id", "project_milestone", ["lead_id"])
    op.create_index("ix_project_milestone__project", "project_milestone", ["project_id", "stage_code"])

    op.create_table(
        "project_site_readiness",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("item_code", sa.String(40), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("label", sa.String(160), nullable=True),
        sa.Column("promise_content_version", sa.String(40), nullable=True),
        sa.Column("status", sa.String(28), nullable=False),
        sa.Column("responsible_party", sa.String(16), nullable=False),
        sa.Column("action", sa.String(500), nullable=True),
        sa.Column("customer_action", sa.String(300), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("note", sa.String(1000), nullable=True),
        sa.Column("resolved_on", UTCDateTime(), nullable=True),
        sa.Column("resolved_by", GUID(), nullable=True),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("evidence_attachment_id", GUID(), nullable=True),
        sa.Column("evidence_reference", sa.String(200), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_project_site_readiness"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_project_site_readiness__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_project_site_readiness__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["evidence_attachment_id"],
            ["attachment.id"],
            name="fk_project_site_readiness__evidence_attachment_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["lead.id"], name="fk_project_site_readiness__lead_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_project_site_readiness__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"], ["app_user.id"], name="fk_project_site_readiness__resolved_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_project_site_readiness__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("length(action) <= 500", name="ck_project_site_readiness__action_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "category IN ('FLOORING', 'PAINTING', 'DOORS_WINDOWS', 'ELECTRICAL_SUPPLY', 'WATER', 'ACCESS', 'SERVICE_LIFT', 'WORK_AREA_CLEARANCE', 'BUILDER_SOCIETY_APPROVAL', 'APPLIANCE_INFORMATION', 'CIVIL_WORK', 'PLUMBING_DEPENDENCIES', 'ELECTRICAL_DEPENDENCIES', 'OTHER', 'CLIENT_SUPPLIED_ITEM', 'APPLIANCE_MODEL', 'APPLIANCE_DIMENSIONS', 'ELECTRICITY', 'SERVICE_LIFT_ACCESS', 'WORKING_ACCESS', 'BUILDER_SOCIETY_PERMISSION', 'CIVIL_READINESS', 'PLUMBING_READINESS', 'ELECTRICAL_READINESS')",
            name="ck_project_site_readiness__category",
        ),
        sa.CheckConstraint("length(category) <= 32", name="ck_project_site_readiness__category_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_site_readiness__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(customer_action) <= 300", name="ck_project_site_readiness__customer_action_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_site_readiness__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "evidence_attachment_id IS NULL OR (length(evidence_attachment_id) = 32 AND evidence_attachment_id NOT GLOB '*[^0-9a-f]*' AND substr(evidence_attachment_id, 13, 1) = '7' AND substr(evidence_attachment_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_site_readiness__evidence_attachment_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(evidence_reference) <= 200", name="ck_project_site_readiness__evidence_reference_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_site_readiness__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_project_site_readiness__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(item_code) <= 40", name="ck_project_site_readiness__item_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("kind IN ('READINESS', 'RESPONSIBILITY')", name="ck_project_site_readiness__kind"),
        sa.CheckConstraint("length(kind) <= 16", name="ck_project_site_readiness__kind_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("source = 'CUSTOMER_PROMISE' OR label IS NOT NULL", name="ck_project_site_readiness__label"),
        sa.CheckConstraint("length(label) <= 160", name="ck_project_site_readiness__label_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_site_readiness__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(note) <= 1000", name="ck_project_site_readiness__note_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_site_readiness__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(promise_content_version) <= 40", name="ck_project_site_readiness__promise_content_version_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("(resolved_on IS NULL) = (resolved_by IS NULL)", name="ck_project_site_readiness__resolved"),
        sa.CheckConstraint(
            "resolved_by IS NULL OR (length(resolved_by) = 32 AND resolved_by NOT GLOB '*[^0-9a-f]*' AND substr(resolved_by, 13, 1) = '7' AND substr(resolved_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_site_readiness__resolved_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "responsible_party IN ('CUSTOMER', 'VEDA', 'THIRD_PARTY', 'TO_BE_CONFIRMED')",
            name="ck_project_site_readiness__responsible_party",
        ),
        sa.CheckConstraint(
            "length(responsible_party) <= 16", name="ck_project_site_readiness__responsible_party_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_project_site_readiness__soft_delete_consistent",
        ),
        sa.CheckConstraint("source IN ('CUSTOMER_PROMISE', 'STAFF')", name="ck_project_site_readiness__source"),
        sa.CheckConstraint("length(source) <= 20", name="ck_project_site_readiness__source_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "status IN ('READY', 'NOT_READY', 'CUSTOMER_ACTION_REQUIRED', 'VEDA_ACTION_REQUIRED', 'NOT_APPLICABLE', 'TO_BE_CONFIRMED')",
            name="ck_project_site_readiness__status",
        ),
        sa.CheckConstraint("length(status) <= 28", name="ck_project_site_readiness__status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_project_site_readiness__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_site_readiness__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_project_site_readiness__version_positive"),
    )
    op.create_index("ix_project_site_readiness__evidence", "project_site_readiness", ["evidence_attachment_id"])
    op.create_index("ix_project_site_readiness__lead_id", "project_site_readiness", ["lead_id"])
    op.create_index(
        "ux_project_site_readiness__item",
        "project_site_readiness",
        ["project_id", "kind", "item_code"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "project_blocker",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("impact", sa.String(16), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("customer_action", sa.String(300), nullable=True),
        sa.Column("responsible_party", sa.String(16), nullable=False),
        sa.Column("assigned_to", GUID(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("blocks_stage_code", sa.String(24), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("resolution", sa.String(1000), nullable=True),
        sa.Column("resolved_on", UTCDateTime(), nullable=True),
        sa.Column("resolved_by", GUID(), nullable=True),
        sa.Column("related_milestone_id", GUID(), nullable=True),
        sa.Column("related_checklist_item_id", GUID(), nullable=True),
        sa.Column("related_site_readiness_id", GUID(), nullable=True),
        sa.Column("related_quotation_id", GUID(), nullable=True),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_project_blocker"),
        sa.ForeignKeyConstraint(
            ["assigned_to"], ["app_user.id"], name="fk_project_blocker__assigned_to", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_project_blocker__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_project_blocker__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_project_blocker__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_project_blocker__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["related_checklist_item_id"],
            ["project_checklist_item.id"],
            name="fk_project_blocker__related_checklist_item_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["related_milestone_id"],
            ["project_milestone.id"],
            name="fk_project_blocker__related_milestone_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["related_quotation_id"],
            ["quotation.id"],
            name="fk_project_blocker__related_quotation_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["related_site_readiness_id"],
            ["project_site_readiness.id"],
            name="fk_project_blocker__related_site_readiness_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"], ["app_user.id"], name="fk_project_blocker__resolved_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_project_blocker__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "assigned_to IS NULL OR (length(assigned_to) = 32 AND assigned_to NOT GLOB '*[^0-9a-f]*' AND substr(assigned_to, 13, 1) = '7' AND substr(assigned_to, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_blocker__assigned_to_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "blocks_stage_code IS NULL OR blocks_stage_code IN ('BOOKED', 'DESIGN_FINALISATION', 'SCOPE_FROZEN', 'SITE_READINESS', 'PRODUCTION_READINESS', 'IN_PRODUCTION', 'READY_FOR_INSTALLATION', 'INSTALLATION', 'QUALITY_CHECK', 'SNAGGING', 'READY_FOR_HANDOVER', 'HANDED_OVER')",
            name="ck_project_blocker__blocks_stage_code",
        ),
        sa.CheckConstraint("length(blocks_stage_code) <= 24", name="ck_project_blocker__blocks_stage_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "category IN ('DESIGN', 'CUSTOMER_DECISION', 'SITE', 'ACCESS', 'MATERIAL_SPECIFICATION', 'COMMERCIAL', 'PRODUCTION', 'INSTALLATION', 'QUALITY', 'OTHER')",
            name="ck_project_blocker__category",
        ),
        sa.CheckConstraint("length(category) <= 24", name="ck_project_blocker__category_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status NOT IN ('RESOLVED', 'CANCELLED') OR (resolution IS NOT NULL AND resolved_on IS NOT NULL AND resolved_by IS NOT NULL)",
            name="ck_project_blocker__closed",
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_blocker__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(customer_action) <= 300", name="ck_project_blocker__customer_action_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_blocker__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(description) <= 2000", name="ck_project_blocker__description_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "impact <> 'GATING' OR blocks_stage_code IS NOT NULL", name="ck_project_blocker__gating_stage"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_blocker__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("impact IN ('GATING', 'INFORMATIONAL')", name="ck_project_blocker__impact"),
        sa.CheckConstraint("length(impact) <= 16", name="ck_project_blocker__impact_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_project_blocker__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_blocker__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_blocker__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "related_checklist_item_id IS NULL OR (length(related_checklist_item_id) = 32 AND related_checklist_item_id NOT GLOB '*[^0-9a-f]*' AND substr(related_checklist_item_id, 13, 1) = '7' AND substr(related_checklist_item_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_blocker__related_checklist_item_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "related_milestone_id IS NULL OR (length(related_milestone_id) = 32 AND related_milestone_id NOT GLOB '*[^0-9a-f]*' AND substr(related_milestone_id, 13, 1) = '7' AND substr(related_milestone_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_blocker__related_milestone_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "related_quotation_id IS NULL OR (length(related_quotation_id) = 32 AND related_quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(related_quotation_id, 13, 1) = '7' AND substr(related_quotation_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_blocker__related_quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "related_site_readiness_id IS NULL OR (length(related_site_readiness_id) = 32 AND related_site_readiness_id NOT GLOB '*[^0-9a-f]*' AND substr(related_site_readiness_id, 13, 1) = '7' AND substr(related_site_readiness_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_blocker__related_site_readiness_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(resolution) <= 1000", name="ck_project_blocker__resolution_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "resolved_by IS NULL OR (length(resolved_by) = 32 AND resolved_by NOT GLOB '*[^0-9a-f]*' AND substr(resolved_by, 13, 1) = '7' AND substr(resolved_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_blocker__resolved_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "responsible_party IN ('CUSTOMER', 'VEDA', 'THIRD_PARTY', 'TO_BE_CONFIRMED')",
            name="ck_project_blocker__responsible_party",
        ),
        sa.CheckConstraint("length(responsible_party) <= 16", name="ck_project_blocker__responsible_party_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_project_blocker__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "source IN ('STAFF', 'SITE_READINESS', 'QUALITY_CHECK', 'SNAG', 'VARIATION')",
            name="ck_project_blocker__source",
        ),
        sa.CheckConstraint("length(source) <= 16", name="ck_project_blocker__source_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status IN ('OPEN', 'IN_PROGRESS', 'WAITING_CUSTOMER', 'WAITING_VEDA', 'RESOLVED', 'CANCELLED')",
            name="ck_project_blocker__status",
        ),
        sa.CheckConstraint("length(status) <= 20", name="ck_project_blocker__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(title) <= 160", name="ck_project_blocker__title_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_project_blocker__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_blocker__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_project_blocker__version_positive"),
    )
    op.create_index("ix_project_blocker__assigned_to", "project_blocker", ["assigned_to"])
    op.create_index("ix_project_blocker__checklist", "project_blocker", ["related_checklist_item_id"])
    op.create_index("ix_project_blocker__lead_id", "project_blocker", ["lead_id"])
    op.create_index("ix_project_blocker__milestone", "project_blocker", ["related_milestone_id"])
    op.create_index("ix_project_blocker__project", "project_blocker", ["project_id", "status"])
    op.create_index("ix_project_blocker__quotation", "project_blocker", ["related_quotation_id"])
    op.create_index("ix_project_blocker__site_readiness", "project_blocker", ["related_site_readiness_id"])

    op.create_table(
        "project_qc_check",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("category", sa.String(28), nullable=False),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("space_id", GUID(), nullable=True),
        sa.Column("observation", sa.String(1000), nullable=True),
        sa.Column("recheck_of_id", GUID(), nullable=True),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("evidence_attachment_id", GUID(), nullable=True),
        sa.Column("evidence_reference", sa.String(200), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_project_qc_check"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_project_qc_check__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_project_qc_check__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["evidence_attachment_id"],
            ["attachment.id"],
            name="fk_project_qc_check__evidence_attachment_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_project_qc_check__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_project_qc_check__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["recheck_of_id"], ["project_qc_check.id"], name="fk_project_qc_check__recheck_of_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["space_id"], ["property_space.id"], name="fk_project_qc_check__space_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_project_qc_check__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "category IN ('DIMENSIONS_AND_ALIGNMENT', 'FINISH_AND_SURFACES', 'HARDWARE_AND_OPERATION', 'SERVICES_FITMENT', 'CLEANLINESS_AND_PROTECTION', 'OTHER')",
            name="ck_project_qc_check__category",
        ),
        sa.CheckConstraint("length(category) <= 28", name="ck_project_qc_check__category_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_qc_check__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_qc_check__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "evidence_attachment_id IS NULL OR (length(evidence_attachment_id) = 32 AND evidence_attachment_id NOT GLOB '*[^0-9a-f]*' AND substr(evidence_attachment_id, 13, 1) = '7' AND substr(evidence_attachment_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_qc_check__evidence_attachment_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(evidence_reference) <= 200", name="ck_project_qc_check__evidence_reference_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("result <> 'FAIL' OR observation IS NOT NULL", name="ck_project_qc_check__fail_observed"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_qc_check__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_project_qc_check__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_qc_check__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(observation) <= 1000", name="ck_project_qc_check__observation_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_qc_check__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "recheck_of_id IS NULL OR (length(recheck_of_id) = 32 AND recheck_of_id NOT GLOB '*[^0-9a-f]*' AND substr(recheck_of_id, 13, 1) = '7' AND substr(recheck_of_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_qc_check__recheck_of_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "result IN ('PASS', 'FAIL', 'NOT_APPLICABLE', 'TO_BE_CONFIRMED')", name="ck_project_qc_check__result"
        ),
        sa.CheckConstraint("length(result) <= 16", name="ck_project_qc_check__result_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_project_qc_check__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "space_id IS NULL OR (length(space_id) = 32 AND space_id NOT GLOB '*[^0-9a-f]*' AND substr(space_id, 13, 1) = '7' AND substr(space_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_qc_check__space_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_project_qc_check__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_qc_check__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_project_qc_check__version_positive"),
    )
    op.create_index("ix_project_qc_check__evidence", "project_qc_check", ["evidence_attachment_id"])
    op.create_index("ix_project_qc_check__lead_id", "project_qc_check", ["lead_id"])
    op.create_index("ix_project_qc_check__project", "project_qc_check", ["project_id", "category", "created_on"])
    op.create_index("ix_project_qc_check__recheck_of", "project_qc_check", ["recheck_of_id"])
    op.create_index("ix_project_qc_check__space_id", "project_qc_check", ["space_id"])

    op.create_table(
        "project_snag",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("snag_no", sa.Integer(), nullable=False),
        sa.Column("space_id", GUID(), nullable=True),
        sa.Column("item_reference", sa.String(200), nullable=True),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("customer_title", sa.String(160), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("is_blocking", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("classification_reason", sa.String(500), nullable=True),
        sa.Column("owner_user_id", GUID(), nullable=True),
        sa.Column("responsible_party", sa.String(16), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("resolution_note", sa.String(1000), nullable=True),
        sa.Column("resolved_on", UTCDateTime(), nullable=True),
        sa.Column("resolved_by", GUID(), nullable=True),
        sa.Column("closed_on", UTCDateTime(), nullable=True),
        sa.Column("closed_by", GUID(), nullable=True),
        sa.Column("qc_check_id", GUID(), nullable=True),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("evidence_attachment_id", GUID(), nullable=True),
        sa.Column("evidence_reference", sa.String(200), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_project_snag"),
        sa.ForeignKeyConstraint(["closed_by"], ["app_user.id"], name="fk_project_snag__closed_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_project_snag__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_project_snag__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["evidence_attachment_id"],
            ["attachment.id"],
            name="fk_project_snag__evidence_attachment_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_project_snag__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["app_user.id"], name="fk_project_snag__owner_user_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_project_snag__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["qc_check_id"], ["project_qc_check.id"], name="fk_project_snag__qc_check_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"], ["app_user.id"], name="fk_project_snag__resolved_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["space_id"], ["property_space.id"], name="fk_project_snag__space_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_project_snag__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "category IN ('CARPENTRY', 'FINISH', 'HARDWARE', 'ALIGNMENT', 'DAMAGE', 'SERVICES_FITMENT', 'CLEANING', 'MISSING_ITEM', 'OTHER')",
            name="ck_project_snag__category",
        ),
        sa.CheckConstraint("length(category) <= 20", name="ck_project_snag__category_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(classification_reason) <= 500", name="ck_project_snag__classification_reason_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(status = 'CLOSED') = (closed_on IS NOT NULL AND closed_by IS NOT NULL)", name="ck_project_snag__closed"
        ),
        sa.CheckConstraint(
            "closed_by IS NULL OR (length(closed_by) = 32 AND closed_by NOT GLOB '*[^0-9a-f]*' AND substr(closed_by, 13, 1) = '7' AND substr(closed_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_snag__closed_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_snag__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(customer_title) <= 160", name="ck_project_snag__customer_title_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_snag__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(description) <= 2000", name="ck_project_snag__description_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "evidence_attachment_id IS NULL OR (length(evidence_attachment_id) = 32 AND evidence_attachment_id NOT GLOB '*[^0-9a-f]*' AND substr(evidence_attachment_id, 13, 1) = '7' AND substr(evidence_attachment_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_snag__evidence_attachment_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(evidence_reference) <= 200", name="ck_project_snag__evidence_reference_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_snag__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_blocking IN (0, 1)", name="ck_project_snag__is_blocking_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_project_snag__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(item_reference) <= 200", name="ck_project_snag__item_reference_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_snag__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "owner_user_id IS NULL OR (length(owner_user_id) = 32 AND owner_user_id NOT GLOB '*[^0-9a-f]*' AND substr(owner_user_id, 13, 1) = '7' AND substr(owner_user_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_snag__owner_user_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_snag__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "qc_check_id IS NULL OR (length(qc_check_id) = 32 AND qc_check_id NOT GLOB '*[^0-9a-f]*' AND substr(qc_check_id, 13, 1) = '7' AND substr(qc_check_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_snag__qc_check_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(resolution_note) <= 1000", name="ck_project_snag__resolution_note_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "status <> 'RESOLVED' OR (resolved_on IS NOT NULL AND resolved_by IS NOT NULL)",
            name="ck_project_snag__resolved",
        ),
        sa.CheckConstraint(
            "resolved_by IS NULL OR (length(resolved_by) = 32 AND resolved_by NOT GLOB '*[^0-9a-f]*' AND substr(resolved_by, 13, 1) = '7' AND substr(resolved_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_snag__resolved_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "responsible_party IN ('CUSTOMER', 'VEDA', 'THIRD_PARTY', 'TO_BE_CONFIRMED')",
            name="ck_project_snag__responsible_party",
        ),
        sa.CheckConstraint("length(responsible_party) <= 16", name="ck_project_snag__responsible_party_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("snag_no >= 1", name="ck_project_snag__snag_no"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_project_snag__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "space_id IS NULL OR (length(space_id) = 32 AND space_id NOT GLOB '*[^0-9a-f]*' AND substr(space_id, 13, 1) = '7' AND substr(space_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_snag__space_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status IN ('OPEN', 'IN_PROGRESS', 'READY_FOR_RECHECK', 'RESOLVED', 'CLOSED')",
            name="ck_project_snag__status",
        ),
        sa.CheckConstraint("length(status) <= 20", name="ck_project_snag__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_project_snag__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_snag__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_project_snag__version_positive"),
    )
    op.create_index("ix_project_snag__evidence", "project_snag", ["evidence_attachment_id"])
    op.create_index("ix_project_snag__lead_id", "project_snag", ["lead_id"])
    op.create_index("ix_project_snag__owner", "project_snag", ["owner_user_id"])
    op.create_index("ix_project_snag__qc_check", "project_snag", ["qc_check_id"])
    op.create_index("ix_project_snag__space_id", "project_snag", ["space_id"])
    op.create_index(
        "ux_project_snag__number",
        "project_snag",
        ["project_id", "snag_no"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "project_event",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("event_code", sa.String(32), nullable=False),
        sa.Column("stage_code", sa.String(24), nullable=True),
        sa.Column("from_state", sa.String(28), nullable=True),
        sa.Column("to_state", sa.String(28), nullable=True),
        sa.Column("detail", JSONType(), nullable=False),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_project_event"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_project_event__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_project_event__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_project_event__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_project_event__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_project_event__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_event__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_event__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("detail IS NULL OR json_valid(detail)", name="ck_project_event__detail_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "event_code IN ('PROJECT_CREATED', 'BASELINE_RECORDED', 'VARIATION_ACCEPTED', 'MEMBER_ASSIGNED', 'OWNER_ASSIGNED', 'MEMBER_REMOVED', 'TRANSITION_REFUSED', 'TRANSITION_AWAITING_APPROVAL', 'TRANSITION_REJECTED', 'TRANSITION_WITHDRAWN', 'STAGE_COMPLETED', 'STAGE_ENTERED', 'CHECKLIST_ITEM_COMPLETED', 'CHECKLIST_ITEM_NOT_APPLICABLE', 'CHECKLIST_ITEM_REOPENED', 'MILESTONE_ADDED', 'MILESTONE_CHANGED', 'BLOCKER_RAISED', 'BLOCKER_UPDATED', 'BLOCKER_RESOLVED', 'BLOCKER_CANCELLED', 'SITE_READINESS_ADDED', 'SITE_READINESS_UPDATED', 'QC_RECORDED', 'SNAG_RAISED', 'SNAG_UPDATED', 'SNAG_RECLASSIFIED', 'SNAG_RESOLVED', 'SNAG_CLOSED', 'HANDOVER_READY', 'HANDED_OVER')",
            name="ck_project_event__event_code",
        ),
        sa.CheckConstraint("length(event_code) <= 32", name="ck_project_event__event_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(from_state) <= 28", name="ck_project_event__from_state_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_event__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted = false AND version = 1", name="ck_project_event__immutable_contract"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_project_event__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_event__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_event__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_project_event__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "stage_code IS NULL OR stage_code IN ('BOOKED', 'DESIGN_FINALISATION', 'SCOPE_FROZEN', 'SITE_READINESS', 'PRODUCTION_READINESS', 'IN_PRODUCTION', 'READY_FOR_INSTALLATION', 'INSTALLATION', 'QUALITY_CHECK', 'SNAGGING', 'READY_FOR_HANDOVER', 'HANDED_OVER')",
            name="ck_project_event__stage_code",
        ),
        sa.CheckConstraint("length(stage_code) <= 24", name="ck_project_event__stage_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(to_state) <= 28", name="ck_project_event__to_state_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_project_event__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_event__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_project_event__version_positive"),
    )
    op.create_index("ix_project_event__lead_id", "project_event", ["lead_id"])
    op.create_index("ix_project_event__project", "project_event", ["project_id", "created_on"])
    # --- end generated DDL ---
    bind = op.get_bind()
    for table in IMMUTABLE:
        ms.create_immutability_guards(bind, table)
    for key, prefix in SEQUENCES:
        ms.seed_sequence(bind, key, prefix)
    ms.sync_permissions(bind, audit=True)
    ms.grant_new_codes(bind, CODES, audit=True)
    ms.assert_rbac_seed(bind)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
