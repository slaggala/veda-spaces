"""Customer identity for the portal (CPP-001, CPP-002): accounts, access, passwordless sign-in and sessions.

**Access.** Staff give an account access to one enquiry (lead) with ``grant``. The account is found or created by the
normalised email; one ACTIVE access per account and lead. ``revoke`` ends one access; an account left without any
ACTIVE access has its sessions ended at once. Every request re-reads the account's ACTIVE access rows, so a revocation
applies from the next request.

**Sign-in.** Passwordless, by email link. ``request_sign_in`` answers the same whether or not the email has access
(nothing is disclosed) and sends a link only to an ACTIVE account with at least one ACTIVE access to a live enquiry.
The link's token is derived from its row id and only its SHA-256 is stored; it works once, expires (15 minutes for a
sign-in, 72 hours for an invitation) and every new link invalidates the account's earlier unused ones. The link
carries the token in the URL fragment, which the browser never sends to a server; the page posts it.

**Sessions.** ``start_session`` exchanges a link for an opaque session token (returned once; SHA-256 stored), sent by
the page only in the ``X-Veda-Portal`` header. A session ends on sign-out, revocation of the last access, account
disablement or lead erasure, 30 minutes idle, or 12 hours after sign-in. A portal session is not a staff session:
staff routes never read this header, and portal routes never read a staff token.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db
from veda.kernel.dto import normalize_email
from veda.kernel.errors import ApiError, field_error
from veda.kernel.ids import new_id
from veda.modules.crm.leads.models import Lead
from veda.platform.auth.crypto import new_opaque_token, sha256_hex

from . import events
from .models import PortalAccess, PortalAccount, PortalSession, PortalSignIn

HEADER = "X-Veda-Portal"
SESSION_PREFIX = "vpp_"
SESSION_RE = re.compile(r"^vpp_[A-Za-z0-9_-]{43}$")
LINK_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
INVITATION_TTL = timedelta(hours=72)
SIGN_IN_TTL = timedelta(minutes=15)
RESEND_GAP = timedelta(seconds=60)  # one sign-in email per account per minute, whatever is asked
DAILY_SIGN_IN_LINKS = 10  # and at most this many sign-in emails per account per 24 hours, from any network
IDLE_TTL = timedelta(minutes=30)
ABSOLUTE_TTL = timedelta(hours=12)
TOUCH_GAP = timedelta(minutes=1)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class Principal:
    """The signed-in customer of one request."""

    session: PortalSession
    account: PortalAccount


def session_invalid() -> ApiError:
    return ApiError(401, "PORTAL_SESSION_INVALID", "Please sign in to your project portal.")


def link_invalid() -> ApiError:
    return ApiError(400, "PORTAL_LINK_INVALID", "This sign-in link has expired or was already used. Please ask for a "
                    "new one.")  # fmt: skip


# --- access (staff) ----------------------------------------------------------------------------------------------------
def active_access(s: Session, account_id: str) -> list[PortalAccess]:
    """The account's ACTIVE access rows to live enquiries: the only path from an account to any data."""
    return list(
        s.execute(
            sa.select(PortalAccess)
            .join(Lead, Lead.id == PortalAccess.lead_id)
            .where(
                PortalAccess.account_id == account_id,
                PortalAccess.status == "ACTIVE",
                Lead.is_deleted == sa.false(),
                Lead.anonymized_on.is_(None),
            )  # fmt: skip
            .order_by(PortalAccess.created_on)
        ).scalars()
    )


def _lock_lead(s: Session, lead_id: str) -> None:
    if s.get_bind().dialect.name == "postgresql":
        s.execute(sa.select(Lead.id).where(Lead.id == lead_id).with_for_update())


def _account(s: Session, email: str, display_name: str, name_source_lead_id: str | None) -> PortalAccount:
    found = s.execute(sa.select(PortalAccount).where(PortalAccount.email_normalized == email)).scalar_one_or_none()
    if found is not None:
        return found  # an existing account keeps its name: a second enquiry never renames anyone
    account = PortalAccount(email_normalized=email, email_hash=email_hash(email), display_name=display_name,
                            status="ACTIVE", name_source_lead_id=name_source_lead_id)  # fmt: skip
    try:
        with s.begin_nested():  # two invitations of one new email at once: the second finds the first's row
            s.add(account)
            s.flush()
    except sa.exc.IntegrityError:
        account = s.execute(sa.select(PortalAccount).where(PortalAccount.email_normalized == email)).scalar_one()
    return account


def grant(s: Session, ctx, lead: Lead, body) -> PortalAccess:
    _lock_lead(s, lead.id)
    s.refresh(lead)
    if lead.anonymized_on is not None or lead.is_deleted:
        raise ApiError(409, "INVALID_STATE", "This enquiry's customer record was erased.")
    email = normalize_email(body.email or lead.email or "")
    if not EMAIL_RE.match(email):
        raise ApiError(422, "VALIDATION_FAILED", "A customer email address is needed to invite them.",
                       errors=[field_error("email", "REQUIRED", "An email address the customer reads.")])  # fmt: skip
    chosen = (body.display_name or "").strip()
    account = _account(s, email, (chosen or lead.name).strip()[:150], None if chosen else lead.id)
    if account.status != "ACTIVE":
        raise ApiError(409, "PORTAL_ACCOUNT_DISABLED", "That customer's portal account is disabled.")
    if any(a.lead_id == lead.id for a in active_access(s, account.id)):
        raise ApiError(409, "PORTAL_ACCESS_EXISTS", "That customer already has portal access to this enquiry.")
    access = PortalAccess(account_id=account.id, lead_id=lead.id, relationship=body.relationship, status="ACTIVE")
    s.add(access)
    s.flush()
    events.record(s, account.id, "ACCESS_GRANTED", lead_id=lead.id, access_id=access.id,
                  relationship=access.relationship, by=ctx.user.id)  # fmt: skip
    row = _issue(s, account, "INVITATION")
    events.record(s, account.id, "SIGN_IN_LINK_SENT", lead_id=lead.id, sign_in_id=row.id, purpose=row.purpose)
    return access


def revoke(s: Session, ctx, access: PortalAccess, reason_code: str = "STAFF_REVOKED") -> PortalAccess:
    _lock_lead(s, access.lead_id)
    s.refresh(access)
    if access.status != "ACTIVE":
        raise ApiError(409, "INVALID_STATE", "That portal access has already ended.")
    access.status, access.revoked_on = "REVOKED", db.tx_time(s)
    access.revoked_by = ctx.user.id if ctx is not None and getattr(ctx, "user", None) else None
    access.revoke_reason_code = reason_code
    s.flush()
    events.record(s, access.account_id, "ACCESS_REVOKED", lead_id=access.lead_id, access_id=access.id,
                  reason=reason_code)  # fmt: skip
    if not active_access(s, access.account_id):
        end_sessions(s, access.account_id, "LEAD_ERASED" if reason_code == "LEAD_ERASED" else "ACCESS_REVOKED")
    return access


def end_sessions(s: Session, account_id: str, reason: str) -> int:
    now = db.tx_time(s)
    rows = s.execute(sa.select(PortalSession).where(PortalSession.account_id == account_id,
                                                    PortalSession.ended_on.is_(None))).scalars().all()  # fmt: skip
    for r in rows:
        r.ended_on, r.end_reason_code = now, reason
    return len(rows)


# --- sign-in links -----------------------------------------------------------------------------------------------------
def _issue(s: Session, account: PortalAccount, purpose: str) -> PortalSignIn:
    """A new link invalidates the account's earlier unused links of the same purpose. A sign-in request never cancels
    an invitation (someone who knows the email must not be able to void the link staff sent); a new invitation
    supersedes every earlier unused link."""
    now = db.tx_time(s)
    earlier = sa.select(PortalSignIn).where(PortalSignIn.account_id == account.id, PortalSignIn.used_on.is_(None),
                                            PortalSignIn.invalidated_on.is_(None))  # fmt: skip
    if purpose == "SIGN_IN":
        earlier = earlier.where(PortalSignIn.purpose == "SIGN_IN")
    for old in s.execute(earlier).scalars():
        old.invalidated_on = now
    row = PortalSignIn(account_id=account.id, purpose=purpose, token_sha256="0" * 64,
                       expires_on=now + (INVITATION_TTL if purpose == "INVITATION" else SIGN_IN_TTL))  # fmt: skip
    row.id = new_id()
    row.token_sha256 = sha256_hex(events.sign_in_token(row))
    s.add(row)
    s.flush()
    events.notify_sign_in(s, row)
    return row


def email_hash(email: str) -> str:
    """The keyed hash of a normalised email (the security-event email HMAC): finds an account without the address."""
    from veda.platform.auth.security_events import email_attempt_hash

    return email_attempt_hash(normalize_email(email or ""))


def rehash_emails(s: Session) -> int:
    """Recompute every account's ``email_hash`` from its stored address, after VEDA_EMAIL_HASH_HMAC_KEY is rotated
    (``python -m veda.cli portal-rehash-emails``). Without it, sign-in requests for existing accounts find nothing:
    the request still answers 202 and no email is sent. Idempotent; returns the number of accounts changed."""
    changed = 0
    for account in s.execute(sa.select(PortalAccount).execution_options(include_deleted=True)).scalars():
        fresh = email_hash(account.email_normalized)
        if account.email_hash != fresh:
            account.email_hash = fresh
            changed += 1
    s.flush()
    return changed


def request_sign_in(s: Session, email: str) -> None:
    """Queue the request, and nothing else: one keyed hash and one outbox row, the same work for every address, so
    neither the answer nor its timing says whether the email has access (review F3). The outbox carries the hash, never
    the address; ``issue_requested`` decides in the worker."""
    from veda.kernel import outbox

    outbox.enqueue(s, events.SIGN_IN_REQUESTED, "portal_sign_in_request", new_id(), email_hash=email_hash(email))


def issue_requested(s: Session, hashed: str | None) -> None:
    """In the outbox worker: send a sign-in link if, and only if, the email has an ACTIVE account with ACTIVE access,
    at most one a minute and ``DAILY_SIGN_IN_LINKS`` a day per account."""
    account = s.execute(sa.select(PortalAccount).where(PortalAccount.email_hash == hashed)
                        ).scalar_one_or_none() if hashed else None  # fmt: skip
    if account is None or account.status != "ACTIVE" or not active_access(s, account.id):
        return
    if s.get_bind().dialect.name == "postgresql":
        s.execute(sa.select(PortalAccount.id).where(PortalAccount.id == account.id).with_for_update())
    now = db.tx_time(s)
    recent = s.execute(sa.select(sa.func.max(PortalSignIn.created_on)).where(
        PortalSignIn.account_id == account.id)).scalar()  # fmt: skip
    if recent is not None and now - recent < RESEND_GAP:
        return
    today = s.execute(sa.select(sa.func.count()).select_from(PortalSignIn).where(
        PortalSignIn.account_id == account.id, PortalSignIn.purpose == "SIGN_IN",
        PortalSignIn.created_on > now - timedelta(hours=24))).scalar() or 0  # fmt: skip
    if today >= DAILY_SIGN_IN_LINKS:
        return
    row = _issue(s, account, "SIGN_IN")
    events.record(s, account.id, "SIGN_IN_LINK_SENT", sign_in_id=row.id, purpose=row.purpose)


# --- sessions ----------------------------------------------------------------------------------------------------------
def start_session(s: Session, token: str | None) -> tuple[PortalSession, str]:
    if not token or not LINK_RE.match(token):
        raise link_invalid()
    row = s.execute(sa.select(PortalSignIn).where(PortalSignIn.token_sha256 == sha256_hex(token))).scalar_one_or_none()
    if row is None:
        raise link_invalid()
    if s.get_bind().dialect.name == "postgresql":
        s.execute(sa.select(PortalSignIn.id).where(PortalSignIn.id == row.id).with_for_update())
        s.refresh(row)
    now = db.tx_time(s)
    account = s.get(PortalAccount, row.account_id)
    usable = row.used_on is None and row.invalidated_on is None and row.expires_on > now
    if not usable or account is None or account.status != "ACTIVE" or not active_access(s, account.id):
        if account is not None:
            reason = "USED" if row.used_on else "INVALIDATED" if row.invalidated_on else "EXPIRED" \
                if row.expires_on <= now else "NO_ACCESS"  # fmt: skip
            from veda.platform.auth.request_auth import schedule_write

            account_id, sign_in_id = account.id, row.id

            def refused(w: Session) -> None:  # its own transaction: this request's writes roll back with the 400
                events.record(w, account_id, "SIGN_IN_REFUSED", sign_in_id=sign_in_id, reason=reason)

            schedule_write(refused)
        raise link_invalid()
    row.used_on = now
    raw = SESSION_PREFIX + new_opaque_token()
    session = PortalSession(account_id=account.id, sign_in_id=row.id, token_sha256=sha256_hex(raw), last_seen_on=now,
                            idle_expires_on=now + IDLE_TTL, absolute_expires_on=now + ABSOLUTE_TTL)  # fmt: skip
    s.add(session)
    account.last_signed_in_on = now
    s.flush()
    events.record(s, account.id, "SIGNED_IN", sign_in_id=row.id, session_id=session.id, purpose=row.purpose)
    return session, raw


def resolve(s: Session, token: str | None) -> Principal:
    """The signed-in customer of this request, or 401. Server-side on every request; nothing is cached."""
    if not token or not SESSION_RE.match(token):
        raise session_invalid()
    session = s.execute(sa.select(PortalSession).where(PortalSession.token_sha256 == sha256_hex(token))
                        ).scalar_one_or_none()  # fmt: skip
    now = db.tx_time(s)
    if session is None or session.ended_on is not None or now >= session.idle_expires_on \
            or now >= session.absolute_expires_on:  # fmt: skip
        raise session_invalid()
    account = s.get(PortalAccount, session.account_id)
    if account is None or account.status != "ACTIVE":
        raise session_invalid()
    if now - session.last_seen_on >= TOUCH_GAP:
        from veda.platform.auth.request_auth import schedule_write

        sid = session.id

        def touch(w: Session) -> None:
            fresh = w.get(PortalSession, sid)
            if fresh is not None and fresh.ended_on is None:
                at = db.tx_time(w)
                fresh.last_seen_on = at
                fresh.idle_expires_on = min(at + IDLE_TTL, fresh.absolute_expires_on)

        schedule_write(touch)
    return Principal(session=session, account=account)


def sign_out(s: Session, p: Principal) -> None:
    session = s.get(PortalSession, p.session.id)
    if session is not None and session.ended_on is None:
        session.ended_on, session.end_reason_code = db.tx_time(s), "SIGNED_OUT"
        events.record(s, p.account.id, "SIGNED_OUT", session_id=session.id)
