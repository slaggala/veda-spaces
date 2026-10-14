"""Closed request schemas for CQX (unknown fields → 422 UNKNOWN_FIELD; no free-form JSON).

Customer text is plain text: trimmed, control characters refused by the platform's text validators, bounded in length,
stored as typed and only ever rendered escaped. Nothing a customer sends is interpreted as markup or as scope.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from veda.kernel.dto import Closed, Id, optional_text, text

RecipientKind = Literal["PRIMARY_CUSTOMER", "CO_OWNER", "FAMILY_MEMBER", "OTHER"]
LineRef = Annotated[str, Field(pattern=r"^L[1-9][0-9]{0,3}$")]
Sha = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
CustomerText = Annotated[str, text(2000, min_len=3)]
StaffText = Annotated[str | None, optional_text(2000)]


class ShareIn(Closed):
    recipient_kind: RecipientKind = "PRIMARY_CUSTOMER"
    recipient_label: Annotated[str | None, optional_text(80)] = None
    expires_in_days: Annotated[int, Field(ge=1, le=30)]


class SelectionIn(Closed):
    line_ref: LineRef
    state: Literal["SELECTED", "DESELECTED", "REQUESTED_FOR_DISCUSSION"]


class RequestIn(Closed):
    category: Literal["LINE_QUESTION", "GENERAL_QUESTION", "ADD_ITEM", "REMOVE_ITEM", "CHANGE_QUANTITY",
                      "CHANGE_MATERIAL", "CHANGE_FINISH", "DISCUSS_PRICE"]  # fmt: skip
    line_ref: LineRef | None = None
    room_ref: Annotated[str | None, Field(pattern=r"^R[1-9][0-9]{0,2}$")] = None
    requested_quantity: Annotated[str | None, optional_text(40)] = None
    message: CustomerText


class AcknowledgeIn(Closed):
    section: Literal["SCOPE", "ASSUMPTIONS", "EXCLUSIONS", "PAYMENT_MILESTONES", "WARRANTY", "SERVICE_SUPPORT", "TERMS",
                     "VALIDITY"]  # fmt: skip
    section_sha256: Sha


class DecisionIn(Closed):
    """What the customer saw when deciding: the exact version and its frozen digest, the total shown and the optional
    items chosen. The server re-derives every one of them and refuses a mismatch."""

    decision: Literal["ACCEPTED", "DECLINED"]
    version_no: Annotated[int, Field(ge=1, le=999)]
    snapshot_sha256: Sha
    displayed_total: Annotated[str | None, Field(max_length=40)] = None
    selected_line_refs: list[LineRef] = Field(default_factory=list, max_length=200)
    confirm: Literal[True]


class RespondIn(Closed):
    status: Literal["UNDER_REVIEW", "NEEDS_CLARIFICATION", "ACCEPTED_FOR_REVISION", "DECLINED", "RESOLVED"]
    response: StaffText = None


class LinkRequestIn(Closed):
    resulting_quotation_id: Id
    response: StaffText = None
