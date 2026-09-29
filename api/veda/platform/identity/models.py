"""Identity tables (03 §4.1, §4.2). The User entity's table is ``app_user`` (ADR-001)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from veda.kernel.base import AuditedBase, Bool, in_check, live_where, where
from veda.kernel.types import GUID, UTCDateTime

USER_TYPES = ("HUMAN", "SYSTEM")
USER_STATUSES = ("INVITED", "ACTIVE", "LOCKED", "DISABLED")
PROTECTION_LEVELS = ("STANDARD", "FOUNDER")
PROFILE_FIELDS = ("full_name", "display_name", "phone_e164", "timezone", "locale")


class User(AuditedBase):
    __tablename__ = "app_user"

    email: Mapped[str] = mapped_column(sa.String(254), nullable=False)
    email_normalized: Mapped[str] = mapped_column(sa.String(254), nullable=False)
    full_name: Mapped[str] = mapped_column(sa.String(150), nullable=False)
    display_name: Mapped[str | None] = mapped_column(sa.String(80))
    phone_e164: Mapped[str | None] = mapped_column(sa.String(16))
    user_type: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="HUMAN", server_default="HUMAN")
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="INVITED", server_default="INVITED")
    status_changed_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    timezone: Mapped[str] = mapped_column(sa.String(40), nullable=False, default="Asia/Kolkata", server_default="Asia/Kolkata")
    locale: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="en-IN", server_default="en-IN")
    email_verified_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # Added by 0008_account_security (05 §8.6, 06 §7.2, 05 §11.5)
    proposed_email: Mapped[str | None] = mapped_column(sa.String(254))
    proposed_email_normalized: Mapped[str | None] = mapped_column(sa.String(254))
    proposed_email_requested_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    proposed_email_requested_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"))
    protection_level: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="STANDARD", server_default="STANDARD")
    mfa_required: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    security_cooling_off_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    authz_version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1, server_default=sa.text("1"))
    last_login_on: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (
        in_check("app_user", "status", USER_STATUSES),
        in_check("app_user", "user_type", USER_TYPES),
        in_check("app_user", "protection_level", PROTECTION_LEVELS),
        CheckConstraint("email_normalized = lower(email_normalized)", name="ck_app_user__email_normalized_lower"),
        CheckConstraint("(proposed_email IS NULL) = (proposed_email_normalized IS NULL)", name="ck_app_user__proposed_email_pair"),
        CheckConstraint(
            "proposed_email_normalized IS NULL OR proposed_email_normalized <> email_normalized",
            name="ck_app_user__proposed_email_differs",
        ),
        CheckConstraint("authz_version >= 1", name="ck_app_user__authz_version_positive"),
        Index("ux_app_user__email_normalized", "email_normalized", unique=True, **live_where()),
        Index("ix_app_user__status", "status", **live_where()),
        Index("ix_app_user__full_name", "full_name"),
        Index(
            "ux_app_user__proposed_email", "proposed_email_normalized", unique=True,
            **where("proposed_email_normalized IS NOT NULL AND is_deleted = 0",
                    "proposed_email_normalized IS NOT NULL AND is_deleted = false"),
        ),
    )

    @property
    def label(self) -> str:
        return self.display_name or self.full_name


class UserCredential(AuditedBase):
    __tablename__ = "user_credential"

    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(sa.String(255))
    password_changed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    must_change_password: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    failed_login_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0, server_default=sa.text("0"))
    failed_window_started_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (
        CheckConstraint("failed_login_count >= 0", name="ck_user_credential__failed_login_count"),
        Index("ux_user_credential__user_id", "user_id", unique=True, **live_where()),
    )
