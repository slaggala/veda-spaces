"""0003_rbac: role, permission, user_role, role_permission, user_permission.

Seeds FOUNDER/ADMIN/SALES, every registry permission and the default matrix
(06 §6), then asserts 06 §3.1 rules 3 and 5 (RBAC-018).

Revision ID: 0003_rbac
Revises: 0002_identity
"""

import sqlalchemy as sa
from alembic import op

from veda.kernel import migration_support as ms  # noqa: F401
from veda.kernel.types import GUID, JSONType, UTCDateTime  # noqa: F401

revision = "0003_rbac"
down_revision = "0002_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- generated DDL (tools/render_migrations.py) ---
    op.create_table(
        "role",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name_normalized", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_assignable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("grant_path", sa.String(25), nullable=False, server_default="STANDARD"),
        sa.Column("mfa_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.PrimaryKeyConstraint("id", name="pk_role"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], name="fk_role__created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["app_user.id"], name="fk_role__deleted_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], name="fk_role__updated_by", ondelete="RESTRICT"),
        sa.CheckConstraint("length(code) <= 50", name="ck_role__code_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("code ~ '^[A-Z][A-Z0-9_]{1,49}$'", name="ck_role__code_pattern").ddl_if(
            dialect="postgresql"
        ),
        sa.CheckConstraint(
            "length(code) BETWEEN 2 AND 50 AND code NOT GLOB '*[^A-Z0-9_]*' AND substr(code, 1, 1) BETWEEN 'A' AND 'Z'",
            name="ck_role__code_pattern",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_role__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_role__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(description) <= 500", name="ck_role__description_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("grant_path IN ('STANDARD', 'FOUNDER_WORKFLOW_ONLY')", name="ck_role__grant_path"),
        sa.CheckConstraint("length(grant_path) <= 25", name="ck_role__grant_path_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_role__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_assignable IN (0, 1)", name="ck_role__is_assignable_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_role__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_system IN (0, 1)", name="ck_role__is_system_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("mfa_required IN (0, 1)", name="ck_role__mfa_required_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(name) <= 100", name="ck_role__name_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(name_normalized) <= 100", name="ck_role__name_normalized_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_role__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_role__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_role__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_role__version_positive"),
    )
    op.create_index(
        "ux_role__code",
        "role",
        ["code"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_role__name_normalized",
        "role",
        ["name_normalized"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "permission",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("resource", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("supports_scope", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sensitivity_class", sa.String(20), nullable=True),
        sa.Column("grant_path", sa.String(25), nullable=False, server_default="STANDARD"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("requirement_ref", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_permission"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], name="fk_permission__created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["app_user.id"], name="fk_permission__deleted_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], name="fk_permission__updated_by", ondelete="RESTRICT"),
        sa.CheckConstraint("length(action) <= 50", name="ck_permission__action_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(code) <= 100", name="ck_permission__code_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "code ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*){1,3}$'", name="ck_permission__code_pattern"
        ).ddl_if(dialect="postgresql"),
        sa.CheckConstraint(
            "code NOT GLOB '*[^a-z0-9_.]*' AND substr(code, 1, 1) BETWEEN 'a' AND 'z' AND code LIKE '%.%' AND code NOT LIKE '%..%' AND code NOT LIKE '%.' AND code NOT LIKE '%.%.%.%.%'",
            name="ck_permission__code_pattern",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_permission__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_permission__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(description) <= 500", name="ck_permission__description_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("grant_path IN ('STANDARD', 'FOUNDER_WORKFLOW_ONLY')", name="ck_permission__grant_path"),
        sa.CheckConstraint("length(grant_path) <= 25", name="ck_permission__grant_path_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_permission__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_permission__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_sensitive IN (0, 1)", name="ck_permission__is_sensitive_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_system IN (0, 1)", name="ck_permission__is_system_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(module) <= 50", name="ck_permission__module_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(name) <= 120", name="ck_permission__name_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(requirement_ref) <= 50", name="ck_permission__requirement_ref_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("length(resource) <= 50", name="ck_permission__resource_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_sensitive = (sensitivity_class IS NOT NULL)", name="ck_permission__sensitivity"),
        sa.CheckConstraint(
            "sensitivity_class IS NULL OR sensitivity_class IN ('ACCOUNT_CONTROL', 'ACCESS_CONTROL', 'SECURITY_DATA', 'BULK_DATA', 'DESTRUCTIVE')",
            name="ck_permission__sensitivity_class",
        ),
        sa.CheckConstraint("length(sensitivity_class) <= 20", name="ck_permission__sensitivity_class_len").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_permission__soft_delete_consistent",
        ),
        sa.CheckConstraint("supports_scope IN (0, 1)", name="ck_permission__supports_scope_bool").ddl_if(
            dialect="sqlite"
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_permission__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_permission__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_permission__version_positive"),
    )
    op.create_index("ix_permission__module_resource", "permission", ["module", "resource"])
    op.create_index(
        "ux_permission__code",
        "permission",
        ["code"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "user_role",
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
        sa.Column("role_id", GUID(), nullable=False),
        sa.Column("valid_from", UTCDateTime(), nullable=True),
        sa.Column("valid_until", UTCDateTime(), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_user_role"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], name="fk_user_role__created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["app_user.id"], name="fk_user_role__deleted_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], name="fk_user_role__role_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], name="fk_user_role__updated_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], name="fk_user_role__user_id", ondelete="RESTRICT"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_user_role__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_user_role__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_user_role__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_user_role__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(reason) <= 500", name="ck_user_role__reason_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(role_id) = 32 AND role_id NOT GLOB '*[^0-9a-f]*' AND substr(role_id, 13, 1) = '7' AND substr(role_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_user_role__role_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_user_role__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_user_role__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_user_role__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(user_id) = 32 AND user_id NOT GLOB '*[^0-9a-f]*' AND substr(user_id, 13, 1) = '7' AND substr(user_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_user_role__user_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "valid_from IS NULL OR valid_until IS NULL OR valid_until > valid_from", name="ck_user_role__validity_order"
        ),
        sa.CheckConstraint("version >= 1", name="ck_user_role__version_positive"),
    )
    op.create_index(
        "ix_user_role__role_id",
        "user_role",
        ["role_id"],
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_user_role__user_role",
        "user_role",
        ["user_id", "role_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "role_permission",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_on", UTCDateTime(), nullable=False),
        sa.Column("updated_on", UTCDateTime(), nullable=False),
        sa.Column("created_by", GUID(), nullable=False),
        sa.Column("updated_by", GUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_on", UTCDateTime(), nullable=True),
        sa.Column("deleted_by", GUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("role_id", GUID(), nullable=False),
        sa.Column("permission_id", GUID(), nullable=False),
        sa.Column("scope", sa.String(10), nullable=False, server_default="ALL"),
        sa.PrimaryKeyConstraint("id", name="pk_role_permission"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_role_permission__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_role_permission__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"], ["permission.id"], name="fk_role_permission__permission_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], name="fk_role_permission__role_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_role_permission__updated_by", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_role_permission__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_role_permission__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_role_permission__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_role_permission__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(permission_id) = 32 AND permission_id NOT GLOB '*[^0-9a-f]*' AND substr(permission_id, 13, 1) = '7' AND substr(permission_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_role_permission__permission_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(role_id) = 32 AND role_id NOT GLOB '*[^0-9a-f]*' AND substr(role_id, 13, 1) = '7' AND substr(role_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_role_permission__role_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("scope IN ('ALL', 'TEAM', 'OWN')", name="ck_role_permission__scope"),
        sa.CheckConstraint("length(scope) <= 10", name="ck_role_permission__scope_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_role_permission__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_role_permission__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_role_permission__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("version >= 1", name="ck_role_permission__version_positive"),
    )
    op.create_index(
        "ix_role_permission__permission_id",
        "role_permission",
        ["permission_id"],
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_role_permission__role_perm",
        "role_permission",
        ["role_id", "permission_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "user_permission",
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
        sa.Column("permission_id", GUID(), nullable=False),
        sa.Column("effect", sa.String(5), nullable=False, server_default="GRANT"),
        sa.Column("scope", sa.String(10), nullable=False, server_default="ALL"),
        sa.Column("valid_from", UTCDateTime(), nullable=True),
        sa.Column("valid_until", UTCDateTime(), nullable=True),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_user_permission"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name="fk_user_permission__created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_user_permission__deleted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"], ["permission.id"], name="fk_user_permission__permission_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], name="fk_user_permission__updated_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], name="fk_user_permission__user_id", ondelete="RESTRICT"),
        sa.CheckConstraint(
            "length(created_by) = 32 AND created_by NOT GLOB '*[^0-9a-f]*' AND substr(created_by, 13, 1) = '7' AND substr(created_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_user_permission__created_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "deleted_by IS NULL OR (length(deleted_by) = 32 AND deleted_by NOT GLOB '*[^0-9a-f]*' AND substr(deleted_by, 13, 1) = '7' AND substr(deleted_by, 17, 1) IN ('8', '9', 'a', 'b'))",
            name="ck_user_permission__deleted_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("effect IN ('GRANT', 'DENY')", name="ck_user_permission__effect"),
        sa.CheckConstraint("length(effect) <= 5", name="ck_user_permission__effect_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(id) = 32 AND id NOT GLOB '*[^0-9a-f]*' AND substr(id, 13, 1) = '7' AND substr(id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_user_permission__id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("is_deleted IN (0, 1)", name="ck_user_permission__is_deleted_bool").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(permission_id) = 32 AND permission_id NOT GLOB '*[^0-9a-f]*' AND substr(permission_id, 13, 1) = '7' AND substr(permission_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_user_permission__permission_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint("length(reason) <= 500", name="ck_user_permission__reason_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint("scope IN ('ALL', 'TEAM', 'OWN')", name="ck_user_permission__scope"),
        sa.CheckConstraint("length(scope) <= 10", name="ck_user_permission__scope_len").ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "(is_deleted = false AND deleted_on IS NULL AND deleted_by IS NULL) OR (is_deleted = true AND deleted_on IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_user_permission__soft_delete_consistent",
        ),
        sa.CheckConstraint("updated_on >= created_on", name="ck_user_permission__updated_after_created"),
        sa.CheckConstraint(
            "length(updated_by) = 32 AND updated_by NOT GLOB '*[^0-9a-f]*' AND substr(updated_by, 13, 1) = '7' AND substr(updated_by, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_user_permission__updated_by_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "length(user_id) = 32 AND user_id NOT GLOB '*[^0-9a-f]*' AND substr(user_id, 13, 1) = '7' AND substr(user_id, 17, 1) IN ('8', '9', 'a', 'b')",
            name="ck_user_permission__user_id_format",
        ).ddl_if(dialect="sqlite"),
        sa.CheckConstraint(
            "valid_from IS NULL OR valid_until IS NULL OR valid_until > valid_from",
            name="ck_user_permission__validity_order",
        ),
        sa.CheckConstraint("version >= 1", name="ck_user_permission__version_positive"),
    )
    op.create_index(
        "ix_user_permission__permission_id",
        "user_permission",
        ["permission_id"],
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ux_user_permission__user_perm",
        "user_permission",
        ["user_id", "permission_id"],
        unique=True,
        sqlite_where=sa.text("is_deleted = 0"),
        postgresql_where=sa.text("is_deleted = false"),
    )
    # --- end generated DDL ---
    bind = op.get_bind()
    ms.sync_permissions(bind, audit=False)  # audit_log arrives in 0005, which backfills CREATE rows
    ms.seed_roles_and_matrix(bind, audit=False)
    ms.assert_rbac_seed(bind)


def downgrade() -> None:
    # Expand-only migrations; no down-migrations are relied on (02 §12.4).
    raise NotImplementedError("down-migrations are not supported")
