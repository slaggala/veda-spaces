"""0212_project_execution: project execution, quality control, snags and handover (PEX, decision log 45).

Extends the Project Lifecycle (0208); it is not a second lifecycle. Four new tables (``veda.modules.project.models``):
``project_work_package`` (a body of work in one stage, explicit start and completion), ``project_qc_point`` (the QC plan),
``project_customer_report`` (an issue in the customer's words, triaged by staff) and ``project_handover_package`` (what
is handed over, frozen with a SHA-256, and the customer's acknowledgement). New nullable or defaulted columns on four
0208 tables: ``project_snag`` (work package, source, priority, customer visibility, the latest fix, fix evidence, closure
code), ``project_qc_check`` (plan point, work package), ``project_blocker`` (work package, customer summary) and
``project_transition`` (the handover package and digest a handover is bound to). A unique index admits one recheck per
quality check. The ``project_event`` code CHECK is widened with the new timeline codes (SQLite: the stored table
definition is rewritten in place, as 0205 did; PostgreSQL: the constraint is replaced). The two new staff codes
``project.manage_work`` and ``project.verify_snag`` are FOUNDER's.

Expand-only: no row, column or constraint is removed or narrowed. Before any change it refuses a database where a check
was rechecked twice (the unique index could not hold). Inert while VEDA_PROJECT_LIFECYCLE_ENABLED is off (the default
everywhere; production refuses it).

Revision ID: 0212_project_execution
Revises: 0211_accountant_role
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0212_project_execution"
down_revision = "0211_accountant_role"
branch_labels = None
depends_on = None

CODES = ("project.manage_work", "project.verify_snag")
OLD_EVENTS = "event_code IN ('PROJECT_CREATED', 'BASELINE_RECORDED', 'VARIATION_ACCEPTED', 'MEMBER_ASSIGNED', 'OWNER_ASSIGNED', 'MEMBER_REMOVED', 'TRANSITION_REFUSED', 'TRANSITION_AWAITING_APPROVAL', 'TRANSITION_REJECTED', 'TRANSITION_WITHDRAWN', 'STAGE_COMPLETED', 'STAGE_ENTERED', 'CHECKLIST_ITEM_COMPLETED', 'CHECKLIST_ITEM_NOT_APPLICABLE', 'CHECKLIST_ITEM_REOPENED', 'MILESTONE_ADDED', 'MILESTONE_CHANGED', 'BLOCKER_RAISED', 'BLOCKER_UPDATED', 'BLOCKER_RESOLVED', 'BLOCKER_CANCELLED', 'SITE_READINESS_ADDED', 'SITE_READINESS_UPDATED', 'QC_RECORDED', 'SNAG_RAISED', 'SNAG_UPDATED', 'SNAG_RECLASSIFIED', 'SNAG_RESOLVED', 'SNAG_CLOSED', 'HANDOVER_READY', 'HANDED_OVER')"
NEW_EVENTS = "event_code IN ('PROJECT_CREATED', 'BASELINE_RECORDED', 'VARIATION_ACCEPTED', 'MEMBER_ASSIGNED', 'OWNER_ASSIGNED', 'MEMBER_REMOVED', 'TRANSITION_REFUSED', 'TRANSITION_AWAITING_APPROVAL', 'TRANSITION_REJECTED', 'TRANSITION_WITHDRAWN', 'STAGE_COMPLETED', 'STAGE_ENTERED', 'CHECKLIST_ITEM_COMPLETED', 'CHECKLIST_ITEM_NOT_APPLICABLE', 'CHECKLIST_ITEM_REOPENED', 'MILESTONE_ADDED', 'MILESTONE_CHANGED', 'BLOCKER_RAISED', 'BLOCKER_UPDATED', 'BLOCKER_RESOLVED', 'BLOCKER_CANCELLED', 'SITE_READINESS_ADDED', 'SITE_READINESS_UPDATED', 'QC_RECORDED', 'SNAG_RAISED', 'SNAG_UPDATED', 'SNAG_RECLASSIFIED', 'SNAG_RESOLVED', 'SNAG_CLOSED', 'HANDOVER_READY', 'HANDED_OVER', 'WORK_PACKAGE_ADDED', 'WORK_PACKAGE_CHANGED', 'WORK_PACKAGE_REPLANNED', 'WORK_PACKAGE_STARTED', 'WORK_PACKAGE_COMPLETED', 'WORK_PACKAGE_REOPENED', 'WORK_PACKAGE_CANCELLED', 'QC_POINT_ADDED', 'QC_POINT_WITHDRAWN', 'SNAG_FIXED', 'SNAG_RECHECK_FAILED', 'CUSTOMER_REPORT_SUBMITTED', 'CUSTOMER_REPORT_ACCEPTED', 'CUSTOMER_REPORT_DECLINED', 'HANDOVER_PACKAGE_PREPARED', 'HANDOVER_PACKAGE_SUPERSEDED', 'HANDOVER_ACKNOWLEDGED', 'HANDOVER_PACKAGE_REDACTED')"

SQLITE = (
    "ALTER TABLE project_snag ADD COLUMN work_package_id CHAR(32) CONSTRAINT fk_project_snag__work_package_id REFERENCES project_work_package (id) ON DELETE RESTRICT CONSTRAINT ck_project_snag__work_package_id_format CHECK (work_package_id IS NULL OR (length(work_package_id) = 32 AND work_package_id NOT GLOB '*[^0-9a-f]*' AND substr(work_package_id, 13, 1) = '7' AND substr(work_package_id, 17, 1) IN ('8', '9', 'a', 'b')))",
    "ALTER TABLE project_snag ADD COLUMN source VARCHAR(16) DEFAULT 'STAFF' NOT NULL CONSTRAINT ck_project_snag__source CHECK (source IN ('STAFF', 'QUALITY_CHECK', 'CUSTOMER')) CONSTRAINT ck_project_snag__source_len CHECK (length(source) <= 16)",
    "ALTER TABLE project_snag ADD COLUMN priority VARCHAR(8) DEFAULT 'NORMAL' NOT NULL CONSTRAINT ck_project_snag__priority CHECK (priority IN ('HIGH', 'NORMAL', 'LOW')) CONSTRAINT ck_project_snag__priority_len CHECK (length(priority) <= 8)",
    "ALTER TABLE project_snag ADD COLUMN customer_visible BOOLEAN DEFAULT 0 NOT NULL CONSTRAINT ck_project_snag__customer_visible_bool CHECK (customer_visible IN (0, 1))",
    "ALTER TABLE project_snag ADD COLUMN fixed_by CHAR(32) CONSTRAINT fk_project_snag__fixed_by REFERENCES app_user (id) ON DELETE RESTRICT CONSTRAINT ck_project_snag__fixed_by_format CHECK (fixed_by IS NULL OR (length(fixed_by) = 32 AND fixed_by NOT GLOB '*[^0-9a-f]*' AND substr(fixed_by, 13, 1) = '7' AND substr(fixed_by, 17, 1) IN ('8', '9', 'a', 'b')))",
    "ALTER TABLE project_snag ADD COLUMN fixed_on VARCHAR(27) CONSTRAINT ck_project_snag__fixed CHECK ((fixed_on IS NULL) = (fixed_by IS NULL))",
    "ALTER TABLE project_snag ADD COLUMN fix_note VARCHAR(1000) CONSTRAINT ck_project_snag__fix_note_len CHECK (length(fix_note) <= 1000)",
    "ALTER TABLE project_snag ADD COLUMN resolution_evidence_attachment_id CHAR(32) CONSTRAINT fk_project_snag__resolution_evidence_attachment_id REFERENCES attachment (id) ON DELETE RESTRICT CONSTRAINT ck_project_snag__resolution_evidence_attachment_id_format CHECK (resolution_evidence_attachment_id IS NULL OR (length(resolution_evidence_attachment_id) = 32 AND resolution_evidence_attachment_id NOT GLOB '*[^0-9a-f]*' AND substr(resolution_evidence_attachment_id, 13, 1) = '7' AND substr(resolution_evidence_attachment_id, 17, 1) IN ('8', '9', 'a', 'b')))",
    "ALTER TABLE project_snag ADD COLUMN closure_code VARCHAR(16) CONSTRAINT ck_project_snag__closure_code CHECK (closure_code IS NULL OR closure_code IN ('FIXED', 'DUPLICATE', 'NOT_A_DEFECT', 'RAISED_IN_ERROR')) CONSTRAINT ck_project_snag__closure_code_len CHECK (length(closure_code) <= 16)",
    "ALTER TABLE project_qc_check ADD COLUMN qc_point_id CHAR(32) CONSTRAINT fk_project_qc_check__qc_point_id REFERENCES project_qc_point (id) ON DELETE RESTRICT CONSTRAINT ck_project_qc_check__qc_point_id_format CHECK (qc_point_id IS NULL OR (length(qc_point_id) = 32 AND qc_point_id NOT GLOB '*[^0-9a-f]*' AND substr(qc_point_id, 13, 1) = '7' AND substr(qc_point_id, 17, 1) IN ('8', '9', 'a', 'b')))",
    "ALTER TABLE project_qc_check ADD COLUMN work_package_id CHAR(32) CONSTRAINT fk_project_qc_check__work_package_id REFERENCES project_work_package (id) ON DELETE RESTRICT CONSTRAINT ck_project_qc_check__work_package_id_format CHECK (work_package_id IS NULL OR (length(work_package_id) = 32 AND work_package_id NOT GLOB '*[^0-9a-f]*' AND substr(work_package_id, 13, 1) = '7' AND substr(work_package_id, 17, 1) IN ('8', '9', 'a', 'b')))",
    "ALTER TABLE project_blocker ADD COLUMN related_work_package_id CHAR(32) CONSTRAINT fk_project_blocker__related_work_package_id REFERENCES project_work_package (id) ON DELETE RESTRICT CONSTRAINT ck_project_blocker__related_work_package_id_format CHECK (related_work_package_id IS NULL OR (length(related_work_package_id) = 32 AND related_work_package_id NOT GLOB '*[^0-9a-f]*' AND substr(related_work_package_id, 13, 1) = '7' AND substr(related_work_package_id, 17, 1) IN ('8', '9', 'a', 'b')))",
    "ALTER TABLE project_blocker ADD COLUMN customer_summary VARCHAR(300) CONSTRAINT ck_project_blocker__customer_summary_len CHECK (length(customer_summary) <= 300)",
    "ALTER TABLE project_transition ADD COLUMN handover_package_id CHAR(32) CONSTRAINT fk_project_transition__handover_package_id REFERENCES project_handover_package (id) ON DELETE RESTRICT CONSTRAINT ck_project_transition__handover_package_id_format CHECK (handover_package_id IS NULL OR (length(handover_package_id) = 32 AND handover_package_id NOT GLOB '*[^0-9a-f]*' AND substr(handover_package_id, 13, 1) = '7' AND substr(handover_package_id, 17, 1) IN ('8', '9', 'a', 'b')))",
    "ALTER TABLE project_transition ADD COLUMN handover_package_sha256 VARCHAR(64) CONSTRAINT ck_project_transition__package_handover_only CHECK (kind = 'HANDOVER' OR (handover_package_id IS NULL AND handover_package_sha256 IS NULL)) CONSTRAINT ck_project_transition__package_pair CHECK ((handover_package_id IS NULL) = (handover_package_sha256 IS NULL)) CONSTRAINT ck_project_transition__handover_package_sha256_len CHECK (handover_package_sha256 IS NULL OR length(handover_package_sha256) = 64)",
)


def _columns_postgresql() -> None:
    op.add_column("project_snag", sa.Column("work_package_id", GUID(), nullable=True))
    op.add_column("project_snag", sa.Column("source", sa.String(16), nullable=False, server_default="STAFF"))
    op.add_column("project_snag", sa.Column("priority", sa.String(8), nullable=False, server_default="NORMAL"))
    op.add_column(
        "project_snag", sa.Column("customer_visible", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("project_snag", sa.Column("fixed_by", GUID(), nullable=True))
    op.add_column("project_snag", sa.Column("fixed_on", UTCDateTime(), nullable=True))
    op.add_column("project_snag", sa.Column("fix_note", sa.String(1000), nullable=True))
    op.add_column("project_snag", sa.Column("resolution_evidence_attachment_id", GUID(), nullable=True))
    op.add_column("project_snag", sa.Column("closure_code", sa.String(16), nullable=True))
    op.create_foreign_key(
        "fk_project_snag__resolution_evidence_attachment_id",
        "project_snag",
        "attachment",
        ["resolution_evidence_attachment_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_project_snag__work_package_id",
        "project_snag",
        "project_work_package",
        ["work_package_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_project_snag__fixed_by", "project_snag", "app_user", ["fixed_by"], ["id"], ondelete="RESTRICT"
    )
    op.create_check_constraint(
        "ck_project_snag__source", "project_snag", "source IN ('STAFF', 'QUALITY_CHECK', 'CUSTOMER')"
    )
    op.create_check_constraint("ck_project_snag__priority", "project_snag", "priority IN ('HIGH', 'NORMAL', 'LOW')")
    op.create_check_constraint(
        "ck_project_snag__closure_code",
        "project_snag",
        "closure_code IS NULL OR closure_code IN ('FIXED', 'DUPLICATE', 'NOT_A_DEFECT', 'RAISED_IN_ERROR')",
    )
    op.create_check_constraint("ck_project_snag__fixed", "project_snag", "(fixed_on IS NULL) = (fixed_by IS NULL)")
    op.add_column("project_qc_check", sa.Column("qc_point_id", GUID(), nullable=True))
    op.add_column("project_qc_check", sa.Column("work_package_id", GUID(), nullable=True))
    op.create_foreign_key(
        "fk_project_qc_check__qc_point_id",
        "project_qc_check",
        "project_qc_point",
        ["qc_point_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_project_qc_check__work_package_id",
        "project_qc_check",
        "project_work_package",
        ["work_package_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column("project_blocker", sa.Column("related_work_package_id", GUID(), nullable=True))
    op.add_column("project_blocker", sa.Column("customer_summary", sa.String(300), nullable=True))
    op.create_foreign_key(
        "fk_project_blocker__related_work_package_id",
        "project_blocker",
        "project_work_package",
        ["related_work_package_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column("project_transition", sa.Column("handover_package_id", GUID(), nullable=True))
    op.add_column("project_transition", sa.Column("handover_package_sha256", sa.String(64), nullable=True))
    op.create_foreign_key(
        "fk_project_transition__handover_package_id",
        "project_transition",
        "project_handover_package",
        ["handover_package_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_project_transition__package_handover_only",
        "project_transition",
        "kind = 'HANDOVER' OR (handover_package_id IS NULL AND handover_package_sha256 IS NULL)",
    )
    op.create_check_constraint(
        "ck_project_transition__package_pair",
        "project_transition",
        "(handover_package_id IS NULL) = (handover_package_sha256 IS NULL)",
    )
    op.create_check_constraint(
        "ck_project_transition__handover_package_sha256_len",
        "project_transition",
        "handover_package_sha256 IS NULL OR length(handover_package_sha256) = 64",
    )


def _columns_sqlite() -> None:
    for statement in SQLITE:
        op.execute(statement)


def _refuse_double_rechecks(bind) -> None:
    rows = bind.exec_driver_sql(
        "SELECT recheck_of_id FROM project_qc_check WHERE recheck_of_id IS NOT NULL AND is_deleted = "
        + ("false" if bind.dialect.name == "postgresql" else "0")
        + " GROUP BY recheck_of_id HAVING count(*) > 1"
    ).all()
    if rows:
        raise RuntimeError(
            f"{len(rows)} quality check(s) were rechecked more than once; one recheck per check cannot be enforced. "
            "Nothing changed: review those checks with the quality owner before running the migration again."
        )


def _widen_event_codes(bind) -> None:
    if bind.dialect.name == "postgresql":
        op.drop_constraint("ck_project_event__event_code", "project_event", type_="check")
        op.create_check_constraint("ck_project_event__event_code", "project_event", NEW_EVENTS)
        return
    stored = bind.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'project_event'"
    ).scalar()
    if stored.count(OLD_EVENTS) != 1:
        raise RuntimeError("project_event's event-code CHECK is not the 0208 definition; refusing to change it")
    version = int(bind.exec_driver_sql("PRAGMA schema_version").scalar())
    bind.exec_driver_sql("PRAGMA writable_schema = ON")
    try:
        bind.exec_driver_sql(
            "UPDATE sqlite_master SET sql = ? WHERE type = 'table' AND name = 'project_event'",
            (stored.replace(OLD_EVENTS, NEW_EVENTS),),
        )
        bind.exec_driver_sql(f"PRAGMA schema_version = {version + 1}")
    finally:
        bind.exec_driver_sql("PRAGMA writable_schema = OFF")
    result = bind.exec_driver_sql("PRAGMA integrity_check").scalar()
    if result != "ok":
        raise RuntimeError(f"integrity check failed after widening the event-code CHECK: {result}")


def upgrade() -> None:
    bind = op.get_bind()
    _refuse_double_rechecks(bind)
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "project_work_package",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("package_no", sa.Integer(), nullable=False),
        sa.Column("stage_code", sa.String(24), nullable=False),
        sa.Column("space_id", GUID(), nullable=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("customer_label", sa.String(120), nullable=True),
        sa.Column("customer_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner_user_id", GUID(), nullable=True),
        sa.Column("depends_on_id", GUID(), nullable=True),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("planned_start", sa.Date(), nullable=True),
        sa.Column("planned_finish", sa.Date(), nullable=True),
        sa.Column("plan_revision", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("replan_reason", sa.String(1000), nullable=True),
        sa.Column("actual_start", sa.Date(), nullable=True),
        sa.Column("actual_finish", sa.Date(), nullable=True),
        sa.Column("started_by", GUID(), nullable=True),
        sa.Column("completed_by", GUID(), nullable=True),
        sa.Column("completion_note", sa.String(1000), nullable=True),
        sa.Column("reopen_reason", sa.String(1000), nullable=True),
        sa.Column("cancel_reason", sa.String(1000), nullable=True),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("evidence_attachment_id", GUID(), nullable=True),
        sa.Column("evidence_reference", sa.String(200), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_project_work_package"),
        sa.ForeignKeyConstraint(
            ["completed_by"], ["app_user.id"], name="fk_project_work_package__completed_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_project_work_package__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_project_work_package__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["depends_on_id"],
            ["project_work_package.id"],
            name="fk_project_work_package__depends_on_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_attachment_id"],
            ["attachment.id"],
            name="fk_project_work_package__evidence_attachment_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_project_work_package__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["app_user.id"], name="fk_project_work_package__owner_user_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_project_work_package__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["space_id"], ["property_space.id"], name="fk_project_work_package__space_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["started_by"], ["app_user.id"], name="fk_project_work_package__started_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_project_work_package__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "actual_finish IS NULL OR actual_finish >= actual_start", name="ck_project_work_package__actual_order"
        ),
        sa.CheckConstraint("length(cancel_reason) <= 1000", name="ck_project_work_package__cancel_reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(status = 'CANCELLED') = (cancel_reason IS NOT NULL)", name="ck_project_work_package__cancelled"
        ),
        sa.CheckConstraint(
            "(status = 'COMPLETED') = (actual_finish IS NOT NULL AND completed_by IS NOT NULL)",
            name="ck_project_work_package__completed",
        ),
        sa.CheckConstraint(
            "completed_by IS NULL OR (length(completed_by) = 32 AND completed_by NOT GLOB '*[^0-9a-f]*' AND substr(completed_by, 13, 1) = '7' AND substr(completed_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_work_package__completed_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(completion_note) <= 1000", name="ck_project_work_package__completion_note_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_work_package__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "customer_visible = false OR customer_label IS NOT NULL", name="ck_project_work_package__customer_label"
        ),
        sa.CheckConstraint("length(customer_label) <= 120", name="ck_project_work_package__customer_label_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("customer_visible IN (0, 1)", name="ck_project_work_package__customer_visible_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_work_package__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "depends_on_id IS NULL OR (length(depends_on_id) = 32 AND depends_on_id NOT GLOB '*[^0-9a-f]*' AND substr(depends_on_id, 13, 1) = '7' AND substr(depends_on_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_work_package__depends_on_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(description) <= 2000", name="ck_project_work_package__description_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "evidence_attachment_id IS NULL OR (length(evidence_attachment_id) = 32 AND evidence_attachment_id NOT GLOB '*[^0-9a-f]*' AND substr(evidence_attachment_id, 13, 1) = '7' AND substr(evidence_attachment_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_work_package__evidence_attachment_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(evidence_reference) <= 200", name="ck_project_work_package__evidence_reference_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_work_package__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_project_work_package__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_work_package__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("depends_on_id IS NULL OR depends_on_id <> id", name="ck_project_work_package__not_self"),
        sa.CheckConstraint(
            "owner_user_id IS NULL OR (length(owner_user_id) = 32 AND owner_user_id NOT GLOB '*[^0-9a-f]*' AND substr(owner_user_id, 13, 1) = '7' AND substr(owner_user_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_work_package__owner_user_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("package_no >= 1", name="ck_project_work_package__package_no"),
        sa.CheckConstraint(
            "planned_start IS NULL OR planned_finish IS NULL OR planned_finish >= planned_start",
            name="ck_project_work_package__planned_order",
        ),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_work_package__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(reopen_reason) <= 1000", name="ck_project_work_package__reopen_reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(replan_reason) <= 1000", name="ck_project_work_package__replan_reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_project_work_package__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "space_id IS NULL OR (length(space_id) = 32 AND space_id NOT GLOB '*[^0-9a-f]*' AND substr(space_id, 13, 1) = '7' AND substr(space_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_work_package__space_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "stage_code IN ('BOOKED', 'DESIGN_FINALISATION', 'SCOPE_FROZEN', 'SITE_READINESS', 'PRODUCTION_READINESS', 'IN_PRODUCTION', 'READY_FOR_INSTALLATION', 'INSTALLATION', 'QUALITY_CHECK', 'SNAGGING', 'READY_FOR_HANDOVER', 'HANDED_OVER')",
            name="ck_project_work_package__stage_code",
        ),
        sa.CheckConstraint("length(stage_code) <= 24", name="ck_project_work_package__stage_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "status NOT IN ('IN_PROGRESS', 'COMPLETED') OR (actual_start IS NOT NULL AND started_by IS NOT NULL)",
            name="ck_project_work_package__started",
        ),
        sa.CheckConstraint(
            "started_by IS NULL OR (length(started_by) = 32 AND started_by NOT GLOB '*[^0-9a-f]*' AND substr(started_by, 13, 1) = '7' AND substr(started_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_work_package__started_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status IN ('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')", name="ck_project_work_package__status"
        ),
        sa.CheckConstraint("length(status) <= 12", name="ck_project_work_package__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(title) <= 160", name="ck_project_work_package__title_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_project_work_package__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_work_package__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_project_work_package__version_positive"),
    )
    op.create_index("ix_project_work_package__completed_by", "project_work_package", ["completed_by"])
    op.create_index("ix_project_work_package__depends_on", "project_work_package", ["depends_on_id"])
    op.create_index("ix_project_work_package__evidence", "project_work_package", ["evidence_attachment_id"])
    op.create_index("ix_project_work_package__lead_id", "project_work_package", ["lead_id"])
    op.create_index("ix_project_work_package__owner", "project_work_package", ["owner_user_id"])
    op.create_index("ix_project_work_package__project", "project_work_package", ["project_id", "stage_code"])
    op.create_index("ix_project_work_package__space_id", "project_work_package", ["space_id"])
    op.create_index("ix_project_work_package__started_by", "project_work_package", ["started_by"])
    op.create_index(
        "ux_project_work_package__number",
        "project_work_package",
        ["project_id", "package_no"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "project_qc_point",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("point_no", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(28), nullable=False),
        sa.Column("space_id", GUID(), nullable=True),
        sa.Column("work_package_id", GUID(), nullable=True),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("evidence_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("withdrawn_reason", sa.String(1000), nullable=True),
        sa.Column("withdrawn_by", GUID(), nullable=True),
        sa.Column("withdrawn_on", UTCDateTime(), nullable=True),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_project_qc_point"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_project_qc_point__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_project_qc_point__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_project_qc_point__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_project_qc_point__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["space_id"], ["property_space.id"], name="fk_project_qc_point__space_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_project_qc_point__updated_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["withdrawn_by"], ["app_user.id"], name="fk_project_qc_point__withdrawn_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["work_package_id"],
            ["project_work_package.id"],
            name="fk_project_qc_point__work_package_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "category IN ('DIMENSIONS_AND_ALIGNMENT', 'FINISH_AND_SURFACES', 'HARDWARE_AND_OPERATION', 'SERVICES_FITMENT', 'CLEANLINESS_AND_PROTECTION', 'OTHER')",
            name="ck_project_qc_point__category",
        ),
        sa.CheckConstraint("length(category) <= 28", name="ck_project_qc_point__category_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_qc_point__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_qc_point__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("evidence_required IN (0, 1)", name="ck_project_qc_point__evidence_required_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_qc_point__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_project_qc_point__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(label) <= 160", name="ck_project_qc_point__label_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_qc_point__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("point_no >= 1", name="ck_project_qc_point__point_no"),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_qc_point__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_project_qc_point__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "space_id IS NULL OR (length(space_id) = 32 AND space_id NOT GLOB '*[^0-9a-f]*' AND substr(space_id, 13, 1) = '7' AND substr(space_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_qc_point__space_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("status IN ('ACTIVE', 'WITHDRAWN')", name="ck_project_qc_point__status"),
        sa.CheckConstraint("length(status) <= 12", name="ck_project_qc_point__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_project_qc_point__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_qc_point__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_project_qc_point__version_positive"),
        sa.CheckConstraint(
            "(status = 'WITHDRAWN') = (withdrawn_reason IS NOT NULL AND withdrawn_by IS NOT NULL AND withdrawn_on IS NOT NULL)",
            name="ck_project_qc_point__withdrawn",
        ),
        sa.CheckConstraint(
            "withdrawn_by IS NULL OR (length(withdrawn_by) = 32 AND withdrawn_by NOT GLOB '*[^0-9a-f]*' AND substr(withdrawn_by, 13, 1) = '7' AND substr(withdrawn_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_qc_point__withdrawn_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(withdrawn_reason) <= 1000", name="ck_project_qc_point__withdrawn_reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "work_package_id IS NULL OR (length(work_package_id) = 32 AND work_package_id NOT GLOB '*[^0-9a-f]*' AND substr(work_package_id, 13, 1) = '7' AND substr(work_package_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_qc_point__work_package_id_format",
        ).ddl_if(dialect="sqlite"),
    )
    op.create_index("ix_project_qc_point__lead_id", "project_qc_point", ["lead_id"])
    op.create_index("ix_project_qc_point__space_id", "project_qc_point", ["space_id"])
    op.create_index("ix_project_qc_point__withdrawn_by", "project_qc_point", ["withdrawn_by"])
    op.create_index("ix_project_qc_point__work_package", "project_qc_point", ["work_package_id"])
    op.create_index(
        "ux_project_qc_point__number",
        "project_qc_point",
        ["project_id", "point_no"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "project_customer_report",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("report_no", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(8), nullable=False),
        sa.Column("account_id", GUID(), nullable=True),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("area", sa.String(120), nullable=True),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("client_key_sha256", sa.String(64), nullable=True),
        sa.Column("request_sha256", sa.String(64), nullable=True),
        sa.Column("triaged_by", GUID(), nullable=True),
        sa.Column("triaged_on", UTCDateTime(), nullable=True),
        sa.Column("snag_id", GUID(), nullable=True),
        sa.Column("decline_code", sa.String(16), nullable=True),
        sa.Column("response", sa.String(500), nullable=True),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_project_customer_report"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["portal_account.id"], name="fk_project_customer_report__account_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_project_customer_report__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_project_customer_report__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["lead.id"], name="fk_project_customer_report__lead_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_project_customer_report__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["snag_id"], ["project_snag.id"], name="fk_project_customer_report__snag_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["triaged_by"], ["app_user.id"], name="fk_project_customer_report__triaged_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_project_customer_report__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "(channel = 'PORTAL') = (account_id IS NOT NULL)", name="ck_project_customer_report__account"
        ),
        sa.CheckConstraint(
            "account_id IS NULL OR (length(account_id) = 32 AND account_id NOT GLOB '*[^0-9a-f]*' AND substr(account_id, 13, 1) = '7' AND substr(account_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_customer_report__account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(area) <= 120", name="ck_project_customer_report__area_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("channel IN ('PORTAL', 'STAFF')", name="ck_project_customer_report__channel"),
        sa.CheckConstraint("length(channel) <= 8", name="ck_project_customer_report__channel_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "client_key_sha256 IS NULL OR length(client_key_sha256) = 64",
            name="ck_project_customer_report__client_key_sha256_len",
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_customer_report__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "decline_code IS NULL OR decline_code IN ('DUPLICATE', 'NOT_A_DEFECT', 'NOT_IN_SCOPE')",
            name="ck_project_customer_report__decline_code",
        ),
        sa.CheckConstraint("length(decline_code) <= 16", name="ck_project_customer_report__decline_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(status = 'DECLINED') = (decline_code IS NOT NULL) AND (status <> 'DECLINED' OR response IS NOT NULL)",
            name="ck_project_customer_report__declined",
        ),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_customer_report__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(description) <= 2000", name="ck_project_customer_report__description_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_customer_report__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_project_customer_report__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(client_key_sha256 IS NULL) = (request_sha256 IS NULL)", name="ck_project_customer_report__key_pair"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_customer_report__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_customer_report__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("report_no >= 1", name="ck_project_customer_report__report_no"),
        sa.CheckConstraint(
            "request_sha256 IS NULL OR length(request_sha256) = 64",
            name="ck_project_customer_report__request_sha256_len",
        ),
        sa.CheckConstraint("length(response) <= 500", name="ck_project_customer_report__response_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("(status = 'ACCEPTED') = (snag_id IS NOT NULL)", name="ck_project_customer_report__snag"),
        sa.CheckConstraint(
            "snag_id IS NULL OR (length(snag_id) = 32 AND snag_id NOT GLOB '*[^0-9a-f]*' AND substr(snag_id, 13, 1) = '7' AND substr(snag_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_customer_report__snag_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_project_customer_report__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "status IN ('SUBMITTED', 'ACCEPTED', 'DECLINED')", name="ck_project_customer_report__status"
        ),
        sa.CheckConstraint("length(status) <= 12", name="ck_project_customer_report__status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(status = 'SUBMITTED') = (triaged_on IS NULL) AND (triaged_on IS NULL) = (triaged_by IS NULL)",
            name="ck_project_customer_report__triaged",
        ),
        sa.CheckConstraint(
            "triaged_by IS NULL OR (length(triaged_by) = 32 AND triaged_by NOT GLOB '*[^0-9a-f]*' AND substr(triaged_by, 13, 1) = '7' AND substr(triaged_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_customer_report__triaged_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_project_customer_report__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_customer_report__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_project_customer_report__version_positive"),
    )
    op.create_index("ix_project_customer_report__lead_id", "project_customer_report", ["lead_id"])
    op.create_index("ix_project_customer_report__project", "project_customer_report", ["project_id", "status"])
    op.create_index("ix_project_customer_report__snag", "project_customer_report", ["snag_id"])
    op.create_index("ix_project_customer_report__triaged_by", "project_customer_report", ["triaged_by"])
    op.create_index(
        "ux_project_customer_report__client_key",
        "project_customer_report",
        ["account_id", "client_key_sha256"],
        unique=True,
        sqlite_where=sa.text("client_key_sha256 IS NOT NULL AND is_deleted = 0"),
        postgresql_where=sa.text("client_key_sha256 IS NOT NULL AND is_deleted = false"),
    )
    op.create_index(
        "ux_project_customer_report__number",
        "project_customer_report",
        ["project_id", "report_no"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "project_handover_package",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("package_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("content", JSONType(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("redacted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("redacted_sha256", sa.String(64), nullable=True),
        sa.Column("superseded_on", UTCDateTime(), nullable=True),
        sa.Column("superseded_by", GUID(), nullable=True),
        sa.Column("acknowledged_on", UTCDateTime(), nullable=True),
        sa.Column("acknowledged_account_id", GUID(), nullable=True),
        sa.Column("completed_on", UTCDateTime(), nullable=True),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_project_handover_package"),
        sa.ForeignKeyConstraint(
            ["acknowledged_account_id"],
            ["portal_account.id"],
            name="fk_project_handover_package__acknowledged_account_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_project_handover_package__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_project_handover_package__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["lead.id"], name="fk_project_handover_package__lead_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_project_handover_package__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by"], ["app_user.id"], name="fk_project_handover_package__superseded_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_project_handover_package__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "(acknowledged_on IS NULL) = (acknowledged_account_id IS NULL)",
            name="ck_project_handover_package__acknowledged",
        ),
        sa.CheckConstraint(
            "acknowledged_account_id IS NULL OR (length(acknowledged_account_id) = 32 AND acknowledged_account_id NOT GLOB '*[^0-9a-f]*' AND substr(acknowledged_account_id, 13, 1) = '7' AND substr(acknowledged_account_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_handover_package__acknowledged_account_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(status = 'COMPLETED') = (completed_on IS NOT NULL)", name="ck_project_handover_package__completed"
        ),
        sa.CheckConstraint(
            "content IS NULL OR json_valid(content)", name="ck_project_handover_package__content_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(content_sha256) = 64", name="ck_project_handover_package__content_sha256_len"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_handover_package__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_handover_package__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_handover_package__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_project_handover_package__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_handover_package__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("package_no >= 1", name="ck_project_handover_package__package_no"),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_handover_package__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("redacted = (redacted_sha256 IS NOT NULL)", name="ck_project_handover_package__redacted"),
        sa.CheckConstraint("redacted IN (0, 1)", name="ck_project_handover_package__redacted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "redacted_sha256 IS NULL OR length(redacted_sha256) = 64",
            name="ck_project_handover_package__redacted_sha256_len",
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_project_handover_package__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "status IN ('PREPARED', 'SUPERSEDED', 'COMPLETED')", name="ck_project_handover_package__status"
        ),
        sa.CheckConstraint("length(status) <= 12", name="ck_project_handover_package__status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(status = 'SUPERSEDED') = (superseded_on IS NOT NULL AND superseded_by IS NOT NULL)",
            name="ck_project_handover_package__superseded",
        ),
        sa.CheckConstraint(
            "superseded_by IS NULL OR (length(superseded_by) = 32 AND superseded_by NOT GLOB '*[^0-9a-f]*' AND substr(superseded_by, 13, 1) = '7' AND substr(superseded_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_handover_package__superseded_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_project_handover_package__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_handover_package__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_project_handover_package__version_positive"),
    )
    op.create_index("ix_project_handover_package__account", "project_handover_package", ["acknowledged_account_id"])
    op.create_index("ix_project_handover_package__lead_id", "project_handover_package", ["lead_id"])
    op.create_index("ix_project_handover_package__superseded_by", "project_handover_package", ["superseded_by"])
    op.create_index(
        "ux_project_handover_package__number",
        "project_handover_package",
        ["project_id", "package_no"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_project_handover_package__one_current",
        "project_handover_package",
        ["project_id"],
        unique=True,
        sqlite_where=sa.text("status = 'PREPARED' AND is_deleted = 0"),
        postgresql_where=sa.text("status = 'PREPARED' AND is_deleted = false"),
    )
    # --- end generated DDL ---
    if bind.dialect.name == "postgresql":
        _columns_postgresql()
    else:
        _columns_sqlite()
    op.create_index("ix_project_snag__fixed_by", "project_snag", ["fixed_by"])
    op.create_index("ix_project_snag__resolution_evidence", "project_snag", ["resolution_evidence_attachment_id"])
    op.create_index("ix_project_snag__work_package", "project_snag", ["work_package_id"])
    op.create_index("ix_project_qc_check__point", "project_qc_check", ["qc_point_id"])
    op.create_index("ix_project_qc_check__work_package", "project_qc_check", ["work_package_id"])
    op.create_index("ix_project_blocker__work_package", "project_blocker", ["related_work_package_id"])
    op.create_index("ix_project_transition__package", "project_transition", ["handover_package_id"])
    op.create_index(
        "ux_project_qc_check__one_recheck",
        "project_qc_check",
        ["recheck_of_id"],
        unique=True,
        sqlite_where=sa.text("recheck_of_id IS NOT NULL AND is_deleted = 0"),
        postgresql_where=sa.text("recheck_of_id IS NOT NULL AND is_deleted = false"),
    )
    _widen_event_codes(bind)
    ms.sync_permissions(bind, audit=True)
    ms.grant_new_codes(bind, CODES, audit=True)
    ms.assert_rbac_seed(bind)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
