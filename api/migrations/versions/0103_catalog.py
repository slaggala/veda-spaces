"""0103_catalog: the catalog-driven estimator (ADR-013).

Six new tables: catalog_record (versioned typed documents), catalog_release (immutable manifests), catalog_event
(lifecycle trail), catalog_media_object (content-addressed media files and their scan state), catalog_configuration
(the configuration snapshot of each V3 estimate) and catalog_analytics_daily (staging counts only). No change to any
existing table. No personal data. Permissions are registry entries (catalog.*), seeded by the RBAC sync.

Expand-only (02 §12.4): new tables, no data rewrite. The N-1 image never reads them, so a rollback runs unchanged
(VEDA_SCHEMA_AHEAD_ACCEPTED).

Revision ID: 0103_catalog
Revises: 0102_estimator_spec
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0103_catalog"
down_revision = "0102_estimator_spec"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "catalog_record",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("record_key", sa.String(100), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="DRAFT"),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("document", JSONType(), nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.Column("submitted_by", GUID(), nullable=True),
        sa.Column("submitted_on", UTCDateTime(), nullable=True),
        sa.Column("reviewed_by", GUID(), nullable=True),
        sa.Column("reviewed_on", UTCDateTime(), nullable=True),
        sa.Column("review_note", sa.String(300), nullable=True),
        sa.Column("contributors", JSONType(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_record"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_catalog_record__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_catalog_record__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"], ["app_user.id"], name="fk_catalog_record__reviewed_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by"], ["app_user.id"], name="fk_catalog_record__submitted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_catalog_record__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "contributors IS NULL OR json_valid(contributors)", name="ck_catalog_record__contributors_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_record__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_record__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("document IS NULL OR json_valid(document)", name="ck_catalog_record__document_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(document_sha256) <= 64", name="ck_catalog_record__document_sha256_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_record__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_catalog_record__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "kind IN ('property_type', 'home_config', 'room_template', 'product_family', 'product', 'extra', 'material', 'hardware', 'media', 'package', 'pricing', 'rule', 'copy')",
            name="ck_catalog_record__kind",
        ),
        sa.CheckConstraint("length(kind) <= 20", name="ck_catalog_record__kind_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(record_key) <= 100", name="ck_catalog_record__record_key_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("record_version >= 1", name="ck_catalog_record__record_version"),
        sa.CheckConstraint("length(review_note) <= 300", name="ck_catalog_record__review_note_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "reviewed_by IS NULL OR (length(reviewed_by) = 32 AND reviewed_by NOT GLOB '*[^0-9a-f]*' AND substr(reviewed_by, 13, 1) = '7' AND substr(reviewed_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_record__reviewed_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(document_sha256) = 64", name="ck_catalog_record__sha_len"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_catalog_record__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'IN_REVIEW', 'APPROVED', 'SCHEDULED', 'ACTIVE', 'RETIRED', 'ARCHIVED')",
            name="ck_catalog_record__status",
        ),
        sa.CheckConstraint("length(status) <= 10", name="ck_catalog_record__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "submitted_by IS NULL OR (length(submitted_by) = 32 AND submitted_by NOT GLOB '*[^0-9a-f]*' AND substr(submitted_by, 13, 1) = '7' AND substr(submitted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_record__submitted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(title) <= 160", name="ck_catalog_record__title_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_catalog_record__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_record__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_catalog_record__version_positive"),
    )
    op.create_index(
        "ix_catalog_record__status",
        "catalog_record",
        ["status", "kind"],
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_catalog_record__kind_key_version",
        "catalog_record",
        ["kind", "record_key", "record_version"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_catalog_record__one_active",
        "catalog_record",
        ["kind", "record_key"],
        unique=True,
        sqlite_where=sa.text("status = 'ACTIVE' AND is_deleted = 0"),
        postgresql_where=sa.text("status = 'ACTIVE' AND is_deleted = false"),
    )

    op.create_table(
        "catalog_release",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("release_code", sa.String(40), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="DRAFT"),
        sa.Column("manifest", JSONType(), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("compiled", JSONType(), nullable=True),
        sa.Column("validation", JSONType(), nullable=True),
        sa.Column("rate_card_id", GUID(), nullable=True),
        sa.Column("previous_release_id", GUID(), nullable=True),
        sa.Column("rollback_of_id", GUID(), nullable=True),
        sa.Column("release_owner", GUID(), nullable=True),
        sa.Column("preview_approved_by", GUID(), nullable=True),
        sa.Column("preview_approved_on", UTCDateTime(), nullable=True),
        sa.Column("submitted_by", GUID(), nullable=True),
        sa.Column("approved_by", GUID(), nullable=True),
        sa.Column("approved_on", UTCDateTime(), nullable=True),
        sa.Column("approval_reference", sa.String(200), nullable=True),
        sa.Column("scheduled_for", UTCDateTime(), nullable=True),
        sa.Column("activated_on", UTCDateTime(), nullable=True),
        sa.Column("deactivated_on", UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_release"),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["app_user.id"], name="fk_catalog_release__approved_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_catalog_release__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_catalog_release__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["preview_approved_by"],
            ["app_user.id"],
            name="fk_catalog_release__preview_approved_by",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_release_id"],
            ["catalog_release.id"],
            name="fk_catalog_release__previous_release_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rate_card_id"], ["estimator_rate_card.id"], name="fk_catalog_release__rate_card_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["release_owner"], ["app_user.id"], name="fk_catalog_release__release_owner", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["rollback_of_id"], ["catalog_release.id"], name="fk_catalog_release__rollback_of_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by"], ["app_user.id"], name="fk_catalog_release__submitted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_catalog_release__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(approval_reference) <= 200", name="ck_catalog_release__approval_reference_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "approved_by IS NULL OR (length(approved_by) = 32 AND approved_by NOT GLOB '*[^0-9a-f]*' AND substr(approved_by, 13, 1) = '7' AND substr(approved_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_release__approved_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("compiled IS NULL OR json_valid(compiled)", name="ck_catalog_release__compiled_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_release__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_release__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_release__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_catalog_release__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("manifest IS NULL OR json_valid(manifest)", name="ck_catalog_release__manifest_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(manifest_sha256) <= 64", name="ck_catalog_release__manifest_sha256_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "preview_approved_by IS NULL OR (length(preview_approved_by) = 32 AND preview_approved_by NOT GLOB '*[^0-9a-f]*' AND substr(preview_approved_by, 13, 1) = '7' AND substr(preview_approved_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_release__preview_approved_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "previous_release_id IS NULL OR (length(previous_release_id) = 32 AND previous_release_id NOT GLOB '*[^0-9a-f]*' AND substr(previous_release_id, 13, 1) = '7' AND substr(previous_release_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_release__previous_release_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "rate_card_id IS NULL OR (length(rate_card_id) = 32 AND rate_card_id NOT GLOB '*[^0-9a-f]*' AND substr(rate_card_id, 13, 1) = '7' AND substr(rate_card_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_release__rate_card_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(release_code) <= 40", name="ck_catalog_release__release_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "release_owner IS NULL OR (length(release_owner) = 32 AND release_owner NOT GLOB '*[^0-9a-f]*' AND substr(release_owner, 13, 1) = '7' AND substr(release_owner, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_release__release_owner_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "rollback_of_id IS NULL OR (length(rollback_of_id) = 32 AND rollback_of_id NOT GLOB '*[^0-9a-f]*' AND substr(rollback_of_id, 13, 1) = '7' AND substr(rollback_of_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_release__rollback_of_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(manifest_sha256) = 64", name="ck_catalog_release__sha_len"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_catalog_release__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'IN_REVIEW', 'APPROVED', 'SCHEDULED', 'ACTIVE', 'RETIRED')",
            name="ck_catalog_release__status",
        ),
        sa.CheckConstraint("length(status) <= 10", name="ck_catalog_release__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "submitted_by IS NULL OR (length(submitted_by) = 32 AND submitted_by NOT GLOB '*[^0-9a-f]*' AND substr(submitted_by, 13, 1) = '7' AND substr(submitted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_release__submitted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_catalog_release__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_release__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "validation IS NULL OR json_valid(validation)", name="ck_catalog_release__validation_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_catalog_release__version_positive"),
    )
    op.create_index(
        "ux_catalog_release__code",
        "catalog_release",
        ["release_code"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_catalog_release__one_active",
        "catalog_release",
        ["status"],
        unique=True,
        sqlite_where=sa.text("status = 'ACTIVE' AND is_deleted = 0"),
        postgresql_where=sa.text("status = 'ACTIVE' AND is_deleted = false"),
    )

    op.create_table(
        "catalog_event",
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
        sa.Column("record_id", GUID(), nullable=True),
        sa.Column("release_id", GUID(), nullable=True),
        sa.Column("detail", JSONType(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_event"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_catalog_event__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_catalog_event__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["record_id"], ["catalog_record.id"], name="fk_catalog_event__record_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["release_id"], ["catalog_release.id"], name="fk_catalog_event__release_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_catalog_event__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_event__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_event__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("detail IS NULL OR json_valid(detail)", name="ck_catalog_event__detail_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "event_type IN ('RECORD_CREATED', 'RECORD_UPDATED', 'RECORD_SUBMITTED', 'RECORD_APPROVED', 'RECORD_REJECTED', 'RECORD_ARCHIVED', 'RELEASE_CREATED', 'RELEASE_VALIDATED', 'RELEASE_PREVIEW_APPROVED', 'RELEASE_SUBMITTED', 'RELEASE_APPROVED', 'RELEASE_REJECTED', 'RELEASE_SCHEDULED', 'RELEASE_ACTIVATED', 'RELEASE_RETIRED', 'RELEASE_ROLLED_BACK', 'CONFIGURATION_PURGED', 'MEDIA_UPLOADED', 'MEDIA_SCANNED', 'IMPORT_APPLIED')",
            name="ck_catalog_event__event_type",
        ),
        sa.CheckConstraint("length(event_type) <= 30", name="ck_catalog_event__event_type_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_event__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_catalog_event__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "record_id IS NULL OR (length(record_id) = 32 AND record_id NOT GLOB '*[^0-9a-f]*' AND substr(record_id, 13, 1) = '7' AND substr(record_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_event__record_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "release_id IS NULL OR (length(release_id) = 32 AND release_id NOT GLOB '*[^0-9a-f]*' AND substr(release_id, 13, 1) = '7' AND substr(release_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_event__release_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_catalog_event__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_catalog_event__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_event__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_catalog_event__version_positive"),
    )
    op.create_index(
        "ix_catalog_event__record",
        "catalog_event",
        ["record_id", "created_on"],
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_catalog_event__release",
        "catalog_event",
        ["release_id", "created_on"],
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "catalog_media_object",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("object_sha256", sa.String(64), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("media_kind", sa.String(10), nullable=False),
        sa.Column("variant", sa.String(20), nullable=False),
        sa.Column("mime_type", sa.String(60), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("storage_key", sa.String(200), nullable=False),
        sa.Column("scan_status", sa.String(15), nullable=False),
        sa.Column("scanned_on", UTCDateTime(), nullable=True),
        sa.Column("source_object_id", GUID(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_media_object"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_catalog_media_object__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_catalog_media_object__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_object_id"],
            ["catalog_media_object.id"],
            name="fk_catalog_media_object__source_object_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_catalog_media_object__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_media_object__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_media_object__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_media_object__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_catalog_media_object__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "media_kind IN ('IMAGE', 'VIDEO', 'GLB', 'GLTF', 'USDZ')", name="ck_catalog_media_object__media_kind"
        ),
        sa.CheckConstraint("length(media_kind) <= 10", name="ck_catalog_media_object__media_kind_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(mime_type) <= 60", name="ck_catalog_media_object__mime_type_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(object_sha256) <= 64", name="ck_catalog_media_object__object_sha256_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("role IN ('SOURCE', 'VARIANT')", name="ck_catalog_media_object__role"),
        sa.CheckConstraint("length(role) <= 10", name="ck_catalog_media_object__role_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "scan_status IN ('PENDING_SCAN', 'CLEAN', 'INFECTED')", name="ck_catalog_media_object__scan_status"
        ),
        sa.CheckConstraint("length(scan_status) <= 15", name="ck_catalog_media_object__scan_status_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(object_sha256) = 64", name="ck_catalog_media_object__sha_len"),
        sa.CheckConstraint("byte_size > 0", name="ck_catalog_media_object__size"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_catalog_media_object__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "source_object_id IS NULL OR (length(source_object_id) = 32 AND source_object_id NOT GLOB '*[^0-9a-f]*' AND substr(source_object_id, 13, 1) = '7' AND substr(source_object_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_media_object__source_object_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(storage_key) <= 200", name="ck_catalog_media_object__storage_key_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_catalog_media_object__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_media_object__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(variant) <= 20", name="ck_catalog_media_object__variant_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("version >= 1", name="ck_catalog_media_object__version_positive"),
    )
    op.create_index(
        "ux_catalog_media_object__sha",
        "catalog_media_object",
        ["object_sha256"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "catalog_configuration",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("configuration_reference", sa.String(9), nullable=False),
        sa.Column("release_id", GUID(), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("versions", JSONType(), nullable=False),
        sa.Column("selections", JSONType(), nullable=False),
        sa.Column("resolved_request", JSONType(), nullable=False),
        sa.Column("estimate_id", GUID(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_configuration"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_catalog_configuration__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_catalog_configuration__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["estimate_id"], ["budget_estimate.id"], name="fk_catalog_configuration__estimate_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["release_id"], ["catalog_release.id"], name="fk_catalog_configuration__release_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_catalog_configuration__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(configuration_reference) <= 9", name="ck_catalog_configuration__configuration_reference_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_configuration__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_configuration__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "estimate_id IS NULL OR (length(estimate_id) = 32 AND estimate_id NOT GLOB '*[^0-9a-f]*' AND substr(estimate_id, 13, 1) = '7' AND substr(estimate_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_configuration__estimate_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_configuration__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_catalog_configuration__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(manifest_sha256) <= 64", name="ck_catalog_configuration__manifest_sha256_len"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(release_id) = 32 AND release_id NOT GLOB '*[^0-9a-f]*' AND substr(release_id, 13, 1) = '7' AND substr(release_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_configuration__release_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "resolved_request IS NULL OR json_valid(resolved_request)",
            name="ck_catalog_configuration__resolved_request_json",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "selections IS NULL OR json_valid(selections)", name="ck_catalog_configuration__selections_json"
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(manifest_sha256) = 64", name="ck_catalog_configuration__sha_len"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_catalog_configuration__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_catalog_configuration__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_configuration__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_catalog_configuration__version_positive"),
        sa.CheckConstraint(
            "versions IS NULL OR json_valid(versions)", name="ck_catalog_configuration__versions_json"
        ).ddl_if(dialect="sqlite"),
    )
    op.create_index(
        "ix_catalog_configuration__estimate",
        "catalog_configuration",
        ["estimate_id"],
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_catalog_configuration__reference",
        "catalog_configuration",
        ["configuration_reference"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "catalog_analytics_daily",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("day", sa.String(10), nullable=False),
        sa.Column("event", sa.String(30), nullable=False),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("release_code", sa.String(40), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_analytics_daily"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_catalog_analytics_daily__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_catalog_analytics_daily__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_catalog_analytics_daily__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("count >= 0", name="ck_catalog_analytics_daily__count"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_analytics_daily__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(day) <= 10", name="ck_catalog_analytics_daily__day_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_catalog_analytics_daily__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "event IN ('room_selected', 'room_deselected', 'extra_viewed', 'extra_selected', 'image_opened', 'gallery_viewed', 'preview_3d_started', 'preview_3d_succeeded', 'preview_3d_fallback', 'estimate_reached', 'estimate_refined', 'quotation_requested')",
            name="ck_catalog_analytics_daily__event",
        ),
        sa.CheckConstraint("length(event) <= 30", name="ck_catalog_analytics_daily__event_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_analytics_daily__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_catalog_analytics_daily__is_deleted_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(release_code) <= 40", name="ck_catalog_analytics_daily__release_code_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_catalog_analytics_daily__soft_delete_consistent",
        ),
        sa.CheckConstraint("length(subject) <= 100", name="ck_catalog_analytics_daily__subject_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_catalog_analytics_daily__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_catalog_analytics_daily__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_catalog_analytics_daily__version_positive"),
    )
    op.create_index(
        "ux_catalog_analytics_daily__key",
        "catalog_analytics_daily",
        ["day", "event", "subject", "release_code"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    # --- end generated DDL ---


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
