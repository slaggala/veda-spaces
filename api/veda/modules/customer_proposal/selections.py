"""Optional-item selection (CQX-06): the customer's explicit choices, recorded as a proposal, never a quotation edit.

A choice is one optional line of the open version the link opens, and one of SELECTED, DESELECTED or
REQUESTED_FOR_DISCUSSION (NOT_SELECTED is the state of a line never touched). Only a priced optional line can be
SELECTED; an unpriced one can only be discussed. Choosing again the state a line already has changes nothing
(idempotent), so a retried request never records twice. Every change is an event (and FULL-audited), so the history of
choices stays visible to staff, who review before any revised quotation is issued.

The quotation never changes: its base total excludes optional items, and the effect of the choices is computed
server-side from the version's own frozen lines, each chosen line counted once, by the same formula the B4 decision
uses (taxable amount plus its GST). Whether the customer sees that figure is the owner's decision CQX-D02: until it is
recorded the page says PRICE CONFIRMATION REQUIRED instead of a number. At acceptance the SELECTED lines, and only
they, become part of the effective accepted baseline (B4 ``variations.freeze_baseline``).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import outbox
from veda.kernel.errors import ApiError, field_error
from veda.modules.mtq_commercial.models import Quotation, QuotationLine

from . import events, grants, policy, projection
from . import vocab as V
from .models import CustomerOptionalSelection, ProposalAccessGrant

PRICE_CONFIRMATION_REQUIRED = "PRICE_CONFIRMATION_REQUIRED"


def money(minor: int | None) -> str | None:
    return None if minor is None else f"{Decimal(minor) / 100:,.2f}"


def require_open(s: Session, q: Quotation) -> None:
    state = grants.proposal_state(s, q)
    if state != "OPEN":
        raise ApiError(409, "PROPOSAL_NOT_OPEN", "This proposal can no longer be changed here. Please contact Veda "
                       "Spaces.", extra={"state": state})  # fmt: skip


def current(s: Session, q: Quotation) -> dict[str, CustomerOptionalSelection]:
    rows = s.execute(
        sa.select(CustomerOptionalSelection).where(CustomerOptionalSelection.quotation_id == q.id)
    ).scalars()
    return {r.line_ref: r for r in rows}


def optional_lines(s: Session, q: Quotation) -> dict[str, QuotationLine]:
    """The optional lines the customer can see in the frozen document (never a line it omits; CQX N3)."""
    return projection.printed(s, q)[1]


def line_value(x: QuotationLine) -> int:
    """What choosing ``x`` adds, exactly as the B4 decision adds it: taxable amount plus its GST."""
    return int(x.amount_minor or 0) - int(x.discount_minor or 0) + int(x.tax_minor or 0)


def frozen_value(s: Session, q: Quotation, refs: list[str]) -> int:
    """What the chosen printed optional items add, from their frozen prices (never mutable rows; CQX N1)."""
    values = projection.frozen_values(s, q)["optional_minor"]
    return sum(values.get(r, 0) for r in refs)


def selected_lines(s: Session, q: Quotation) -> list[QuotationLine]:
    lines = optional_lines(s, q)
    return [lines[ref] for ref, r in sorted(current(s, q).items()) if r.state == "SELECTED" and ref in lines]


def choose(s: Session, g: ProposalAccessGrant, q: Quotation, line_ref: str, state: str) -> CustomerOptionalSelection:
    if g.recipient_kind not in V.DECIDING_KINDS:
        raise ApiError(403, "RECIPIENT_NOT_AUTHORISED", "Only the primary customer's link can choose optional items; "
                       "you can ask Veda Spaces about them.")  # fmt: skip
    grants.locked(s, g, q)  # lock first, then re-read the link and the quotation (CQX N5)
    projection.frozen_document(q)  # never act on a version whose frozen document does not verify
    require_open(s, q)
    lines = optional_lines(s, q)
    line = lines.get(line_ref)
    if line is None:
        raise ApiError(422, "VALIDATION_FAILED", "Please choose one of the optional items of this proposal.",
                       errors=[field_error("line_ref", "NOT_OPTIONAL", "Not an optional item of this proposal.")])  # fmt: skip
    if state == "SELECTED" and (not line.is_priced or line_ref not in projection.frozen_values(s, q)["optional_minor"]):
        raise ApiError(422, "VALIDATION_FAILED", "This item has no confirmed price yet; ask Veda Spaces about it.",
                       errors=[field_error("state", "PRICE_CONFIRMATION_REQUIRED", "Not priced yet.")])  # fmt: skip
    row = current(s, q).get(line_ref)
    if row is not None and row.state == state:
        return row  # idempotent: nothing changes, nothing is recorded twice
    before = row.state if row is not None else "NOT_SELECTED"
    if row is None:
        row = CustomerOptionalSelection(lead_id=q.lead_id, quotation_id=q.id, quotation_line_id=line.id,
                                        line_ref=line_ref, line_key=line.line_key, state=state,
                                        changed_by_grant_id=g.id, change_no=1)  # fmt: skip
        s.add(row)
    else:
        row.state, row.changed_by_grant_id, row.change_no = state, g.id, row.change_no + 1
    events.record(
        s, q.id, q.lead_id, "SELECTION_CHANGED", grant=g, line_ref=line_ref, from_state=before, to_state=state
    )
    outbox.enqueue(s, events.OPTIONAL_SELECTED, "quotation", q.id, quotation_id=q.id, grant_id=g.id)
    s.flush()
    return row


def summary(s: Session, q: Quotation) -> dict[str, Any]:
    """The choices and, when CQX-D02 allows it, the server's total with them (each chosen line counted once)."""
    lines = optional_lines(s, q)
    rows = current(s, q)
    chosen = selected_lines(s, q)
    decided = policy.decision("CQX-D02")
    live = bool(decided and decided.live_total) and q.total_minor is not None and q.snapshot is not None
    extra = frozen_value(s, q, [f"L{x.position}" for x in chosen]) if chosen else 0
    return {
        "items": [
            {"ref": ref, "state": rows[ref].state if ref in rows else "NOT_SELECTED", "priced": x.is_priced}
            for ref, x in lines.items()
        ],  # fmt: skip
        "selected_refs": [ref for ref, r in sorted(rows.items()) if r.state == "SELECTED" and ref in lines],
        "status": "CALCULATED" if live else PRICE_CONFIRMATION_REQUIRED,
        "extra": money(extra) if live and chosen else None,
        "total_with_selections": money(projection.frozen_values(s, q)["total_minor"] + extra) if live else None,
    }


def contribute(s: Session, g: ProposalAccessGrant, q: Quotation, page: dict[str, Any]) -> None:
    page["selections"] = summary(s, q)
    page["selections"]["can_choose"] = g.recipient_kind in V.DECIDING_KINDS
    items = page["selections"]["items"]
    if (
        page["capabilities"]["interaction"]
        and page["selections"]["can_choose"]
        and items
        and all(i["state"] == "NOT_SELECTED" for i in items)
    ):
        page["actions"].append(
            {"code": "REVIEW_OPTIONAL_ITEMS", "label": "Review the optional items", "target": "optional"}
        )


def staff_view(s: Session, q: Quotation) -> list[dict[str, Any]]:
    lines = optional_lines(s, q)
    return [{"line_ref": r.line_ref, "description": lines[r.line_ref].description if r.line_ref in lines else None,
             "state": r.state, "change_no": r.change_no, "changed_on": r.updated_on.isoformat()}
            for r in current(s, q).values()]  # fmt: skip


PAGE_FIELDS: dict[str, str] = {
    "selections.items[].ref": "optional line reference",
    "selections.items[].state": "the customer's choice",
    "selections.items[].priced": "whether it can be selected",
    "selections.selected_refs[]": "chosen lines",
    "selections.can_choose": "whether this link may choose (the primary customer's only)",
    "selections.status": "CALCULATED or PRICE_CONFIRMATION_REQUIRED (CQX-D02)",
    "selections.extra": "what the choices add (only when CQX-D02 allows it)",
    "selections.total_with_selections": "total with the choices (only when CQX-D02 allows it)",
}
