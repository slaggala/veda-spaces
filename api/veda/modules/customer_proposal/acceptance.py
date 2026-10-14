"""Digital acceptance (CQX-10): the customer accepts or declines the exact version their link opens.

The decision is recorded by the one B4 decision service (``quotations.record_decision``, method CUSTOMER_DIGITAL), so
everything B4 guarantees holds: only the issued, latest, unexpired version; only priced optional items of that version;
acceptance freezes the effective accepted baseline (included lines plus the chosen optional items) with its digest, and
the accepted quotation never changes again (later changes are variations). Around it this module adds what a customer
decision needs:

- **Version and content binding.** The request names the version number and the frozen-document digest the page showed;
  a different version (another version's page, a stale tab) or digest (tampering, a changed document) is refused, as is
  a document whose own digests do not verify.
- **Explicit choices.** The optional items accepted are exactly the customer's current SELECTED choices (CQX-06), sent
  back by the page; any difference is refused. With choices, their total must have been shown (CQX-D02), and the total
  the page displayed must equal the server's.
- **Acknowledgements.** Every section the owner requires (CQX-D03) must be acknowledged through this link, at the digest
  of the current text.
- **Evidence.** One evidence row per version: digests (document, HTML, baseline), version, the displayed total, the
  chosen items, the acknowledged sections with their digests, the time, the link (grant), the request trace and only
  the network/device data CQX-D04 permits; an evidence digest over all of it.
- **Idempotency.** A retry (same Idempotency-Key) or a second identical acceptance returns the recorded decision; a
  conflicting second decision is refused. The database admits one evidence row per version.
- **Hand-off.** A lead activity through the lead service (the lead's status is not changed: B4 records acceptance the
  same way) and the ``quotation.accepted`` booking hand-off event. The project domain is not built here.

**Fail closed.** Digital acceptance needs, besides the flag: OI-MTQ-08 (validity), OI-MTQ-09 (terms, milestones,
warranty), OI-MTQ-11 including CUSTOMER_DIGITAL, CQX-D01 with an implemented verification method, CQX-D03 and CQX-D04,
the required customer-safe content, and an issued, open version. Until each is recorded the proposal stays viewable and
the page says acceptance is not available yet; nothing here gives a digital signature any legal status.
"""

from __future__ import annotations

import hashlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, db, outbox
from veda.kernel.context import acting, current_actor, system_context
from veda.kernel.errors import ApiError
from veda.kernel.ids import ANONYMOUS_USER_ID
from veda.kernel.jcs import canonical_bytes
from veda.modules.crm.leads import service as lead_service
from veda.modules.crm.leads.models import Lead
from veda.modules.mtq import sets as site_sets
from veda.modules.mtq_commercial import policy as commercial_policy
from veda.modules.mtq_commercial import quotations
from veda.modules.mtq_commercial.models import Quotation

from . import acknowledgements, events, grants, policy, projection, selections
from . import vocab as V
from .models import ProposalAccessGrant, QuotationAcceptanceEvidence
from .requests import key_digest

METHOD = "CUSTOMER_DIGITAL"
NOT_AVAILABLE = (
    "Digital acceptance is not available for this proposal yet. Please contact your Veda Spaces representative."
)


def _b(code: str, message: str, decision: str | None = None, customer: str | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "decision": decision, "customer": customer}


def blockers(s: Session, g: ProposalAccessGrant, q: Quotation, decision: str = "ACCEPTED") -> list[dict[str, Any]]:
    """Everything that stops a digital decision on ``q`` now, each with a staff message and, where the customer can act,
    customer words. Declining needs the method, verification and evidence decisions but no acknowledgements."""
    out: list[dict[str, Any]] = []
    if g.recipient_kind not in V.DECIDING_KINDS:
        out.append(_b("RECIPIENT_NOT_AUTHORISED", f"A {g.recipient_kind} link cannot decide; only the primary customer's.",
                      customer="Only the primary customer's link can accept or decline this proposal."))  # fmt: skip
    state = grants.proposal_state(s, q)
    if state != "OPEN":
        out.append(_b("PROPOSAL_NOT_OPEN", f"The proposal is {state.lower()}."))
    decisions = ["OI-MTQ-11"] + (["OI-MTQ-08", "OI-MTQ-09"] if decision == "ACCEPTED" else [])
    for code in decisions:
        if commercial_policy.decision(code) is None:
            out.append(_b("OWNER_DECISION_REQUIRED", commercial_policy.required(code)["message"], code))
    methods = commercial_policy.decision("OI-MTQ-11")
    if methods is not None and METHOD not in methods.methods:
        out.append(_b("METHOD_NOT_APPROVED", "OI-MTQ-11 does not include digital acceptance (CUSTOMER_DIGITAL).",
                      "OI-MTQ-11"))  # fmt: skip
    verification = policy.decision("CQX-D01")
    if verification is None:
        out.append(_b("OWNER_DECISION_REQUIRED", policy.required("CQX-D01")["message"], "CQX-D01"))
    elif verification.method not in policy.IMPLEMENTED_VERIFICATION:
        out.append(_b("VERIFICATION_NOT_IMPLEMENTED", f"Verification {verification.method} is chosen but not built.",
                      "CQX-D01"))  # fmt: skip
    for code in ("CQX-D04",) + (("CQX-D03",) if decision == "ACCEPTED" else ()):
        if policy.decision(code) is None:
            out.append(_b("OWNER_DECISION_REQUIRED", policy.required(code)["message"], code))
    if decision != "ACCEPTED":
        return out
    try:
        p = projection.build(s, q)
    except ApiError:
        return [*out, _b("SNAPSHOT_INTEGRITY_FAILED", "The frozen document does not verify.")]
    if not (
        p["payment_schedule"] and p["warranty"] and p["terms"] and p.get("valid_until") and p["summary"].get("total")
    ):
        out.append(_b("CONTENT_MISSING", "Payment milestones, warranty, terms, validity or the total are missing."))
    required = acknowledgements.required_sections() or ()
    terms = acknowledgements.view(s, g, q, p)
    unavailable = [x["code"] for x in terms["sections"] if x["code"] in required and not x["available"]]
    if unavailable:
        out.append(
            _b("REQUIRED_SECTION_MISSING", f"Required sections without approved content: {', '.join(unavailable)}.")
        )
    pending = [c for c in terms["pending"] if c not in unavailable]
    if pending:
        out.append(_b("ACKNOWLEDGEMENT_REQUIRED", f"Not yet acknowledged: {', '.join(pending)}.",
                      customer="Please read and acknowledge the required sections first."))  # fmt: skip
    choice = selections.summary(s, q)
    if choice["selected_refs"] and choice["status"] != "CALCULATED":
        out.append(_b("PRICE_CONFIRMATION_REQUIRED", "Optional choices whose total is not shown (CQX-D02).",
                      customer="Veda Spaces needs to confirm the price of your optional choices before you can "
                               "accept. You can also remove them."))  # fmt: skip
    return out


def total_to_accept(s: Session, q: Quotation) -> int | None:
    chosen = selections.selected_lines(s, q)
    if q.total_minor is None:
        return None
    return int(q.total_minor) + sum(selections.line_value(x) for x in chosen)


def evidence_of(s: Session, q: Quotation) -> QuotationAcceptanceEvidence | None:
    return s.execute(sa.select(QuotationAcceptanceEvidence).where(QuotationAcceptanceEvidence.quotation_id == q.id)
                     ).scalar_one_or_none()  # fmt: skip


def _refuse(code: str, message: str, status: int = 409, **extra) -> ApiError:
    from veda.kernel import metrics

    metrics.emit("ProposalDecisionRefused", 1)
    return ApiError(status, code, message, extra=extra or None)


def decide(s: Session, g: ProposalAccessGrant, q: Quotation, body, idempotency_key: str | None, *, ip: str | None,
           user_agent: str | None, request_trace: str | None) -> QuotationAcceptanceEvidence:  # fmt: skip
    digest = key_digest(idempotency_key)
    decision = "ACCEPTED" if body.decision == "ACCEPTED" else "DECLINED"
    site_sets.lock_property(s, q.property_id)
    s.refresh(q)
    found = evidence_of(s, q)
    if found is not None:
        same = found.decision == decision and sorted(found.selected_line_refs) == sorted(body.selected_line_refs)
        if found.client_key_sha256 == digest or same:
            return found  # a retry or a duplicate of the same decision: idempotent
        raise _refuse("ALREADY_DECIDED", "A decision on this version has already been recorded.")
    if body.version_no != q.version_no:
        raise _refuse("VERSION_MISMATCH", "This decision is for another version of the proposal. Please reload it.")
    projection.frozen_document(q)  # tampered documents are refused before anything else is compared
    if body.snapshot_sha256 != q.snapshot_sha256:
        raise _refuse("PROPOSAL_CHANGED", "The proposal you saw is not this version's document. Please reload it.")
    found_blockers = blockers(s, g, q, decision)
    if found_blockers:
        words = next((b["customer"] for b in found_blockers if b.get("customer")), NOT_AVAILABLE)
        raise _refuse("ACCEPTANCE_UNAVAILABLE", words, reasons=[b["code"] for b in found_blockers])
    chosen = selections.selected_lines(s, q) if decision == "ACCEPTED" else []
    chosen_refs = sorted(f"L{x.position}" for x in chosen)
    if decision == "ACCEPTED" and chosen_refs != sorted(body.selected_line_refs):
        raise _refuse("SELECTION_MISMATCH", "Your optional choices changed. Please review them and try again.")
    if decision == "DECLINED" and body.selected_line_refs:
        raise _refuse("VALIDATION_FAILED", "A decline chooses no optional items.", status=422)
    total = total_to_accept(s, q) if decision == "ACCEPTED" else q.total_minor
    shown = selections.money(total)
    if decision == "ACCEPTED" and (body.displayed_total or "") != (shown or ""):
        raise _refuse("TOTAL_MISMATCH", "The total you saw is not the current total. Please reload the proposal.")
    quotations.record_decision(s, q, decision="ACCEPTED" if decision == "ACCEPTED" else "REJECTED", method=METHOD,
                               chosen=[x.id for x in chosen], note=None, recorded_by=ANONYMOUS_USER_ID)  # fmt: skip
    now = q.decided_on or db.tx_time(s)
    p = projection.build(s, q)
    acks = acknowledgements.existing(s, q, g)
    acknowledged = [{"section": c, "section_sha256": a.section_sha256, "acknowledged_on": clock.to_rfc3339(a.created_on)}
                    for c, a in sorted(acks.items())]  # fmt: skip
    meta = policy.decision("CQX-D04")
    network = {k: v for k, v in (("ip", ip if meta and meta.record_ip else None),
                                 ("user_agent", user_agent if meta and meta.record_user_agent else None)) if v}  # fmt: skip
    verification = policy.decision("CQX-D01")
    evidence = {
        "decision": decision, "method": METHOD, "verification_method": verification.method,
        "quotation_number": q.quotation_number, "variation_no": q.variation_no, "version_no": q.version_no,
        "snapshot_sha256": q.snapshot_sha256, "issued_html_sha256": q.issued_html_sha256,
        "accepted_baseline_sha256": q.accepted_baseline_sha256, "displayed_total": shown, "accepted_total_minor":
        q.accepted_total_minor, "selected": [{"ref": f"L{x.position}", "description": x.description,
                                              "amount": selections.money(x.amount_minor)} for x in chosen],
        "acknowledged": acknowledged, "decided_on": clock.to_rfc3339(now), "grant_id": g.id,
        "recipient_kind": g.recipient_kind, "request_trace": request_trace, "client_key_sha256": digest,
        "policy": {"commercial": commercial_policy.current().version, "proposal": policy.current().version},
        "network_recorded": sorted(network), "reference": p["reference"],
    }  # fmt: skip
    row = QuotationAcceptanceEvidence(
        lead_id=q.lead_id, quotation_id=q.id, quotation_number=q.quotation_number, variation_no=q.variation_no,
        version_no=q.version_no, grant_id=g.id, decision=decision, method=METHOD,
        verification_method=verification.method, snapshot_sha256=q.snapshot_sha256 or "",
        issued_html_sha256=q.issued_html_sha256 or "", displayed_total_minor=total, selected_line_refs=chosen_refs,
        acknowledgements=acknowledged, decided_on=now, request_trace=request_trace, client_key_sha256=digest,
        network=network or None, evidence=evidence, evidence_sha256=hashlib.sha256(canonical_bytes(evidence)).hexdigest(),
    )  # fmt: skip
    s.add(row)
    s.flush()
    events.record(s, q.id, q.lead_id, decision, grant=g, evidence_sha256=row.evidence_sha256,
                  accepted_total_minor=q.accepted_total_minor if decision == "ACCEPTED" else None)  # fmt: skip
    outbox.enqueue(s, events.ACCEPTED if decision == "ACCEPTED" else events.DECLINED, "quotation", q.id,
                   quotation_id=q.id, grant_id=g.id, evidence_id=row.id)  # fmt: skip
    _lead_activity(s, q, decision, row)
    return row


def _lead_activity(s: Session, q: Quotation, decision: str, row: QuotationAcceptanceEvidence) -> None:
    """Through the lead service, as SYSTEM (as B4 does on issue): an activity carrying the ids; no status change."""
    lead = s.get(Lead, q.lead_id)
    if lead is None:
        return
    caller = current_actor()
    words = "accepted" if decision == "ACCEPTED" else "declined"
    with acting(s, system_context("SYSTEM_JOB", caller.request_id if caller else None)):
        lead_service.add_system_activity(s, lead, "SYSTEM", f"Quotation {quotations.number_label(q)} {words} by the "
                                         "customer (digital)", metadata={"quotation_id": q.id,
                                         "evidence_id": row.id, "event": f"quotation_{words}_digitally"})  # fmt: skip


def customer_view(s: Session, g: ProposalAccessGrant, q: Quotation, page: dict[str, Any]) -> dict[str, Any]:
    found = evidence_of(s, q)
    if found is not None:
        mine = found.grant_id == g.id
        return {"available": False, "decided": found.decision, "decided_on": clock.to_rfc3339(found.decided_on),
                "by_this_link": mine, "total": selections.money(found.displayed_total_minor) if mine else None,
                "selected_refs": found.selected_line_refs if mine else [],
                "evidence_sha256": found.evidence_sha256 if mine else None}  # fmt: skip
    if not page["capabilities"]["acceptance"]:
        return {"available": False, "decided": None, "reason": NOT_AVAILABLE if page["state"] == "OPEN" else None}
    found_blockers = blockers(s, g, q)
    total = total_to_accept(s, q)
    return {"available": not found_blockers, "decided": None,
            "reason": None if not found_blockers else next((b["customer"] for b in found_blockers if b.get("customer")),
                                                          NOT_AVAILABLE),
            "can_decline": not blockers(s, g, q, "DECLINED"),
            "version_no": q.version_no, "snapshot_sha256": q.snapshot_sha256,
            "total": selections.money(total) if not found_blockers else None,
            "selected_refs": selections.summary(s, q)["selected_refs"],
            "statement": f"I accept {page['proposal']['reference']} as shown, including the optional items I chose, "
                         "and I have read the sections I acknowledged."}  # fmt: skip


def contribute(s: Session, g: ProposalAccessGrant, q: Quotation, page: dict[str, Any]) -> None:
    page["decision"] = customer_view(s, g, q, page)
    if page["decision"].get("available"):
        page["actions"].append({"code": "DECIDE", "label": "Accept or decline the proposal", "target": "decision"})


def staff_view(s: Session, g_kind: dict[str, str], q: Quotation) -> dict[str, Any]:
    found = evidence_of(s, q)
    out: dict[str, Any] = {"evidence": None, "blockers": []}
    if found is not None:
        verified = hashlib.sha256(canonical_bytes(found.evidence)).hexdigest() == found.evidence_sha256
        out["evidence"] = {"decision": found.decision, "method": found.method, "verification_method": found.verification_method,
                           "decided_on": clock.to_rfc3339(found.decided_on), "recipient_kind": g_kind.get(found.grant_id),
                           "version_no": found.version_no, "snapshot_sha256": found.snapshot_sha256,
                           "issued_html_sha256": found.issued_html_sha256,
                           "displayed_total": selections.money(found.displayed_total_minor),
                           "selected_line_refs": found.selected_line_refs, "acknowledgements": found.acknowledgements,
                           "network": found.network, "evidence_sha256": found.evidence_sha256,
                           "evidence_verified": verified, "evidence": found.evidence}  # fmt: skip
    live = s.execute(sa.select(ProposalAccessGrant).where(ProposalAccessGrant.quotation_id == q.id)
                     .order_by(ProposalAccessGrant.created_on.desc()).limit(1)).scalar_one_or_none()  # fmt: skip
    if live is not None and found is None:
        out["blockers"] = [{k: v for k, v in b.items() if k != "customer"} for b in blockers(s, live, q)]
    return out


PAGE_FIELDS: dict[str, str] = {
    **{
        f"decision.{k}": "the customer's decision state"
        for k in (
            "available",
            "decided",
            "decided_on",
            "by_this_link",
            "total",
            "selected_refs[]",
            "evidence_sha256",
            "reason",
            "can_decline",
            "version_no",
            "snapshot_sha256",
            "statement",
        )
    },
}
