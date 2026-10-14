"""0205_customer_proposal: the Customer Quotation Experience (CQX; decision log 35).

Tables (each references one quotation version; none copies frozen quotation content):

- ``proposal_access_grant``: a secure link to one issued version for one recipient kind (token SHA-256 only).
- ``proposal_event``: the proposal's own append-only log (shared, viewed, choices, requests, decisions, revocations).
- ``customer_optional_selection``: the customer's current choice per optional line (a proposal, never a quotation edit).
- ``customer_proposal_request``: questions and structured change requests, with the staff response and the revision or
  variation that answered them.
- ``quotation_acknowledgement``: a recipient's acknowledgement of one frozen section, bound to its digest.
- ``quotation_acceptance_evidence``: the evidence of a customer's digital decision on one version.

The staff permission codes for the existing roles. And one widening of an existing constraint: ``quotation``'s
``ck_quotation__decision_method`` admits ``CUSTOMER_DIGITAL`` (a decision the customer made through their link). Every
existing row satisfies the wider check. PostgreSQL drops and re-adds the constraint; SQLite cannot alter a CHECK in place,
and rebuilding ``quotation`` (referenced by four tables, with foreign keys enforced) is the riskier path, so the table's
stored definition is updated by SQLite's documented procedure for loosening a CHECK constraint (writable_schema, then
schema_version incremented, then an integrity check), which rewrites no row.

Numbered 0205: 0201–0203 were reserved for B2–B4 (0203 stays free) and 0204 is taken (MTQ self-service).
Expand-only; inert while VEDA_CUSTOMER_PROPOSAL_ENABLED is off (the default everywhere; production refuses it).

Revision ID: 0205_customer_proposal
Revises: 0202_mtq_commercial
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0205_customer_proposal"
down_revision = "0202_mtq_commercial"
branch_labels = None
depends_on = None

CODES = (
    "proposal.preview",
    "proposal.share",
    "proposal.access.revoke",
    "proposal.request.review",
    "proposal.acceptance.review",
)
OLD_METHODS = "decision_method IS NULL OR decision_method IN ('STAFF_RECORDED', 'SIGNED_COPY')"
NEW_METHODS = "decision_method IS NULL OR decision_method IN ('STAFF_RECORDED', 'SIGNED_COPY', 'CUSTOMER_DIGITAL')"


def _widen_decision_methods(bind) -> None:
    if bind.dialect.name == "postgresql":
        op.drop_constraint("ck_quotation__decision_method", "quotation", type_="check")
        op.create_check_constraint("ck_quotation__decision_method", "quotation", NEW_METHODS)
        return
    stored = bind.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'quotation'").scalar()
    if stored.count(OLD_METHODS) != 1:
        raise RuntimeError("quotation's decision-method CHECK is not the 0202 definition; refusing to change it")
    version = int(bind.exec_driver_sql("PRAGMA schema_version").scalar())
    bind.exec_driver_sql("PRAGMA writable_schema = ON")
    try:
        bind.exec_driver_sql(
            "UPDATE sqlite_master SET sql = ? WHERE type = 'table' AND name = 'quotation'",
            (stored.replace(OLD_METHODS, NEW_METHODS),),
        )
        bind.exec_driver_sql(f"PRAGMA schema_version = {version + 1}")
    finally:
        bind.exec_driver_sql("PRAGMA writable_schema = OFF")
    result = bind.exec_driver_sql("PRAGMA integrity_check").scalar()
    if result != "ok":
        raise RuntimeError(f"integrity check failed after widening the decision-method CHECK: {result}")


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "proposal_access_grant",
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
        sa.Column("quotation_id", GUID(), nullable=False),
        sa.Column("quotation_number", sa.String(24), nullable=False),
        sa.Column("variation_no", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("recipient_kind", sa.String(20), nullable=False),
        sa.Column("recipient_label", sa.String(80), nullable=True),
        sa.Column("token_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("expires_on", UTCDateTime(), nullable=False),
        sa.Column("first_viewed_on", UTCDateTime(), nullable=True),
        sa.Column("last_viewed_on", UTCDateTime(), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revoked_on", UTCDateTime(), nullable=True),
        sa.Column("revoked_by", GUID(), nullable=True),
        sa.Column("revoke_reason_code", sa.String(16), nullable=True),
        sa.Column("replaces_grant_id", GUID(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_proposal_access_grant"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_proposal_access_grant__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_proposal_access_grant__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["lead.id"], name="fk_proposal_access_grant__lead_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["property.id"], name="fk_proposal_access_grant__property_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id"], ["quotation.id"], name="fk_proposal_access_grant__quotation_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["replaces_grant_id"],
            ["proposal_access_grant.id"],
            name="fk_proposal_access_grant__replaces_grant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by"], ["app_user.id"], name="fk_proposal_access_grant__revoked_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_proposal_access_grant__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "status <> 'ACTIVE' OR first_viewed_on IS NOT NULL", name="ck_proposal_access_grant__active"
        ),
        sa.CheckConstraint(
            "view_count >= 0 AND version_no >= 1 AND variation_no >= 0", name="ck_proposal_access_grant__counts"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_proposal_access_grant__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_proposal_access_grant__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_proposal_access_grant__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_proposal_access_grant__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_proposal_access_grant__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "replaces_grant_id IS NULL OR replaces_grant_id <> id", name="ck_proposal_access_grant__not_self"
        ),
        sa.CheckConstraint(
            "length(property_id) = 32 AND property_id NOT GLOB '*[^0-9a-f]*' AND substr(property_id, 13, 1) = '7' AND substr(property_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_proposal_access_grant__property_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(quotation_id) = 32 AND quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(quotation_id, 13, 1) = '7' AND substr(quotation_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_proposal_access_grant__quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(quotation_number) <= 24", name="ck_proposal_access_grant__quotation_number_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "recipient_kind IN ('PRIMARY_CUSTOMER', 'CO_OWNER', 'FAMILY_MEMBER', 'OTHER')",
            name="ck_proposal_access_grant__recipient_kind",
        ),
        sa.CheckConstraint("length(recipient_kind) <= 20", name="ck_proposal_access_grant__recipient_kind_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(recipient_label) <= 80", name="ck_proposal_access_grant__recipient_label_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "replaces_grant_id IS NULL OR (length(replaces_grant_id) = 32 AND replaces_grant_id NOT GLOB '*[^0-9a-f]*' AND substr(replaces_grant_id, 13, 1) = '7' AND substr(replaces_grant_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_proposal_access_grant__replaces_grant_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "revoke_reason_code IS NULL OR revoke_reason_code IN ('STAFF_REVOKED', 'ROTATED', 'SUPERSEDED', 'LEAD_ERASED', 'LEAD_CLOSED')",
            name="ck_proposal_access_grant__revoke_reason_code",
        ),
        sa.CheckConstraint(
            "length(revoke_reason_code) <= 16", name="ck_proposal_access_grant__revoke_reason_code_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(status = 'REVOKED') = (revoked_on IS NOT NULL AND revoke_reason_code IS NOT NULL)",
            name="ck_proposal_access_grant__revoked",
        ),
        sa.CheckConstraint(
            "revoked_by IS NULL OR (length(revoked_by) = 32 AND revoked_by NOT GLOB '*[^0-9a-f]*' AND substr(revoked_by, 13, 1) = '7' AND substr(revoked_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_proposal_access_grant__revoked_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_proposal_access_grant__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "status IN ('CREATED', 'ACTIVE', 'EXPIRED', 'REVOKED')", name="ck_proposal_access_grant__status"
        ),
        sa.CheckConstraint("length(status) <= 10", name="ck_proposal_access_grant__status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(token_sha256) = 64", name="ck_proposal_access_grant__token_len"),
        sa.CheckConstraint("length(token_sha256) <= 64", name="ck_proposal_access_grant__token_sha256_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_proposal_access_grant__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_proposal_access_grant__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_proposal_access_grant__version_positive"),
    )
    op.create_index("ix_proposal_access_grant__lead_id", "proposal_access_grant", ["lead_id"])
    op.create_index("ix_proposal_access_grant__number", "proposal_access_grant", ["quotation_number", "variation_no"])
    op.create_index("ix_proposal_access_grant__property_id", "proposal_access_grant", ["property_id"])
    op.create_index("ix_proposal_access_grant__quotation_id", "proposal_access_grant", ["quotation_id"])
    op.create_index("ix_proposal_access_grant__replaces", "proposal_access_grant", ["replaces_grant_id"])
    op.create_index("ix_proposal_access_grant__status_expires", "proposal_access_grant", ["status", "expires_on"])
    op.create_index(
        "ux_proposal_access_grant__one_live",
        "proposal_access_grant",
        ["quotation_id", "recipient_kind"],
        unique=True,
        sqlite_where=sa.text("status IN ('CREATED', 'ACTIVE') AND is_deleted = 0"),
        postgresql_where=sa.text("status IN ('CREATED', 'ACTIVE') AND is_deleted = false"),
    )
    op.create_index(
        "ux_proposal_access_grant__token",
        "proposal_access_grant",
        ["token_sha256"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "proposal_event",
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
        sa.Column("quotation_id", GUID(), nullable=False),
        sa.Column("grant_id", GUID(), nullable=True),
        sa.Column("event_code", sa.String(24), nullable=False),
        sa.Column("detail", JSONType(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_proposal_event"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_proposal_event__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_proposal_event__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["grant_id"], ["proposal_access_grant.id"], name="fk_proposal_event__grant_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_proposal_event__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["quotation_id"], ["quotation.id"], name="fk_proposal_event__quotation_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_proposal_event__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_proposal_event__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_proposal_event__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("detail IS NULL OR json_valid(detail)", name="ck_proposal_event__detail_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "event_code IN ('SHARED', 'VIEWED', 'ROTATED', 'REVOKED', 'EXPIRED', 'SELECTION_CHANGED', 'QUESTION_SUBMITTED', 'CHANGE_REQUESTED', 'REQUEST_UPDATED', 'REQUEST_LINKED', 'ACKNOWLEDGED', 'ACCEPTED', 'DECLINED', 'ACCEPTANCE_REFUSED', 'ACCESS_REFUSED')",
            name="ck_proposal_event__event_code",
        ),
        sa.CheckConstraint("length(event_code) <= 24", name="ck_proposal_event__event_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "grant_id IS NULL OR (length(grant_id) = 32 AND grant_id NOT GLOB '*[^0-9a-f]*' AND substr(grant_id, 13, 1) = '7' AND substr(grant_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_proposal_event__grant_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_proposal_event__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_proposal_event__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_proposal_event__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(quotation_id) = 32 AND quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(quotation_id, 13, 1) = '7' AND substr(quotation_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_proposal_event__quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_proposal_event__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_proposal_event__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_proposal_event__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_proposal_event__version_positive"),
    )
    op.create_index("ix_proposal_event__grant_id", "proposal_event", ["grant_id"])
    op.create_index("ix_proposal_event__lead_id", "proposal_event", ["lead_id"])
    op.create_index("ix_proposal_event__quotation", "proposal_event", ["quotation_id", "created_on"])

    op.create_table(
        "customer_optional_selection",
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
        sa.Column("quotation_id", GUID(), nullable=False),
        sa.Column("quotation_line_id", GUID(), nullable=False),
        sa.Column("line_ref", sa.String(12), nullable=False),
        sa.Column("line_key", sa.String(200), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("changed_by_grant_id", GUID(), nullable=False),
        sa.Column("change_no", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id", name="pk_customer_optional_selection"),
        sa.ForeignKeyConstraint(
            ["changed_by_grant_id"],
            ["proposal_access_grant.id"],
            name="fk_customer_optional_selection__changed_by_grant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_customer_optional_selection__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_customer_optional_selection__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["lead.id"], name="fk_customer_optional_selection__lead_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id"], ["quotation.id"], name="fk_customer_optional_selection__quotation_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["quotation_line_id"],
            ["quotation_line.id"],
            name="fk_customer_optional_selection__quotation_line_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_customer_optional_selection__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("change_no >= 1", name="ck_customer_optional_selection__change_no"),
        sa.CheckConstraint(
            "length(changed_by_grant_id) = 32 AND changed_by_grant_id NOT GLOB '*[^0-9a-f]*' AND substr(changed_by_grant_id, 13, 1) = '7' AND substr(changed_by_grant_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_optional_selection__changed_by_grant_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_optional_selection__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_customer_optional_selection__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_optional_selection__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_customer_optional_selection__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_optional_selection__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(line_key) <= 200", name="ck_customer_optional_selection__line_key_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(line_ref) <= 12", name="ck_customer_optional_selection__line_ref_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(quotation_id) = 32 AND quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(quotation_id, 13, 1) = '7' AND substr(quotation_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_optional_selection__quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(quotation_line_id) = 32 AND quotation_line_id NOT GLOB '*[^0-9a-f]*' AND substr(quotation_line_id, 13, 1) = '7' AND substr(quotation_line_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_optional_selection__quotation_line_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_customer_optional_selection__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "state IN ('NOT_SELECTED', 'SELECTED', 'DESELECTED', 'REQUESTED_FOR_DISCUSSION')",
            name="ck_customer_optional_selection__state",
        ),
        sa.CheckConstraint("length(state) <= 24", name="ck_customer_optional_selection__state_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_customer_optional_selection__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_optional_selection__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_customer_optional_selection__version_positive"),
    )
    op.create_index("ix_customer_optional_selection__grant_id", "customer_optional_selection", ["changed_by_grant_id"])
    op.create_index("ix_customer_optional_selection__lead_id", "customer_optional_selection", ["lead_id"])
    op.create_index("ix_customer_optional_selection__line_id", "customer_optional_selection", ["quotation_line_id"])
    op.create_index(
        "ux_customer_optional_selection__line",
        "customer_optional_selection",
        ["quotation_id", "quotation_line_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "customer_proposal_request",
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
        sa.Column("quotation_id", GUID(), nullable=False),
        sa.Column("quotation_number", sa.String(24), nullable=False),
        sa.Column("variation_no", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("grant_id", GUID(), nullable=False),
        sa.Column("request_kind", sa.String(16), nullable=False),
        sa.Column("category_code", sa.String(20), nullable=False),
        sa.Column("quotation_line_id", GUID(), nullable=True),
        sa.Column("line_ref", sa.String(12), nullable=True),
        sa.Column("space_id", GUID(), nullable=True),
        sa.Column("room_label", sa.String(120), nullable=True),
        sa.Column("requested_quantity", sa.String(40), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("staff_response", sa.Text(), nullable=True),
        sa.Column("responded_by", GUID(), nullable=True),
        sa.Column("responded_on", UTCDateTime(), nullable=True),
        sa.Column("resulting_quotation_id", GUID(), nullable=True),
        sa.Column("client_key_sha256", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_customer_proposal_request"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_customer_proposal_request__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_customer_proposal_request__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["grant_id"],
            ["proposal_access_grant.id"],
            name="fk_customer_proposal_request__grant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["lead.id"], name="fk_customer_proposal_request__lead_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["property.id"], name="fk_customer_proposal_request__property_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id"], ["quotation.id"], name="fk_customer_proposal_request__quotation_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["quotation_line_id"],
            ["quotation_line.id"],
            name="fk_customer_proposal_request__quotation_line_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["responded_by"], ["app_user.id"], name="fk_customer_proposal_request__responded_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["resulting_quotation_id"],
            ["quotation.id"],
            name="fk_customer_proposal_request__resulting_quotation_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["space_id"], ["property_space.id"], name="fk_customer_proposal_request__space_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_customer_proposal_request__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "category_code IN ('LINE_QUESTION', 'GENERAL_QUESTION', 'ADD_ITEM', 'REMOVE_ITEM', 'CHANGE_QUANTITY', 'CHANGE_MATERIAL', 'CHANGE_FINISH', 'DISCUSS_PRICE')",
            name="ck_customer_proposal_request__category_code",
        ),
        sa.CheckConstraint(
            "length(category_code) <= 20", name="ck_customer_proposal_request__category_code_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "client_key_sha256 IS NULL OR length(client_key_sha256) = 64",
            name="ck_customer_proposal_request__client_key_sha256_len",
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_proposal_request__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_customer_proposal_request__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(grant_id) = 32 AND grant_id NOT GLOB '*[^0-9a-f]*' AND substr(grant_id, 13, 1) = '7' AND substr(grant_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_proposal_request__grant_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_proposal_request__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_customer_proposal_request__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(request_kind = 'QUESTION') = (category_code IN ('LINE_QUESTION', 'GENERAL_QUESTION'))",
            name="ck_customer_proposal_request__kind",
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_proposal_request__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "category_code NOT IN ('LINE_QUESTION', 'REMOVE_ITEM', 'CHANGE_QUANTITY', 'CHANGE_MATERIAL', 'CHANGE_FINISH') OR quotation_line_id IS NOT NULL",
            name="ck_customer_proposal_request__line",
        ),
        sa.CheckConstraint("length(line_ref) <= 12", name="ck_customer_proposal_request__line_ref_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(property_id) = 32 AND property_id NOT GLOB '*[^0-9a-f]*' AND substr(property_id, 13, 1) = '7' AND substr(property_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_proposal_request__property_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(quotation_id) = 32 AND quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(quotation_id, 13, 1) = '7' AND substr(quotation_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_proposal_request__quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "quotation_line_id IS NULL OR (length(quotation_line_id) = 32 AND quotation_line_id NOT GLOB '*[^0-9a-f]*' AND substr(quotation_line_id, 13, 1) = '7' AND substr(quotation_line_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_customer_proposal_request__quotation_line_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(quotation_number) <= 24", name="ck_customer_proposal_request__quotation_number_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "request_kind IN ('QUESTION', 'CHANGE_REQUEST')", name="ck_customer_proposal_request__request_kind"
        ),
        sa.CheckConstraint("length(request_kind) <= 16", name="ck_customer_proposal_request__request_kind_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(requested_quantity) <= 40", name="ck_customer_proposal_request__requested_quantity_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status NOT IN ('DECLINED', 'RESOLVED', 'NEEDS_CLARIFICATION', 'ACCEPTED_FOR_REVISION') OR (responded_by IS NOT NULL AND responded_on IS NOT NULL)",
            name="ck_customer_proposal_request__responded",
        ),
        sa.CheckConstraint(
            "responded_by IS NULL OR (length(responded_by) = 32 AND responded_by NOT GLOB '*[^0-9a-f]*' AND substr(responded_by, 13, 1) = '7' AND substr(responded_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_customer_proposal_request__responded_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "resulting_quotation_id IS NULL OR (length(resulting_quotation_id) = 32 AND resulting_quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(resulting_quotation_id, 13, 1) = '7' AND substr(resulting_quotation_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_customer_proposal_request__resulting_quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(room_label) <= 120", name="ck_customer_proposal_request__room_label_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_customer_proposal_request__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "space_id IS NULL OR (length(space_id) = 32 AND space_id NOT GLOB '*[^0-9a-f]*' AND substr(space_id, 13, 1) = '7' AND substr(space_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_customer_proposal_request__space_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status IN ('OPEN', 'UNDER_REVIEW', 'NEEDS_CLARIFICATION', 'ACCEPTED_FOR_REVISION', 'DECLINED', 'RESOLVED')",
            name="ck_customer_proposal_request__status",
        ),
        sa.CheckConstraint("length(status) <= 24", name="ck_customer_proposal_request__status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_customer_proposal_request__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_proposal_request__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_customer_proposal_request__version_positive"),
    )
    op.create_index("ix_customer_proposal_request__grant_id", "customer_proposal_request", ["grant_id"])
    op.create_index("ix_customer_proposal_request__lead_id", "customer_proposal_request", ["lead_id"])
    op.create_index("ix_customer_proposal_request__line_id", "customer_proposal_request", ["quotation_line_id"])
    op.create_index("ix_customer_proposal_request__property_id", "customer_proposal_request", ["property_id"])
    op.create_index(
        "ix_customer_proposal_request__quotation", "customer_proposal_request", ["quotation_id", "created_on"]
    )
    op.create_index("ix_customer_proposal_request__resulting", "customer_proposal_request", ["resulting_quotation_id"])
    op.create_index("ix_customer_proposal_request__space_id", "customer_proposal_request", ["space_id"])
    op.create_index("ix_customer_proposal_request__status", "customer_proposal_request", ["status"])
    op.create_index(
        "ux_customer_proposal_request__client_key",
        "customer_proposal_request",
        ["grant_id", "client_key_sha256"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "quotation_acknowledgement",
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
        sa.Column("quotation_id", GUID(), nullable=False),
        sa.Column("grant_id", GUID(), nullable=False),
        sa.Column("section_code", sa.String(20), nullable=False),
        sa.Column("section_sha256", sa.String(64), nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_quotation_acknowledgement"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_quotation_acknowledgement__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_quotation_acknowledgement__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["grant_id"],
            ["proposal_access_grant.id"],
            name="fk_quotation_acknowledgement__grant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["lead.id"], name="fk_quotation_acknowledgement__lead_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id"], ["quotation.id"], name="fk_quotation_acknowledgement__quotation_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_quotation_acknowledgement__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_acknowledgement__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_quotation_acknowledgement__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "evidence_sha256 IS NULL OR length(evidence_sha256) = 64",
            name="ck_quotation_acknowledgement__evidence_sha256_len",
        ),
        sa.CheckConstraint(
            "length(grant_id) = 32 AND grant_id NOT GLOB '*[^0-9a-f]*' AND substr(grant_id, 13, 1) = '7' AND substr(grant_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_acknowledgement__grant_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_acknowledgement__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_quotation_acknowledgement__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_acknowledgement__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(quotation_id) = 32 AND quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(quotation_id, 13, 1) = '7' AND substr(quotation_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_acknowledgement__quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "section_code IN ('SCOPE', 'ASSUMPTIONS', 'EXCLUSIONS', 'PAYMENT_MILESTONES', 'WARRANTY', 'SERVICE_SUPPORT', 'TERMS', 'VALIDITY')",
            name="ck_quotation_acknowledgement__section_code",
        ),
        sa.CheckConstraint("length(section_code) <= 20", name="ck_quotation_acknowledgement__section_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "section_sha256 IS NULL OR length(section_sha256) = 64",
            name="ck_quotation_acknowledgement__section_sha256_len",
        ),
        sa.CheckConstraint(
            "snapshot_sha256 IS NULL OR length(snapshot_sha256) = 64",
            name="ck_quotation_acknowledgement__snapshot_sha256_len",
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_quotation_acknowledgement__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_quotation_acknowledgement__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_acknowledgement__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_quotation_acknowledgement__version_positive"),
    )
    op.create_index("ix_quotation_acknowledgement__grant_id", "quotation_acknowledgement", ["grant_id"])
    op.create_index("ix_quotation_acknowledgement__lead_id", "quotation_acknowledgement", ["lead_id"])
    op.create_index(
        "ux_quotation_acknowledgement__section",
        "quotation_acknowledgement",
        ["quotation_id", "grant_id", "section_code"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "quotation_acceptance_evidence",
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
        sa.Column("quotation_id", GUID(), nullable=False),
        sa.Column("quotation_number", sa.String(24), nullable=False),
        sa.Column("variation_no", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("grant_id", GUID(), nullable=False),
        sa.Column("decision", sa.String(10), nullable=False),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("verification_method", sa.String(24), nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("issued_html_sha256", sa.String(64), nullable=False),
        sa.Column("displayed_total_minor", sa.BigInteger(), nullable=True),
        sa.Column("selected_line_refs", JSONType(), nullable=False),
        sa.Column("acknowledgements", JSONType(), nullable=False),
        sa.Column("decided_on", UTCDateTime(), nullable=False),
        sa.Column("request_trace", sa.String(64), nullable=True),
        sa.Column("client_key_sha256", sa.String(64), nullable=False),
        sa.Column("network", JSONType(), nullable=True),
        sa.Column("evidence", JSONType(), nullable=False),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_quotation_acceptance_evidence"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_quotation_acceptance_evidence__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_quotation_acceptance_evidence__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["grant_id"],
            ["proposal_access_grant.id"],
            name="fk_quotation_acceptance_evidence__grant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["lead.id"], name="fk_quotation_acceptance_evidence__lead_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id"],
            ["quotation.id"],
            name="fk_quotation_acceptance_evidence__quotation_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_quotation_acceptance_evidence__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "acknowledgements IS NULL OR json_valid(acknowledgements)",
            name="ck_quotation_acceptance_evidence__acknowledgements_json",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "client_key_sha256 IS NULL OR length(client_key_sha256) = 64",
            name="ck_quotation_acceptance_evidence__client_key_sha256_len",
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_acceptance_evidence__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("decision IN ('ACCEPTED', 'DECLINED')", name="ck_quotation_acceptance_evidence__decision"),
        sa.CheckConstraint("length(decision) <= 10", name="ck_quotation_acceptance_evidence__decision_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_quotation_acceptance_evidence__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "evidence IS NULL OR json_valid(evidence)", name="ck_quotation_acceptance_evidence__evidence_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "evidence_sha256 IS NULL OR length(evidence_sha256) = 64",
            name="ck_quotation_acceptance_evidence__evidence_sha256_len",
        ),
        sa.CheckConstraint(
            "length(grant_id) = 32 AND grant_id NOT GLOB '*[^0-9a-f]*' AND substr(grant_id, 13, 1) = '7' AND substr(grant_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_acceptance_evidence__grant_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_acceptance_evidence__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_quotation_acceptance_evidence__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "issued_html_sha256 IS NULL OR length(issued_html_sha256) = 64",
            name="ck_quotation_acceptance_evidence__issued_html_sha256_len",
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_acceptance_evidence__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("method = 'CUSTOMER_DIGITAL'", name="ck_quotation_acceptance_evidence__method"),
        sa.CheckConstraint("length(method) <= 16", name="ck_quotation_acceptance_evidence__method_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "network IS NULL OR json_valid(network)", name="ck_quotation_acceptance_evidence__network_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(quotation_id) = 32 AND quotation_id NOT GLOB '*[^0-9a-f]*' AND substr(quotation_id, 13, 1) = '7' AND substr(quotation_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_acceptance_evidence__quotation_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(quotation_number) <= 24", name="ck_quotation_acceptance_evidence__quotation_number_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(request_trace) <= 64", name="ck_quotation_acceptance_evidence__request_trace_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "selected_line_refs IS NULL OR json_valid(selected_line_refs)",
            name="ck_quotation_acceptance_evidence__selected_line_refs_json",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "snapshot_sha256 IS NULL OR length(snapshot_sha256) = 64",
            name="ck_quotation_acceptance_evidence__snapshot_sha256_len",
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_quotation_acceptance_evidence__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_quotation_acceptance_evidence__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_quotation_acceptance_evidence__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(verification_method) <= 24", name="ck_quotation_acceptance_evidence__verification_method_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_quotation_acceptance_evidence__version_positive"),
    )
    op.create_index("ix_quotation_acceptance_evidence__grant_id", "quotation_acceptance_evidence", ["grant_id"])
    op.create_index("ix_quotation_acceptance_evidence__lead_id", "quotation_acceptance_evidence", ["lead_id"])
    op.create_index(
        "ux_quotation_acceptance_evidence__quotation",
        "quotation_acceptance_evidence",
        ["quotation_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    # --- end generated DDL ---
    bind = op.get_bind()
    _widen_decision_methods(bind)
    ms.sync_permissions(bind, audit=True)
    ms.grant_new_codes(bind, CODES, audit=True)
    ms.assert_rbac_seed(bind)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
