"""Proposal events (CQX-11): the proposal's own log and its outbox event contracts.

``record`` appends a ``proposal_event`` row (ids, codes and counts only: never customer text, a token, an amount or a
name). The outbox events below are drained by the platform worker after commit; their payloads hold ids only
(``outbox.enqueue``) and every handler is idempotent per event (in-app rows are unique per event and recipient).

Recipients are staff only, resolved by permission and lead scope, never by role name: the lead's assignee, the staff
member who shared the link, and holders of the relevant permission at ALL scope. **No customer is notified by this
module.** A customer-directed message needs an approved channel and approved copy (owner blocker CQX-B05); until then
staff send the link themselves, and the customer sees every state on the proposal page.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from veda.platform.notifications.handlers import handler, notify_in_app
from veda.platform.notifications.models import OutboxEvent
from veda.platform.rbac.resolver import holders_of

from .models import ProposalEvent

SHARED = "proposal.shared"
VIEWED = "proposal.viewed"
OPTIONAL_SELECTED = "proposal.optional_selected"
QUESTION_SUBMITTED = "proposal.question_submitted"
CHANGE_REQUESTED = "proposal.change_requested"
REVISED_AVAILABLE = "proposal.revised_available"
NEARING_EXPIRY = "proposal.nearing_expiry"
ACCEPTED = "quotation.accepted"  # the booking hand-off event (CQX-10); the project domain is not built here
DECLINED = "quotation.declined"
ACCESS_REVOKED = "proposal.access_revoked"

EVENT_TYPES = (SHARED, VIEWED, OPTIONAL_SELECTED, QUESTION_SUBMITTED, CHANGE_REQUESTED, REVISED_AVAILABLE,
               NEARING_EXPIRY, ACCEPTED, DECLINED, ACCESS_REVOKED)  # fmt: skip


def record(s: Session, quotation_id: str, lead_id: str, code: str, *, grant=None, **detail: Any) -> None:
    s.add(ProposalEvent(quotation_id=quotation_id, lead_id=lead_id, grant_id=grant.id if grant is not None else None,
                        event_code=code, detail={k: v for k, v in detail.items() if v is not None}))  # fmt: skip


# --- staff notifications ----------------------------------------------------------------------------------------------
def _context(s: Session, event: OutboxEvent):
    from veda.modules.crm.leads.models import Lead
    from veda.modules.mtq_commercial import quotations
    from veda.modules.mtq_commercial.models import Quotation

    from .models import ProposalAccessGrant

    q = s.get(Quotation, event.payload.get("quotation_id"))
    if q is None:
        return None
    lead = s.get(Lead, q.lead_id)
    grant = s.get(ProposalAccessGrant, event.payload["grant_id"]) if event.payload.get("grant_id") else None
    return q, lead, grant, quotations.number_label(q)


def _recipients(s: Session, lead, grant, permission: str) -> list[str]:
    out = [u for u in (lead.assigned_to if lead else None, grant.created_by if grant else None) if u]
    out += holders_of(s, permission, min_scope="ALL")
    return list(dict.fromkeys(out))


def _notify(s: Session, event: OutboxEvent, permission: str, kind: str, title: str) -> None:
    found = _context(s, event)
    if found is None:
        return
    q, lead, grant, label = found
    if lead is None or lead.anonymized_on is not None:
        return
    notify_in_app(s, event, _recipients(s, lead, grant, permission), notification_type=kind,
                  title=title.format(label=label), entity=("quotation", q.id),
                  link_path=f"/site/properties/{q.property_id}/commercial")  # fmt: skip


@handler(SHARED)
def _shared(s: Session, event: OutboxEvent) -> None:
    _notify(s, event, "proposal.share", "PROPOSAL_SHARED", "Proposal {label} shared with the customer")


@handler(VIEWED)
def _viewed(s: Session, event: OutboxEvent) -> None:
    _notify(s, event, "proposal.share", "PROPOSAL_VIEWED", "The customer opened proposal {label}")


@handler(OPTIONAL_SELECTED)
def _optional(s: Session, event: OutboxEvent) -> None:
    _notify(s, event, "proposal.request.review", "PROPOSAL_OPTIONAL_CHOICE",
            "The customer changed optional-item choices on {label}")  # fmt: skip


@handler(QUESTION_SUBMITTED)
def _question(s: Session, event: OutboxEvent) -> None:
    _notify(s, event, "proposal.request.review", "PROPOSAL_QUESTION", "New customer question on {label}")


@handler(CHANGE_REQUESTED)
def _change(s: Session, event: OutboxEvent) -> None:
    _notify(s, event, "proposal.request.review", "PROPOSAL_CHANGE_REQUEST", "New customer change request on {label}")


@handler(REVISED_AVAILABLE)
def _revised(s: Session, event: OutboxEvent) -> None:
    _notify(s, event, "proposal.share", "PROPOSAL_REVISED", "Revised proposal {label} shared; earlier links retired")


@handler(NEARING_EXPIRY)
def _nearing(s: Session, event: OutboxEvent) -> None:
    _notify(
        s, event, "proposal.share", "PROPOSAL_NEARING_EXPIRY", "Proposal {label} is nearing the end of its validity"
    )


@handler(ACCEPTED)
def _accepted(s: Session, event: OutboxEvent) -> None:
    _notify(s, event, "proposal.acceptance.review", "QUOTATION_ACCEPTED_DIGITALLY",
            "The customer accepted {label}: ready for booking hand-off")  # fmt: skip


@handler(DECLINED)
def _declined(s: Session, event: OutboxEvent) -> None:
    _notify(s, event, "proposal.acceptance.review", "QUOTATION_DECLINED_DIGITALLY", "The customer declined {label}")


@handler(ACCESS_REVOKED)
def _revoked(s: Session, event: OutboxEvent) -> None:
    _notify(s, event, "proposal.access.revoke", "PROPOSAL_ACCESS_REVOKED", "A proposal link for {label} was revoked")
