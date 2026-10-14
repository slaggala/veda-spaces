"""Internal estimates (blueprint §9; instruction B3.1-B3.7): a reviewed BOQ priced with the rate card in force.

**One pricing engine.** Every rate comes from the ACTIVE estimator rate card (the card the estimator and Catalogue V3
already govern: versioned, approved, immutable once active), and every amount is the estimator engine's own
``line_amount_minor`` (quantity × rate, paise, half up). Provenance per line: BOQ line → card product and line →
card version and document digest → tier → rate → amount. An estimate is priced with exactly the card its BOQ was built
against (same card row and document digest; anything else is refused as PRICING_CONTEXT_MISMATCH, and the BOQ is stale
once another card is active). A later card never changes a stored estimate: it is reported stale (RATE_CARD_CHANGED,
CATALOGUE_CHANGED), never re-priced in place, and ``reproduce`` recomputes it from its pinned card document.

**Nothing is invented.** A line without an approved rate is kept, unpriced, with the reason: a tier without approved
staff rates (RATE_CARD_NOT_APPROVED, OI-MTQ-05), a finish variant without a rate (FINISH_RATE_NOT_APPROVED), an item
with no card line (CATALOGUE_MAPPING_MISSING), a preparation-package driver not decided (OWNER_DECISION_REQUIRED,
OI-MTQ-15) — owner decisions, which block customer issuance — or a data gap (RATE_MISSING, QUANTITY_MISSING),
which blocks approval. The Custom Features Allowance (ADR-012 D9) is not carried: a measured quotation replaces it
with the actual items. Labour and installation are inside the card's supply-and-install rates; nothing separate is
charged for them.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, db
from veda.kernel.errors import ApiError
from veda.kernel.jcs import canonical_bytes
from veda.modules.estimator import engine, ratecard
from veda.modules.estimator.models import EstimatorRateCard
from veda.modules.mtq.models import Property

from . import boqs, lineage, policy, requirements, rules, tax
from . import vocab as V
from .models import Boq, BoqLine, CostEstimate, CostEstimateAdjustment, CostEstimateLine, Scope, ScopeItem

PREP_COMPONENTS = {
    "FLOOR_PROTECTION": "SITE_PROTECTION",
    "PLY_PROTECTION": "SITE_PROTECTION",
    "FREIGHT": "TRANSPORT",
    "DEBRIS": "OTHER_SERVICE",
    "DEEP_CLEANING": "OTHER_SERVICE",
    "PEST_CONTROL": "OTHER_SERVICE",
}
ITEM_COMPONENTS = {"ELECTRICAL_SHIFTING": "ELECTRICAL_SHIFTING", "SENSOR_LIGHTING": "ELECTRICAL_SHIFTING"}
DATA_BLOCKERS = frozenset({"RATE_MISSING", "QUANTITY_MISSING", "QUANTITY_BASIS_CHANGED"})
LINE_FIELDS = ("id", "boq_line_id", "scope_item_id", "requirement_id", "space_id", "position", "component_code",
               "category_code", "card_product_code", "card_line_code", "prep_component_code", "item_type_code",
               "label", "uom_code", "quantity_centi", "tier_code", "finish_code", "rate_minor", "rate_status",
               "rate_note", "amount_minor", "discount_minor", "taxable_minor", "tax_rate_bp", "tax_minor",
               "is_optional", "dimension_source_code", "provenance")  # fmt: skip


def tier_approved(card: ratecard.RateCard, tier: str) -> bool:
    """ESSENTIAL is approved by the card's own activation (owner approval reference); PREMIUM and LUXURY also need
    the card to enable them and the owner's staff-rate decision (OI-MTQ-05)."""
    if not card.packages.get(tier):
        return False
    if tier == "ESSENTIAL":
        return True
    rates = policy.decision("OI-MTQ-05")
    return rates is not None and tier in rates.staff_tiers


def _card_row(s: Session, row_id: str) -> tuple[EstimatorRateCard, ratecard.RateCard]:
    row = s.get(EstimatorRateCard, row_id)
    assert row is not None
    return row, ratecard.parse(row.document)


def _price(card: ratecard.RateCard, line: BoqLine, item: ScopeItem | None, tier: str) -> dict[str, Any]:
    """The rate of one BOQ line: rate, status and note (never an invented value)."""
    finish = item.finish_code if item else None
    prov = {"card_version": card.version, "tier": tier, "product": line.card_product_code, "line": line.card_line_code}
    if line.card_product_code is None:
        itype = rules.item_type(line.item_type_code)
        return {"rate_minor": None, "rate_status": "CATALOGUE_MAPPING_MISSING", "rate_note": itype.unmapped_reason,
                "provenance": prov}  # fmt: skip
    product = card.product(line.card_product_code)
    spec = next((x for x in product.lines if x.code == line.card_line_code), None) if product else None
    if spec is None:
        return {"rate_minor": None, "rate_status": "RATE_MISSING", "provenance": prov,
                "rate_note": f"Rate card {card.version} has no line {line.card_product_code}.{line.card_line_code}."}  # fmt: skip
    if line.final_quantity_centi is None:
        return {"rate_minor": None, "rate_status": "QUANTITY_MISSING", "provenance": prov,
                "rate_note": "The BOQ line has no quantity."}  # fmt: skip
    if finish is not None:
        rates = policy.decision("OI-MTQ-05")
        key = f"{line.card_product_code}.{line.card_line_code}"
        variant = (rates.finish_rates.get(finish, {}).get(key, {}).get(tier)) if rates else None
        if variant is None:
            return {"rate_minor": None, "rate_status": "FINISH_RATE_NOT_APPROVED", "provenance": {**prov, "finish": finish},
                    "rate_note": f"No approved {finish.lower()} rate for {key} (owner decision OI-MTQ-05)."}  # fmt: skip
        return {"rate_minor": int(variant), "rate_status": "PRICED", "provenance": {**prov, "finish": finish,
                "rate_source": f"policy {policy.current().version} finish_rates"}, "rate_note": None}  # fmt: skip
    if tier not in spec.rates:
        return {"rate_minor": None, "rate_status": "RATE_MISSING", "provenance": prov,
                "rate_note": f"Rate card {card.version} has no {tier} rate for {spec.code}."}  # fmt: skip
    return {"rate_minor": int(spec.rates[tier]), "rate_status": "PRICED",
            "provenance": {**prov, "rate_source": "card"}, "rate_note": None}  # fmt: skip


def _home_size(prop: Property) -> tuple[str | None, str]:
    """The card's preparation key for this property, from the derived bedroom count (never a stored BHK)."""
    beds = int(prop.derived_bedroom_count or 0)
    drivers = policy.decision("OI-MTQ-15")
    mapped = (drivers.home_size_by_bedrooms or {}).get(str(beds)) if drivers else None
    if mapped:
        return mapped, f"{beds} bedrooms → {mapped} (policy {policy.current().version})"
    if 1 <= beds <= 4:
        return f"{beds}BHK", f"{beds} bedrooms derived from the space tree"
    return None, f"{beds} bedrooms: no approved preparation amount (owner decision OI-MTQ-15)"


def _prep_lines(card: ratecard.RateCard, prop: Property, categories: set[str], tier: str) -> list[dict[str, Any]]:
    out = []
    size, size_note = _home_size(prop)
    ih = prop.property_type_code == "INDEPENDENT_HOUSE"
    drivers = policy.decision("OI-MTQ-15")
    ih_factor = drivers.independent_house_factor_bp if drivers else None
    for comp in card.project_preparation:
        if not categories & set(comp.applies_to):
            continue
        base = {"component_code": PREP_COMPONENTS.get(comp.code, "OTHER_SERVICE"), "category_code": "PROJECT",
                "prep_component_code": comp.code, "label": f"{engine.PREP_PACKAGE}: {comp.label}"[:300],
                "uom_code": "LUMP", "quantity_centi": 100, "dimension_source_code": "DERIVED"}  # fmt: skip
        prov = {"card_version": card.version, "tier": tier, "prep_component": comp.code, "driver": size_note,
                "property_type": prop.property_type_code}  # fmt: skip
        if size is None or size not in comp.amounts:
            note = size_note if size is None else f"Rate card {card.version} has no {size} amount for {comp.code}."
            out.append({**base, "rate_minor": None, "rate_status": "OWNER_DECISION_REQUIRED", "rate_note": note,
                        "provenance": prov})  # fmt: skip
            continue
        if ih and ih_factor is None:
            out.append({**base, "rate_minor": None, "rate_status": "OWNER_DECISION_REQUIRED", "provenance": prov,
                        "rate_note": "Independent-house factor not decided (owner decision OI-MTQ-15); the card's "
                                     "villa factor is not applied to an independent house."})  # fmt: skip
            continue
        amount = Decimal(comp.amounts[size])
        if ih and ih_factor is not None:
            amount = amount * Decimal(ih_factor) / Decimal(10_000)
            prov["independent_house_factor_bp"] = ih_factor
        out.append({**base, "rate_minor": engine.paise(amount), "rate_status": "PRICED", "rate_note": None,
                    "provenance": {**prov, "home_size": size, "rate_source": "card project_preparation"}})  # fmt: skip
    return out


def _next_revision(s: Session, property_id: str) -> int:
    top = s.execute(
        sa.select(sa.func.max(CostEstimate.revision_no))
        .where(CostEstimate.property_id == property_id)
        .execution_options(include_deleted=True)
    ).scalar()
    return int(top or 0) + 1


def create(s: Session, ctx, boq: Boq, prop: Property, body) -> CostEstimate:
    """Price a reviewed, current BOQ. Supersedes the open draft (an explicit regeneration)."""
    from . import estimator_card

    require_lineage(s, boq, prop)
    if boq.status != "REVIEWED":
        raise ApiError(409, "BOQ_NOT_REVIEWED", "An estimate prices a reviewed BOQ.", extra={"status": boq.status})
    reasons = lineage.boq_reasons(s, boq)
    if reasons:
        raise ApiError(409, "BOQ_STALE", "The BOQ is out of date; regenerate and review it first.",
                       extra={"reasons": reasons})  # fmt: skip
    card_row, card = estimator_card.active(s)
    if card_row.id != boq.catalogue_card_id or card_row.document_sha256 != boq.catalogue_card_sha256:
        # Exact consistency: the BOQ's lines are the product structure of the card it was built against. Pricing it
        # with another card would silently drop lines that card adds (or keep lines it removed); regenerate instead.
        raise ApiError(409, "PRICING_CONTEXT_MISMATCH", f"BOQ revision {boq.revision_no} was built against rate card "
                       f"{boq.catalogue_card_version}; the active card is {card_row.card_version}. Regenerate and "
                       "review the BOQ against the card in force, then price it.",
                       extra={"boq_card_version": boq.catalogue_card_version,
                              "active_card_version": card_row.card_version})  # fmt: skip
    tier = body.tier_code
    if not tier_approved(card, tier):
        raise ApiError(409, "RATE_CARD_NOT_APPROVED",
                       f"{tier.title()} has no approved staff rates on rate card {card.version} (owner decision "
                       "OI-MTQ-05); price this BOQ in an approved tier.", extra={"tier_code": tier,
                       "decision": "OI-MTQ-05"})  # fmt: skip
    scope = s.get(Scope, boq.scope_id)
    assert scope is not None
    draft = s.execute(
        sa.select(CostEstimate).where(CostEstimate.property_id == prop.id, CostEstimate.status == "DRAFT")
    ).scalar_one_or_none()
    if draft is not None:
        draft.status = "SUPERSEDED"
        s.flush()
    est = CostEstimate(
        lead_id=prop.lead_id, property_id=prop.id, boq_id=boq.id, boq_revision_no=boq.revision_no,
        boq_snapshot_sha256=boq.snapshot_sha256 or "", scope_id=scope.id, scope_revision_no=scope.revision_no,
        measurement_set_id=boq.measurement_set_id, measurement_revision_no=boq.measurement_revision_no,
        revision_no=_next_revision(s, prop.id), supersedes_estimate_id=draft.id if draft else None, status="DRAFT",
        tier_code=tier, rate_card_id=card_row.id, rate_card_version=card_row.card_version,
        rate_card_sha256=card_row.document_sha256, calculation_version=engine.CALCULATION_VERSION,
        policy_version=policy.current().version, policy_sha256=policy.sha256(), pricing_basis_code="MEASURED",
        tax_status="GST_POLICY_REQUIRED", notes=body.notes,
    )  # fmt: skip
    s.add(est)
    s.flush()
    items = {i.id: i for i in scopes_items(s, scope)}
    position = 0
    categories: set[str] = set()
    for line in boqs.lines(s, boq):
        item = items.get(line.scope_item_id)
        priced = _price(card, line, item, tier)
        product = card.product(line.card_product_code) if line.card_product_code else None
        category = product.category if product else "UNMAPPED"
        if not line.is_optional and product is not None:
            categories.add(product.category)
        position += 1
        amount = (
            engine.line_amount_minor(Decimal(line.final_quantity_centi) / 100, priced["rate_minor"])
            if priced["rate_status"] == "PRICED" and line.final_quantity_centi is not None
            else None
        )
        s.add(CostEstimateLine(
            estimate_id=est.id, boq_line_id=line.id, scope_item_id=line.scope_item_id,
            requirement_id=line.requirement_id, space_id=line.space_id, position=position,
            component_code=ITEM_COMPONENTS.get(line.item_type_code, "PRODUCT"), category_code=category,
            card_product_code=line.card_product_code, card_line_code=line.card_line_code,
            item_type_code=line.item_type_code, label=line.label, uom_code=line.uom_code,
            quantity_centi=line.final_quantity_centi, tier_code=tier, finish_code=item.finish_code if item else None,
            rate_minor=priced["rate_minor"] if priced["rate_status"] == "PRICED" else None,
            rate_status=priced["rate_status"], rate_note=(priced.get("rate_note") or None),
            amount_minor=amount, discount_minor=0, is_optional=line.is_optional,
            dimension_source_code=line.dimension_source_code,
            provenance={**priced["provenance"], "boq_id": boq.id, "boq_revision_no": boq.revision_no,
                        "boq_line_id": line.id, "derivation": line.derivation,
                        "measurement_source": line.measurement_source},
        ))  # fmt: skip
    for data in _prep_lines(card, prop, categories, tier):
        position += 1
        rate = data.pop("rate_minor")
        s.add(CostEstimateLine(estimate_id=est.id, position=position, tier_code=tier, is_optional=False,
                               rate_minor=rate, amount_minor=rate if data["rate_status"] == "PRICED" else None,
                               discount_minor=0, **data))  # fmt: skip
    s.flush()
    recompute(s, est)
    return est


def require_lineage(s: Session, boq: Boq, prop: Property) -> None:
    """The BOQ, its scope and its measurement set all belong to ``prop`` and to each other (never mixed lineage)."""
    from veda.modules.mtq.models import MeasurementSet

    scope = s.get(Scope, boq.scope_id)
    mset = s.get(MeasurementSet, boq.measurement_set_id)
    bad = []
    if boq.property_id != prop.id:
        bad.append("boq")
    if scope is None or scope.property_id != prop.id or scope.measurement_set_id != boq.measurement_set_id:
        bad.append("scope")
    if mset is None or mset.property_id != prop.id:
        bad.append("measurement_set")
    if bad:
        raise ApiError(422, "LINEAGE_MISMATCH", "The BOQ's lineage does not belong to this property.",
                       extra={"mismatched": bad})  # fmt: skip


def scopes_items(s: Session, scope: Scope) -> list[ScopeItem]:
    from . import scopes

    return scopes.items(s, scope)


def lines(s: Session, est: CostEstimate) -> list[CostEstimateLine]:
    return list(
        s.execute(
            sa.select(CostEstimateLine)
            .where(CostEstimateLine.estimate_id == est.id)
            .order_by(CostEstimateLine.position)
        ).scalars()
    )


def adjustments(s: Session, est: CostEstimate) -> list[CostEstimateAdjustment]:
    return list(
        s.execute(
            sa.select(CostEstimateAdjustment)
            .where(CostEstimateAdjustment.estimate_id == est.id)
            .order_by(CostEstimateAdjustment.created_on, CostEstimateAdjustment.id)
        ).scalars()
    )


def recompute(s: Session, est: CostEstimate) -> None:
    """Totals, discount allocation, tax and blockers, from the lines and the approved adjustments. Everything is read
    first and the estimate's totals are written together, so no flush ever sees them half-updated."""
    from . import discounts

    rows = lines(s, est)
    approved = [a for a in adjustments(s, est) if a.status == "APPROVED"]
    included = [x for x in rows if not x.is_optional and x.rate_status == "PRICED"]
    with s.no_autoflush:
        discounts.allocate(est, rows, approved)
        subtotal = sum(int(x.amount_minor or 0) for x in included)
        discount = sum(int(x.discount_minor or 0) for x in included)
        est.subtotal_minor, est.discount_minor, est.taxable_minor = subtotal, discount, subtotal - discount
        est.optional_minor = sum(int(x.amount_minor or 0) for x in rows if x.is_optional and x.rate_status == "PRICED")
        est.unpriced_lines = sum(1 for x in rows if x.rate_status != "PRICED")
        est.pricing_basis_code = "MIXED" if any(x.dimension_source_code == "ASSUMED" for x in rows) else "MEASURED"
        tax.apply(est, rows)
    est.blockers = blockers(s, est, rows)


def blockers(s: Session, est: CostEstimate, rows: list[CostEstimateLine]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_status: OrderedDict[str, list[CostEstimateLine]] = OrderedDict()
    for x in rows:
        if x.rate_status != "PRICED" and not (x.is_optional and x.rate_status in V.OWNER_DECISION_RATE_STATUSES):
            by_status.setdefault(x.rate_status, []).append(x)
    for status, xs in by_status.items():
        kind = "DATA" if status in DATA_BLOCKERS else "OWNER_DECISION"
        out.append({"code": status, "kind": kind, "severity": "BLOCKING", "lines": [x.id for x in xs],
                    "message": f"{len(xs)} line(s): " + "; ".join(sorted({x.rate_note or x.label for x in xs}))[:600],
                    "decision": "OI-MTQ-15" if status == "OWNER_DECISION_REQUIRED" else
                                ("OI-MTQ-05" if kind == "OWNER_DECISION" else None)})  # fmt: skip
    if est.tax_status == "GST_POLICY_REQUIRED":
        out.append({"code": "GST_POLICY_REQUIRED", "kind": "OWNER_DECISION", "severity": "BLOCKING",
                    "decision": "OI-MTQ-07", "message": "GST treatment is not decided (OI-MTQ-07): no tax is computed "
                    "and the total is shown before GST."})  # fmt: skip
    scope = s.get(Scope, est.scope_id)
    if scope is not None and scope.ruleset_status != rules.APPROVED_STATUS:
        out.append({"code": "RULESET_NOT_APPROVED", "kind": "OWNER_DECISION", "severity": "BLOCKING",
                    "decision": "OI-MTQ-03", "message": f"Scope ruleset {scope.ruleset_version} is PROPOSED "
                    "(OI-MTQ-03, OI-MTQ-04 undecided)."})  # fmt: skip
    if any(a.status == "PROPOSED" for a in adjustments(s, est)):
        out.append({"code": "DISCOUNT_APPROVAL_PENDING", "kind": "DATA", "severity": "BLOCKING",
                    "message": "A proposed discount awaits approval or withdrawal."})  # fmt: skip
    return out


def stale_reasons(s: Session, est: CostEstimate) -> list[dict[str, Any]]:
    boq = s.get(Boq, est.boq_id)
    assert boq is not None
    out = lineage.boq_reasons(s, boq)
    from . import estimator_card

    active = estimator_card.active_row(s)
    if active is None or active.id != est.rate_card_id:
        out.append({"code": "RATE_CARD_CHANGED", "message": f"Rate card {est.rate_card_version} is no longer the active "
                    "card; the estimate keeps its rates until it is re-priced.",
                    "active_card_version": active.card_version if active else None})  # fmt: skip
    if est.status == "SUPERSEDED":
        out.append({"code": "ESTIMATE_SUPERSEDED", "message": f"Estimate revision {est.revision_no} was superseded."})
    return out


def approve(s: Session, ctx, est: CostEstimate) -> CostEstimate:
    if est.status != "DRAFT":
        raise ApiError(409, "ESTIMATE_FROZEN", f"Estimate revision {est.revision_no} is {est.status.lower()}.")
    recompute(s, est)
    reasons = stale_reasons(s, est)
    if reasons:
        raise ApiError(
            409, "ESTIMATE_STALE", "The estimate is out of date; re-price it first.", extra={"reasons": reasons}
        )
    data = [b for b in est.blockers if b["kind"] == "DATA"]
    if data:
        raise ApiError(409, "ESTIMATE_HAS_BLOCKING_ISSUES", "Resolve the data issues before approving.",
                       extra={"blockers": data})  # fmt: skip
    if est.discount_minor > 0 and est.created_by == ctx.user.id:
        raise ApiError(
            409, "FOUR_EYES_REQUIRED", "A discounted estimate is approved by someone other than its preparer."
        )
    digest = snapshot_sha256(s, est)
    previous = s.execute(
        sa.select(CostEstimate).where(CostEstimate.property_id == est.property_id, CostEstimate.status == "APPROVED")
    ).scalar_one_or_none()
    if previous is not None:
        previous.status = "SUPERSEDED"
        s.flush()
    est.status, est.approved_on, est.approved_by = "APPROVED", db.tx_time(s), ctx.user.id
    est.snapshot_sha256 = digest
    return est


def snapshot(s: Session, est: CostEstimate) -> dict[str, Any]:
    return {
        "estimate_id": est.id, "revision_no": est.revision_no, "boq": [est.boq_id, est.boq_snapshot_sha256],
        "rate_card": [est.rate_card_version, est.rate_card_sha256], "calculation_version": est.calculation_version,
        "policy": [est.policy_version, est.policy_sha256], "tier": est.tier_code,
        "totals": [est.subtotal_minor, est.optional_minor, est.discount_minor, est.taxable_minor, est.tax_status,
                   est.tax_minor, est.total_minor],
        "lines": [{k: getattr(x, k) for k in LINE_FIELDS} for x in lines(s, est)],
        "adjustments": [{k: getattr(a, k) for k in ("id", "scope_code", "target_line_id", "target_category",
                                                     "kind_code", "value_bp", "amount_minor", "base_minor",
                                                     "discount_minor", "post_minor", "status", "authority_code")}
                        for a in adjustments(s, est)],
    }  # fmt: skip


def snapshot_sha256(s: Session, est: CostEstimate) -> str:
    return hashlib.sha256(canonical_bytes(snapshot(s, est))).hexdigest()


def reproduce(s: Session, est: CostEstimate) -> dict[str, Any]:
    """Recompute every priced amount from the pinned card document (not the active card) and compare."""
    row, card = _card_row(s, est.rate_card_id)
    sha_ok = row.document_sha256 == est.rate_card_sha256
    mismatches = []
    for x in lines(s, est):
        if x.rate_status != "PRICED" or x.card_product_code is None or x.finish_code:
            continue
        product = card.product(x.card_product_code)
        spec = next((y for y in product.lines if y.code == x.card_line_code), None) if product else None
        rate = spec.rates.get(x.tier_code) if spec else None
        amount = engine.line_amount_minor(Decimal(int(x.quantity_centi or 0)) / 100, rate) if rate is not None else None
        if rate != x.rate_minor or amount != x.amount_minor:
            mismatches.append({"line_id": x.id, "stored": [x.rate_minor, x.amount_minor], "recomputed": [rate, amount]})
    sealed = est.snapshot_sha256 is None or est.snapshot_sha256 == snapshot_sha256(s, est)
    return {"reproducible": sha_ok and not mismatches and sealed, "card_document_matches": sha_ok,
            "snapshot_matches": sealed, "mismatches": mismatches, "rate_card_version": est.rate_card_version}  # fmt: skip


def _key(x: CostEstimateLine) -> tuple:
    return (x.requirement_id or x.prep_component_code, x.card_product_code or x.item_type_code, x.card_line_code or "")


def compare(s: Session, a: CostEstimate, b: CostEstimate) -> dict[str, Any]:
    if a.property_id != b.property_id:
        raise ApiError(422, "VALIDATION_FAILED", "Both estimates must belong to the same property.")
    left, right = {_key(x): x for x in lines(s, a)}, {_key(x): x for x in lines(s, b)}
    out: list[dict[str, Any]] = []
    for key in list(OrderedDict.fromkeys([*left, *right])):
        la, rb = left.get(key), right.get(key)
        if la is None or rb is None:
            x = rb or la
            assert x is not None
            out.append({"change": "ADDED" if la is None else "REMOVED", "label": x.label, "space_id": x.space_id,
                        "from_amount_minor": la.amount_minor if la else None,
                        "to_amount_minor": rb.amount_minor if rb else None})  # fmt: skip
            continue
        tags = []
        if la.quantity_centi != rb.quantity_centi:
            tags.append("QUANTITY")
        if la.rate_minor != rb.rate_minor:
            tags.append("RATE")
        if la.finish_code != rb.finish_code or la.tier_code != rb.tier_code:
            tags.append("FINISH_OR_TIER")
        if la.discount_minor != rb.discount_minor:
            tags.append("DISCOUNT")
        if la.rate_status != rb.rate_status:
            tags.append("PRICING_STATUS")
        if tags:
            out.append({"change": "CHANGED", "tags": tags, "label": rb.label, "space_id": rb.space_id,
                        "from_quantity_centi": la.quantity_centi, "to_quantity_centi": rb.quantity_centi,
                        "from_rate_minor": la.rate_minor, "to_rate_minor": rb.rate_minor,
                        "from_amount_minor": la.amount_minor, "to_amount_minor": rb.amount_minor})  # fmt: skip
    totals = {k: {"from": getattr(a, k), "to": getattr(b, k)} for k in
              ("subtotal_minor", "optional_minor", "discount_minor", "taxable_minor", "tax_minor", "total_minor")}  # fmt: skip
    return {"from_estimate_id": a.id, "to_estimate_id": b.id, "from_revision": a.revision_no,
            "to_revision": b.revision_no, "rate_card": {"from": a.rate_card_version, "to": b.rate_card_version},
            "lines": out, "totals": totals}  # fmt: skip


def _views(rows: list[CostEstimateLine], spaces: dict) -> dict[str, Any]:
    rooms: OrderedDict[str | None, dict[str, Any]] = OrderedDict()
    cats: OrderedDict[str | None, dict[str, Any]] = OrderedDict()
    comps: OrderedDict[str | None, dict[str, Any]] = OrderedDict()
    for x in rows:
        sp = spaces.get(x.space_id) if x.space_id else None
        for bucket, key, label in ((rooms, x.space_id, sp.label if sp else "Project"),
                                   (cats, x.category_code, x.category_code.replace("_", " ").title()),
                                   (comps, x.component_code, x.component_code.replace("_", " ").title())):  # fmt: skip
            b = bucket.setdefault(key, {"key": key, "label": label, "amount_minor": 0, "discount_minor": 0,
                                        "optional_minor": 0, "unpriced_lines": 0})  # fmt: skip
            if x.rate_status != "PRICED":
                b["unpriced_lines"] += 1
            elif x.is_optional:
                b["optional_minor"] += int(x.amount_minor or 0)
            else:
                b["amount_minor"] += int(x.amount_minor or 0)
                b["discount_minor"] += int(x.discount_minor or 0)
    return {"rooms": list(rooms.values()), "categories": list(cats.values()), "components": list(comps.values())}


def present_line(x: CostEstimateLine, spaces: dict, *, rates: bool) -> dict[str, Any]:
    sp = spaces.get(x.space_id) if x.space_id else None
    out = {k: getattr(x, k) for k in LINE_FIELDS if k != "provenance"}
    out["space_label"] = sp.label if sp else None
    out["version"] = x.version
    if rates:
        out["provenance"] = x.provenance
    else:  # amounts only: no unit rate, no card path
        out["rate_minor"] = None
        out["provenance"] = None
    return out


def present(s: Session, est: CostEstimate, ctx=None, *, full: bool = True) -> dict[str, Any]:
    rates = ctx is None or ctx.scope("cost_estimate.rate.view") is not None
    prop = s.get(Property, est.property_id)
    assert prop is not None
    spaces = requirements.spaces_of(s, prop)
    rows = lines(s, est)
    out: dict[str, Any] = {
        "id": est.id, "version": est.version, "property_id": est.property_id, "lead_id": est.lead_id,
        "revision_no": est.revision_no, "status": est.status, "tier_code": est.tier_code,
        "boq_id": est.boq_id, "boq_revision_no": est.boq_revision_no, "scope_id": est.scope_id,
        "scope_revision_no": est.scope_revision_no, "measurement_set_id": est.measurement_set_id,
        "measurement_revision_no": est.measurement_revision_no, "supersedes_estimate_id": est.supersedes_estimate_id,
        "rate_card_version": est.rate_card_version if rates else None,
        "rate_card_sha256": est.rate_card_sha256 if rates else None,
        "calculation_version": est.calculation_version, "policy_version": est.policy_version,
        "pricing_basis_code": est.pricing_basis_code, "currency": est.currency,
        "subtotal_minor": est.subtotal_minor, "optional_minor": est.optional_minor,
        "discount_minor": est.discount_minor, "taxable_minor": est.taxable_minor, "tax_status": est.tax_status,
        "tax_minor": est.tax_minor, "total_minor": est.total_minor, "unpriced_lines": est.unpriced_lines,
        "blockers": est.blockers or [], "approved_on": clock.to_rfc3339(est.approved_on) if est.approved_on else None,
        "approved_by": est.approved_by, "snapshot_sha256": est.snapshot_sha256, "notes": est.notes,
        "created_by": est.created_by, "created_on": clock.to_rfc3339(est.created_on),
        "lineage": {"stale": False, "reasons": []},
        "views": _views(rows, spaces),
    }  # fmt: skip
    reasons = stale_reasons(s, est)
    out["lineage"] = {"stale": bool(reasons), "reasons": reasons}
    if full:
        out["lines"] = [present_line(x, spaces, rates=rates) for x in rows]
        from . import discounts

        out["adjustments"] = [discounts.present(a) for a in adjustments(s, est)]
        out["discount_policy"] = discounts.policy_view()
    return out
