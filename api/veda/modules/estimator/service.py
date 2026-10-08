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
from decimal import Decimal

import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import db
from veda.kernel.context import ActorContext, acting
from veda.kernel.errors import ApiError, not_found
from veda.kernel.ids import WEB_INTAKE_USER_ID

from . import engine, ratecard
from .models import (
    BudgetEstimate,
    BudgetEstimateAssumption,
    BudgetEstimateLeadLink,
    BudgetEstimateLine,
    BudgetEstimateProjectItem,
    EstimateEvent,
    EstimatorRateCard,
    EstimatorRateItem,
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
    return int((Decimal(str(value)) * 100).to_integral_value())


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
        optional_minor=est.optional_minor,
        gst_low_minor=est.gst_low_minor,
        gst_high_minor=est.gst_high_minor,
        timeline_min_days=est.timeline["min_days"],
        timeline_max_days=est.timeline["max_days"],
        budget_range_code=est.budget_range_code,
        project_type_code=est.project_type_code,
        expires_on=now + timedelta(days=est.validity_days),
    )
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
    view["project_preparation"] = {k: v for k, v in row.result["project_preparation"].items() if k != "components"}
    view["warranty"] = dict(row.result["warranty"], policy_url=settings().warranty_policy_url or None)
    view["reference"] = row.public_reference
    view["expires_on"] = row.expires_on.date().isoformat()
    return view


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


def link(s: Session, estimate: BudgetEstimate, lead, *, policy_version: str | None, preferred_contact: str | None):
    """Link in the lead's own transaction (atomic with the enquiry)."""
    s.add(
        BudgetEstimateLeadLink(
            estimate_id=estimate.id,
            lead_id=lead.id,
            consent_policy_version=policy_version,
            preferred_contact=preferred_contact,
            linked_on=db.tx_time(s),
        )
    )
    _event(s, "ESTIMATE_LINKED", estimate_id=estimate.id, detail={"lead": lead.lead_number})


def summary_line(s: Session, lead_id: str) -> str | None:
    """One line for the lead notification: 'Budgetary Estimate ₹a–b L (Essential, 3 rooms)'."""
    row = s.execute(
        sa.select(BudgetEstimate)
        .join(BudgetEstimateLeadLink, BudgetEstimateLeadLink.estimate_id == BudgetEstimate.id)
        .where(BudgetEstimateLeadLink.lead_id == lead_id)
        .order_by(BudgetEstimate.created_on.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        return None
    rooms = len(row.result.get("rooms", []))
    return (
        f"Budgetary Estimate {_lakh(row.range_low_minor)}–{_lakh(row.range_high_minor)} "
        f"({row.package.title()}, {rooms} room{'s' if rooms != 1 else ''})"
    )


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
    """Soft-delete estimates never linked to a lead, once expired for longer than the retention period."""
    cutoff = db.tx_time(s) - timedelta(days=settings().estimate_retention_days)
    linked = sa.select(BudgetEstimateLeadLink.estimate_id)
    rows = list(
        s.execute(
            sa.select(BudgetEstimate).where(BudgetEstimate.expires_on < cutoff, BudgetEstimate.id.not_in(linked))
        ).scalars()
    )
    if not dry_run:
        now = db.tx_time(s)
        for row in rows:
            for model in (BudgetEstimateLine, BudgetEstimateAssumption, BudgetEstimateProjectItem):
                for child in s.execute(sa.select(model).where(model.estimate_id == row.id)).scalars():
                    child.is_deleted, child.deleted_on = True, now
            row.is_deleted, row.deleted_on = True, now
            _event(s, "ESTIMATE_EXPIRED", estimate_id=row.id)
    return len(rows)
