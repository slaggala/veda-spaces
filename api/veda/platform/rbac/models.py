"""RBAC tables (03 §4.3–§4.7) and dual-control requests (03 §5.8)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from veda.kernel.base import AuditedBase, Bool, in_check, live_where, sqlite_check, where
from veda.kernel.types import GUID, JSONType, UTCDateTime

SCOPES = ("ALL", "TEAM", "OWN")
EFFECTS = ("GRANT", "DENY")
GRANT_PATHS = ("STANDARD", "FOUNDER_WORKFLOW_ONLY")
SENSITIVITY_CLASSES = ("ACCOUNT_CONTROL", "ACCESS_CONTROL", "SECURITY_DATA", "BULK_DATA", "DESTRUCTIVE")

APPROVAL_CLASSES = ("STANDARD", "FOUNDER")
STANDARD_ACTIONS = ("MFA_RESET", "EMAIL_CHANGE")
FOUNDER_ACTIONS = (
    "GRANT_FOUNDER",
    "REVOKE_FOUNDER",
    "FOUNDER_MFA_RESET",
    "FOUNDER_STATUS_CHANGE",
    "FOUNDER_EMAIL_CHANGE",
)
APPROVAL_CHANNELS = ("IN_APP", "BREAK_GLASS")
APPROVAL_STATUSES = ("PENDING", "APPROVED", "DENIED", "EXPIRED", "CANCELLED", "EXECUTED", "FAILED")


class Role(AuditedBase):
    __tablename__ = "role"

    code: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    name_normalized: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.String(500))
    is_system: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    is_assignable: Mapped[bool] = mapped_column(Bool(), nullable=False, default=True, server_default=sa.true())
    grant_path: Mapped[str] = mapped_column(
        sa.String(25), nullable=False, default="STANDARD", server_default="STANDARD"
    )
    mfa_required: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    sort_order: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=100, server_default=sa.text("100"))

    __table_args__ = (
        in_check("role", "grant_path", GRANT_PATHS),
        sqlite_check(
            "length(code) BETWEEN 2 AND 50 AND code NOT GLOB '*[^A-Z0-9_]*' AND substr(code, 1, 1) BETWEEN 'A' AND 'Z'",
            "ck_role__code_pattern",
        ),
        CheckConstraint("code ~ '^[A-Z][A-Z0-9_]{1,49}$'", name="ck_role__code_pattern").ddl_if(dialect="postgresql"),
        Index("ux_role__code", "code", unique=True, **live_where()),
        Index("ux_role__name_normalized", "name_normalized", unique=True, **live_where()),
    )


class Permission(AuditedBase):
    __tablename__ = "permission"

    code: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    module: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    resource: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    action: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.String(500))
    supports_scope: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    is_sensitive: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    sensitivity_class: Mapped[str | None] = mapped_column(sa.String(20))
    grant_path: Mapped[str] = mapped_column(
        sa.String(25), nullable=False, default="STANDARD", server_default="STANDARD"
    )
    is_system: Mapped[bool] = mapped_column(Bool(), nullable=False, default=True, server_default=sa.true())
    requirement_ref: Mapped[str | None] = mapped_column(sa.String(50))

    __table_args__ = (
        in_check("permission", "sensitivity_class", SENSITIVITY_CLASSES, nullable=True),
        in_check("permission", "grant_path", GRANT_PATHS),
        CheckConstraint("is_sensitive = (sensitivity_class IS NOT NULL)", name="ck_permission__sensitivity"),
        sqlite_check(
            "code NOT GLOB '*[^a-z0-9_.]*' AND substr(code, 1, 1) BETWEEN 'a' AND 'z' AND code LIKE '%.%' "
            "AND code NOT LIKE '%..%' AND code NOT LIKE '%.' AND code NOT LIKE '%.%.%.%.%'",
            "ck_permission__code_pattern",
        ),
        CheckConstraint(
            "code ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*){1,3}$'", name="ck_permission__code_pattern"
        ).ddl_if(dialect="postgresql"),
        Index("ux_permission__code", "code", unique=True, **live_where()),
        Index("ix_permission__module_resource", "module", "resource"),
    )


class UserRole(AuditedBase):
    __tablename__ = "user_role"

    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False)
    role_id: Mapped[str] = mapped_column(GUID(), ForeignKey("role.id", ondelete="RESTRICT"), nullable=False)
    valid_from: Mapped[datetime | None] = mapped_column(UTCDateTime())
    valid_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reason: Mapped[str | None] = mapped_column(sa.String(500))

    __table_args__ = (
        CheckConstraint(
            "valid_from IS NULL OR valid_until IS NULL OR valid_until > valid_from", name="ck_user_role__validity_order"
        ),
        Index("ux_user_role__user_role", "user_id", "role_id", unique=True, **live_where()),
        Index("ix_user_role__role_id", "role_id", **live_where()),
    )


class RolePermission(AuditedBase):
    __tablename__ = "role_permission"

    role_id: Mapped[str] = mapped_column(GUID(), ForeignKey("role.id", ondelete="RESTRICT"), nullable=False)
    permission_id: Mapped[str] = mapped_column(GUID(), ForeignKey("permission.id", ondelete="RESTRICT"), nullable=False)
    scope: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="ALL", server_default="ALL")

    __table_args__ = (
        in_check("role_permission", "scope", SCOPES),
        Index("ux_role_permission__role_perm", "role_id", "permission_id", unique=True, **live_where()),
        Index("ix_role_permission__permission_id", "permission_id", **live_where()),
    )


class UserPermission(AuditedBase):
    __tablename__ = "user_permission"

    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False)
    permission_id: Mapped[str] = mapped_column(GUID(), ForeignKey("permission.id", ondelete="RESTRICT"), nullable=False)
    effect: Mapped[str] = mapped_column(sa.String(5), nullable=False, default="GRANT", server_default="GRANT")
    scope: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="ALL", server_default="ALL")
    valid_from: Mapped[datetime | None] = mapped_column(UTCDateTime())
    valid_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reason: Mapped[str] = mapped_column(sa.String(500), nullable=False)

    __table_args__ = (
        in_check("user_permission", "effect", EFFECTS),
        in_check("user_permission", "scope", SCOPES),
        CheckConstraint(
            "valid_from IS NULL OR valid_until IS NULL OR valid_until > valid_from",
            name="ck_user_permission__validity_order",
        ),
        Index("ux_user_permission__user_perm", "user_id", "permission_id", unique=True, **live_where()),
        Index("ix_user_permission__permission_id", "permission_id", **live_where()),
    )


class AdminApprovalRequest(AuditedBase):
    __tablename__ = "admin_approval_request"

    action_class: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    action_type: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    channel: Mapped[str] = mapped_column(sa.String(12), nullable=False, default="IN_APP", server_default="IN_APP")
    target_user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False)
    requested_by: Mapped[str] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    reason: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(12), nullable=False, default="PENDING", server_default="PENDING")
    status_reason: Mapped[str | None] = mapped_column(sa.String(30))
    approver_user_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"))
    external_requester_ref: Mapped[str | None] = mapped_column(sa.String(2048))
    external_approver_ref: Mapped[str | None] = mapped_column(sa.String(2048))
    external_approver_human: Mapped[str | None] = mapped_column(sa.String(200))
    decided_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    decision_reason: Mapped[str | None] = mapped_column(sa.String(1000))
    not_before: Mapped[datetime | None] = mapped_column(UTCDateTime())
    expires_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    executed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (
        in_check("admin_approval_request", "action_class", APPROVAL_CLASSES),
        in_check("admin_approval_request", "action_type", STANDARD_ACTIONS + FOUNDER_ACTIONS),
        in_check("admin_approval_request", "channel", APPROVAL_CHANNELS),
        in_check("admin_approval_request", "status", APPROVAL_STATUSES),
        CheckConstraint(
            "approver_user_id IS NULL OR (approver_user_id <> requested_by AND approver_user_id <> target_user_id)",
            name="ck_admin_approval_request__approver_distinct",
        ),
        CheckConstraint(
            "requested_by <> target_user_id OR (action_type = 'REVOKE_FOUNDER' AND channel = 'IN_APP')",
            name="ck_admin_approval_request__no_self_target",
        ),
        CheckConstraint(
            "approver_user_id IS NULL OR approver_user_id <> requested_by",
            name="ck_admin_approval_request__no_self_approval",
        ),
        CheckConstraint(
            "(action_class = 'FOUNDER') = (action_type IN ('GRANT_FOUNDER','REVOKE_FOUNDER','FOUNDER_MFA_RESET',"
            "'FOUNDER_STATUS_CHANGE','FOUNDER_EMAIL_CHANGE'))",
            name="ck_admin_approval_request__class_matches_type",
        ),
        CheckConstraint(
            "external_approver_ref IS NULL OR external_requester_ref IS NULL OR external_approver_ref <> external_requester_ref",
            name="ck_admin_approval_request__external_distinct",
        ),
        CheckConstraint("is_deleted = false", name="ck_admin_approval_request__never_deleted"),
        Index("ix_admin_approval_request__pending", "status", "expires_on", **where("status = 'PENDING'")),
        Index("ix_admin_approval_request__target", "target_user_id", sa.text("created_on DESC")),
        Index(
            "ux_admin_approval_request__open_per_target_action",
            "target_user_id",
            "action_type",
            unique=True,
            **where("status IN ('PENDING','APPROVED')"),
        ),
        Index(
            "ux_admin_approval_request__open_founder_target",
            "target_user_id",
            unique=True,
            **where("action_class = 'FOUNDER' AND status IN ('PENDING','APPROVED')"),
        ),
    )
