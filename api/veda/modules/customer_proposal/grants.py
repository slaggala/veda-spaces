"""Secure proposal access (CQX-01): opaque links to one issued quotation version.

A grant is created by staff for one ISSUED (or ACCEPTED, for reference) quotation version, for one recipient kind, with
a lifetime the staff member chooses (1 to ``MAX_DAYS`` days; a security bound, not a commercial term). The link carries
a 256-bit random token in the URL **fragment** (``/proposal#t=…``), so it never reaches a server log, a proxy or a
``Referer``; the page moves it into memory, scrubs the address bar and sends it only in the ``X-Veda-Proposal`` header.
Only its SHA-256 is stored, so a database reader cannot use a link, and the token is shown to staff once.

Lifecycle::

    CREATED ─first view─► ACTIVE ─► EXPIRED (its own expiry, independent of the quotation's validity)
       └──────────────────┴───────► REVOKED (staff; ROTATED by a new link; SUPERSEDED when a newer version is shared to
                                             the same recipient kind; LEAD_ERASED; LEAD_CLOSED)

One live grant per (version, recipient kind): sharing again is a rotation, never a duplicate. A revoked or expired
grant stops serving on the next request (every request resolves the token again; nothing is cached). The quotation's
own state is separate: a link to a version that is later superseded, expired, accepted or declined still opens, and
shows that state instead of offering actions.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import clock, db, outbox
from veda.kernel.errors import ApiError
from veda.modules.crm.leads.models import Lead
from veda.modules.mtq_commercial import quotations
from veda.modules.mtq_commercial.models import Quotation
from veda.platform.auth.crypto import new_opaque_token

from . import events
from . import vocab as V
from .models import ProposalAccessGrant

TOKEN_PREFIX = "vsp_"
TOKEN_RE = re.compile(r"^vsp_[A-Za-z0-9_-]{43}$")
HEADER = "X-Veda-Proposal"
MAX_DAYS = 30  # security bound on one link's life; the customer gets a fresh link (rotation) if they need longer
SHAREABLE = ("ISSUED", "ACCEPTED")
VIEW_EVENT_GAP = timedelta(minutes=15)  # repeat views inside this window update counters only (bounded event growth)


def token_sha256(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def link_for(token: str) -> str:
    return settings().app_base_url.rstrip("/") + "/proposal#t=" + token


def _new_token() -> str:
    return TOKEN_PREFIX + new_opaque_token()


def is_live(g: ProposalAccessGrant, now=None) -> bool:
    now = now or clock.now()
    return g.status in V.LIVE_GRANT_STATUSES and g.expires_on > now


def expire_if_due(s: Session, g: ProposalAccessGrant) -> bool:
    if g.status in V.LIVE_GRANT_STATUSES and g.expires_on <= db.tx_time(s):
        g.status = "EXPIRED"
        events.record(s, g.quotation_id, g.lead_id, "EXPIRED", grant=g)
        s.flush()
        return True
    return False


def _revoke(s: Session, g: ProposalAccessGrant, reason: str, by: str | None) -> None:
    g.status, g.revoked_on, g.revoked_by, g.revoke_reason_code = "REVOKED", db.tx_time(s), by, reason
    events.record(s, g.quotation_id, g.lead_id, "REVOKED", grant=g, reason_code=reason)
    outbox.enqueue(s, events.ACCESS_REVOKED, "proposal_access_grant", g.id, grant_id=g.id, quotation_id=g.quotation_id,
                   reason_code=reason)  # fmt: skip


def _require_shareable(s: Session, q: Quotation) -> None:
    from veda.modules.mtq_commercial import rendering

    if q.status not in SHAREABLE:
        raise ApiError(409, "NOT_SHAREABLE", "Only an issued quotation is shared with a customer.",
                       extra={"quotation_status": q.status})  # fmt: skip
    head = quotations.latest(s, q.quotation_number, q.variation_no)
    if head.id != q.id:
        raise ApiError(409, "QUOTATION_SUPERSEDED", "A newer version exists; share that one.",
                       extra={"latest_quotation_id": head.id})  # fmt: skip
    if not rendering.integrity(q):
        raise ApiError(409, "SNAPSHOT_INTEGRITY_FAILED", "The frozen document does not match its digest; it is not "
                       "shared.", extra={"quotation_id": q.id})  # fmt: skip
    lead = s.get(Lead, q.lead_id)
    if lead is None or lead.anonymized_on is not None:
        raise ApiError(409, "LEAD_CLOSED", "This lead is closed to customer sharing.")


@dataclass
class Issued:
    grant: ProposalAccessGrant
    token: str


def _create(s: Session, q: Quotation, *, recipient_kind: str, recipient_label: str | None, expires_on,
            replaces: ProposalAccessGrant | None = None) -> Issued:  # fmt: skip
    token = _new_token()
    g = ProposalAccessGrant(
        lead_id=q.lead_id, property_id=q.property_id, quotation_id=q.id, quotation_number=q.quotation_number,
        variation_no=q.variation_no, version_no=q.version_no, recipient_kind=recipient_kind,
        recipient_label=recipient_label, token_sha256=token_sha256(token), status="CREATED", expires_on=expires_on,
        replaces_grant_id=replaces.id if replaces else None,
    )  # fmt: skip
    s.add(g)
    s.flush()
    return Issued(g, token)


def share(s: Session, ctx, q: Quotation, body) -> Issued:
    """A new link for ``q``'s recipient kind. Live links of earlier versions of the same quotation (or variation) to
    the same recipient kind are revoked as SUPERSEDED, so a customer never has two current proposals in hand."""
    _require_shareable(s, q)
    for g in live_for(s, q.id):
        expire_if_due(s, g)
    if any(g.recipient_kind == body.recipient_kind and g.status in V.LIVE_GRANT_STATUSES for g in live_for(s, q.id)):
        raise ApiError(409, "GRANT_EXISTS", "A live link for this recipient already exists; rotate or revoke it.")
    older = s.execute(
        sa.select(ProposalAccessGrant).where(
            ProposalAccessGrant.quotation_number == q.quotation_number,
            ProposalAccessGrant.variation_no == q.variation_no,
            ProposalAccessGrant.version_no < q.version_no,
            ProposalAccessGrant.recipient_kind == body.recipient_kind,
            ProposalAccessGrant.status.in_(V.LIVE_GRANT_STATUSES),
        )
    ).scalars().all()  # fmt: skip
    for g in older:
        _revoke(s, g, "SUPERSEDED", ctx.user.id)
    issued = _create(s, q, recipient_kind=body.recipient_kind, recipient_label=body.recipient_label,
                     expires_on=db.tx_time(s) + timedelta(days=body.expires_in_days))  # fmt: skip
    events.record(s, q.id, q.lead_id, "SHARED", grant=issued.grant, expires_in_days=body.expires_in_days,
                  superseded_grants=len(older))  # fmt: skip
    outbox.enqueue(s, events.SHARED, "proposal_access_grant", issued.grant.id, grant_id=issued.grant.id,
                   quotation_id=q.id)  # fmt: skip
    if older:
        outbox.enqueue(s, events.REVISED_AVAILABLE, "proposal_access_grant", issued.grant.id,
                       grant_id=issued.grant.id, quotation_id=q.id)  # fmt: skip
    return issued


def rotate(s: Session, ctx, g: ProposalAccessGrant) -> Issued:
    """A new token for the same recipient and expiry; the old link stops at once (revoked ROTATED)."""
    expire_if_due(s, g)
    if g.status not in V.LIVE_GRANT_STATUSES:
        raise ApiError(409, "GRANT_NOT_LIVE", "Only a live link is rotated; share a new one.",
                       extra={"link_status": g.status})  # fmt: skip
    q = s.get(Quotation, g.quotation_id)
    assert q is not None
    _require_shareable(s, q)
    _revoke(s, g, "ROTATED", ctx.user.id)
    s.flush()
    issued = _create(s, q, recipient_kind=g.recipient_kind, recipient_label=g.recipient_label,
                     expires_on=g.expires_on, replaces=g)  # fmt: skip
    events.record(s, q.id, q.lead_id, "ROTATED", grant=issued.grant, replaces_grant_id=g.id)
    return issued


def revoke(s: Session, ctx, g: ProposalAccessGrant) -> ProposalAccessGrant:
    expire_if_due(s, g)
    if g.status == "REVOKED":
        return g  # idempotent
    if g.status == "EXPIRED":
        raise ApiError(409, "GRANT_NOT_LIVE", "This link has already expired.")
    _revoke(s, g, "STAFF_REVOKED", ctx.user.id)
    return g


def revoke_all_for_lead(s: Session, lead_id: str, reason: str) -> int:
    rows = s.execute(
        sa.select(ProposalAccessGrant).where(
            ProposalAccessGrant.lead_id == lead_id, ProposalAccessGrant.status.in_(V.LIVE_GRANT_STATUSES)
        )
    ).scalars().all()  # fmt: skip
    for g in rows:
        _revoke(s, g, reason, None)
    return len(rows)


def live_for(s: Session, quotation_id: str) -> list[ProposalAccessGrant]:
    return list(s.execute(
        sa.select(ProposalAccessGrant).where(ProposalAccessGrant.quotation_id == quotation_id,
                                             ProposalAccessGrant.status.in_(V.LIVE_GRANT_STATUSES))
    ).scalars())  # fmt: skip


def for_quotation(s: Session, quotation_id: str) -> list[ProposalAccessGrant]:
    return list(s.execute(
        sa.select(ProposalAccessGrant).where(ProposalAccessGrant.quotation_id == quotation_id)
        .order_by(ProposalAccessGrant.created_on.desc())
    ).scalars())  # fmt: skip


# --- customer side ----------------------------------------------------------------------------------------------------
# What a link answers, in order. Safe messages only: no number, name, amount or internal identifier.
def link_invalid() -> ApiError:
    return ApiError(404, "PROPOSAL_LINK_INVALID", "This link is not valid. Please ask Veda Spaces for a new one.")


def _gone(code: str, message: str) -> ApiError:
    return ApiError(410, code, message)


def resolve(s: Session, token: str | None) -> tuple[ProposalAccessGrant, Quotation]:
    """The grant and quotation version a token opens, or a safe refusal. Server-side on every request."""
    if not token or not TOKEN_RE.match(token):
        raise link_invalid()
    g = s.execute(
        sa.select(ProposalAccessGrant).where(ProposalAccessGrant.token_sha256 == token_sha256(token))
    ).scalar_one_or_none()
    if g is None:
        raise link_invalid()
    _check_live(s, g)
    q = s.get(Quotation, g.quotation_id)
    lead = s.get(Lead, g.lead_id)
    if q is None or q.is_deleted or lead is None or lead.anonymized_on is not None:
        raise link_invalid()
    return g, q


def locked(s: Session, g: ProposalAccessGrant, q: Quotation) -> None:
    """Every customer mutation (choice, request, acknowledgement, decision) runs under the property lock that staff
    writes and decisions take, and re-reads the link and the quotation under it, so a revocation, rotation, new version
    or decision that committed while this request waited is seen before anything is written (CQX N5)."""
    from veda.modules.mtq import sets as site_sets

    site_sets.lock_property(s, q.property_id)
    s.refresh(g)
    s.refresh(q)
    _check_live(s, g)
    lead = s.get(Lead, g.lead_id)
    if q.is_deleted or lead is None or lead.anonymized_on is not None:
        raise link_invalid()


def _check_live(s: Session, g: ProposalAccessGrant) -> None:
    if g.status == "REVOKED":
        if g.revoke_reason_code == "SUPERSEDED":
            raise _gone("PROPOSAL_SUPERSEDED", "A newer version of this proposal has been shared with you. Please use "
                        "the latest link from Veda Spaces.")  # fmt: skip
        raise _gone("PROPOSAL_LINK_REVOKED", "This link is no longer active. Please ask Veda Spaces for a new one.")
    if expire_if_due(s, g) or g.status == "EXPIRED":
        raise _gone("PROPOSAL_LINK_EXPIRED", "This link has expired. Please ask Veda Spaces for a new one.")


def record_view(s: Session, g: ProposalAccessGrant) -> None:
    now = db.tx_time(s)
    first = g.first_viewed_on is None
    if first:
        g.first_viewed_on, g.status = now, "ACTIVE"
        outbox.enqueue(s, events.VIEWED, "proposal_access_grant", g.id, grant_id=g.id, quotation_id=g.quotation_id)
    if first or g.last_viewed_on is None or now - g.last_viewed_on >= VIEW_EVENT_GAP:
        events.record(s, g.quotation_id, g.lead_id, "VIEWED", grant=g, first=first)
    g.last_viewed_on = now
    g.view_count = int(g.view_count or 0) + 1
    s.flush()


def proposal_state(s: Session, q: Quotation) -> str:
    """The customer-facing state of the version a link opens (separate from the link's own state)."""
    if q.status == "SUPERSEDED":
        return "SUPERSEDED"
    head = quotations.latest(s, q.quotation_number, q.variation_no)
    if head.id != q.id and head.status in ("ISSUED", "ACCEPTED", "REJECTED", "EXPIRED"):
        return "SUPERSEDED"
    if q.status == "ISSUED" and q.valid_until is not None and q.valid_until < db.tx_time(s).date():
        return "EXPIRED"
    return {"ISSUED": "OPEN", "ACCEPTED": "ACCEPTED", "REJECTED": "DECLINED", "EXPIRED": "EXPIRED"}.get(
        q.status, "UNAVAILABLE"
    )


def present(g: ProposalAccessGrant, *, now=None) -> dict[str, Any]:
    now = now or clock.now()
    status = "EXPIRED" if g.status in V.LIVE_GRANT_STATUSES and g.expires_on <= now else g.status
    return {"id": g.id, "version": g.version, "quotation_id": g.quotation_id, "quotation_number": g.quotation_number,
            "variation_no": g.variation_no, "version_no": g.version_no, "recipient_kind": g.recipient_kind,
            "recipient_label": g.recipient_label, "status": status,
            "expires_on": clock.to_rfc3339(g.expires_on),
            "first_viewed_on": clock.to_rfc3339(g.first_viewed_on) if g.first_viewed_on else None,
            "last_viewed_on": clock.to_rfc3339(g.last_viewed_on) if g.last_viewed_on else None,
            "view_count": g.view_count, "revoke_reason_code": g.revoke_reason_code,
            "revoked_on": clock.to_rfc3339(g.revoked_on) if g.revoked_on else None,
            "replaces_grant_id": g.replaces_grant_id, "shared_by": g.created_by,
            "shared_on": clock.to_rfc3339(g.created_on)}  # fmt: skip
