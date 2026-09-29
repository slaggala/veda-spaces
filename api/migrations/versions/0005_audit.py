"""0005_audit: audit_log (+ immutability guards).

Backfills CREATE audit rows for the identity and RBAC rows seeded by 0002 and
0003, which ran before audit_log existed (07 §3 data migrations).

Revision ID: 0005_audit
Revises: 0004_auth
"""
import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms  # noqa: F401
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0005_audit"
down_revision = "0004_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "audit_log",
        sa.Column('id', GUID(), nullable=False),
        sa.Column('created_on', UTCDateTime(), nullable=False),
        sa.Column('updated_on', UTCDateTime(), nullable=False),
        sa.Column('created_by', GUID(), nullable=False),
        sa.Column('updated_by', GUID(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('deleted_on', UTCDateTime(), nullable=True),
        sa.Column('deleted_by', GUID(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.Column('entity_type', sa.String(60), nullable=False),
        sa.Column('entity_id', GUID(), nullable=False),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('old_value', JSONType(), nullable=True),
        sa.Column('new_value', JSONType(), nullable=True),
        sa.Column('changed_fields', JSONType(), nullable=True),
        sa.Column('performed_by', GUID(), nullable=False),
        sa.Column('performed_on', UTCDateTime(), nullable=False),
        sa.Column('performed_via', sa.String(20), nullable=False),
        sa.Column('parent_entity_type', sa.String(60), nullable=True),
        sa.Column('parent_entity_id', GUID(), nullable=True),
        sa.Column('transaction_id', GUID(), nullable=False),
        sa.Column('request_id', sa.String(64), nullable=True),
        sa.Column('session_id', GUID(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('reason', sa.String(500), nullable=True),
        sa.Column('payload_schema', sa.SmallInteger(), nullable=False, server_default=sa.text('1')),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
        sa.ForeignKeyConstraint(['created_by'], ['app_user.id'], name='fk_audit_log__created_by', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['deleted_by'], ['app_user.id'], name='fk_audit_log__deleted_by', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['performed_by'], ['app_user.id'], name='fk_audit_log__performed_by', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['updated_by'], ['app_user.id'], name='fk_audit_log__updated_by', ondelete='RESTRICT'),
        sa.CheckConstraint("action IN ('CREATE', 'UPDATE', 'DELETE', 'RESTORE', 'HARD_DELETE', 'EXPORT', 'ANONYMIZE')", name='ck_audit_log__action'),
        sa.CheckConstraint('length(action) <= 20', name='ck_audit_log__action_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('changed_fields IS NULL OR json_valid(changed_fields)', name='ck_audit_log__changed_fields_json').ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')", name='ck_audit_log__created_by_format').ddl_if(dialect="sqlite"),
        sa.CheckConstraint("deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))", name='ck_audit_log__deleted_by_format').ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(entity_id) = 32 AND entity_id NOT GLOB '*[^0-9a-f]*' AND substr(entity_id, 13, 1) = '7' AND substr(entity_id, 17, 1) IN ('8', '9', 'a', 'b')", name='ck_audit_log__entity_id_format').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('length(entity_type) <= 60', name='ck_audit_log__entity_type_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint("entity_type ~ '^[a-z][a-z0-9_]{1,59}$'", name='ck_audit_log__entity_type_pattern').ddl_if(dialect="postgresql"),
        sa.CheckConstraint("length(entity_type) BETWEEN 2 AND 60 AND entity_type NOT GLOB '*[^a-z0-9_]*' AND substr(entity_type, 1, 1) BETWEEN 'a' AND 'z'", name='ck_audit_log__entity_type_pattern').ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')", name='ck_audit_log__id_format').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('is_deleted = false AND version = 1', name='ck_audit_log__immutable_contract'),
        sa.CheckConstraint('length(ip_address) <= 45', name='ck_audit_log__ip_address_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('is_deleted IN (0, 1)', name='ck_audit_log__is_deleted_bool').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('new_value IS NULL OR json_valid(new_value)', name='ck_audit_log__new_value_json').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('old_value IS NULL OR json_valid(old_value)', name='ck_audit_log__old_value_json').ddl_if(dialect="sqlite"),
        sa.CheckConstraint("parent_entity_id IS NULL OR (length(parent_entity_id) = 32 AND parent_entity_id NOT GLOB '*[^0-9a-f]*' AND substr(parent_entity_id, 13, 1) = '7' AND substr(parent_entity_id, 17, 1) IN ('8', '9', 'a', 'b'))", name='ck_audit_log__parent_entity_id_format').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('length(parent_entity_type) <= 60', name='ck_audit_log__parent_entity_type_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('(parent_entity_type IS NULL) = (parent_entity_id IS NULL)', name='ck_audit_log__parent_pair'),
        sa.CheckConstraint("length(performed_by) = 32 AND performed_by NOT GLOB '*[^0-9a-f]*' AND substr(performed_by, 13, 1) = '7' AND substr(performed_by, 17, 1) IN ('8', '9', 'a', 'b')", name='ck_audit_log__performed_by_format').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('performed_by = created_by AND performed_on = created_on', name='ck_audit_log__performed_matches_contract'),
        sa.CheckConstraint("performed_via IN ('API', 'PUBLIC_FORM', 'SYSTEM_JOB', 'MIGRATION', 'CLI')", name='ck_audit_log__performed_via'),
        sa.CheckConstraint('length(performed_via) <= 20', name='ck_audit_log__performed_via_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('length(reason) <= 500', name='ck_audit_log__reason_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('length(request_id) <= 64', name='ck_audit_log__request_id_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint("session_id IS NULL OR (length(session_id) = 32 AND session_id NOT GLOB '*[^0-9a-f]*' AND substr(session_id, 13, 1) = '7' AND substr(session_id, 17, 1) IN ('8', '9', 'a', 'b'))", name='ck_audit_log__session_id_format').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)', name='ck_audit_log__soft_delete_consistent'),
        sa.CheckConstraint("length(transaction_id) = 32 AND transaction_id NOT GLOB '*[^0-9a-f]*' AND substr(transaction_id, 13, 1) = '7' AND substr(transaction_id, 17, 1) IN ('8', '9', 'a', 'b')", name='ck_audit_log__transaction_id_format').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('updated_on >= created_on', name='ck_audit_log__updated_after_created'),
        sa.CheckConstraint("length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')", name='ck_audit_log__updated_by_format').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('length(user_agent) <= 500', name='ck_audit_log__user_agent_len').ddl_if(dialect="sqlite"),
        sa.CheckConstraint('version >= 1', name='ck_audit_log__version_positive'),
    )
    op.create_index('ix_audit_log__entity', "audit_log", ['entity_type', 'entity_id', sa.text('performed_on DESC')])
    op.create_index('ix_audit_log__parent', "audit_log", ['parent_entity_type', 'parent_entity_id', sa.text('performed_on DESC')], sqlite_where=sa.text('parent_entity_id IS NOT NULL'), postgresql_where=sa.text('parent_entity_id IS NOT NULL'))
    op.create_index('ix_audit_log__performed_by', "audit_log", ['performed_by', sa.text('performed_on DESC')])
    op.create_index('ix_audit_log__performed_on', "audit_log", [sa.text('performed_on DESC')])
    op.create_index('ix_audit_log__transaction_id', "audit_log", ['transaction_id'])
    # --- end generated DDL ---
    bind = op.get_bind()
    ms.create_immutability_guards(bind, "audit_log")
    ms.backfill_audit(bind, ["app_user", "role", "permission", "role_permission"])


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")

