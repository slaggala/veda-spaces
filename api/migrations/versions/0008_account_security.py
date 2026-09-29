"""0008_account_security: admin_approval_request + app_user account-security columns.

Adds proposed-email (05 §8.6), protection_level (06 §7.2) and the recovery
cooling-off column (05 §11.5) to app_user. The ALTERs are expand-only: new
nullable columns, or NOT NULL with a constant default (02 §12.4).

Revision ID: 0008_account_security
Revises: 0007_notifications
"""
import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms  # noqa: F401
from veda.kernel.base import guid_format_sql
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0008_account_security"
down_revision = "0007_notifications"
branch_labels = None
depends_on = None


def _app_user_columns_sqlite() -> None:
    fmt = guid_format_sql("proposed_email_requested_by")
    statements = [
        "ALTER TABLE app_user ADD COLUMN proposed_email VARCHAR(254) "
        "CONSTRAINT ck_app_user__proposed_email_len CHECK (length(proposed_email) <= 254)",
        "ALTER TABLE app_user ADD COLUMN proposed_email_normalized VARCHAR(254) "
        "CONSTRAINT ck_app_user__proposed_email_normalized_len CHECK (length(proposed_email_normalized) <= 254) "
        "CONSTRAINT ck_app_user__proposed_email_pair CHECK ((proposed_email IS NULL) = (proposed_email_normalized IS NULL)) "
        "CONSTRAINT ck_app_user__proposed_email_differs "
        "CHECK (proposed_email_normalized IS NULL OR proposed_email_normalized <> email_normalized)",
        "ALTER TABLE app_user ADD COLUMN proposed_email_requested_on VARCHAR(27)",
        "ALTER TABLE app_user ADD COLUMN proposed_email_requested_by CHAR(32) "
        "CONSTRAINT fk_app_user__proposed_email_requested_by REFERENCES app_user (id) ON DELETE RESTRICT "
        f"CONSTRAINT ck_app_user__proposed_email_requested_by_format CHECK (proposed_email_requested_by IS NULL OR ({fmt}))",
        "ALTER TABLE app_user ADD COLUMN protection_level VARCHAR(10) DEFAULT 'STANDARD' NOT NULL "
        "CONSTRAINT ck_app_user__protection_level CHECK (protection_level IN ('STANDARD', 'FOUNDER')) "
        "CONSTRAINT ck_app_user__protection_level_len CHECK (length(protection_level) <= 10)",
        "ALTER TABLE app_user ADD COLUMN security_cooling_off_until VARCHAR(27)",
    ]
    for statement in statements:
        op.execute(statement)


def _app_user_columns_postgresql() -> None:
    op.add_column("app_user", sa.Column("proposed_email", sa.String(254), nullable=True))
    op.add_column("app_user", sa.Column("proposed_email_normalized", sa.String(254), nullable=True))
    op.add_column("app_user", sa.Column("proposed_email_requested_on", UTCDateTime(), nullable=True))
    op.add_column("app_user", sa.Column("proposed_email_requested_by", GUID(), nullable=True))
    op.add_column("app_user", sa.Column("protection_level", sa.String(10), nullable=False, server_default="STANDARD"))
    op.add_column("app_user", sa.Column("security_cooling_off_until", UTCDateTime(), nullable=True))
    op.create_foreign_key("fk_app_user__proposed_email_requested_by", "app_user", "app_user",
                          ["proposed_email_requested_by"], ["id"], ondelete="RESTRICT")
    op.create_check_constraint("ck_app_user__protection_level", "app_user",
                               "protection_level IN ('STANDARD', 'FOUNDER')")
    op.create_check_constraint("ck_app_user__proposed_email_pair", "app_user",
                               "(proposed_email IS NULL) = (proposed_email_normalized IS NULL)")
    op.create_check_constraint("ck_app_user__proposed_email_differs", "app_user",
                               "proposed_email_normalized IS NULL OR proposed_email_normalized <> email_normalized")


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "admin_approval_request",
        sa.Column('id', GUID(), nullable=False),
        sa.Column('created_on', UTCDateTime(), nullable=False),
        sa.Column('updated_on', UTCDateTime(), nullable=False),
        sa.Column('created_by', GUID(), nullable=False),
        sa.Column('updated_by', GUID(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('deleted_on', UTCDateTime(), nullable=True),
        sa.Column('deleted_by', GUID(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.Column('action_class', sa.String(10), nullable=False),
        sa.Column('action_type', sa.String(30), nullable=False),
        sa.Column('channel', sa.String(12), nullable=False, server_default='IN_APP'),
        sa.Column('target_user_id', GUID(), nullable=False),
        sa.Column('requested_by', GUID(), nullable=False),
        sa.Column('request_payload', JSONType(), nullable=False),
        sa.Column('reason', sa.String(1000), nullable=False),
        sa.Column('status', sa.String(12), nullable=False, server_default='PENDING'),
        sa.Column('status_reason', sa.String(30), nullable=True),
        sa.Column('approver_user_id', GUID(), nullable=True),
        sa.Column('external_requester_ref', sa.String(2048), nullable=True),
        sa.Column('external_approver_ref', sa.String(2048), nullable=True),
        sa.Column('external_approver_human', sa.String(200), nullable=True),
        sa.Column('decided_on', UTCDateTime(), nullable=True),
        sa.Column('decision_reason', sa.String(1000), nullable=True),
        sa.Column('not_before', UTCDateTime(), nullable=True),
        sa.Column('expires_on', UTCDateTime(), nullable=False),
        sa.Column('executed_on', UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_admin_approval_request"),
        sa.ForeignKeyConstraint(['approver_user_id'], ['app_user.id'], name='fk_admin_approval_request__approver_user_id', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['app_user.id'], name='fk_admin_approval_request__created_by', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['deleted_by'], ['app_user.id'], name='fk_admin_approval_request__deleted_by', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['requested_by'], ['app_user.id'], name='fk_admin_approval_request__requested_by', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['target_user_id'], ['app_user.id'], name='fk_admin_approval_request__target_user_id', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['updated_by'], ['app_user.id'], name='fk_admin_approval_request__updated_by', ondelete='RESTRICT'),
        sa.CheckConstraint("action_class IN ('STANDARD', 'FOUNDER')", name='ck_admin_approval_request__action_class'),
        sa.CheckConstraint('length(action_class) <= 10', name='ck_admin_approval_request__action_class_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint("action_type IN ('MFA_RESET', 'EMAIL_CHANGE', 'GRANT_FOUNDER', 'REVOKE_FOUNDER', 'FOUNDER_MFA_RESET', 'FOUNDER_STATUS_CHANGE', 'FOUNDER_EMAIL_CHANGE')", name='ck_admin_approval_request__action_type'),
        sa.CheckConstraint('length(action_type) <= 30', name='ck_admin_approval_request__action_type_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('approver_user_id IS NULL OR (approver_user_id <> requested_by AND approver_user_id <> target_user_id)', name='ck_admin_approval_request__approver_distinct'),
        sa.CheckConstraint("approver_user_id IS NULL OR (length(approver_user_id) = 32 AND approver_user_id NOT GLOB '*[^0-9a-f]*' AND substr(approver_user_id, 13, 1) = '7' AND substr(approver_user_id, 17, 1) IN ('8', '9', 'a', 'b'))", name='ck_admin_approval_request__approver_user_id_format').ddl_if(dialect="sqlite"),
        sa.CheckConstraint("channel IN ('IN_APP', 'BREAK_GLASS')", name='ck_admin_approval_request__channel'),
        sa.CheckConstraint('length(channel) <= 12', name='ck_admin_approval_request__channel_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint("(action_class = 'FOUNDER') = (action_type IN ('GRANT_FOUNDER','REVOKE_FOUNDER','FOUNDER_MFA_RESET','FOUNDER_STATUS_CHANGE','FOUNDER_EMAIL_CHANGE'))", name='ck_admin_approval_request__class_matches_type'),
        sa.CheckConstraint("length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')", name='ck_admin_approval_request__created_by_format').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('length(decision_reason) <= 1000', name='ck_admin_approval_request__decision_reason_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint("deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))", name='ck_admin_approval_request__deleted_by_format').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('length(external_approver_human) <= 200', name='ck_admin_approval_request__external_approver_human_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('length(external_approver_ref) <= 2048', name='ck_admin_approval_request__external_approver_ref_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('external_approver_ref IS NULL OR external_requester_ref IS NULL OR external_approver_ref <> external_requester_ref', name='ck_admin_approval_request__external_distinct'),
        sa.CheckConstraint('length(external_requester_ref) <= 2048', name='ck_admin_approval_request__external_requester_ref_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')", name='ck_admin_approval_request__id_format').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('is_deleted IN (0, 1)', name='ck_admin_approval_request__is_deleted_bool').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('is_deleted = false', name='ck_admin_approval_request__never_deleted'),
        sa.CheckConstraint('approver_user_id IS NULL OR approver_user_id <> requested_by', name='ck_admin_approval_request__no_self_approval'),
        sa.CheckConstraint("requested_by <> target_user_id OR (action_type = 'REVOKE_FOUNDER' AND channel = 'IN_APP')", name='ck_admin_approval_request__no_self_target'),
        sa.CheckConstraint('length(reason) <= 1000', name='ck_admin_approval_request__reason_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('request_payload IS NULL OR json_valid(request_payload)', name='ck_admin_approval_request__request_payload_json').ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(requested_by) = 32 AND requested_by NOT GLOB '*[^0-9a-f]*' AND substr(requested_by, 13, 1) = '7' AND substr(requested_by, 17, 1) IN ('8', '9', 'a', 'b')", name='ck_admin_approval_request__requested_by_format').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)', name='ck_admin_approval_request__soft_delete_consistent'),
        sa.CheckConstraint("status IN ('PENDING', 'APPROVED', 'DENIED', 'EXPIRED', 'CANCELLED', 'EXECUTED', 'FAILED')", name='ck_admin_approval_request__status'),
        sa.CheckConstraint('length(status) <= 12', name='ck_admin_approval_request__status_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('length(status_reason) <= 30', name='ck_admin_approval_request__status_reason_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(target_user_id) = 32 AND target_user_id NOT GLOB '*[^0-9a-f]*' AND substr(target_user_id, 13, 1) = '7' AND substr(target_user_id, 17, 1) IN ('8', '9', 'a', 'b')", name='ck_admin_approval_request__target_user_id_format').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('updated_on >= created_on', name='ck_admin_approval_request__updated_after_created'),
        sa.CheckConstraint("length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')", name='ck_admin_approval_request__updated_by_format').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('version >= 1', name='ck_admin_approval_request__version_positive'),
    )
    op.create_index('ix_admin_approval_request__pending', "admin_approval_request", ['status', 'expires_on'], sqlite_where=sa.text("status = 'PENDING'"), postgresql_where=sa.text("status = 'PENDING'"))
    op.create_index('ix_admin_approval_request__target', "admin_approval_request", ['target_user_id', sa.text('created_on DESC')])
    op.create_index('ux_admin_approval_request__open_founder_target', "admin_approval_request", ['target_user_id'], unique=True, sqlite_where=sa.text("action_class = 'FOUNDER' AND status IN ('PENDING','APPROVED')"), postgresql_where=sa.text("action_class = 'FOUNDER' AND status IN ('PENDING','APPROVED')"))
    op.create_index('ux_admin_approval_request__open_per_target_action', "admin_approval_request", ['target_user_id', 'action_type'], unique=True, sqlite_where=sa.text("status IN ('PENDING','APPROVED')"), postgresql_where=sa.text("status IN ('PENDING','APPROVED')"))
    # --- end generated DDL ---
    if op.get_bind().dialect.name == "sqlite":
        _app_user_columns_sqlite()
    else:
        _app_user_columns_postgresql()
    op.create_index(
        "ux_app_user__proposed_email", "app_user", ["proposed_email_normalized"], unique=True,
        sqlite_where=sa.text("proposed_email_normalized IS NOT NULL AND is_deleted = 0"),
        postgresql_where=sa.text("proposed_email_normalized IS NOT NULL AND is_deleted = false"),
    )


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
