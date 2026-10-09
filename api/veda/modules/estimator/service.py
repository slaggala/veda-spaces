"""Budgetary Estimate service: rate-card lifecycle, estimate persistence, lead linking and staff actions (ADR-012).

The engine (engine.py) is pure; this module stores what it computed. An estimate is immutable once created: staff
"revise" or "duplicate" by creating a new estimate that points at its source. No personal data is stored here.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy.orm import Session, object_session

from veda.config import settings
from veda.kernel import db
from veda.kernel.context import ActorContext, acting
from veda.kernel.errors import ApiError, not_found
from veda.kernel.ids import WEB_INTAKE_USER_ID

from . import activation, customer_spec, engine, promise_matrix, ratecard
from .models import (
    BudgetEstimate,
    BudgetEstimateAssumption,
    BudgetEstimateLeadLink,
    BudgetEstimateLine,
    BudgetEstimateProjectItem,
    EstimateEvent,
    EstimatorCustomerSpec,
    EstimatorCustomerSpecItem,
    EstimatorRateCard,
    EstimatorRateItem,
    EstimatorSpecEvent,
)

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # pragma: allowlist secret (an alphabet)
REFERENCE_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}$")
# Customer information never belongs in a rate card (owner instruction Part I): emails, phone numbers.
_PII_IN_CARD = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")

_card_cache: dict[tuple[str, str], ratecard.RateCard] = {}


class CardError(ValueError):
    """A rate card was refused (validation, state or approval)."""


# --- rate cards (operator CLI only; no API exposes a card) -----------------------------------------------------------


def validate_document(document: dict) -> ratecard.RateCard:
    """Dry run: schema and business validation, plus a refusal of anything that looks like customer data."""
    try:
        card = ratecard.parse(document)
    except ValidationError as err:
        raise CardError(f"invalid rate card: {err.error_count()} problem(s)\n{err}") from err
    text = json.dumps(document, ensure_ascii=False)
    if _PII_IN_CARD.search(text):
        raise CardError("the rate card contains an email address or a phone number; customer data is not allowed")
    return card


def _sha(document: dict) -> str:
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _event(s: Session, event_type: str, *, estimate_id=None, rate_card_id=None, detail=None) -> None:
    s.add(EstimateEvent(event_type=event_type, estimate_id=estimate_id, rate_card_id=rate_card_id, detail=detail))


def load_card(s: Session, document: dict) -> EstimatorRateCard:
    """Store a validated card as DRAFT. A version is loaded once; a changed document needs a new version."""
    card = validate_document(document)
    if s.execute(sa.select(EstimatorRateCard.id).where(EstimatorRateCard.card_version == card.version)).first():
        raise CardError(f"rate card {card.version} is already loaded; give a changed card a new version")
    row = EstimatorRateCard(
        card_version=card.version,
        status="DRAFT",
        effective_on=datetime.combine(card.effective_on, datetime.min.time(), tzinfo=UTC),
        calculation_version=engine.CALCULATION_VERSION,
        document=document,
        document_sha256=_sha(document),
    )
    s.add(row)
    s.flush()
    for product in card.products:
        for line in product.lines:
            s.add(
                EstimatorRateItem(
                    rate_card_id=row.id,
                    product_code=product.code,
                    line_code=line.code,
                    label=line.label,
                    uom=line.uom,
                    rate_essential_minor=line.rates.get("ESSENTIAL"),
                    rate_premium_minor=line.rates.get("PREMIUM"),
                    rate_luxury_minor=line.rates.get("LUXURY"),
                )
            )
    _event(s, "CARD_LOADED", rate_card_id=row.id, detail={"version": card.version, "sha256": row.document_sha256})
    return row


def _by_version(s: Session, version: str) -> EstimatorRateCard:
    row = s.execute(sa.select(EstimatorRateCard).where(EstimatorRateCard.card_version == version)).scalar_one_or_none()
    if row is None:
        raise CardError(f"no rate card {version}")
    return row


def _active(s: Session) -> EstimatorRateCard | None:
    return s.execute(sa.select(EstimatorRateCard).where(EstimatorRateCard.status == "ACTIVE")).scalar_one_or_none()


def activate_card(s: Session, version: str, approval_reference: str, actor_id: str | None = None) -> EstimatorRateCard:
    """Make a DRAFT (or a RETIRED card, for rollback) the one ACTIVE card; the previous one is RETIRED."""
    if len((approval_reference or "").strip()) < 10:
        raise CardError("activation needs the owner's approval reference (at least 10 characters)")
    row = _by_version(s, version)
    if row.status == "ACTIVE":
        raise CardError(f"{version} is already active")
    if row.document_sha256 != _sha(row.document):
        raise CardError(f"{version}: the stored document does not match its SHA-256; refusing")
    validate_document(row.document)
    now = db.tx_time(s)
    previous = _active(s)
    if previous is not None:
        previous.status, previous.retired_on = "RETIRED", now
        _event(s, "CARD_RETIRED", rate_card_id=previous.id, detail={"version": previous.card_version, "by": version})
        s.flush()
    rollback = row.status == "RETIRED"
    row.status, row.activated_on, row.retired_on = "ACTIVE", now, None
    row.activated_by, row.approval_reference = actor_id, approval_reference.strip()[:200]
    _event(
        s,
        "CARD_ROLLED_BACK" if rollback else "CARD_ACTIVATED",
        rate_card_id=row.id,
        detail={"version": version, "previous": previous.card_version if previous else None},
    )
    return row


def rollback_card(s: Session, approval_reference: str, actor_id: str | None = None) -> EstimatorRateCard:
    """Re-activate the most recently retired card."""
    previous = s.execute(
        sa.select(EstimatorRateCard)
        .where(EstimatorRateCard.status == "RETIRED")
        .order_by(EstimatorRateCard.retired_on.desc())
        .limit(1)
    ).scalar_one_or_none()
    if previous is None:
        raise CardError("no retired card to roll back to")
    return activate_card(s, previous.card_version, approval_reference, actor_id)


def list_cards(s: Session) -> list[dict]:
    rows = s.execute(sa.select(EstimatorRateCard).order_by(EstimatorRateCard.created_on)).scalars()
    return [
        {
            "version": r.card_version,
            "status": r.status,
            "effective_on": r.effective_on.date().isoformat(),
            "sha256": r.document_sha256,
            "activated_on": r.activated_on.isoformat() if r.activated_on else None,
        }
        for r in rows
    ]


def active_card(s: Session) -> tuple[EstimatorRateCard, ratecard.RateCard]:
    row = _active(s)
    if row is None:
        raise ApiError(503, "ESTIMATOR_UNAVAILABLE", "Estimates are not available right now.")
    key = (row.id, row.document_sha256)
    if key not in _card_cache:
        _card_cache[key] = ratecard.parse(row.document)
    return row, _card_cache[key]


# --- customer specifications (ADR-012 T9; operator CLI only, like rate cards) ----------------------------------------


class SpecError(ValueError):
    """A customer specification was refused (validation, state or approval)."""


def validate_spec(document: dict) -> customer_spec.CustomerSpec:
    """Dry run: schema, the no-amounts / no-durations / no-personal-data rules."""
    try:
        return customer_spec.parse(document)
    except ValidationError as err:
        raise SpecError(f"invalid customer specification: {err.error_count()} problem(s)\n{err}") from err


def _spec_event(s: Session, event_type: str, row: EstimatorCustomerSpec, detail: dict | None = None) -> None:
    s.add(EstimatorSpecEvent(event_type=event_type, customer_spec_id=row.id, detail=detail))


def load_spec(s: Session, document: dict) -> EstimatorCustomerSpec:
    """Store a validated specification as DRAFT. A spec_code is loaded once; a change is a new version."""
    spec = validate_spec(document)
    taken = s.execute(
        sa.select(EstimatorCustomerSpec.id).where(EstimatorCustomerSpec.spec_code == spec.spec_code)
    ).first()
    if taken:
        raise SpecError(f"specification {spec.spec_code} is already loaded; give a changed specification a new version")
    row = EstimatorCustomerSpec(
        spec_code=spec.spec_code,
        spec_version=spec.version,
        package=spec.package,
        name=spec.name,
        summary=spec.summary,
        status="DRAFT",
        effective_on=datetime.combine(spec.effective_on, datetime.min.time(), tzinfo=UTC),
        document=document,
        document_sha256=_sha(document),
    )
    s.add(row)
    s.flush()
    for c in spec.categories:
        s.add(
            EstimatorCustomerSpecItem(
                customer_spec_id=row.id,
                category_code=c.code,
                label=c.label,
                summary=c.summary,
                requirement=c.requirement,
                grade=c.grade,
                thickness="; ".join(c.thickness)[:300] or None,
                finish=c.finish,
                brand_examples=", ".join(c.brand_examples)[:400] or None,
                equivalent_rule=c.equivalent_rule,
                final_selection=c.final_selection,
                hardware_category=c.hardware_category,
                warranty_summary=c.warranty_summary,
                applicability={"rooms": list(c.applies_to.rooms), "products": list(c.applies_to.products)},
            )
        )
    _spec_event(s, "SPEC_LOADED", row, {"spec": spec.spec_code, "sha256": row.document_sha256})
    return row


def _spec_by_code(s: Session, spec_code: str) -> EstimatorCustomerSpec:
    row = s.execute(
        sa.select(EstimatorCustomerSpec).where(EstimatorCustomerSpec.spec_code == spec_code)
    ).scalar_one_or_none()
    if row is None:
        raise SpecError(f"no customer specification {spec_code}")
    return row


def active_spec(s: Session, package: str) -> EstimatorCustomerSpec | None:
    return s.execute(
        sa.select(EstimatorCustomerSpec).where(
            EstimatorCustomerSpec.package == package, EstimatorCustomerSpec.status == "ACTIVE"
        )
    ).scalar_one_or_none()


def _active_card_sha(s: Session) -> str | None:
    row = _active(s)
    return row.document_sha256 if row is not None else None


def activation_report(s: Session, document: dict, *, env: str, approval_reference: str | None = None) -> dict:
    """Every guard for activating `document` on `env`, read-only (the `activation-check` report)."""
    spec = validate_spec(document)
    digest = _sha(document)
    blocked: list[str] = []
    evidence: dict = {"spec": spec.spec_code, "specification_sha256": digest}
    if not customer_spec.room_promises(spec):
        blocked.append(
            f"{spec.spec_code} has no room promises: UX V2 must not run on it; it may only be (re)activated with "
            "STAGING_ESTIMATOR_UX=v1 deployed and --ux-v1-confirmed"
        )
    else:
        gate_blocked, evidence = activation.gate(
            document, digest, env=env, active_card_sha256=_active_card_sha(s), approval_reference=approval_reference
        )
        blocked += gate_blocked
    current = _spec_by_code_or_none(s, spec.spec_code)
    if current is not None and current.status == "ACTIVE":
        blocked.append(f"{spec.spec_code} is already active")
    if current is not None and current.document_sha256 != digest:
        blocked.append(f"the loaded {spec.spec_code} is not this document")
    return {"blockers": blocked, "evidence": evidence, "digests": activation.digests(spec.spec_code)}


def _spec_by_code_or_none(s: Session, spec_code: str) -> EstimatorCustomerSpec | None:
    return s.execute(
        sa.select(EstimatorCustomerSpec).where(EstimatorCustomerSpec.spec_code == spec_code)
    ).scalar_one_or_none()


def _gate_or_refuse(
    s: Session, row: EstimatorCustomerSpec, approval_reference: str, *, ux_v1_confirmed: bool, release: str | None
) -> dict:
    """Run every guard for (re)activating `row`; refuse, failing closed, on any blocker. Returns the evidence."""
    if len((approval_reference or "").strip()) < 10:
        raise SpecError("activation needs the owner's approval reference (at least 10 characters)")
    if row.document_sha256 != _sha(row.document):
        raise SpecError(f"{row.spec_code}: the stored document does not match its SHA-256; refusing")
    spec = validate_spec(row.document)
    evidence: dict = {"spec": row.spec_code, "specification_sha256": row.document_sha256}
    if not customer_spec.room_promises(spec):
        if not ux_v1_confirmed:
            raise SpecError(
                f"{row.spec_code} has no room promises, so UX V2 must not run on it: set STAGING_ESTIMATOR_UX=v1, "
                "redeploy the staging site, then repeat with --ux-v1-confirmed"
            )
        evidence["ux_v1_confirmed"] = True
        return evidence
    env = settings().env
    if env in activation.DEPLOYED:
        if not release or not activation.RELEASE_RE.match(release):
            raise SpecError("give the deployed release commit (--release <commit>) so the activation records it")
        blocked, evidence = activation.gate(
            row.document,
            row.document_sha256,
            env=env,
            active_card_sha256=_active_card_sha(s),
            approval_reference=approval_reference,
        )
        if blocked:
            raise SpecError(f"{row.spec_code} is not ready for activation: {'; '.join(blocked[:5])}")
    return evidence


def _activation_record(evidence: dict, approval_reference: str, release: str | None, operator: str | None, now) -> dict:
    """What every activation and reactivation records (M1): commit, digests, decision versions, approval, operator."""
    return {
        **evidence,
        "release": release or activation.repository_commit(),
        "approval_reference": approval_reference.strip()[:200],
        "operator": (operator or "")[:120] or None,
        "environment": settings().env,
        "at": now.isoformat(),
    }


def activate_spec(
    s: Session,
    spec_code: str,
    approval_reference: str,
    actor_id: str | None = None,
    *,
    ux_v1_confirmed: bool = False,
    release: str | None = None,
    operator: str | None = None,
) -> EstimatorCustomerSpec:
    """Make a DRAFT (or a RETIRED version) the one ACTIVE specification of its package, after every guard.

    On staging and production a specification with room promises passes the whole activation gate (the reviewed
    records packaged with this release, approved and current); one without room promises needs `ux_v1_confirmed`.
    """
    row = _spec_by_code(s, spec_code)
    if row.status == "ACTIVE":
        raise SpecError(f"{spec_code} is already active")
    evidence = _gate_or_refuse(s, row, approval_reference, ux_v1_confirmed=ux_v1_confirmed, release=release)
    return _make_active(
        s, row, approval_reference, actor_id, evidence, release, operator, rollback=row.status == "RETIRED"
    )


def _make_active(s, row, approval_reference, actor_id, evidence, release, operator, *, rollback: bool):
    now = db.tx_time(s)
    previous = active_spec(s, row.package)
    if previous is not None:
        previous.status, previous.retired_on = "RETIRED", now
        _spec_event(s, "SPEC_RETIRED", previous, {"spec": previous.spec_code, "by": row.spec_code})
        s.flush()
    row.status, row.activated_on, row.retired_on = "ACTIVE", now, None
    row.activated_by, row.approval_reference = actor_id, approval_reference.strip()[:200]
    record = _activation_record(evidence, approval_reference, release, operator, now)
    record["previous"] = previous.spec_code if previous else None
    _spec_event(s, "SPEC_ROLLED_BACK" if rollback else "SPEC_ACTIVATED", row, record)
    return row


def rollback_spec(
    s: Session,
    package: str,
    approval_reference: str,
    actor_id: str | None = None,
    *,
    ux_v1_confirmed: bool = False,
    release: str | None = None,
    operator: str | None = None,
):
    """Re-activate the most recently retired specification of a package. A reactivation is a new activation: it runs
    the whole gate again (M2), so no earlier activation counts as standing approval."""
    previous = s.execute(
        sa.select(EstimatorCustomerSpec)
        .where(EstimatorCustomerSpec.package == package, EstimatorCustomerSpec.status == "RETIRED")
        .order_by(EstimatorCustomerSpec.retired_on.desc())
        .limit(1)
    ).scalar_one_or_none()
    if previous is None:
        raise SpecError(f"no retired {package} specification to roll back to")
    evidence = _gate_or_refuse(s, previous, approval_reference, ux_v1_confirmed=ux_v1_confirmed, release=release)
    return _make_active(s, previous, approval_reference, actor_id, evidence, release, operator, rollback=True)


def list_specs(s: Session) -> list[dict]:
    rows = s.execute(sa.select(EstimatorCustomerSpec).order_by(EstimatorCustomerSpec.created_on)).scalars()
    return [
        {
            "spec": r.spec_code,
            "package": r.package,
            "status": r.status,
            "effective_on": r.effective_on.date().isoformat(),
            "sha256": r.document_sha256,
            "activated_on": r.activated_on.isoformat() if r.activated_on else None,
        }
        for r in rows
    ]


def _snapshot_spec(s: Session, row: BudgetEstimate) -> dict | None:
    """The specification an estimate showed (frozen at creation), as the customer sees it."""
    if not row.customer_spec_id:
        return None
    spec = s.get(EstimatorCustomerSpec, row.customer_spec_id)
    return customer_spec.customer_view(spec.document) if spec is not None else None


def room_details(s: Session, row: BudgetEstimate) -> list[dict]:
    """Per room, what the customer was told about it: the material promise derived from the specification snapshot
    and the lines priced in that room (never a generic line), and the typical sizes assumed there. No amount."""
    lines = s.execute(
        sa.select(BudgetEstimateLine.room, BudgetEstimateLine.product_code, BudgetEstimateLine.line_code)
        .where(BudgetEstimateLine.estimate_id == row.id, BudgetEstimateLine.is_deleted.is_(False))
        .order_by(BudgetEstimateLine.position)
    ).all()
    assumed = s.execute(
        sa.select(BudgetEstimateAssumption.room, BudgetEstimateAssumption.text)
        .where(BudgetEstimateAssumption.estimate_id == row.id, BudgetEstimateAssumption.is_deleted.is_(False))
        .order_by(BudgetEstimateAssumption.position)
    ).all()
    priced: dict[str, list[tuple[str, str]]] = {}
    for room, product, line in lines:
        priced.setdefault(room, []).append((product, line))
    spec = s.get(EstimatorCustomerSpec, row.customer_spec_id) if row.customer_spec_id else None
    materials = customer_spec.room_materials(spec.document, priced) if spec is not None else {}
    return [
        {
            "room": room,
            "materials": materials.get(room),
            "assumptions": [text for r, text in assumed if r == room],
        }
        for room in priced
    ]


# --- estimates -------------------------------------------------------------------------------------------------------


def _new_reference(s: Session) -> str:
    for _ in range(10):
        raw = "".join(secrets.choice(CROCKFORD) for _ in range(8))
        ref = f"{raw[:4]}-{raw[4:]}"
        taken = s.execute(
            sa.select(BudgetEstimate.id)
            .where(BudgetEstimate.public_reference == ref)
            .execution_options(include_deleted=True)
        ).first()
        if not taken:
            return ref
    raise RuntimeError("could not allocate an estimate reference")


def _centi(value) -> int:
    return int((Decimal(str(value)) * 100).to_integral_value(rounding=ROUND_HALF_UP))  # as the engine rounds


def calculate(card: ratecard.RateCard, request: engine.EstimateRequest) -> engine.Estimate:
    try:
        return engine.calculate(card, request)
    except engine.EstimateError as err:
        raise ApiError(422, "VALIDATION_FAILED", "Some estimate inputs need attention.", errors=err.errors) from err


def store(
    s: Session,
    card_row: EstimatorRateCard,
    request: engine.EstimateRequest,
    est: engine.Estimate,
    *,
    origin: str,
    source: BudgetEstimate | None = None,
) -> BudgetEstimate:
    now = db.tx_time(s)
    row = BudgetEstimate(
        public_reference=_new_reference(s),
        rate_card_id=card_row.id,
        rate_card_version=est.rate_card_version,
        calculation_version=est.calculation_version,
        origin=origin,
        source_estimate_id=source.id if source else None,
        package=est.package,
        property_type=est.property_type,
        home_size=est.home_size,
        project_kind=est.project_kind,
        city=est.city,
        inputs=request.model_dump(mode="json"),
        result=json.loads(json.dumps(est.staff_view(), default=str)),
        base_minor=est.base_minor,
        range_low_minor=est.low_minor,
        range_high_minor=est.high_minor,
        preparation_minor=est.prep_minor,
        allowance_minor=est.allowance_minor,
        allowance_low_minor=est.allowance_low_minor,
        allowance_high_minor=est.allowance_high_minor,
        optional_minor=est.optional_minor,
        gst_low_minor=est.gst_low_minor,
        gst_high_minor=est.gst_high_minor,
        timeline_min_days=est.timeline["min_days"],
        timeline_max_days=est.timeline["max_days"],
        budget_range_code=est.budget_range_code,
        project_type_code=est.project_type_code,
        expires_on=now + timedelta(days=est.validity_days),
    )
    spec = active_spec(s, est.package)  # T9: the specification shown is frozen with the estimate
    if spec is not None:
        row.customer_spec_id, row.customer_spec_sha256 = spec.id, spec.document_sha256
    s.add(row)
    s.flush()
    for i, line in enumerate(est.lines, start=1):
        s.add(
            BudgetEstimateLine(
                estimate_id=row.id,
                position=i,
                room=line.room,
                instance=line.instance,
                product_code=line.product,
                line_code=line.code,
                label=line.label,
                uom=line.uom,
                quantity_centi=_centi(line.quantity),
                rate_minor=line.rate_minor,
                amount_minor=line.amount_minor,
                is_typical=line.typical,
                is_optional=line.optional,
            )
        )
    for i, a in enumerate(est.assumptions, start=1):
        s.add(
            BudgetEstimateAssumption(
                estimate_id=row.id,
                position=i,
                room=a.room,
                instance=a.instance,
                product_code=a.product,
                input_code=a.input,
                value_centi=_centi(a.value),
                unit=a.unit,
                text=a.text[:300],
            )
        )
    for c in est.prep:
        s.add(
            BudgetEstimateProjectItem(
                estimate_id=row.id,
                component_code=c.code,
                label=c.label,
                inclusion=c.inclusion,
                amount_minor=c.amount_minor,
            )
        )
    _event(
        s,
        "ESTIMATE_CREATED" if source is None else "ESTIMATE_REVISED",
        estimate_id=row.id,
        rate_card_id=card_row.id,
        detail={"origin": origin, "source": source.public_reference if source else None},
    )
    return row


def public_view(row: BudgetEstimate) -> dict:
    """The customer-safe response: the customer view, the reference and expiry. No internal identifier, no rate, no
    line amount, no workflow state."""
    view = {k: v for k, v in row.result.items() if k in _CUSTOMER_KEYS}
    # The stored snapshot is the staff view (exact room amounts); customers see them rounded (review S2).
    view["rooms"] = [dict(r, amount_minor=engine.customer_amount(r["amount_minor"])) for r in row.result["rooms"]]
    view["project_preparation"] = {k: v for k, v in row.result["project_preparation"].items() if k != "components"}
    # Which components were priced for this scope (codes only, no amounts): V2 lists exactly these.
    view["project_preparation"]["component_codes"] = [
        c["code"] for c in row.result["project_preparation"]["components"]
    ]
    view["custom_features_allowance"] = {
        k: row.result["custom_features_allowance"][k] for k in ("label", "description", "low_minor", "high_minor")
    }
    view["warranty"] = dict(row.result["warranty"], policy_url=settings().warranty_policy_url or None)
    view["reference"] = row.public_reference
    view["expires_on"] = row.expires_on.date().isoformat()
    session = object_session(row)
    view["specification"] = _snapshot_spec(session, row) if session is not None else None
    view["room_details"] = room_details(session, row) if session is not None else []
    view["v2_copy"] = _registered_copy(session, row, view) if session is not None else {"approved": False}
    return view


def _registered_copy(s: Session, row: BudgetEstimate, view: dict) -> dict:
    """The runtime texts V2 may show (M3): only those the reviewed promise matrix of the estimate's own specification
    snapshot registers. Without a matching packaged matrix nothing is approved and V2 shows none of them."""
    spec_row = s.get(EstimatorCustomerSpec, row.customer_spec_id) if row.customer_spec_id else None
    matrix = promise_matrix.load(spec_row.spec_code) if spec_row is not None else None
    if spec_row is None or matrix is None:
        return {"approved": False}
    try:
        promise_matrix.validate(spec_row.document, matrix)
    except promise_matrix.MatrixError:
        return {"approved": False}
    return promise_matrix.registered_text(matrix, view, view["room_details"])


_CUSTOMER_KEYS = frozenset(
    {
        "title",
        "disclaimer",
        "subject_to",
        "package",
        "property_type",
        "home_size",
        "range",
        "gst",
        "rooms",
        "optional_items_minor",
        "timeline",
        "assumptions",
        "exclusions",
        "client_scope",
        "rate_card_version",
        "validity_days",
    }
)


def create_public(s: Session, request: engine.EstimateRequest, *, ip, ua, request_id) -> dict:
    with acting(
        s, ActorContext(actor_id=WEB_INTAKE_USER_ID, via="PUBLIC_FORM", request_id=request_id, ip=ip, user_agent=ua)
    ):
        if request.package == "LUXURY":  # D2: never priced publicly, whatever the card enables
            raise ApiError(
                422,
                "VALIDATION_FAILED",
                "Some estimate inputs need attention.",
                errors=[
                    {
                        "field": "package",
                        "code": "PACKAGE_UNAVAILABLE",
                        "message": "Luxury is priced after a design consultation.",
                    }
                ],
            )
        card_row, card = active_card(s)
        est = calculate(card, request)
        row = store(s, card_row, request, est, origin="PUBLIC")
        return public_view(row)


def usable_for_enquiry(s: Session, reference: str | None) -> tuple[BudgetEstimate | None, str | None]:
    """The estimate an enquiry refers to, or why it cannot be used (never an error: the enquiry is still taken)."""
    if not isinstance(reference, str) or not REFERENCE_RE.match(reference.strip().upper()):
        return None, "INVALID" if reference else None
    row = s.execute(
        sa.select(BudgetEstimate).where(BudgetEstimate.public_reference == reference.strip().upper())
    ).scalar_one_or_none()
    if row is None:
        return None, "UNKNOWN"
    if row.expires_on < db.tx_time(s):
        return None, "EXPIRED"
    if s.execute(sa.select(BudgetEstimateLeadLink.id).where(BudgetEstimateLeadLink.estimate_id == row.id)).first():
        return None, "ALREADY_LINKED"
    return row, None


def link(
    s: Session, estimate: BudgetEstimate, lead, *, policy_version: str | None, preferred_contact: str | None
) -> bool:
    """Link in the lead's own transaction (atomic with the enquiry). A concurrent enquiry may have linked the estimate
    since it was checked: the link is then skipped under a savepoint and recorded on the lead, never rejecting the
    enquiry. Returns whether the link was made."""
    from sqlalchemy.exc import IntegrityError

    savepoint = s.begin_nested()
    try:
        s.add(
            BudgetEstimateLeadLink(
                estimate_id=estimate.id,
                lead_id=lead.id,
                consent_policy_version=policy_version,
                preferred_contact=preferred_contact,
                linked_on=db.tx_time(s),
            )
        )
        s.flush()
        savepoint.commit()
    except IntegrityError:
        savepoint.rollback()
        lead.intake_unmapped = {
            **(lead.intake_unmapped or {}),
            "estimate_reference": f"ALREADY_LINKED:{estimate.public_reference}",
        }
        return False
    _event(s, "ESTIMATE_LINKED", estimate_id=estimate.id, detail={"lead": lead.lead_number})
    return True


def summary_line(s: Session, lead_id: str) -> str | None:
    """One line for the lead notification: 'Budgetary Estimate ₹a–b L (Essential, 3 rooms)', or the Luxury design
    consultation request (D2)."""
    row = s.execute(
        sa.select(BudgetEstimate)
        .join(BudgetEstimateLeadLink, BudgetEstimateLeadLink.estimate_id == BudgetEstimate.id)
        .where(BudgetEstimateLeadLink.lead_id == lead_id)
        .order_by(BudgetEstimate.created_on.desc())
        .limit(1)
    ).scalar_one_or_none()
    from veda.modules.crm.leads.models import LeadActivity

    luxury = s.execute(
        sa.select(LeadActivity.id)
        .where(LeadActivity.lead_id == lead_id, LeadActivity.subject.startswith(LUXURY_CONSULTATION))
        .limit(1)
    ).first()
    parts = ["Luxury design consultation requested"] if luxury else []
    if row is not None:
        rooms = len(row.result.get("rooms", []))
        parts.append(
            f"Budgetary Estimate {_lakh(row.range_low_minor)}–{_lakh(row.range_high_minor)} "
            f"({row.package.title()}, {rooms} room{'s' if rooms != 1 else ''})"
        )
    return " · ".join(parts) or None


def _lakh(minor: int) -> str:
    return f"₹{Decimal(minor) / 10_000_000:.1f} L"


# --- staff ------------------------------------------------------------------------------------------------------------


def _linked_lead_id(s: Session, estimate_id: str) -> str | None:
    return s.execute(
        sa.select(BudgetEstimateLeadLink.lead_id).where(BudgetEstimateLeadLink.estimate_id == estimate_id)
    ).scalar_one_or_none()


def get_for_staff(s: Session, ctx, estimate_id: str) -> tuple[BudgetEstimate, object | None]:
    """The estimate if the viewer may see its lead; an unlinked estimate needs lead visibility over ALL leads."""
    from veda.modules.crm.leads import repository as lead_repo

    row = s.get(BudgetEstimate, estimate_id)
    if row is None or row.is_deleted:
        raise not_found()
    lead_id = _linked_lead_id(s, row.id)
    if lead_id is None:
        if ctx.scope("lead.read") != "ALL":
            raise not_found()
        return row, None
    return row, lead_repo.get_visible(s, ctx, lead_id)


def for_lead(s: Session, ctx, lead_id: str) -> list[BudgetEstimate]:
    from veda.modules.crm.leads import repository as lead_repo

    lead_repo.get_visible(s, ctx, lead_id)
    return list(
        s.execute(
            sa.select(BudgetEstimate)
            .join(BudgetEstimateLeadLink, BudgetEstimateLeadLink.estimate_id == BudgetEstimate.id)
            .where(BudgetEstimateLeadLink.lead_id == lead_id)
            .order_by(BudgetEstimate.created_on.desc())
        ).scalars()
    )


def staff_view(s: Session, row: BudgetEstimate, lead=None) -> dict:
    events = s.execute(
        sa.select(EstimateEvent).where(EstimateEvent.estimate_id == row.id).order_by(EstimateEvent.created_on)
    ).scalars()
    link_row = s.execute(
        sa.select(BudgetEstimateLeadLink).where(BudgetEstimateLeadLink.estimate_id == row.id)
    ).scalar_one_or_none()
    source = s.get(BudgetEstimate, row.source_estimate_id) if row.source_estimate_id else None
    return {
        "id": row.id,
        "reference": row.public_reference,
        "created_on": row.created_on.isoformat(),
        "expires_on": row.expires_on.isoformat(),
        "origin": row.origin,
        "source_reference": source.public_reference if source else None,
        "rate_card_version": row.rate_card_version,
        "calculation_version": row.calculation_version,
        "property_type": row.property_type,
        "home_size": row.home_size,
        "project_kind": row.project_kind,
        "city": row.city,
        "package": row.package,
        "inputs": row.inputs,
        "estimate": dict(
            row.result, warranty=dict(row.result["warranty"], policy_url=settings().warranty_policy_url or None)
        ),
        "site_measurement_required": row.site_measurement_required,
        "specification": (
            {
                "spec_code": spec_row.spec_code,
                "version": spec_row.spec_version,
                "sha256": row.customer_spec_sha256,
                "document": customer_spec.customer_view(spec_row.document),
            }
            if (spec_row := (s.get(EstimatorCustomerSpec, row.customer_spec_id) if row.customer_spec_id else None))
            else None
        ),
        "room_details": room_details(s, row),
        "lead": {"id": lead.id, "lead_number": lead.lead_number, "status": lead.status} if lead is not None else None,
        "preferred_contact": link_row.preferred_contact if link_row else None,
        "events": [
            {"type": e.event_type, "on": e.created_on.isoformat(), "by": e.created_by, "detail": e.detail}
            for e in events
        ],
    }


def derive(s: Session, ctx, source: BudgetEstimate, *, package: str | None, selections: list | None) -> BudgetEstimate:
    """Duplicate (no changes) or revise (package and/or selections) into a new estimate on the active card."""
    inputs = dict(source.inputs)
    if package is not None:
        inputs["package"] = package
    if selections is not None:
        inputs["selections"] = selections
    try:
        request = engine.EstimateRequest.model_validate(inputs)
    except ValidationError as err:
        raise ApiError(422, "VALIDATION_FAILED", "Some estimate inputs need attention.") from err
    card_row, card = active_card(s)
    est = calculate(card, request)
    row = store(s, card_row, request, est, origin="STAFF", source=source)
    if package is None and selections is None:
        _event(s, "ESTIMATE_DUPLICATED", estimate_id=row.id, detail={"source": source.public_reference})
    lead_id = _linked_lead_id(s, source.id)
    if lead_id is not None:
        s.add(
            BudgetEstimateLeadLink(
                estimate_id=row.id, lead_id=lead_id, consent_policy_version=None, linked_on=db.tx_time(s)
            )
        )
    return row


def mark_site_measurement(s: Session, row: BudgetEstimate, lead) -> None:
    from veda.modules.crm.leads.service import add_system_activity

    if not row.site_measurement_required:
        row.site_measurement_required = True
        _event(s, "SITE_MEASUREMENT_REQUIRED", estimate_id=row.id)
        if lead is not None:
            add_system_activity(s, lead, "SYSTEM", f"Site measurement required (estimate {row.public_reference})")


LUXURY_CONSULTATION = "Luxury design consultation requested (Luxury is priced after a design consultation)"


def request_luxury_consultation(s: Session, lead, *, preferred_contact: str | None) -> None:
    """ADR-012 D2: Luxury has no public price. The enquiry is marked on the lead for a design consultation."""
    from veda.modules.crm.leads.service import add_system_activity

    contact = f"; prefers {preferred_contact.lower()}" if preferred_contact else ""
    add_system_activity(s, lead, "SYSTEM", f"{LUXURY_CONSULTATION}{contact}")


def start_quotation_process(s: Session, row: BudgetEstimate, lead) -> None:
    """Records that the official quotation process has started from this estimate. It never creates a quotation and
    never changes the lead's status: the official quotation is prepared separately."""
    from veda.modules.crm.leads.service import add_system_activity

    if lead is None:
        raise ApiError(409, "NOT_LINKED", "Link the estimate to a lead before starting the quotation process.")
    _event(s, "QUOTATION_PROCESS_STARTED", estimate_id=row.id)
    add_system_activity(s, lead, "SYSTEM", f"Official quotation process started from estimate {row.public_reference}")


def consultation_copy(s: Session, row: BudgetEstimate) -> dict:
    """The customer-safe estimate for a consultation, with its inputs and assumptions. Never a quotation."""
    _event(s, "CONSULTATION_COPY", estimate_id=row.id)
    view = public_view(row)
    view["heading"] = "Consultation copy"
    view["inputs"] = row.inputs
    view["created_on"] = row.created_on.date().isoformat()
    return view


# --- retention ---------------------------------------------------------------------------------------------------------


def purge_expired(s: Session, *, dry_run: bool = False) -> int:
    """Soft-delete estimates never linked to a lead once the retention period (ADR-012 D7: 90 days from creation)
    has passed. An estimate that is still valid is never removed; a linked one stays with its lead."""
    now = db.tx_time(s)
    cutoff = now - timedelta(days=settings().estimate_retention_days)
    linked = sa.select(BudgetEstimateLeadLink.estimate_id)
    rows = list(
        s.execute(
            sa.select(BudgetEstimate).where(
                BudgetEstimate.created_on < cutoff, BudgetEstimate.expires_on < now, BudgetEstimate.id.not_in(linked)
            )
        ).scalars()
    )
    if not dry_run:
        for row in rows:
            for model in (BudgetEstimateLine, BudgetEstimateAssumption, BudgetEstimateProjectItem):
                for child in s.execute(sa.select(model).where(model.estimate_id == row.id)).scalars():
                    child.is_deleted, child.deleted_on = True, now
            row.is_deleted, row.deleted_on = True, now
            _event(s, "ESTIMATE_EXPIRED", estimate_id=row.id)
    return len(rows)
