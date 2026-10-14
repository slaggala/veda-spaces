"""Customer questions and structured change requests (CQX-07).

A customer asks about a line or the proposal, or asks for a change (add, remove, change quantity, material or finish,
discuss price), always against the exact version their link opens. The request is a message to staff and nothing more:
its text is plain text (control characters stripped, 3 to 2000 characters, stored as typed and only ever shown
escaped), it never becomes a requirement, scope item or price, and nothing in the quotation changes because of it.
A change reaches the customer only as a new quotation version, or, after acceptance, a variation, which staff build
through B2-B4 and then link to the request (``link``), so the customer sees what answered it.

Lifecycle::

    OPEN ─► UNDER_REVIEW ─► NEEDS_CLARIFICATION ─► (customer asks again: a new request)
      └────────┴──────────► ACCEPTED_FOR_REVISION ─► RESOLVED
      └────────┴──────────► DECLINED | RESOLVED   (final)

Requests are open on a proposal that is open, past its validity (a revision may follow) or accepted (a change after
acceptance is a variation); not on a superseded or withdrawn one. Each submission needs an Idempotency-Key: a retry
returns the same request, never a duplicate. A customer sees the requests sent through links for the same quotation and
the same recipient kind only, never another recipient's.
"""

from __future__ import annotations

import hashlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, db, outbox
from veda.kernel.errors import ApiError, field_error
from veda.modules.mtq import sets as site_sets
from veda.modules.mtq_commercial import quotations
from veda.modules.mtq_commercial.models import Quotation

from . import events, grants, projection
from . import vocab as V
from .models import CustomerProposalRequest, ProposalAccessGrant

ASKABLE_STATES = ("OPEN", "EXPIRED", "ACCEPTED")
LINE_CATEGORIES = ("LINE_QUESTION", "REMOVE_ITEM", "CHANGE_QUANTITY", "CHANGE_MATERIAL", "CHANGE_FINISH")
MAX_OPEN_PER_LINK = 50  # a ceiling against abuse; staff can always be reached another way
FINAL = ("DECLINED", "RESOLVED")
TRANSITIONS = {
    "OPEN": ("UNDER_REVIEW", "NEEDS_CLARIFICATION", "ACCEPTED_FOR_REVISION", "DECLINED", "RESOLVED"),
    "UNDER_REVIEW": ("NEEDS_CLARIFICATION", "ACCEPTED_FOR_REVISION", "DECLINED", "RESOLVED"),
    "NEEDS_CLARIFICATION": ("UNDER_REVIEW", "ACCEPTED_FOR_REVISION", "DECLINED", "RESOLVED"),
    "ACCEPTED_FOR_REVISION": ("RESOLVED",),
}
RESPONSE_REQUIRED = ("NEEDS_CLARIFICATION", "DECLINED")
CATEGORY_LABEL = {
    "LINE_QUESTION": "Question about an item", "GENERAL_QUESTION": "Question about the proposal",
    "ADD_ITEM": "Add an item", "REMOVE_ITEM": "Remove an item", "CHANGE_QUANTITY": "Change a quantity",
    "CHANGE_MATERIAL": "Change a material", "CHANGE_FINISH": "Change a finish", "DISCUSS_PRICE": "Discuss the price",
}  # fmt: skip
STATUS_LABEL = {
    "OPEN": "Sent", "UNDER_REVIEW": "Being reviewed", "NEEDS_CLARIFICATION": "We need a little more detail",
    "ACCEPTED_FOR_REVISION": "Accepted for a revised proposal", "DECLINED": "Not possible", "RESOLVED": "Answered",
}  # fmt: skip


def key_digest(key: str | None) -> str:
    from veda.kernel.http import IDEMPOTENCY_KEY_RE

    if not key or not IDEMPOTENCY_KEY_RE.match(key):
        raise ApiError(422, "VALIDATION_FAILED", "Please try again.",
                       errors=[field_error("Idempotency-Key", "REQUIRED", "An Idempotency-Key is required.")])  # fmt: skip
    return hashlib.sha256(key.encode()).hexdigest()


def submit(
    s: Session, g: ProposalAccessGrant, q: Quotation, body, idempotency_key: str | None
) -> CustomerProposalRequest:
    digest = key_digest(idempotency_key)
    projection.frozen_document(q)
    state = grants.proposal_state(s, q)
    if state not in ASKABLE_STATES:
        raise ApiError(409, "PROPOSAL_NOT_OPEN", "Please use the latest proposal link from Veda Spaces to ask about it.",
                       extra={"state": state})  # fmt: skip
    site_sets.lock_property(s, q.property_id)
    again = s.execute(
        sa.select(CustomerProposalRequest).where(CustomerProposalRequest.grant_id == g.id,
                                                 CustomerProposalRequest.client_key_sha256 == digest)
    ).scalar_one_or_none()  # fmt: skip
    if again is not None:
        if again.body != body.message or again.category_code != body.category:
            raise ApiError(409, "IDEMPOTENCY_KEY_REUSED", "This request was already sent with different content.")
        return again
    open_count = s.execute(
        sa.select(sa.func.count()).select_from(CustomerProposalRequest).where(
            CustomerProposalRequest.grant_id == g.id, CustomerProposalRequest.status.in_(V.OPEN_REQUEST_STATUSES))
    ).scalar()  # fmt: skip
    if int(open_count or 0) >= MAX_OPEN_PER_LINK:
        raise ApiError(429, "TOO_MANY_OPEN_REQUESTS", "You have many requests waiting. Veda Spaces will answer them "
                       "first; please contact your representative directly if it is urgent.")  # fmt: skip
    refs = projection.refs(s, q)
    line = None
    if body.line_ref is not None:
        line = refs.get(body.line_ref)
        if line is None:
            raise ApiError(422, "VALIDATION_FAILED", "Please choose an item of this proposal.",
                           errors=[field_error("line_ref", "UNKNOWN_LINE", "Not an item of this proposal.")])  # fmt: skip
    if body.category in LINE_CATEGORIES and line is None:
        raise ApiError(422, "VALIDATION_FAILED", "Please choose the item this is about.",
                       errors=[field_error("line_ref", "REQUIRED", "Choose the item.")])  # fmt: skip
    if body.requested_quantity is not None and body.category != "CHANGE_QUANTITY":
        raise ApiError(422, "VALIDATION_FAILED", "A quantity goes with a quantity change only.",
                       errors=[field_error("requested_quantity", "NOT_ALLOWED", "Only for a quantity change.")])  # fmt: skip
    room_label, space_id = None, None
    page = projection.build(s, q)
    rooms = {r["ref"]: r for r in page["rooms"]}
    if line is not None:
        space_id = line.space_id
        room_label = next((r["title"] for r in page["rooms"] if any(x["ref"] == body.line_ref for x in r["lines"])),
                          None) or next((x["room_title"] for x in page["optional_items"] if x["ref"] == body.line_ref), None)  # fmt: skip
    elif body.room_ref is not None:
        if body.room_ref not in rooms:
            raise ApiError(422, "VALIDATION_FAILED", "Please choose a room of this proposal.",
                           errors=[field_error("room_ref", "UNKNOWN_ROOM", "Not a room of this proposal.")])  # fmt: skip
        room_label = rooms[body.room_ref]["title"]
        sec = next((sec for n, sec in enumerate([x for x in quotations.sections(s, q) if x.section_code != "OPTIONAL"],
                                                start=1) if f"R{n}" == body.room_ref), None)  # fmt: skip
        space_id = sec.space_id if sec is not None else None
    kind = "QUESTION" if body.category in V.QUESTION_CATEGORIES else "CHANGE_REQUEST"
    row = CustomerProposalRequest(
        lead_id=q.lead_id, property_id=q.property_id, quotation_id=q.id, quotation_number=q.quotation_number,
        variation_no=q.variation_no, version_no=q.version_no, grant_id=g.id, request_kind=kind,
        category_code=body.category, quotation_line_id=line.id if line is not None else None,
        line_ref=body.line_ref, space_id=space_id, room_label=(room_label or None) and room_label[:120],
        requested_quantity=body.requested_quantity, body=body.message, status="OPEN", client_key_sha256=digest,
    )  # fmt: skip
    s.add(row)
    s.flush()
    code = "QUESTION_SUBMITTED" if kind == "QUESTION" else "CHANGE_REQUESTED"
    events.record(
        s, q.id, q.lead_id, code, grant=g, customer_request_id=row.id, category=body.category, line_ref=body.line_ref
    )
    outbox.enqueue(s, events.QUESTION_SUBMITTED if kind == "QUESTION" else events.CHANGE_REQUESTED,
                   "customer_proposal_request", row.id, quotation_id=q.id, grant_id=g.id, customer_request_id=row.id)  # fmt: skip
    return row


def _label(s: Session, quotation_id: str | None) -> str | None:
    if not quotation_id:
        return None
    q = s.get(Quotation, quotation_id)
    if q is None:
        return None
    return f"Variation {q.variation_no}, version {q.version_no}" if q.variation_no else f"Version {q.version_no}"


def for_customer(s: Session, g: ProposalAccessGrant) -> list[dict[str, Any]]:
    """Requests sent through links for the same quotation and recipient kind (never another recipient's)."""
    rows = s.execute(
        sa.select(CustomerProposalRequest).join(ProposalAccessGrant, ProposalAccessGrant.id == CustomerProposalRequest.grant_id)
        .where(CustomerProposalRequest.quotation_number == g.quotation_number,
               ProposalAccessGrant.recipient_kind == g.recipient_kind)
        .order_by(CustomerProposalRequest.created_on)
    ).scalars().all()  # fmt: skip
    return [{"ref": f"#{n}", "category": r.category_code, "category_label": CATEGORY_LABEL[r.category_code],
             "line_ref": r.line_ref if r.quotation_id == g.quotation_id else None, "room": r.room_label,
             "about_version": r.version_no, "about_variation": r.variation_no, "message": r.body,
             "requested_quantity": r.requested_quantity, "status": r.status, "status_label": STATUS_LABEL[r.status],
             "response": r.staff_response if r.status != "OPEN" else None,
             "sent_on": clock.to_rfc3339(r.created_on),
             "responded_on": clock.to_rfc3339(r.responded_on) if r.responded_on else None,
             "answered_by_revision": _label(s, r.resulting_quotation_id)} for n, r in enumerate(rows, start=1)]  # fmt: skip


def respond(s: Session, ctx, r: CustomerProposalRequest, status: str, response: str | None) -> CustomerProposalRequest:
    allowed = TRANSITIONS.get(r.status, ())
    if status not in allowed:
        raise ApiError(409, "INVALID_STATE", f"A request that is {r.status.lower().replace('_', ' ')} cannot become "
                       f"{status.lower().replace('_', ' ')}.", extra={"status": r.status, "allowed": list(allowed)})  # fmt: skip
    if status in RESPONSE_REQUIRED and not response:
        raise ApiError(422, "VALIDATION_FAILED", "Tell the customer why.",
                       errors=[field_error("response", "REQUIRED", "A response is required for this status.")])  # fmt: skip
    if status == "ACCEPTED_FOR_REVISION" and r.resulting_quotation_id is None:
        raise ApiError(422, "VALIDATION_FAILED", "Link the revised version or variation that answers it.",
                       errors=[field_error("status", "LINK_REQUIRED", "Use the link action.")])  # fmt: skip
    frm = r.status
    r.status, r.responded_by, r.responded_on = status, ctx.user.id, db.tx_time(s)
    if response is not None:
        r.staff_response = response
    events.record(
        s, r.quotation_id, r.lead_id, "REQUEST_UPDATED", customer_request_id=r.id, from_status=frm, to_status=status
    )
    return r


def link(
    s: Session, ctx, r: CustomerProposalRequest, target: Quotation, response: str | None
) -> CustomerProposalRequest:
    """The revision or variation that answers ``r``: a newer version of the same quotation, or a variation of it."""
    newer = target.quotation_number == r.quotation_number and (
        (target.variation_no == r.variation_no and target.version_no > r.version_no)
        or target.variation_no > r.variation_no
    )
    if target.property_id != r.property_id or not newer:
        raise ApiError(422, "LINEAGE_MISMATCH", "Link a newer version or a variation of the same quotation.")
    if r.status in FINAL:
        raise ApiError(409, "INVALID_STATE", "This request is already closed.")
    frm = r.status
    r.resulting_quotation_id = target.id
    r.status, r.responded_by, r.responded_on = "ACCEPTED_FOR_REVISION", ctx.user.id, db.tx_time(s)
    if response is not None:
        r.staff_response = response
    events.record(s, r.quotation_id, r.lead_id, "REQUEST_LINKED", customer_request_id=r.id, from_status=frm,
                  resulting_quotation_id=target.id)  # fmt: skip
    return r


def staff_view(s: Session, q: Quotation) -> list[dict[str, Any]]:
    rows = s.execute(
        sa.select(CustomerProposalRequest).where(CustomerProposalRequest.quotation_number == q.quotation_number)
        .order_by(CustomerProposalRequest.created_on)
    ).scalars().all()  # fmt: skip
    ids = list({r.grant_id for r in rows})
    kinds = {g.id: g.recipient_kind for g in s.execute(
        sa.select(ProposalAccessGrant).where(ProposalAccessGrant.id.in_(ids))).scalars()} if ids else {}  # fmt: skip
    return [{"id": r.id, "version": r.version, "request_kind": r.request_kind, "category": r.category_code,
             "version_no": r.version_no, "variation_no": r.variation_no, "line_ref": r.line_ref, "room": r.room_label,
             "message": r.body, "requested_quantity": r.requested_quantity, "status": r.status,
             "response": r.staff_response, "recipient_kind": kinds.get(r.grant_id),
             "sent_on": clock.to_rfc3339(r.created_on),
             "responded_on": clock.to_rfc3339(r.responded_on) if r.responded_on else None,
             "resulting_quotation_id": r.resulting_quotation_id,
             "resulting_label": _label(s, r.resulting_quotation_id)} for r in rows]  # fmt: skip


def contribute(s: Session, g: ProposalAccessGrant, q: Quotation, page: dict[str, Any]) -> None:
    state = page["state"]
    page["requests"] = {"items": for_customer(s, g), "can_ask": bool(page["capabilities"]["interaction"] or (
        state in ("EXPIRED", "ACCEPTED") and _interaction_on()))}  # fmt: skip
    if any(i["status"] == "NEEDS_CLARIFICATION" for i in page["requests"]["items"]):
        page["actions"].append({"code": "CLARIFY_REQUEST", "label": "Veda Spaces asked you for more detail",
                                "target": "questions"})  # fmt: skip


def _interaction_on() -> bool:
    from veda.config import settings

    return bool(settings().customer_proposal_interaction_enabled)


PAGE_FIELDS: dict[str, str] = {
    "requests.can_ask": "whether the customer may ask or request a change here",
    **{
        f"requests.items[].{k}": "the customer's own request and its answer"
        for k in (
            "ref",
            "category",
            "category_label",
            "line_ref",
            "room",
            "about_version",
            "about_variation",
            "message",
            "requested_quantity",
            "status",
            "status_label",
            "response",
            "sent_on",
            "responded_on",
            "answered_by_revision",
        )
    },
}
