"""Customer Project Portal tables (migration 0209_customer_portal).

The portal's only new concept is the customer's identity; everything it shows is read from the modules that own it.

- ``portal_account``: one customer (a person), by normalised email. Not an ``app_user``: a customer never holds a
  staff session, role or permission, and never appears in a staff list (implementation map, "Identity decision").
- ``portal_access``: which enquiries (leads) an account may see, granted and revoked by staff. Everything the portal
  shows is reached through an ACTIVE access row; there is no other path from an account to data.
- ``portal_sign_in``: a single-use sign-in link (invitation or sign-in). The link's token is derived from the row id
  (``derive_action_token``), so nothing secret is stored.
- ``portal_session``: a signed-in browser; only the opaque token's SHA-256 is stored.
- ``portal_event``: the immutable record of access and sign-in (codes and ids only; database triggers refuse update
  and delete).
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from veda.kernel.base import AuditedBase, in_check, live_where, where
from veda.kernel.types import GUID, JSONType, UTCDateTime

from . import vocab as V


def _fk(target: str):
    return ForeignKey(target, ondelete="RESTRICT")


class PortalAccount(AuditedBase):
    __tablename__ = "portal_account"

    email_normalized: Mapped[str] = mapped_column(sa.String(254), nullable=False)
    email_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)  # keyed HMAC: sign-in requests find it
    display_name: Mapped[str] = mapped_column(sa.String(150), nullable=False)
    # The enquiry the display name was copied from (staff gave no name), so erasing that enquiry renames the account;
    # null when staff chose the name. Never another person's name: see erasure.erase_for_lead.
    name_source_lead_id: Mapped[str | None] = mapped_column(GUID(), _fk("lead.id"))
    status: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="ACTIVE")
    last_signed_in_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    erased_on: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (
        in_check("portal_account", "status", V.ACCOUNT_STATUSES),
        CheckConstraint("erased_on IS NULL OR status = 'DISABLED'", name="ck_portal_account__erased"),
        Index("ux_portal_account__email", "email_normalized", unique=True, **live_where()),
        Index("ux_portal_account__email_hash", "email_hash", unique=True, **live_where()),
        CheckConstraint("length(email_hash) = 64", name="ck_portal_account__email_hash_len"),
        Index("ix_portal_account__name_source", "name_source_lead_id"),
    )


class PortalAccess(AuditedBase):
    __tablename__ = "portal_access"

    account_id: Mapped[str] = mapped_column(GUID(), _fk("portal_account.id"), nullable=False)
    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    relationship: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="ACTIVE")
    revoked_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    revoke_reason_code: Mapped[str | None] = mapped_column(sa.String(16))

    __table_args__ = (
        in_check("portal_access", "status", V.ACCESS_STATUSES),
        in_check("portal_access", "relationship", V.RELATIONSHIPS),
        in_check("portal_access", "revoke_reason_code", V.ACCESS_REVOKE_REASONS, nullable=True),
        CheckConstraint(
            "(status = 'REVOKED') = (revoked_on IS NOT NULL AND revoke_reason_code IS NOT NULL)",
            name="ck_portal_access__revoked",
        ),
        # One active access per account and enquiry: granting again is refused, never duplicated.
        Index(
            "ux_portal_access__active",
            "account_id",
            "lead_id",
            unique=True,
            **where("status = 'ACTIVE' AND is_deleted = 0", "status = 'ACTIVE' AND is_deleted = false"),
        ),
        Index("ix_portal_access__lead_id", "lead_id"),
        Index("ix_portal_access__account_id", "account_id"),
    )


class PortalSignIn(AuditedBase):
    __tablename__ = "portal_sign_in"

    account_id: Mapped[str] = mapped_column(GUID(), _fk("portal_account.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(sa.String(12), nullable=False)
    token_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)  # of the derived link token
    expires_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    used_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    invalidated_on: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (
        in_check("portal_sign_in", "purpose", V.SIGN_IN_PURPOSES),
        CheckConstraint("length(token_sha256) = 64", name="ck_portal_sign_in__token_len"),
        CheckConstraint("used_on IS NULL OR invalidated_on IS NULL", name="ck_portal_sign_in__single_outcome"),
        Index("ux_portal_sign_in__token", "token_sha256", unique=True, **live_where()),
        Index("ix_portal_sign_in__account_id", "account_id", "expires_on"),
    )


class PortalSession(AuditedBase):
    __tablename__ = "portal_session"

    account_id: Mapped[str] = mapped_column(GUID(), _fk("portal_account.id"), nullable=False)
    sign_in_id: Mapped[str] = mapped_column(GUID(), _fk("portal_sign_in.id"), nullable=False)
    token_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    last_seen_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    idle_expires_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    absolute_expires_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    ended_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    end_reason_code: Mapped[str | None] = mapped_column(sa.String(16))

    __table_args__ = (
        in_check("portal_session", "end_reason_code", V.SESSION_END_REASONS, nullable=True),
        CheckConstraint("length(token_sha256) = 64", name="ck_portal_session__token_len"),
        CheckConstraint("(ended_on IS NULL) = (end_reason_code IS NULL)", name="ck_portal_session__ended"),
        Index("ux_portal_session__token", "token_sha256", unique=True, **live_where()),
        Index("ix_portal_session__account_id", "account_id"),
        Index("ix_portal_session__sign_in_id", "sign_in_id", unique=True, **live_where()),
    )


class PortalEvent(AuditedBase):
    """Immutable: the actor is ``created_by`` (staff, or the anonymous actor for the customer), the account is named."""

    __tablename__ = "portal_event"

    account_id: Mapped[str] = mapped_column(GUID(), _fk("portal_account.id"), nullable=False)
    lead_id: Mapped[str | None] = mapped_column(GUID(), _fk("lead.id"))
    event_code: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)  # codes and ids only

    __table_args__ = (
        in_check("portal_event", "event_code", V.EVENTS),
        CheckConstraint("is_deleted = false AND version = 1", name="ck_portal_event__immutable_contract"),
        Index("ix_portal_event__account", "account_id", "created_on"),
        Index("ix_portal_event__lead_id", "lead_id"),
    )


TABLES = ("portal_account", "portal_access", "portal_sign_in", "portal_session", "portal_event")
