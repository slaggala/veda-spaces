"""Authentication, MFA and security-event tables (03 §5.1–§5.7, ADR-004, ADR-006)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from veda.kernel.base import AuditedBase, in_check, live_where, sqlite_check, where
from veda.kernel.types import GUID, JSONType, UTCDateTime

SESSION_TYPES = ("FULL", "RECOVERY")
REVOKE_REASONS = (
    "LOGOUT", "LOGOUT_ALL", "ADMIN_REVOKE", "PASSWORD_CHANGED", "PASSWORD_RESET", "USER_DISABLED", "TOKEN_REUSE",
    "MFA_RESET", "MFA_RECOVERY", "RECOVERY_COMPLETED", "EMAIL_CHANGED", "EXPIRED",
)
ACTION_TOKEN_PURPOSES = (
    "PASSWORD_RESET", "INVITE", "MFA_ENROLLMENT", "EMAIL_VERIFICATION", "EMAIL_CHANGE_CANCEL", "APPROVAL_CANCEL",
)
FACTOR_TYPES = ("TOTP",)
FACTOR_STATUSES = ("PENDING", "ACTIVE", "REVOKED")
FACTOR_REVOKE_REASONS = ("USER_REMOVED", "ADMIN_RESET", "REPLACED", "ENROLLMENT_ABANDONED", "BREAK_GLASS")
CHALLENGE_PURPOSES = ("LOGIN", "ENROLLMENT", "STEP_UP")
EVENT_CATEGORIES = ("AUTHENTICATION", "SESSION", "PASSWORD", "MFA", "ACCOUNT", "AUTHORIZATION", "PUBLIC_INTAKE")
OUTCOMES = ("SUCCESS", "FAILURE", "BLOCKED")
SEVERITIES = ("INFO", "WARNING", "CRITICAL")


class UserSession(AuditedBase):
    __tablename__ = "user_session"

    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False)
    started_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_seen_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    idle_expires_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    absolute_expires_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    session_type: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="FULL", server_default="FULL")
    auth_methods: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    reauth_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    mfa_verified_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"))
    revoke_reason: Mapped[str | None] = mapped_column(sa.String(30))
    ip_address: Mapped[str | None] = mapped_column(sa.String(45))
    user_agent: Mapped[str | None] = mapped_column(sa.String(500))
    device_label: Mapped[str | None] = mapped_column(sa.String(100))

    __table_args__ = (
        in_check("user_session", "session_type", SESSION_TYPES),
        in_check("user_session", "revoke_reason", REVOKE_REASONS, nullable=True),
        in_check("user_session", "auth_methods", ("pwd", "pwd+totp", "pwd+recovery")),
        CheckConstraint("is_deleted = false", name="ck_user_session__never_deleted"),
        Index("ix_user_session__user_active", "user_id", **where("revoked_on IS NULL")),
        Index("ix_user_session__absolute_expires_on", "absolute_expires_on"),
    )

    @property
    def methods(self) -> list[str]:
        return self.auth_methods.split("+")


class RefreshToken(AuditedBase):
    __tablename__ = "refresh_token"

    session_id: Mapped[str] = mapped_column(GUID(), ForeignKey("user_session.id", ondelete="RESTRICT"), nullable=False)
    token_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    issued_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    expires_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    used_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    replaced_by_id: Mapped[str | None] = mapped_column(GUID())  # non-FK correlation (EXC-009)
    grace_used_on: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (
        CheckConstraint("is_deleted = false", name="ck_refresh_token__never_deleted"),
        Index("ux_refresh_token__token_hash", "token_hash", unique=True),
        Index("ix_refresh_token__session_id", "session_id"),
        Index("ix_refresh_token__expires_on", "expires_on"),
    )


class UserActionToken(AuditedBase):
    __tablename__ = "user_action_token"

    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False)
    purpose: Mapped[str] = mapped_column(sa.String(25), nullable=False)
    token_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    expires_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    sent_to_email_normalized: Mapped[str] = mapped_column(sa.String(254), nullable=False)
    used_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    invalidated_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    requested_ip: Mapped[str | None] = mapped_column(sa.String(45))

    __table_args__ = (
        in_check("user_action_token", "purpose", ACTION_TOKEN_PURPOSES),
        CheckConstraint("is_deleted = false", name="ck_user_action_token__never_deleted"),
        Index("ux_user_action_token__token_hash", "token_hash", unique=True),
        Index("ix_user_action_token__user_open", "user_id", "purpose", **where("used_on IS NULL AND invalidated_on IS NULL")),
    )


class UserMfaFactor(AuditedBase):
    __tablename__ = "user_mfa_factor"

    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False)
    factor_type: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="TOTP", server_default="TOTP")
    status: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="PENDING", server_default="PENDING")
    secret_ciphertext: Mapped[str] = mapped_column(sa.Text, nullable=False)
    wrapped_data_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    kms_key_arn: Mapped[str] = mapped_column(sa.String(2048), nullable=False)
    label: Mapped[str | None] = mapped_column(sa.String(100))
    confirmed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_used_step: Mapped[int | None] = mapped_column(sa.BigInteger)
    last_used_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoke_reason: Mapped[str | None] = mapped_column(sa.String(20))

    __table_args__ = (
        in_check("user_mfa_factor", "factor_type", FACTOR_TYPES),
        in_check("user_mfa_factor", "status", FACTOR_STATUSES),
        in_check("user_mfa_factor", "revoke_reason", FACTOR_REVOKE_REASONS, nullable=True),
        CheckConstraint("status <> 'ACTIVE' OR confirmed_on IS NOT NULL", name="ck_user_mfa_factor__active_confirmed"),
        # At most one PENDING and one ACTIVE factor per user and type. `status` is part of the key so an
        # ACTIVE factor and its PENDING replacement can coexist during re-enrollment (05 §11.5, TD-E).
        Index(
            "ux_user_mfa_factor__user_live", "user_id", "factor_type", "status", unique=True,
            **where("status IN ('PENDING','ACTIVE') AND is_deleted = 0", "status IN ('PENDING','ACTIVE') AND is_deleted = false"),
        ),
    )


class UserMfaRecoveryCode(AuditedBase):
    __tablename__ = "user_mfa_recovery_code"

    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False)
    batch_id: Mapped[str] = mapped_column(GUID(), nullable=False)  # registered FK-less group id (EXC-011)
    code_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    used_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    invalidated_on: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (
        CheckConstraint("is_deleted = false", name="ck_user_mfa_recovery_code__never_deleted"),
        Index("ux_user_mfa_recovery_code__hash", "code_hash", unique=True),
        Index("ix_user_mfa_recovery_code__batch", "user_id", "batch_id"),
        Index("ix_user_mfa_recovery_code__user_open", "user_id", **where("used_on IS NULL AND invalidated_on IS NULL")),
    )


class MfaChallenge(AuditedBase):
    __tablename__ = "mfa_challenge"

    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False)
    purpose: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    token_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    session_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("user_session.id", ondelete="RESTRICT"))
    expires_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    failed_attempts: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0, server_default=sa.text("0"))
    completed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    ip_address: Mapped[str | None] = mapped_column(sa.String(45))

    __table_args__ = (
        in_check("mfa_challenge", "purpose", CHALLENGE_PURPOSES),
        CheckConstraint("failed_attempts BETWEEN 0 AND 5", name="ck_mfa_challenge__failed_attempts"),
        CheckConstraint("is_deleted = false", name="ck_mfa_challenge__never_deleted"),
        Index("ux_mfa_challenge__token_hash", "token_hash", unique=True),
        Index("ix_mfa_challenge__expires_on", "expires_on"),
    )


class SecurityEventLog(AuditedBase):
    __tablename__ = "security_event_log"

    event_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    event_category: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    outcome: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    severity: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="INFO", server_default="INFO")
    subject_user_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"))
    session_id: Mapped[str | None] = mapped_column(GUID())  # non-FK correlation (EXC-009)
    email_attempted_hash: Mapped[str | None] = mapped_column(sa.CHAR(64))
    failure_reason: Mapped[str | None] = mapped_column(sa.String(40))
    permission_code: Mapped[str | None] = mapped_column(sa.String(100))
    target_entity_type: Mapped[str | None] = mapped_column(sa.String(60))
    target_entity_id: Mapped[str | None] = mapped_column(GUID())  # registered FK-less (EXC-011)
    occurred_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(sa.String(45))
    user_agent: Mapped[str | None] = mapped_column(sa.String(500))
    request_id: Mapped[str | None] = mapped_column(sa.String(64))
    detail: Mapped[dict | None] = mapped_column(JSONType())
    chain_seq: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    prev_hash: Mapped[str | None] = mapped_column(sa.CHAR(64))
    chain_key_label: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    row_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)

    __table_args__ = (
        in_check("security_event_log", "event_category", EVENT_CATEGORIES),
        in_check("security_event_log", "outcome", OUTCOMES),
        in_check("security_event_log", "severity", SEVERITIES),
        CheckConstraint("(target_entity_type IS NULL) = (target_entity_id IS NULL)", name="ck_security_event_log__target_pair"),
        CheckConstraint("chain_seq >= 1", name="ck_security_event_log__chain_seq_positive"),
        CheckConstraint("is_deleted = false AND version = 1", name="ck_security_event_log__immutable_contract"),
        Index("ux_security_event_log__chain_seq", "chain_seq", unique=True),
        Index("ix_security_event_log__occurred", sa.text("occurred_on DESC"), sa.text("id DESC")),
        Index("ix_security_event_log__subject", "subject_user_id", sa.text("occurred_on DESC")),
        Index("ix_security_event_log__type", "event_type", sa.text("occurred_on DESC")),
        Index("ix_security_event_log__ip", "ip_address", sa.text("occurred_on DESC")),
        Index(
            "ix_security_event_log__target", "target_entity_type", "target_entity_id", sa.text("occurred_on DESC"),
            **where("target_entity_id IS NOT NULL"),
        ),
        Index("ix_security_event_log__outcome", "outcome", sa.text("occurred_on DESC"), **where("outcome <> 'SUCCESS'")),
    )


# Re-exported for the conformance check (sqlite_check/live_where used above).
__all__ = [
    "MfaChallenge", "RefreshToken", "SecurityEventLog", "UserActionToken", "UserMfaFactor",
    "UserMfaRecoveryCode", "UserSession", "live_where", "sqlite_check",
]
