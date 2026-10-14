"""The customer's proposal page model (CQX-03): the frozen projection plus what is live about it.

Live, and never part of the frozen document: the proposal's state (open, superseded, expired, accepted, declined), the
link's own expiry, the earlier issued versions the customer may compare against, what the customer can still do
(capabilities follow the flags, the proposal state and the owner's decisions) and the outstanding actions. Each later
CQX step adds its part through ``CONTRIBUTORS`` (optional-item choices, requests, acknowledgements, decision), so the
page model is assembled in one place.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import clock, db
from veda.modules.mtq_commercial.models import Quotation

from . import grants, projection
from .models import ProposalAccessGrant

STATE_NOTICES = {
    "SUPERSEDED": "A newer version of this proposal is available. Please use the latest link from Veda Spaces.",
    "EXPIRED": "This proposal is past its validity date. Please contact Veda Spaces for a revised proposal.",
    "ACCEPTED": "You accepted this proposal. Veda Spaces will contact you about the next steps.",
    "DECLINED": "You declined this proposal. Veda Spaces may contact you about a revised proposal.",
    "UNAVAILABLE": "This proposal is not available. Please contact Veda Spaces.",
}
LINK_EXPIRY_WARNING = timedelta(days=2)

# (s, grant, quotation, page) -> None: each CQX step adds its section of the page model and its outstanding actions.
CONTRIBUTORS: list[Callable[[Session, ProposalAccessGrant, Quotation, dict[str, Any]], None]] = []


def history(s: Session, q: Quotation) -> list[dict[str, Any]]:
    """Earlier versions of the same quotation (or variation) that were issued to the customer: version and date only."""
    rows = s.execute(
        sa.select(Quotation).where(
            Quotation.quotation_number == q.quotation_number,
            Quotation.variation_no == q.variation_no,
            Quotation.version_no < q.version_no,
            Quotation.issued_on.is_not(None),
        ).order_by(Quotation.version_no.desc())
    ).scalars()  # fmt: skip
    return [{"version_no": r.version_no, "issued_on": r.issued_on.date().isoformat() if r.issued_on else None}
            for r in rows]  # fmt: skip


def capabilities(state: str) -> dict[str, bool]:
    cfg = settings()
    open_ = state == "OPEN"
    return {
        "interaction": bool(cfg.customer_proposal_interaction_enabled) and open_,
        "acceptance": bool(cfg.customer_quotation_acceptance_enabled) and open_,
    }


def customer_view(s: Session, g: ProposalAccessGrant, q: Quotation) -> dict[str, Any]:
    proposal = projection.build(s, q)  # verified frozen document, or a refusal before anything is recorded
    state = grants.proposal_state(s, q)
    notices: list[dict[str, str]] = []
    if state in STATE_NOTICES:
        notices.append({"code": state, "message": STATE_NOTICES[state]})
    if g.expires_on - db.tx_time(s) < LINK_EXPIRY_WARNING:
        notices.append({"code": "LINK_EXPIRES_SOON", "message": "This link expires soon. Veda Spaces can send you a "
                        "new one if you need more time."})  # fmt: skip
    page: dict[str, Any] = {
        "state": state,
        "link": {"expires_on": clock.to_rfc3339(g.expires_on), "status": g.status},
        "proposal": proposal,
        "history": history(s, q),
        "capabilities": capabilities(state),
        "notices": notices,
        "actions": [],
    }
    for contribute in CONTRIBUTORS:
        contribute(s, g, q, page)
    return page
