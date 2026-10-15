"""Quotation binding (CPA-23, CPA-24): which customer pack a quotation version freezes.

OI-MTQ-18 decides the source (``mtq_commercial.policy``):

- not recorded: no pack; every section is "to be confirmed";
- recorded as a pack (the PR #96 form): that pack;
- recorded as ``PromiseAuthority``: the Customer Promise Pack *published* now, verified against its digest (fail
  closed). Nothing else satisfies the decision: not a draft, not a submitted or approved version, not a superseded one.

A version copies the pack into its terms when it is drafted, with a reference (pack id, version, digest), and the issued
document freezes it (``rendering.freeze``), so a later publication never changes an issued quotation. Issue is refused
while a newer pack is published than the one the version carries (``stale_blocker``): the version is revised, which
takes the current pack and keeps staff's choices whose codes it still has.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel.errors import ApiError

from . import sections as SEC
from .models import CustomerPromisePack

NOT_RECORDED, RECORDED_INLINE, DELEGATED = "NOT_RECORDED", "RECORDED_AS_PACK", "DELEGATED_TO_CUSTOMER_PROMISE"


def _decision() -> Any:
    from veda.modules.mtq_commercial import policy

    return policy.decision("OI-MTQ-18")


def authority_state() -> dict[str, Any]:
    from veda.modules.mtq_commercial.policy import PromiseAuthority

    d = _decision()
    if d is None:
        return {"state": NOT_RECORDED, "register_reference": None, "decided_on": None}
    if isinstance(d, PromiseAuthority):
        return {"state": DELEGATED, "register_reference": d.register_reference, "decided_on": d.decided_on}
    return {"state": RECORDED_INLINE, "register_reference": None, "decided_on": None}


def current_published(s: Session) -> CustomerPromisePack | None:
    return s.execute(
        sa.select(CustomerPromisePack).where(CustomerPromisePack.status == "PUBLISHED")
    ).scalar_one_or_none()


def verified(p: CustomerPromisePack) -> dict[str, Any]:
    """A published version's frozen customer content, after checking it against its digest."""
    if p.published_content is None or SEC.digest(p.published_content) != p.published_sha256:
        raise ApiError(409, "CUSTOMER_PROMISE_INTEGRITY_FAILED", f"Customer Promise Pack version {p.version_no} does "
                       "not match its published digest; it is not used.", extra={"pack_id": p.id})  # fmt: skip
    return p.published_content


def reference(p: CustomerPromisePack) -> dict[str, Any]:
    return {"pack_id": p.id, "version_no": p.version_no, "sha256": p.published_sha256}


def for_quotation(s: Session) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """(the customer pack a version drafted now carries, its Customer Promise reference or None)."""
    from veda.modules.mtq_commercial.policy import PromiseAuthority

    d = _decision()
    if d is None:
        return None, None
    if not isinstance(d, PromiseAuthority):
        return d.model_dump(mode="json"), None
    p = current_published(s)
    if p is None:
        return None, None
    return verified(p), {**reference(p), "register_reference": d.register_reference}


def stale_blocker(s: Session, terms: dict[str, Any] | None) -> dict[str, Any] | None:
    """The issuance blocker when the published Customer Promise Pack is not the one this version carries."""
    from veda.modules.mtq_commercial.policy import PromiseAuthority

    if not isinstance(_decision(), PromiseAuthority):
        return None
    current = current_published(s)
    if current is None:
        return None
    carried = (terms or {}).get("customer_promise") or {}
    if carried.get("pack_id") == current.id and carried.get("sha256") == current.published_sha256:
        return None
    return {"code": "CUSTOMER_PROMISE_SUPERSEDED", "kind": "DATA", "severity": "BLOCKING",
            "message": f"Customer Promise Pack version {current.version_no} was published after this version was "
                       "drafted; create a new version to give the customer the current pack.",
            "current_pack_version": current.version_no, "carried_pack_version": carried.get("version_no")}  # fmt: skip


def usage(s: Session) -> dict[str, dict[str, int]]:
    """Per pack id: how many quotation versions carry it, by status (counts only; no customer or quotation data)."""
    from veda.modules.mtq_commercial.models import Quotation

    out: dict[str, dict[str, int]] = {}
    for terms, status in s.execute(sa.select(Quotation.terms, Quotation.status)).all():
        ref = (terms or {}).get("customer_promise") or {}
        if ref.get("pack_id"):
            bucket = out.setdefault(ref["pack_id"], {})
            bucket[status] = bucket.get(status, 0) + 1
    return out
