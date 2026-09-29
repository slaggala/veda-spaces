"""0007_notifications: outbox_event, notification.

Revision ID: 0007_notifications
Revises: 0006_reference
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms  # noqa: F401
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0007_notifications"
down_revision = "0006_reference"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "outbox_event",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("aggregate_type", sa.String(60), nullable=False),
        sa.Column("aggregate_id", GUID(), nullable=False),
        sa.Column("payload", JSONType(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("next_attempt_on", UTCDateTime(), nullable=False),
        sa.Column("locked_by", sa.String(64), nullable=True),
        sa.Column("locked_on", UTCDateTime(), nullable=True),
        sa.Column("processed_on", UTCDateTime(), nullable=True),
        sa.Column("last_error", sa.String(2000), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_event"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_outbox_event__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_outbox_event__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_outbox_event__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(aggregate_id) = 32 AND aggregate_id NOT GLOB '*[^0-9a-f]*' AND substr(aggregate_id, 13, 1) = '7' AND substr(aggregate_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_outbox_event__aggregate_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(aggregate_type) <= 60", name="ck_outbox_event__aggregate_type_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_outbox_event__attempts"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_outbox_event__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_outbox_event__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(event_type) <= 80", name="ck_outbox_event__event_type_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_outbox_event__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_outbox_event__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(last_error) <= 2000", name="ck_outbox_event__last_error_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(locked_by) <= 64", name="ck_outbox_event__locked_by_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted = false", name="ck_outbox_event__never_deleted"),
        sa.CheckConstraint("payload IS NULL OR json_valid(payload)", name="ck_outbox_event__payload_json").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_outbox_event__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'DONE', 'FAILED', 'DEAD')", name="ck_outbox_event__status"
        ),
        sa.CheckConstraint("length(status) <= 12", name="ck_outbox_event__status_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_outbox_event__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_outbox_event__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_outbox_event__version_positive"),
    )
    op.create_index("ix_outbox_event__aggregate", "outbox_event", ["aggregate_type", "aggregate_id"])
    op.create_index(
        "ix_outbox_event__due",
        "outbox_event",
        ["status", "next_attempt_on"],
        sqlite_where=sa.text("status IN ('PENDING','FAILED')"),
        postgresql_where=sa.text("status IN ('PENDING','FAILED')"),
    )

    op.create_table(
        "notification",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("recipient_user_id", GUID(), nullable=False),
        sa.Column("notification_type", sa.String(60), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.String(1000), nullable=True),
        sa.Column("entity_type", sa.String(60), nullable=True),
        sa.Column("entity_id", GUID(), nullable=True),
        sa.Column("link_path", sa.String(300), nullable=True),
        sa.Column("read_on", UTCDateTime(), nullable=True),
        sa.Column("source_event_id", GUID(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_notification"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_notification__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_notification__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"], ["app_user.id"], name="fk_notification__recipient_user_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_event_id"], ["outbox_event.id"], name="fk_notification__source_event_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_notification__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("length(body) <= 1000", name="ck_notification__body_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_notification__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_notification__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "entity_id IS NULL OR (length(entity_id) = 32 AND entity_id NOT GLOB '*[^0-9a-f]*' AND substr(entity_id, 13, 1) = '7' AND substr(entity_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_notification__entity_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("(entity_type IS NULL) = (entity_id IS NULL)", name="ck_notification__entity_pair"),
        sa.CheckConstraint("length(entity_type) <= 60", name="ck_notification__entity_type_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_notification__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_notification__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(link_path) <= 300", name="ck_notification__link_path_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(notification_type) <= 60", name="ck_notification__notification_type_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "length(recipient_user_id) = 32 AND recipient_user_id NOT GLOB '*[^0-9a-f]*' AND substr(recipient_user_id, 13, 1) = '7' AND substr(recipient_user_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_notification__recipient_user_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_notification__soft_delete_consistent",
        ),
        sa.CheckConstraint(
            "source_event_id IS NULL OR (length(source_event_id) = 32 AND source_event_id NOT GLOB '*[^0-9a-f]*' AND substr(source_event_id, 13, 1) = '7' AND substr(source_event_id, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_notification__source_event_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(title) <= 200", name="ck_notification__title_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("updated_on >= created_on", name="ck_notification__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_notification__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_notification__version_positive"),
    )
    op.create_index(
        "ix_notification__entity",
        "notification",
        ["entity_type", "entity_id"],
        sqlite_where=sa.text("entity_id IS NOT NULL"),
        postgresql_where=sa.text("entity_id IS NOT NULL"),
    )
    op.create_index("ix_notification__recipient_all", "notification", ["recipient_user_id", sa.text("created_on DESC")])
    op.create_index(
        "ix_notification__recipient_unread",
        "notification",
        ["recipient_user_id", sa.text("created_on DESC")],
        sqlite_where=sa.text("read_on IS NULL AND is_deleted = 0"),
        postgresql_where=sa.text("read_on IS NULL AND is_deleted = false"),
    )
    op.create_index(
        "ux_notification__event_recipient",
        "notification",
        ["source_event_id", "recipient_user_id"],
        unique=True,
        sqlite_where=sa.text("source_event_id IS NOT NULL"),
        postgresql_where=sa.text("source_event_id IS NOT NULL"),
    )
    # --- end generated DDL ---
    pass


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
