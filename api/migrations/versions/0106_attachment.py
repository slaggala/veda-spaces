"""0106_attachment: the attachment table and permissions (ATT; MTQ B1-SCOPE §2.8, blocker closure §6, decision log 26).

One new table (no change to existing ones): attachment, polymorphic over the MTQ site records through
``entity_type`` / ``entity_id`` (registered FK-less identifier, EXC-011) and owned by a lead (FK). Bytes are never
stored in the database. Adds the permission codes attachment.read, attachment.create and attachment.delete and grants
them per the matrix where missing (fresh databases already have them from 0003, which reads the live registry); the
SURVEYOR and DESIGNER grants arrive with 0200_mtq_site. Seeds the ATTACHMENT_CATEGORY lookup.

Expand-only (02 §12.4): the N-1 image never touches this table, so it runs unchanged on this schema. Every route that
uses it answers 404 while VEDA_MTQ_SITE_ENABLED is off (the default; production refuses it).

Revision ID: 0106_attachment
Revises: 0105_catalog_claim_control
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0106_attachment"
down_revision = "0105_catalog_claim_control"
branch_labels = None
depends_on = None

CODES = ("attachment.read", "attachment.create", "attachment.delete")

# Frozen seed (B1-SCOPE §4 step 1). Values are only ever added by later migrations, never edited.
LOOKUPS = (
    (
        "ATTACHMENT_CATEGORY",
        "Attachment category",
        "What a site attachment shows",
        (
            ("SITE_PHOTO", "Site photo", None),
            ("LASER_READING", "Laser reading", None),
            ("SKETCH", "Sketch", None),
            ("FLOOR_PLAN", "Floor plan", None),
            ("OTHER", "Other", None),
        ),
    ),
)


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "attachment",
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
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", GUID(), nullable=False),
        sa.Column("category_code", sa.String(20), nullable=False),
        sa.Column("caption", sa.String(200), nullable=True),
        sa.Column("original_filename", sa.String(120), nullable=True),
        sa.Column("declared_mime_type", sa.String(40), nullable=False),
        sa.Column("mime_type", sa.String(40), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("storage_backend", sa.String(10), nullable=False),
        sa.Column("upload_key", sa.String(100), nullable=False),
        sa.Column("upload_status", sa.String(20), nullable=False, server_default="AWAITING_UPLOAD"),
        sa.Column("rejection_reason", sa.String(60), nullable=True),
        sa.Column("scan_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("scanned_on", UTCDateTime(), nullable=True),
        sa.Column("variant_status", sa.String(20), nullable=False, server_default="NONE"),
        sa.Column("variants", JSONType(), nullable=True),
        sa.Column("uploaded_by", GUID(), nullable=False),
        sa.Column("uploaded_on", UTCDateTime(), nullable=True),
        sa.Column("withdrawn_on", UTCDateTime(), nullable=True),
        sa.Column("withdrawn_by", GUID(), nullable=True),
        sa.Column("withdrawal_reason", sa.String(200), nullable=True),
        sa.Column("retention_state", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("bytes_deleted_on", UTCDateTime(), nullable=True),
        sa.Column("visibility_code", sa.String(10), nullable=False, server_default="STANDARD"),
        sa.Column("client_ref", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_attachment"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], name="fk_attachment__created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["app_user.id"], name="fk_attachment__deleted_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], name="fk_attachment__lead_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], name="fk_attachment__updated_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["app_user.id"], name="fk_attachment__uploaded_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["withdrawn_by"], ["app_user.id"], name="fk_attachment__withdrawn_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("byte_size BETWEEN 1 AND 15728640", name="ck_attachment__byte_size"),
        sa.CheckConstraint("length(caption) <= 200", name="ck_attachment__caption_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "category_code IN ('SITE_PHOTO', 'LASER_READING', 'SKETCH', 'FLOOR_PLAN', 'OTHER')",
            name="ck_attachment__category_code",
        ),
        sa.CheckConstraint("length(category_code) <= 20", name="ck_attachment__category_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(client_ref) <= 64", name="ck_attachment__client_ref_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_attachment__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(declared_mime_type) <= 40", name="ck_attachment__declared_mime_type_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_attachment__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(width IS NULL AND height IS NULL) OR (width > 0 AND height > 0)", name="ck_attachment__dimensions"
        ),
        sa.CheckConstraint(
            "length(entity_id) = 32 AND entity_id NOT GLOB '*[^0-9a-f]*' AND substr(entity_id, 13, 1) = '7' AND substr(entity_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_attachment__entity_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "entity_type IN ('property', 'property_space', 'measurement_set', 'space_wall', 'space_opening', 'space_electrical_point', 'measurement_note')",
            name="ck_attachment__entity_type",
        ),
        sa.CheckConstraint("length(entity_type) <= 30", name="ck_attachment__entity_type_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_attachment__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_attachment__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(lead_id) = 32 AND lead_id NOT GLOB '*[^0-9a-f]*' AND substr(lead_id, 13, 1) = '7' AND substr(lead_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_attachment__lead_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(mime_type) <= 40", name="ck_attachment__mime_type_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(original_filename) <= 120", name="ck_attachment__original_filename_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(rejection_reason) <= 60", name="ck_attachment__rejection_reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "retention_state IN ('ACTIVE', 'WITHDRAWN', 'ERASED', 'PURGED')", name="ck_attachment__retention_state"
        ),
        sa.CheckConstraint("length(retention_state) <= 20", name="ck_attachment__retention_state_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "scan_status IN ('PENDING', 'CLEAN', 'INFECTED', 'FAILED', 'WITHDRAWN')", name="ck_attachment__scan_status"
        ),
        sa.CheckConstraint("length(scan_status) <= 20", name="ck_attachment__scan_status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(sha256) <= 64", name="ck_attachment__sha256_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_attachment__sha256_len64"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_attachment__soft_delete_consistent",
        ),
        sa.CheckConstraint("storage_backend IN ('local', 's3')", name="ck_attachment__storage_backend"),
        sa.CheckConstraint("length(storage_backend) <= 10", name="ck_attachment__storage_backend_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_attachment__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_attachment__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(upload_key) <= 100", name="ck_attachment__upload_key_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "upload_status IN ('AWAITING_UPLOAD', 'RECEIVED', 'REJECTED')", name="ck_attachment__upload_status"
        ),
        sa.CheckConstraint("length(upload_status) <= 20", name="ck_attachment__upload_status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(uploaded_by) = 32 AND uploaded_by NOT GLOB '*[^0-9a-f]*' AND substr(uploaded_by, 13, 1) = '7' AND substr(uploaded_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_attachment__uploaded_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("variant_status IN ('NONE', 'READY', 'FAILED')", name="ck_attachment__variant_status"),
        sa.CheckConstraint("length(variant_status) <= 20", name="ck_attachment__variant_status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("variants IS NULL OR json_valid(variants)", name="ck_attachment__variants_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("version >= 1", name="ck_attachment__version_positive"),
        sa.CheckConstraint("visibility_code IN ('STANDARD', 'INTERNAL')", name="ck_attachment__visibility_code"),
        sa.CheckConstraint("length(visibility_code) <= 10", name="ck_attachment__visibility_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(withdrawn_on IS NULL AND withdrawn_by IS NULL) OR (withdrawn_on IS NOT NULL AND withdrawn_by IS NOT NULL)",
            name="ck_attachment__withdrawal_pair",
        ),
        sa.CheckConstraint("length(withdrawal_reason) <= 200", name="ck_attachment__withdrawal_reason_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "withdrawn_by IS NULL OR (length(withdrawn_by) = 32 AND withdrawn_by NOT GLOB '*[^0-9a-f]*' AND substr(withdrawn_by, 13, 1) = '7' AND substr(withdrawn_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_attachment__withdrawn_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "scan_status <> 'WITHDRAWN' OR retention_state <> 'ACTIVE'", name="ck_attachment__withdrawn_not_active"
        ),
    )
    op.create_index("ix_attachment__entity", "attachment", ["entity_type", "entity_id"])
    op.create_index("ix_attachment__lead_id", "attachment", ["lead_id"])
    op.create_index("ix_attachment__scan_status", "attachment", ["scan_status", "upload_status"])
    op.create_index("ix_attachment__sha256", "attachment", ["sha256"])
    op.create_index(
        "ux_attachment__lead_client_ref",
        "attachment",
        ["lead_id", "client_ref"],
        unique=True,
        sqlite_where=sa.text("client_ref IS NOT NULL AND is_deleted = 0"),
        postgresql_where=sa.text("client_ref IS NOT NULL AND is_deleted = false"),
    )
    # --- end generated DDL ---
    bind = op.get_bind()
    ms.seed_lookups(bind, LOOKUPS, module="attachments")
    ms.sync_permissions(bind, audit=True)
    ms.grant_new_codes(bind, CODES, audit=True)
    ms.assert_rbac_seed(bind)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
