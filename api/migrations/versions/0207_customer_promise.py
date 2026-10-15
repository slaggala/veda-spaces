"""0207_customer_promise: Customer Promise administration (decision log 37; OI-MTQ-18 governed source).

Tables:

- ``customer_promise_pack``: the versions of the Customer Promise Pack (authoring content, workflow people and dates,
  the frozen customer content and digest of a published version). One PUBLISHED and at most one open version at a time
  (partial unique indexes). Never deleted: an unwanted draft is DISCARDED, a replaced version SUPERSEDED.
- ``customer_promise_review``: per-section review decisions, bound to the section digest (append-only).
- ``customer_promise_event``: the pack's append-only history.

The thirteen ``customer_promise.*`` permission codes and their default grants (FOUNDER: all; SALES_MANAGER: the
commercial author and ordinary reviewer; ADMIN: view). No business content is seeded: the first version is an empty
draft a person starts. Expand-only; inert while VEDA_CUSTOMER_PROMISE_ADMIN_ENABLED is off (the default everywhere;
production refuses it), and quotations read a published pack only once OI-MTQ-18 names this portal as its source.

Numbered 0207: 0206 is the head (customer completeness); 0203 stays reserved.

Revision ID: 0207_customer_promise
Revises: 0206_customer_completeness
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0207_customer_promise"
down_revision = "0206_customer_completeness"
branch_labels = None
depends_on = None

CODES = (
    "customer_promise.view",
    "customer_promise.draft.create",
    "customer_promise.edit",
    "customer_promise.contacts.edit",
    "customer_promise.warranty.edit",
    "customer_promise.payment_safety.edit",
    "customer_promise.submit",
    "customer_promise.review",
    "customer_promise.review.sensitive",
    "customer_promise.approve",
    "customer_promise.publish",
    "customer_promise.preview",
    "customer_promise.audit.read",
)


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "customer_promise_pack",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("origin", sa.String(10), nullable=False),
        sa.Column("based_on_pack_id", GUID(), nullable=True),
        sa.Column("change_summary", sa.String(500), nullable=True),
        sa.Column("content", JSONType(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("contributors", JSONType(), nullable=False),
        sa.Column("review_round", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submitted_by", GUID(), nullable=True),
        sa.Column("submitted_on", UTCDateTime(), nullable=True),
        sa.Column("approved_by", GUID(), nullable=True),
        sa.Column("approved_on", UTCDateTime(), nullable=True),
        sa.Column("approved_sha256", sa.String(64), nullable=True),
        sa.Column("published_by", GUID(), nullable=True),
        sa.Column("published_on", UTCDateTime(), nullable=True),
        sa.Column("published_content", JSONType(), nullable=True),
        sa.Column("published_sha256", sa.String(64), nullable=True),
        sa.Column("superseded_by_pack_id", GUID(), nullable=True),
        sa.Column("superseded_on", UTCDateTime(), nullable=True),
        sa.Column("discarded_on", UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_customer_promise_pack"),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["app_user.id"], name="fk_customer_promise_pack__approved_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["based_on_pack_id"],
            ["customer_promise_pack.id"],
            name="fk_customer_promise_pack__based_on_pack_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_customer_promise_pack__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_customer_promise_pack__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["published_by"], ["app_user.id"], name="fk_customer_promise_pack__published_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by"], ["app_user.id"], name="fk_customer_promise_pack__submitted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by_pack_id"],
            ["customer_promise_pack.id"],
            name="fk_customer_promise_pack__superseded_by_pack_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_customer_promise_pack__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "approved_by IS NULL OR (length(approved_by) = 32 AND approved_by NOT GLOB '*[^0-9a-f]*' AND substr(approved_by, 13, 1) = '7' AND substr(approved_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_customer_promise_pack__approved_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "approved_sha256 IS NULL OR length(approved_sha256) = 64",
            name="ck_customer_promise_pack__approved_sha256_len",
        ),
        sa.CheckConstraint(
            "based_on_pack_id IS NULL OR (length(based_on_pack_id) = 32 AND based_on_pack_id NOT GLOB '*[^0-9a-f]*' AND substr(based_on_pack_id, 13, 1) = '7' AND substr(based_on_pack_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_customer_promise_pack__based_on_pack_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(change_summary) <= 500", name="ck_customer_promise_pack__change_summary_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "content IS NULL OR json_valid(content)", name="ck_customer_promise_pack__content_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(content_sha256) = 64", name="ck_customer_promise_pack__content_sha256_len"),
        sa.CheckConstraint(
            "contributors IS NULL OR json_valid(contributors)", name="ck_customer_promise_pack__contributors_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_promise_pack__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_customer_promise_pack__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_promise_pack__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_customer_promise_pack__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("origin IN ('NEW', 'REVISION', 'ROLLBACK')", name="ck_customer_promise_pack__origin"),
        sa.CheckConstraint("length(origin) <= 10", name="ck_customer_promise_pack__origin_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "published_by IS NULL OR (length(published_by) = 32 AND published_by NOT GLOB '*[^0-9a-f]*' AND substr(published_by, 13, 1) = '7' AND substr(published_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_customer_promise_pack__published_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status NOT IN ('PUBLISHED', 'SUPERSEDED') OR (published_on IS NOT NULL AND published_by IS NOT NULL AND published_content IS NOT NULL AND published_sha256 IS NOT NULL)",
            name="ck_customer_promise_pack__published_complete",
        ),
        sa.CheckConstraint(
            "published_content IS NULL OR json_valid(published_content)",
            name="ck_customer_promise_pack__published_content_json",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "published_sha256 IS NULL OR length(published_sha256) = 64",
            name="ck_customer_promise_pack__published_sha256_len",
        ),
        sa.CheckConstraint("review_round >= 0", name="ck_customer_promise_pack__review_round"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_customer_promise_pack__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'IN_REVIEW', 'APPROVED', 'PUBLISHED', 'SUPERSEDED', 'DISCARDED')",
            name="ck_customer_promise_pack__status",
        ),
        sa.CheckConstraint("length(status) <= 12", name="ck_customer_promise_pack__status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "submitted_by IS NULL OR (length(submitted_by) = 32 AND submitted_by NOT GLOB '*[^0-9a-f]*' AND substr(submitted_by, 13, 1) = '7' AND substr(submitted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_customer_promise_pack__submitted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "superseded_by_pack_id IS NULL OR (length(superseded_by_pack_id) = 32 AND superseded_by_pack_id NOT GLOB '*[^0-9a-f]*' AND substr(superseded_by_pack_id, 13, 1) = '7' AND substr(superseded_by_pack_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_customer_promise_pack__superseded_by_pack_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "status <> 'SUPERSEDED' OR superseded_on IS NOT NULL", name="ck_customer_promise_pack__superseded_complete"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_customer_promise_pack__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_promise_pack__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version_no >= 1", name="ck_customer_promise_pack__version_no"),
        sa.CheckConstraint("version >= 1", name="ck_customer_promise_pack__version_positive"),
    )
    op.create_index(
        "ux_customer_promise_pack__one_open",
        "customer_promise_pack",
        ["is_deleted"],
        unique=True,
        sqlite_where=sa.text("status IN ('DRAFT', 'IN_REVIEW', 'APPROVED') AND is_deleted = 0"),
        postgresql_where=sa.text("status IN ('DRAFT', 'IN_REVIEW', 'APPROVED') AND is_deleted = false"),
    )
    op.create_index(
        "ux_customer_promise_pack__one_published",
        "customer_promise_pack",
        ["status"],
        unique=True,
        sqlite_where=sa.text("status = 'PUBLISHED' AND is_deleted = 0"),
        postgresql_where=sa.text("status = 'PUBLISHED' AND is_deleted = false"),
    )
    op.create_index(
        "ux_customer_promise_pack__version_no",
        "customer_promise_pack",
        ["version_no"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "customer_promise_review",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("pack_id", GUID(), nullable=False),
        sa.Column("review_round", sa.Integer(), nullable=False),
        sa.Column("section_code", sa.String(20), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("section_sha256", sa.String(64), nullable=False),
        sa.Column("comment", sa.String(1000), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_customer_promise_review"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_customer_promise_review__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_customer_promise_review__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["pack_id"], ["customer_promise_pack.id"], name="fk_customer_promise_review__pack_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_customer_promise_review__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("length(comment) <= 1000", name="ck_customer_promise_review__comment_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "decision <> 'CHANGES_REQUESTED' OR comment IS NOT NULL",
            name="ck_customer_promise_review__comment_required",
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_promise_review__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "decision IN ('APPROVED', 'CHANGES_REQUESTED')", name="ck_customer_promise_review__decision"
        ),
        sa.CheckConstraint("length(decision) <= 20", name="ck_customer_promise_review__decision_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_customer_promise_review__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_promise_review__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_customer_promise_review__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(pack_id) = 32 AND pack_id NOT GLOB '*[^0-9a-f]*' AND substr(pack_id, 13, 1) = '7' AND substr(pack_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_promise_review__pack_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("review_round >= 1", name="ck_customer_promise_review__review_round"),
        sa.CheckConstraint(
            "section_code IN ('CONTACTS', 'INCLUSIONS', 'RESPONSIBILITIES', 'SITE_READINESS', 'SITE_WORK', 'WARRANTY', 'EXCLUSIONS', 'SERVICE', 'HANDOVER', 'CARE', 'NEXT_STEPS', 'PAYMENT_SAFETY')",
            name="ck_customer_promise_review__section_code",
        ),
        sa.CheckConstraint("length(section_code) <= 20", name="ck_customer_promise_review__section_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(section_sha256) = 64", name="ck_customer_promise_review__section_sha256_len"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_customer_promise_review__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_customer_promise_review__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_promise_review__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_customer_promise_review__version_positive"),
    )
    op.create_index(
        "ix_customer_promise_review__pack",
        "customer_promise_review",
        ["pack_id", "review_round", "section_code"],
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "customer_promise_event",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("pack_id", GUID(), nullable=False),
        sa.Column("event_code", sa.String(20), nullable=False),
        sa.Column("section_code", sa.String(20), nullable=True),
        sa.Column("from_status", sa.String(12), nullable=True),
        sa.Column("to_status", sa.String(12), nullable=True),
        sa.Column("reason", sa.String(1000), nullable=True),
        sa.Column("detail", JSONType(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_customer_promise_event"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_customer_promise_event__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_customer_promise_event__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["pack_id"], ["customer_promise_pack.id"], name="fk_customer_promise_event__pack_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_customer_promise_event__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_promise_event__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_customer_promise_event__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "detail IS NULL OR json_valid(detail)", name="ck_customer_promise_event__detail_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "event_code IN ('DRAFT_CREATED', 'SECTION_UPDATED', 'SUMMARY_UPDATED', 'DRAFT_DISCARDED', 'SUBMITTED', 'SECTION_APPROVED', 'CHANGES_REQUESTED', 'RETURNED_TO_DRAFT', 'APPROVED', 'PUBLISHED', 'SUPERSEDED', 'PREVIEWED')",
            name="ck_customer_promise_event__event_code",
        ),
        sa.CheckConstraint("length(event_code) <= 20", name="ck_customer_promise_event__event_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(from_status) <= 12", name="ck_customer_promise_event__from_status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_promise_event__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_customer_promise_event__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(pack_id) = 32 AND pack_id NOT GLOB '*[^0-9a-f]*' AND substr(pack_id, 13, 1) = '7' AND substr(pack_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_promise_event__pack_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(reason) <= 1000", name="ck_customer_promise_event__reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "section_code IS NULL OR section_code IN ('CONTACTS', 'INCLUSIONS', 'RESPONSIBILITIES', 'SITE_READINESS', 'SITE_WORK', 'WARRANTY', 'EXCLUSIONS', 'SERVICE', 'HANDOVER', 'CARE', 'NEXT_STEPS', 'PAYMENT_SAFETY')",
            name="ck_customer_promise_event__section_code",
        ),
        sa.CheckConstraint("length(section_code) <= 20", name="ck_customer_promise_event__section_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_customer_promise_event__soft_delete_consistent",
        ),
        sa.CheckConstraint("length(to_status) <= 12", name="ck_customer_promise_event__to_status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_customer_promise_event__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_customer_promise_event__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_customer_promise_event__version_positive"),
    )
    op.create_index(
        "ix_customer_promise_event__pack",
        "customer_promise_event",
        ["pack_id", "created_on"],
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    # --- end generated DDL ---
    bind = op.get_bind()
    ms.sync_permissions(bind, audit=True)
    ms.grant_new_codes(bind, CODES, audit=True)
    ms.assert_rbac_seed(bind)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
