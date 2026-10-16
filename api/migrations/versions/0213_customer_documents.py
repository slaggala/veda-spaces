"""0213_customer_documents: customer-visible project documents (CPP-D04, decision log 46).

One new table, ``project_customer_document``: an explicit staff publication of an attachment of the project's customer
record to the customer's portal, as one customer-visible class (progress photograph, handover photograph, approved
drawing), with a customer title; withdrawal keeps the row. A file is never customer-visible because it belongs to a
project: only a PUBLISHED row makes it so, and only while the attachment stays scanned clean and available. The new
staff code ``project.publish_document`` is FOUNDER's.

Expand-only: one new table and one new permission code. Inert while VEDA_PROJECT_LIFECYCLE_ENABLED or
VEDA_PROJECT_DELIVERY_PORTAL_ENABLED is off (production refuses both).

Revision ID: 0213_customer_documents
Revises: 0212_project_execution
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0213_customer_documents"
down_revision = "0212_project_execution"
branch_labels = None
depends_on = None

CODES = ("project.publish_document",)


def upgrade() -> None:
    bind = op.get_bind()
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "project_customer_document",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("attachment_id", GUID(), nullable=False),
        sa.Column("document_class", sa.String(20), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("published_by", GUID(), nullable=False),
        sa.Column("published_on", UTCDateTime(), nullable=False),
        sa.Column("withdrawn_by", GUID(), nullable=True),
        sa.Column("withdrawn_on", UTCDateTime(), nullable=True),
        sa.Column("withdrawn_reason", sa.String(300), nullable=True),
        sa.Column("project_id", GUID(), nullable=False),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_project_customer_document"),
        sa.ForeignKeyConstraint(
            ["attachment_id"],
            ["attachment.id"],
            name="fk_project_customer_document__attachment_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_project_customer_document__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_project_customer_document__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["lead.id"], name="fk_project_customer_document__lead_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name="fk_project_customer_document__project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["published_by"], ["app_user.id"], name="fk_project_customer_document__published_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_project_customer_document__updated_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["withdrawn_by"], ["app_user.id"], name="fk_project_customer_document__withdrawn_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(attachment_id) = 32 AND attachment_id NOT GLOB '*[^0-9a-f]*' AND substr(attachment_id, 13, 1) = '7' AND substr(attachment_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_customer_document__attachment_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_customer_document__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_customer_document__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "document_class IN ('PROGRESS_PHOTO', 'HANDOVER_PHOTO', 'APPROVED_DRAWING')",
            name="ck_project_customer_document__document_class",
        ),
        sa.CheckConstraint(
            "length(document_class) <= 20", name="ck_project_customer_document__document_class_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_customer_document__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_project_customer_document__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_customer_document__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(project_id) = 32 AND project_id NOT GLOB '*[^0-9a-f]*' AND substr(project_id, 13, 1) = '7' AND substr(project_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_customer_document__project_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(published_by) = 32 AND published_by NOT GLOB '*[^0-9a-f]*' AND substr(published_by, 13, 1) = '7' AND substr(published_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_customer_document__published_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_project_customer_document__soft_delete_consistent",
        ),
        sa.CheckConstraint("status IN ('PUBLISHED', 'WITHDRAWN')", name="ck_project_customer_document__status"),
        sa.CheckConstraint("length(status) <= 10", name="ck_project_customer_document__status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(title) <= 120", name="ck_project_customer_document__title_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_project_customer_document__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_project_customer_document__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_project_customer_document__version_positive"),
        sa.CheckConstraint(
            "(status = 'WITHDRAWN') = (withdrawn_on IS NOT NULL AND withdrawn_by IS NOT NULL AND withdrawn_reason IS NOT NULL)",
            name="ck_project_customer_document__withdrawn",
        ),
        sa.CheckConstraint(
            "withdrawn_by IS NULL OR (length(withdrawn_by) = 32 AND withdrawn_by NOT GLOB '*[^0-9a-f]*' AND substr(withdrawn_by, 13, 1) = '7' AND substr(withdrawn_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_project_customer_document__withdrawn_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(withdrawn_reason) <= 300", name="ck_project_customer_document__withdrawn_reason_len"
        ).ddl_if(dialect="sqlite"),
    )
    op.create_index("ix_project_customer_document__attachment", "project_customer_document", ["attachment_id"])
    op.create_index("ix_project_customer_document__lead_id", "project_customer_document", ["lead_id"])
    op.create_index("ix_project_customer_document__project", "project_customer_document", ["project_id", "status"])
    op.create_index("ix_project_customer_document__published_by", "project_customer_document", ["published_by"])
    op.create_index("ix_project_customer_document__withdrawn_by", "project_customer_document", ["withdrawn_by"])
    op.create_index(
        "ux_project_customer_document__published",
        "project_customer_document",
        ["project_id", "attachment_id"],
        unique=True,
        sqlite_where=sa.text("status = 'PUBLISHED' AND is_deleted = 0"),
        postgresql_where=sa.text("status = 'PUBLISHED' AND is_deleted = false"),
    )

    # --- end generated DDL ---
    ms.sync_permissions(bind, audit=True)
    ms.grant_new_codes(bind, CODES, audit=True)
    ms.assert_rbac_seed(bind)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
