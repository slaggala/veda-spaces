"""Quotations (blueprint §10; instruction B4.1-B4.8).

A quotation version is built from an APPROVED, current estimate: one customer line per estimate line, in room-wise
sections, a project section and an optional-items section, with the terms snapshot of the commercial policy in force.
It references its whole lineage (property, measurement revision, scope, BOQ and estimate revisions with the estimate's
sealed digest).

Lifecycle (instruction B4.3)::

    DRAFT ─submit─► INTERNAL_REVIEW ─approve─► APPROVED ─issue─► ISSUED ─► ACCEPTED / REJECTED / EXPIRED
      ▲                 │ return                 │ return                  └─► SUPERSEDED (a newer version issued)
      └─────────────────┴────────────────────────┘

Only a DRAFT changes. ISSUE freezes the version: the customer document is stored with its digest, and nothing about
it changes again (a change is a new version, never an edit). Issue requires the quotation to be customer-issuable:
no stale lineage, every included line priced, and every owner decision it depends on recorded (GST, validity, terms
and payment milestones, warranty, acceptance mechanism; the scope ruleset; for a variation, the variation policy).
Numbers come from the platform's number sequence (``QUOTATION``), allocated under its row lock.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, db, sequences
from veda.kernel.context import acting, current_actor, system_context
from veda.kernel.errors import ApiError, field_error
from veda.modules.crm.leads import service as lead_service
from veda.modules.crm.leads.models import OPEN_STATUSES, Lead
from veda.modules.mtq.models import Property
from veda.modules.mtq.visits import SystemLeadContext

from . import estimates, policy, requirements
from . import vocab as V
from .models import (
    CostEstimate,
    CostEstimateLine,
    Quotation,
    QuotationEvent,
    QuotationLine,
    QuotationSection,
    Requirement,
)

TERMINAL = ("ACCEPTED", "REJECTED", "EXPIRED", "SUPERSEDED")
FINISH_TEXT = {"LAMINATE": "Laminate finish", "ACRYLIC": "Acrylic finish", "VENEER": "Veneer finish",
               "PU": "PU finish", "GLASS": "Glass finish", "MEMBRANE": "Membrane finish", "CUSTOM": "Custom finish"}  # fmt: skip


def number_label(q: Quotation) -> str:
    base = q.quotation_number if q.variation_no == 0 else f"{q.quotation_number}-V{q.variation_no:02d}"
    return f"{base} v{q.version_no}"


def event(s: Session, q: Quotation, code: str, frm: str | None = None, to: str | None = None, **detail) -> None:
    s.add(QuotationEvent(quotation_id=q.id, event_code=code, from_status=frm, to_status=to, detail=detail))


def line_key(x: CostEstimateLine) -> str:
    return f"{x.requirement_id or x.prep_component_code}:{x.card_product_code or x.item_type_code}:{x.card_line_code or ''}"


# --- terms snapshot ----------------------------------------------------------------------------------------------------
def terms_snapshot(s: Session, est: CostEstimate, *, variation: bool = False) -> dict[str, Any]:
    """The terms in force for this version: the policy's (when recorded) plus facts from this scope (its exclusions and
    the dimensions it quotes on assumption). Undecided parts are absent, never filled in."""
    from .models import Scope, ScopeItem

    p = policy.current()
    validity = policy.decision("OI-MTQ-08")
    terms_d = policy.decision("OI-MTQ-09")
    shown = policy.decision("OI-MTQ-10")
    pack = policy.decision("OI-MTQ-18")
    scope = s.get(Scope, est.scope_id)
    assert scope is not None
    spaces = requirements.spaces_of(s, s.get(Property, est.property_id))  # type: ignore[arg-type]  # FK guarantees the row
    exclusions = [f"Not included: {e['label']}" + (f" ({e['space_label']})" if e.get("space_label") else "") + ", as discussed."
                  for e in scope.exclusions or []]  # fmt: skip
    assumptions = []
    for item in s.execute(sa.select(ScopeItem).where(ScopeItem.scope_id == scope.id)).scalars():
        if item.inclusion_code == "EXCLUDED":
            continue
        for name, d in ((item.dimensions or {}).get("inputs") or {}).items():
            if d.get("source") == "ASSUMED" and name not in (item.dimension_overrides or {}) and d.get("value"):
                where = spaces[item.space_id].label if item.space_id in spaces else "Project"
                assumptions.append(f"{where} – {item.label}: quoted on an assumed {name.lower().replace('_', ' ')} "
                                   f"of {d['value']} {d.get('unit', '')}".rstrip() + "; confirmed on site before production.")  # fmt: skip
    return {
        "policy_version": p.version,
        "validity_days": validity.validity_days if validity else None,
        "terms_version": terms_d.terms_version if terms_d else None,
        "payment_milestones": [m.model_dump() for m in terms_d.payment_milestones] if terms_d else None,
        "warranty": list(terms_d.warranty) if terms_d else None,
        "service_support": list(terms_d.service_support) if terms_d else [],
        "assumptions": (list(terms_d.assumptions) if terms_d else []) + assumptions,
        "exclusions": (list(terms_d.exclusions) if terms_d else []) + exclusions,
        "change_order_terms": terms_d.change_order_terms if terms_d else None,
        "cancellation_terms": terms_d.cancellation_terms if terms_d else None,
        "general_terms": list(terms_d.general_terms) if terms_d else [],
        "show_unit_rates": bool(shown.show_unit_rates) if shown else False,
        # OI-MTQ-18 as recorded when this version was drafted (frozen into the issued document; None: to be confirmed)
        "customer_pack": pack.model_dump(mode="json") if pack else None,
    }


# --- building ----------------------------------------------------------------------------------------------------------
def _necessity(s: Session, req_ids: list[str]) -> dict[str, str]:
    if not req_ids:
        return {}
    return dict(
        s.execute(sa.select(Requirement.id, Requirement.necessity_code).where(Requirement.id.in_(req_ids))).all()
    )


def _populate(s: Session, q: Quotation, est: CostEstimate) -> None:
    """Sections and lines of a base quotation from its estimate (room walk order, project, optional)."""
    rows = estimates.lines(s, est)
    prop = s.get(Property, est.property_id)
    assert prop is not None
    spaces = requirements.spaces_of(s, prop)
    order = {sid: (sp.level_index, sp.sort_order) for sid, sp in spaces.items()}
    necessity = _necessity(s, [x.requirement_id for x in rows if x.requirement_id])
    groups: dict[tuple, list[CostEstimateLine]] = {}
    for x in rows:
        if x.is_optional:
            key: tuple = (2, (0, 0), "OPTIONAL", None)
        elif x.space_id:
            key = (0, order.get(x.space_id, (99, 99)), "SPACE", x.space_id)
        else:
            key = (1, (0, 0), "PROJECT", None)
        groups.setdefault(key, []).append(x)
    position = 0
    for n, key in enumerate(sorted(groups, key=lambda k: (k[0], k[1])), start=1):
        _, _, code, space_id = key
        title = (
            spaces[space_id].label
            if space_id in spaces
            else {"PROJECT": "Project-wide", "OPTIONAL": "Optional items"}[code]
        )
        sec = QuotationSection(quotation_id=q.id, position=n, section_code=code, space_id=space_id, title=title[:120])
        s.add(sec)
        s.flush()
        for x in groups[key]:
            position += 1
            room = spaces[x.space_id].label if x.is_optional and x.space_id in spaces else None
            detail = "; ".join(t for t in (room, FINISH_TEXT.get(x.finish_code or "")) if t) or None
            priced = x.rate_status == "PRICED"
            s.add(QuotationLine(
                quotation_id=q.id, section_id=sec.id, cost_estimate_line_id=x.id, requirement_id=x.requirement_id,
                space_id=x.space_id, position=position, line_key=line_key(x)[:200], description=x.label[:300],
                detail=detail, uom_code=x.uom_code, quantity_centi=x.quantity_centi, finish_code=x.finish_code,
                rate_minor=x.rate_minor if priced else None, amount_minor=x.amount_minor if priced else None,
                discount_minor=int(x.discount_minor or 0), tax_minor=x.tax_minor, is_priced=priced,
                is_optional=x.is_optional, is_mandatory=necessity.get(x.requirement_id or "") == "MANDATORY",
            ))  # fmt: skip
        sec.subtotal_minor = sum(
            int(x.amount_minor or 0) for x in groups[key] if not x.is_optional and x.rate_status == "PRICED"
        )
        sec.optional_minor = sum(
            int(x.amount_minor or 0) for x in groups[key] if x.is_optional and x.rate_status == "PRICED"
        )
    s.flush()


def _copy_totals(q: Quotation, est: CostEstimate) -> None:
    q.base_total_minor, q.optional_minor = est.subtotal_minor, est.optional_minor
    q.discount_minor, q.taxable_minor = est.discount_minor, est.taxable_minor
    q.tax_status, q.tax_minor, q.total_minor = est.tax_status, est.tax_minor, est.total_minor


def _title(s: Session, prop: Property) -> str:
    beds = int(prop.derived_bedroom_count or 0)
    kind = "independent house" if prop.property_type_code == "INDEPENDENT_HOUSE" else "apartment"
    where = f", {prop.city}" if prop.city else ""
    return f"Interior works — {beds} BHK {kind}{where}"[:160]


def require_estimate_ready(s: Session, est: CostEstimate) -> None:
    if est.status != "APPROVED":
        raise ApiError(409, "ESTIMATE_NOT_APPROVED", "A quotation is built from an approved estimate.",
                       extra={"status": est.status})  # fmt: skip
    reasons = estimates.stale_reasons(s, est)
    if reasons:
        raise ApiError(409, "ESTIMATE_STALE", "The estimate is out of date; re-price and approve it first.",
                       extra={"reasons": reasons})  # fmt: skip


def require_lineage(s: Session, est: CostEstimate, prop: Property, *quotations_: Quotation | None) -> None:
    """Every artefact a quotation version is built from belongs to one property lineage: the quotation (and, for a
    variation, its base and baseline), the estimate, its BOQ, the BOQ's scope and the measurement set. A mismatch is
    refused before anything is created (422 LINEAGE_MISMATCH)."""
    from .models import Boq

    bad = [f"quotation {q.id}" for q in quotations_ if q is not None and q.property_id != prop.id]
    if est.property_id != prop.id:
        bad.append("estimate")
    boq = s.get(Boq, est.boq_id)
    if boq is None or boq.scope_id != est.scope_id or boq.measurement_set_id != est.measurement_set_id:
        bad.append("boq")
    if bad:
        raise ApiError(422, "LINEAGE_MISMATCH", "The estimate's lineage does not belong to this quotation's property.",
                       extra={"mismatched": bad})  # fmt: skip
    assert boq is not None
    try:
        estimates.require_lineage(s, boq, prop)
    except ApiError as err:
        raise ApiError(
            422,
            "LINEAGE_MISMATCH",
            "The estimate's lineage does not belong to this quotation's property.",
            extra=err.extra,
        ) from err


def _new(s: Session, est: CostEstimate, prop: Property, *, number: str, version_no: int, kind: str = "BASE",
         variation_no: int = 0, supersedes: Quotation | None = None, title: str | None = None, variation_of: str | None = None, baseline: str | None = None) -> Quotation:  # fmt: skip
    q = Quotation(
        quotation_number=number, version_no=version_no, quotation_kind=kind, variation_no=variation_no,
        supersedes_quotation_id=supersedes.id if supersedes else None, variation_of_quotation_id=variation_of,
        baseline_quotation_id=baseline, lead_id=prop.lead_id, property_id=prop.id,
        measurement_set_id=est.measurement_set_id, measurement_revision_no=est.measurement_revision_no,
        scope_id=est.scope_id, scope_revision_no=est.scope_revision_no, boq_id=est.boq_id,
        boq_revision_no=est.boq_revision_no, cost_estimate_id=est.id, estimate_revision_no=est.revision_no,
        estimate_snapshot_sha256=est.snapshot_sha256 or "", status="DRAFT", title=title or _title(s, prop),
        cover_note=supersedes.cover_note if supersedes else None, tier_code=est.tier_code,
        policy_version=policy.current().version, policy_sha256=policy.sha256(),
        terms=terms_snapshot(s, est, variation=kind == "VARIATION"), tax_status=est.tax_status,
    )  # fmt: skip
    _copy_totals(q, est)
    s.add(q)
    s.flush()
    return q


def create(s: Session, ctx, est: CostEstimate, prop: Property, body) -> Quotation:
    require_lineage(s, est, prop)
    require_estimate_ready(s, est)
    q = _new(s, est, prop, number=sequences.next_number(s, "QUOTATION"), version_no=1, title=body.title)
    q.cover_note = body.cover_note
    _populate(s, q, est)
    event(s, q, "CREATED", None, "DRAFT", cost_estimate_id=est.id, estimate_revision_no=est.revision_no)
    refresh_blockers(s, q)
    return q


def latest(s: Session, number: str, variation_no: int) -> Quotation:
    found = s.execute(
        sa.select(Quotation)
        .where(Quotation.quotation_number == number, Quotation.variation_no == variation_no)
        .order_by(Quotation.version_no.desc())
        .limit(1)
    ).scalar_one()
    return found


def new_version(s: Session, ctx, q: Quotation, est: CostEstimate, prop: Property, body) -> Quotation:
    """Version n+1 of the same quotation (or variation), from a (possibly newer) approved estimate. Open earlier
    versions are superseded now; an issued one when the new version is issued."""
    head = latest(s, q.quotation_number, q.variation_no)
    if head.id != q.id:
        raise ApiError(409, "QUOTATION_SUPERSEDED", f"Version {head.version_no} is the latest; revise that one.",
                       extra={"latest_quotation_id": head.id})  # fmt: skip
    if q.status == "ACCEPTED":
        raise ApiError(409, "QUOTATION_ACCEPTED", "An accepted quotation never changes; raise a variation instead.")
    if q.quotation_kind == "VARIATION":
        from . import variations

        return variations.new_version(s, ctx, q, est, prop)
    require_lineage(s, est, prop, q)
    require_estimate_ready(s, est)
    if q.status in V.OPEN_QUOTATION_STATUSES:
        _supersede(s, q)
    nq = _new(s, est, prop, number=q.quotation_number, version_no=q.version_no + 1, supersedes=q,
              title=(body.title if body else None) or q.title)  # fmt: skip
    _populate(s, nq, est)
    event(s, nq, "VERSION_CREATED", None, "DRAFT", supersedes_quotation_id=q.id, cost_estimate_id=est.id)
    refresh_blockers(s, nq)
    return nq


def _supersede(s: Session, q: Quotation) -> None:
    frm = q.status
    q.status = "SUPERSEDED"
    event(s, q, "SUPERSEDED", frm, "SUPERSEDED")
    s.flush()


def require_status(q: Quotation, *statuses: str) -> None:
    if q.status not in statuses:
        code = "QUOTATION_FROZEN" if q.status not in V.OPEN_QUOTATION_STATUSES else "INVALID_STATE"
        raise ApiError(409, code, f"{number_label(q)} is {q.status.lower().replace('_', ' ')}.",
                       extra={"status": q.status})  # fmt: skip


def edit(s: Session, ctx, q: Quotation, body) -> Quotation:
    require_status(q, "DRAFT")
    data = body.model_dump(exclude_unset=True)
    if "title" in data and body.title:
        q.title = body.title
    if "cover_note" in data:
        q.cover_note = body.cover_note
    if "customer_information" in data:
        from . import customer_pack

        q.customer_inputs = (
            None if body.customer_information is None
            else customer_pack.validate_inputs((q.terms or {}).get("customer_pack"),
                                               body.customer_information.model_dump())
        )  # fmt: skip
    event(s, q, "EDITED", "DRAFT", "DRAFT", fields=sorted(data))
    return q


# --- blockers ----------------------------------------------------------------------------------------------------------
def issuance_blockers(s: Session, q: Quotation) -> list[dict[str, Any]]:
    """Everything that stops this version from being customer-issuable, each with its reason."""
    from .models import QuotationLine as QL

    est = s.get(CostEstimate, q.cost_estimate_id)
    assert est is not None
    out: list[dict[str, Any]] = []
    for b in est.blockers or []:
        out.append({**b, "source": "estimate"})
    for r in estimates.stale_reasons(s, est):
        out.append({"code": "STALE_LINEAGE", "kind": "DATA", "severity": "BLOCKING", "message": r["message"],
                    "reason": r["code"]})  # fmt: skip
    if est.status != "APPROVED":
        out.append({"code": "ESTIMATE_NOT_APPROVED", "kind": "DATA", "severity": "BLOCKING",
                    "message": f"Estimate revision {est.revision_no} is {est.status.lower()}."})  # fmt: skip
    needed = ["OI-MTQ-08", "OI-MTQ-09", "OI-MTQ-11"] + (["OI-MTQ-13"] if q.quotation_kind == "VARIATION" else [])
    for code in needed:
        if policy.decision(code) is None:
            out.append({**policy.required(code), "kind": "OWNER_DECISION"})
    if q.quotation_kind == "VARIATION":
        var = policy.decision("OI-MTQ-13")
        if var is not None and not var.allowed:
            out.append({"code": "VARIATIONS_NOT_PERMITTED", "kind": "OWNER_DECISION", "severity": "BLOCKING",
                        "decision": "OI-MTQ-13", "message": "The variation policy does not permit variations."})  # fmt: skip
        rate_changes = s.execute(
            sa.select(sa.func.count()).select_from(QL).where(QL.quotation_id == q.id, QL.change_code == "CHANGE_RATE")
        ).scalar()
        if rate_changes and not (var is not None and var.rate_changes_allowed):
            out.append({"code": "VARIATION_RATE_CHANGE_NOT_PERMITTED", "kind": "OWNER_DECISION",
                        "severity": "BLOCKING", "decision": "OI-MTQ-13",
                        "message": f"{rate_changes} line(s) change an accepted rate; the variation policy does not "
                                   "permit rate changes."})  # fmt: skip
    unpriced = s.execute(
        sa.select(sa.func.count())
        .select_from(QL)
        .where(QL.quotation_id == q.id, QL.is_priced == sa.false(), QL.is_optional == sa.false())  # fmt: skip
    ).scalar()
    if unpriced:
        out.append({"code": "UNPRICED_LINES", "kind": "DATA", "severity": "BLOCKING",
                    "message": f"{unpriced} included line(s) have no approved price."})  # fmt: skip
    if q.total_minor is None:
        out.append({"code": "NO_FINAL_TOTAL", "kind": "OWNER_DECISION", "severity": "BLOCKING",
                    "decision": "OI-MTQ-07", "message": "There is no final amount until GST treatment is decided."})  # fmt: skip
    seen, unique = set(), []
    for b in out:
        key = (b["code"], b.get("decision"), b.get("reason"))
        if key not in seen:
            seen.add(key)
            unique.append(b)
    return unique


def refresh_blockers(s: Session, q: Quotation) -> list[dict[str, Any]]:
    if q.status in V.OPEN_QUOTATION_STATUSES:
        q.blockers = issuance_blockers(s, q)
    return q.blockers or []


# --- lifecycle ---------------------------------------------------------------------------------------------------------
def submit(s: Session, ctx, q: Quotation) -> Quotation:
    require_status(q, "DRAFT")
    q.status, q.submitted_on = "INTERNAL_REVIEW", db.tx_time(s)
    event(s, q, "SUBMITTED_FOR_REVIEW", "DRAFT", "INTERNAL_REVIEW", blockers=len(refresh_blockers(s, q)))
    return q


def return_to_draft(s: Session, ctx, q: Quotation, reason: str) -> Quotation:
    require_status(q, "INTERNAL_REVIEW", "APPROVED")
    frm = q.status
    q.status, q.approved_on, q.approved_by = "DRAFT", None, None
    event(s, q, "RETURNED_TO_DRAFT", frm, "DRAFT", reason=reason)
    return q


def approve(s: Session, ctx, q: Quotation) -> Quotation:
    require_status(q, "INTERNAL_REVIEW")
    if q.discount_minor > 0 and q.created_by == ctx.user.id:
        raise ApiError(
            409, "FOUR_EYES_REQUIRED", "A discounted quotation is approved by someone other than its preparer."
        )
    blockers = refresh_blockers(s, q)
    q.status, q.approved_on, q.approved_by = "APPROVED", db.tx_time(s), ctx.user.id
    event(s, q, "APPROVED", "INTERNAL_REVIEW", "APPROVED", open_blockers=[b["code"] for b in blockers])
    return q


def issue(s: Session, ctx, q: Quotation) -> Quotation:
    """Freeze and issue: only an approved, customer-issuable version. Supersedes an issued earlier version."""
    from . import rendering

    require_status(q, "APPROVED")
    blockers = refresh_blockers(s, q)
    if blockers:
        raise ApiError(409, "NOT_CUSTOMER_ISSUABLE", f"{len(blockers)} issue(s) stop this quotation from reaching a "
                       "customer.", extra={"blockers": blockers})  # fmt: skip
    head = latest(s, q.quotation_number, q.variation_no)
    if head.id != q.id:
        raise ApiError(409, "QUOTATION_SUPERSEDED", "A newer version exists.", extra={"latest_quotation_id": head.id})
    now = db.tx_time(s)
    validity = policy.decision("OI-MTQ-08")
    assert validity is not None  # a blocker otherwise
    for older in s.execute(
        sa.select(Quotation).where(
            Quotation.quotation_number == q.quotation_number,
            Quotation.variation_no == q.variation_no,
            Quotation.status == "ISSUED",
        )  # fmt: skip
    ).scalars():
        _supersede(s, older)
    q.issued_on, q.issued_by = now, ctx.user.id
    q.valid_until = now.date() + timedelta(days=validity.validity_days)
    rendering.freeze(s, q)
    q.status = "ISSUED"
    event(s, q, "ISSUED", "APPROVED", "ISSUED", snapshot_sha256=q.snapshot_sha256,
          html_sha256=q.issued_html_sha256, template_version=q.template_version,
          valid_until=q.valid_until.isoformat())  # fmt: skip
    _sync_lead_on_issue(s, q)
    return q


class _ToQuotationSent:
    to_status = "QUOTATION_SENT"
    comment = None
    lost_reason_code = None
    lost_reason_note = None
    won_on = None


def _sync_lead_on_issue(s: Session, q: Quotation) -> None:
    """Act as SYSTEM through the lead module (as B1 does for site visits): a system activity carrying the quotation id,
    the lead moved forward to QUOTATION_SENT if it is earlier in the pipeline (never backward, never a won or lost
    lead), and the quoted amount for a base quotation."""
    lead = s.get(Lead, q.lead_id)
    assert lead is not None
    s.flush()
    caller = current_actor()
    with acting(s, system_context("SYSTEM_JOB", caller.request_id if caller else None)):
        lead_service.add_system_activity(s, lead, "SYSTEM", f"Quotation {number_label(q)} issued",
                                         metadata={"quotation_id": q.id, "quotation_number": q.quotation_number,
                                                   "event": "quotation_issued"})  # fmt: skip
        if lead.status in OPEN_STATUSES and OPEN_STATUSES.index(lead.status) < OPEN_STATUSES.index("QUOTATION_SENT"):
            lead_service.change_status(s, SystemLeadContext(), lead, _ToQuotationSent())
        if q.quotation_kind == "BASE" and q.total_minor is not None and lead.status in OPEN_STATUSES:
            lead.quoted_amount_minor = q.total_minor
        s.flush()


def expire_due(s: Session, today=None) -> int:
    """ISSUED versions past their validity become EXPIRED. Run by the maintenance job ``veda maintenance
    mtq-quotation-expiry`` (platform.maintenance.mtq_quotation_expiry); it is NOT scheduled: scheduling it is a
    pre-customer-issuance operational requirement (OI-MTQ-08). Until then an issued version past its validity stays
    ISSUED, and recording a decision on it expires it instead (``decide``)."""
    today = today or db.tx_time(s).date()
    n = 0
    for q in s.execute(
        sa.select(Quotation).where(Quotation.status == "ISSUED", Quotation.valid_until < today)
    ).scalars():
        q.status = "EXPIRED"
        event(s, q, "EXPIRED", "ISSUED", "EXPIRED", valid_until=q.valid_until.isoformat() if q.valid_until else None)
        n += 1
    s.flush()
    return n


def decide(s: Session, ctx, q: Quotation, body) -> Quotation:
    """Record the customer's decision on the issued, latest, unexpired version (OI-MTQ-11 decides how)."""
    return record_decision(s, q, decision=body.decision, method=body.method,
                           chosen=list(dict.fromkeys(body.selected_optional_line_ids or [])), note=body.note,
                           recorded_by=ctx.user.id)  # fmt: skip


def record_decision(s: Session, q: Quotation, *, decision: str, method: str, chosen: list[str], note: str | None,
                    recorded_by: str) -> Quotation:  # fmt: skip
    """The one place a customer's decision on an issued version is recorded, whoever records it: staff (``decide``,
    STAFF_RECORDED or SIGNED_COPY) or the customer through their proposal link (CQX-10, CUSTOMER_DIGITAL). Only the
    issued, latest, unexpired version; only an approved method (OI-MTQ-11); only priced optional items of this version.
    Acceptance freezes the effective accepted baseline (the included lines plus the chosen optional items)."""
    require_status(q, "ISSUED")
    head = latest(s, q.quotation_number, q.variation_no)
    if head.id != q.id:
        raise ApiError(409, "QUOTATION_SUPERSEDED", "Only the latest version can be decided.",
                       extra={"latest_quotation_id": head.id})  # fmt: skip
    today = db.tx_time(s).date()
    if q.valid_until is not None and q.valid_until < today:
        q.status = "EXPIRED"
        event(s, q, "EXPIRED", "ISSUED", "EXPIRED")
        s.flush()
        raise ApiError(409, "QUOTATION_EXPIRED", f"{number_label(q)} expired on {q.valid_until.isoformat()}.")
    allowed = policy.decision("OI-MTQ-11")
    if allowed is None:
        raise ApiError(409, "OWNER_DECISION_REQUIRED", "How a customer's acceptance is recorded is not decided "
                       "(OI-MTQ-11).", extra={"decision": "OI-MTQ-11"})  # fmt: skip
    if method not in allowed.methods:
        raise ApiError(422, "VALIDATION_FAILED", f"{method} is not an approved acceptance method.",
                       errors=[field_error("method", "NOT_ALLOWED", "Not an approved method.")])  # fmt: skip
    lines = s.execute(sa.select(QuotationLine).where(QuotationLine.quotation_id == q.id)).scalars().all()
    optional = {x.id: x for x in lines if x.is_optional and x.is_priced}
    chosen = list(dict.fromkeys(chosen))
    if decision == "REJECTED" and chosen:
        raise ApiError(422, "VALIDATION_FAILED", "A rejection selects no optional items.")
    unknown = [i for i in chosen if i not in optional]
    if unknown:
        raise ApiError(422, "VALIDATION_FAILED", "Only priced optional items of this version can be selected.",
                       errors=[field_error("selected_optional_line_ids", "UNKNOWN_LINE", "Not an optional item.")])  # fmt: skip
    q.decision_method, q.decided_on, q.decision_recorded_by = method, db.tx_time(s), recorded_by
    q.decision_note = note
    frm = q.status
    if decision == "ACCEPTED":
        extra = sum(int(optional[i].amount_minor or 0) - int(optional[i].discount_minor or 0)
                    + int(optional[i].tax_minor or 0) for i in chosen)  # fmt: skip
        from . import variations

        q.selected_optional_line_ids = chosen
        q.accepted_total_minor = int(q.total_minor or 0) + extra
        variations.freeze_baseline(s, q, chosen)
        q.status = "ACCEPTED"
        event(s, q, "ACCEPTED", frm, "ACCEPTED", method=method, selected_optional=len(chosen),
              accepted_total_minor=q.accepted_total_minor, accepted_baseline_sha256=q.accepted_baseline_sha256)  # fmt: skip
        if q.quotation_kind == "VARIATION":
            variations.on_accepted(s, q)
    else:
        q.status = "REJECTED"
        event(s, q, "REJECTED", frm, "REJECTED", method=method)
    return q


# --- read --------------------------------------------------------------------------------------------------------------
def sections(s: Session, q: Quotation) -> list[QuotationSection]:
    return list(s.execute(
        sa.select(QuotationSection).where(QuotationSection.quotation_id == q.id).order_by(QuotationSection.position)
    ).scalars())  # fmt: skip


def lines(s: Session, q: Quotation) -> list[QuotationLine]:
    return list(s.execute(
        sa.select(QuotationLine).where(QuotationLine.quotation_id == q.id).order_by(QuotationLine.position)
    ).scalars())  # fmt: skip


def events(s: Session, q: Quotation) -> list[dict[str, Any]]:
    rows = s.execute(
        sa.select(QuotationEvent)
        .where(QuotationEvent.quotation_id == q.id)
        .order_by(QuotationEvent.created_on, QuotationEvent.id)  # fmt: skip
    ).scalars()
    return [{"event_code": e.event_code, "from_status": e.from_status, "to_status": e.to_status, "detail": e.detail,
             "actor_id": e.created_by, "occurred_on": clock.to_rfc3339(e.created_on)} for e in rows]  # fmt: skip


def snapshot_verified(q: Quotation) -> bool | None:
    if q.snapshot is None:
        return None
    from . import rendering

    return rendering.integrity(q)


def trace(s: Session, line: QuotationLine, *, rates: bool = False) -> dict[str, Any]:
    """A quotation line walked back to the measurement (instruction: core design principle)."""
    from .models import Boq, BoqLine, Scope, ScopeItem

    out: dict[str, Any] = {"quotation_line_id": line.id, "description": line.description}
    x = s.get(CostEstimateLine, line.cost_estimate_line_id) if line.cost_estimate_line_id else None
    if x is None:
        return out
    est = s.get(CostEstimate, x.estimate_id)
    assert est is not None
    out["estimate_line"] = {"id": x.id, "estimate_id": x.estimate_id, "estimate_revision_no": est.revision_no,
                            "rate_status": x.rate_status, "tier_code": x.tier_code,
                            "prep_component_code": x.prep_component_code}  # fmt: skip
    if rates:  # pricing provenance: only with cost_estimate.rate.view
        out["estimate_line"].update({"rate_card_version": est.rate_card_version,
                                     "rate_card_sha256": est.rate_card_sha256, "provenance": x.provenance})  # fmt: skip
    bl = s.get(BoqLine, x.boq_line_id) if x.boq_line_id else None
    if bl is None:
        out["driver"] = (x.provenance or {}).get("driver")
        return out
    boq = s.get(Boq, bl.boq_id)
    assert boq is not None
    out["boq_line"] = {"id": bl.id, "boq_id": bl.boq_id, "boq_revision_no": boq.revision_no,
                       "formula_kind": bl.formula_kind, "derivation": bl.derivation,
                       "calculated_quantity_centi": bl.calculated_quantity_centi,
                       "override_quantity_centi": bl.override_quantity_centi, "override_reason": bl.override_reason,
                       "final_quantity_centi": bl.final_quantity_centi}  # fmt: skip
    item = s.get(ScopeItem, bl.scope_item_id)
    scope = s.get(Scope, item.scope_id) if item else None
    if item is not None and scope is not None:
        out["scope_item"] = {"id": item.id, "scope_id": scope.id, "scope_revision_no": scope.revision_no,
                             "item_type_code": item.item_type_code, "origin_code": item.origin_code,
                             "rule_key": item.rule_key, "dimension_overrides": item.dimension_overrides,
                             "override_reason": item.override_reason}  # fmt: skip
    req = s.get(Requirement, bl.requirement_id)
    if req is not None:
        out["requirement"] = {"id": req.id, "requirement_type_code": req.requirement_type_code,
                              "source_code": req.source_code, "status": req.status, "source_ref": req.source_ref}  # fmt: skip
    out["property_space_id"] = bl.space_id
    out["measurement"] = {**(bl.measurement_source or {}),
                          "inputs": {k: v.get("refs") for k, v in ((bl.formula_inputs or {}).get("inputs") or {}).items()}}  # fmt: skip
    return out


def present(s: Session, q: Quotation, ctx=None, *, full: bool = True) -> dict[str, Any]:
    rates = ctx is None or ctx.scope("cost_estimate.rate.view") is not None
    blockers = refresh_blockers(s, q) if q.status in V.OPEN_QUOTATION_STATUSES else (q.blockers or [])
    out: dict[str, Any] = {
        "id": q.id, "version": q.version, "quotation_number": q.quotation_number, "version_no": q.version_no,
        "label": number_label(q), "quotation_kind": q.quotation_kind, "variation_no": q.variation_no,
        "variation_of_quotation_id": q.variation_of_quotation_id, "baseline_quotation_id": q.baseline_quotation_id,
        "supersedes_quotation_id": q.supersedes_quotation_id, "property_id": q.property_id, "lead_id": q.lead_id,
        "lineage": {"measurement_set_id": q.measurement_set_id, "measurement_revision_no": q.measurement_revision_no,
                    "scope_id": q.scope_id, "scope_revision_no": q.scope_revision_no, "boq_id": q.boq_id,
                    "boq_revision_no": q.boq_revision_no, "cost_estimate_id": q.cost_estimate_id,
                    "estimate_revision_no": q.estimate_revision_no,
                    "estimate_snapshot_sha256": q.estimate_snapshot_sha256},
        "status": q.status, "title": q.title, "cover_note": q.cover_note, "tier_code": q.tier_code,
        "policy_version": q.policy_version, "terms": q.terms or {}, "customer_inputs": q.customer_inputs, "currency": q.currency,
        "base_total_minor": q.base_total_minor, "optional_minor": q.optional_minor,
        "discount_minor": q.discount_minor, "taxable_minor": q.taxable_minor, "tax_status": q.tax_status,
        "tax_minor": q.tax_minor, "total_minor": q.total_minor,
        "customer_issuable": not blockers, "blockers": blockers,
        "prepared_by": q.created_by, "approved_by": q.approved_by,
        "approved_on": clock.to_rfc3339(q.approved_on) if q.approved_on else None,
        "issued_on": clock.to_rfc3339(q.issued_on) if q.issued_on else None, "issued_by": q.issued_by,
        "valid_until": q.valid_until.isoformat() if q.valid_until else None,
        "snapshot_sha256": q.snapshot_sha256, "snapshot_verified": snapshot_verified(q),
        "template_version": q.template_version, "issued_html_sha256": q.issued_html_sha256,
        "decision": ({"method": q.decision_method, "decided_on": clock.to_rfc3339(q.decided_on),
                      "recorded_by": q.decision_recorded_by, "selected_optional_line_ids": q.selected_optional_line_ids,
                      "accepted_total_minor": q.accepted_total_minor, "note": q.decision_note,
                      "accepted_baseline_sha256": q.accepted_baseline_sha256,
                      "accepted_baseline_lines": len(q.accepted_baseline or [])}
                     if q.decided_on else None),
        "created_on": clock.to_rfc3339(q.created_on),
    }  # fmt: skip
    if full:
        secs = sections(s, q)
        rows = lines(s, q)
        out["sections"] = [
            {"id": sec.id, "position": sec.position, "section_code": sec.section_code, "space_id": sec.space_id,
             "title": sec.title, "subtotal_minor": sec.subtotal_minor, "optional_minor": sec.optional_minor,
             "lines": [{"id": x.id, "position": x.position, "line_key": x.line_key, "description": x.description,
                        "detail": x.detail, "uom_code": x.uom_code, "quantity_centi": x.quantity_centi,
                        "finish_code": x.finish_code, "rate_minor": x.rate_minor if rates else None,
                        "amount_minor": x.amount_minor, "discount_minor": x.discount_minor, "tax_minor": x.tax_minor,
                        "is_priced": x.is_priced, "is_optional": x.is_optional, "is_mandatory": x.is_mandatory,
                        "change_code": x.change_code, "baseline_amount_minor": x.baseline_amount_minor,
                        "delta_amount_minor": x.delta_amount_minor, "cost_estimate_line_id": x.cost_estimate_line_id}
                       for x in rows if x.section_id == sec.id]}
            for sec in secs
        ]  # fmt: skip
        out["events"] = events(s, q)
    return out


def money(minor: int | None) -> str | None:
    return None if minor is None else str(Decimal(minor) / 100)
