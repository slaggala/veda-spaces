"""V3 customer flow: the public catalog view, estimates from configurations, and their snapshots (ADR-013 D4).

Estimate first, measurements later: a configuration of rooms, items, options and extras is resolved to the engine
request and priced by the existing engine with the ACTIVE release's compiled card. The configuration snapshot freezes
the release, the manifest digest, every record version used, the selections and the resolved request.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import UTC, date, datetime, timedelta

import sqlalchemy as sa
import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import clock, db
from veda.kernel.context import ActorContext, acting
from veda.kernel.errors import ApiError
from veda.kernel.ids import WEB_INTAKE_USER_ID
from veda.modules.estimator import engine, ratecard
from veda.modules.estimator import service as estimator_service
from veda.modules.estimator.models import BudgetEstimate, EstimatorRateCard

from . import compile as catalog_compile
from . import kinds, public, rules, service
from .models import ANALYTICS_EVENTS, CatalogAnalyticsDaily, CatalogConfiguration, CatalogEvent, CatalogRelease

log = structlog.get_logger("veda.catalog")
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # pragma: allowlist secret (an alphabet)
_view_cache: dict[tuple[str, str], dict] = {}
_card_cache: dict[tuple[str, str], ratecard.RateCard] = {}


def enabled() -> bool:
    return settings().catalog_estimator_enabled


def _active(s: Session) -> CatalogRelease:
    release = service.active_release(s)
    if release is None or release.rate_card_id is None:
        raise ApiError(503, "ESTIMATOR_UNAVAILABLE", "Estimates are not available right now.")
    return release


def public_catalog(s: Session) -> dict:
    """The ACTIVE release's customer view (cached by release and manifest digest)."""
    release = _active(s)
    key = (release.id, release.manifest_sha256)
    if key not in _view_cache:
        cat = _load(s, release)
        dto = public.build_catalog(cat)
        _served(public.check_payload(dto, governed=cat.of(kinds.Copy)), "catalog", release.release_code)
        _view_cache[key] = dto.model_dump(mode="json", by_alias=True, exclude_none=True)
    return _view_cache[key]


def _served(problems: list[str], what: str, release_code: str) -> None:
    """Defence in depth: the release gate checked this payload, the serialiser checks it again (the same canonical
    checks) and refuses to serve anything that fails: V3 becomes unavailable rather than show it."""
    if problems:
        log.error("catalog.public_payload_refused", payload=what, release=release_code, problems=problems[:20])
        raise ApiError(503, "ESTIMATOR_UNAVAILABLE", "Estimates are not available right now.")


def public_estimate(s: Session, row: BudgetEstimate, snap: CatalogConfiguration, release: CatalogRelease) -> dict:
    """The V3 estimate response: the strict public DTO built from the stored result, checked before it is served."""
    spec = estimator_service._snapshot_spec(s, row)
    dto = public.build_estimate(row.result, reference=row.public_reference,
                                expires_on=row.expires_on.date().isoformat(),
                                configuration_reference=snap.configuration_reference,
                                catalog_release=release.release_code, specification=spec)  # fmt: skip
    _served(public.check_payload(dto), "estimate", release.release_code)
    return dto.model_dump(mode="json", exclude_none=True)


def _load(s: Session, release: CatalogRelease) -> catalog_compile.Catalog:
    """The active release's records, or 503: content that no longer validates (a manifest that drifted, or a record
    the current rules refuse, such as a market condition) makes V3 unavailable rather than half-evaluated."""
    try:
        return catalog_compile.load_release(s, release)
    except ValueError as err:
        raise ApiError(503, "ESTIMATOR_UNAVAILABLE", "Estimates are not available right now.") from err


def _card(s: Session, release: CatalogRelease) -> tuple[EstimatorRateCard, ratecard.RateCard]:
    row = s.get(EstimatorRateCard, release.rate_card_id)
    if row is None or row.document_sha256 != estimator_service._sha(row.document):
        raise ApiError(503, "ESTIMATOR_UNAVAILABLE", "Estimates are not available right now.")
    key = (row.id, row.document_sha256)
    if key not in _card_cache:
        _card_cache[key] = ratecard.parse(row.document)
    return row, _card_cache[key]


def _reference(s: Session) -> str:
    for _ in range(10):
        ref = "C" + "".join(secrets.choice(_CROCKFORD) for _ in range(8))
        taken = s.execute(
            sa.select(CatalogConfiguration.id).where(CatalogConfiguration.configuration_reference == ref)
        ).first()
        if not taken:
            return ref
    raise RuntimeError("could not allocate a configuration reference")


def _refused(err: catalog_compile.CompileError) -> ApiError:
    return ApiError(422, "VALIDATION_FAILED", "Some choices need attention.", errors=err.errors)


IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9_-]{32,64}$")  # at least 128 random bits from the browser
IDEMPOTENCY_TTL = timedelta(hours=24)
_CLIENT = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


def key_digest(key: str, client: str | None) -> str:
    """What is stored for an Idempotency-Key: a SHA-256 of the key scoped to the browser's X-Veda-Client token, never
    the key itself. Another browser presenting the same key has a different scope, so it can never replay (or learn)
    someone else's estimate; a database reader cannot replay a request either."""
    scope = client if client and _CLIENT.match(client) else "-"
    return hashlib.sha256(f"veda.catalog.idempotency/1\0{scope}\0{key}".encode()).hexdigest()


def fingerprint(config: object) -> str:
    """The SHA-256 of the configuration exactly as sent (canonical JSON), to tell a repeat from a different request."""
    return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def stored_for_key(s: Session, key: str) -> CatalogConfiguration | None:
    return s.execute(
        sa.select(CatalogConfiguration).where(
            CatalogConfiguration.idempotency_key == key, CatalogConfiguration.is_deleted.is_(False)
        )
    ).scalar_one_or_none()


def replay(s: Session, key: str, config: object) -> dict:
    """The response first given for this key (`key` is the scoped digest), or 409: the key was used for different
    choices, the first request is still in flight, or the key is older than IDEMPOTENCY_TTL."""
    snap = stored_for_key(s, key)
    if snap is None or snap.estimate_id is None:
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "This request is still being processed. Try again.")
    if clock.now() - _aware(snap.created_on) > IDEMPOTENCY_TTL:
        raise ApiError(409, "IDEMPOTENCY_KEY_EXPIRED", "This request has expired. Start a new estimate.")
    if snap.request_fingerprint != fingerprint(config):
        raise ApiError(409, "IDEMPOTENCY_KEY_REUSED", "This request was already used for different choices.")
    from veda.modules.estimator.models import BudgetEstimate

    row = s.get(BudgetEstimate, snap.estimate_id)
    release = s.get(CatalogRelease, snap.release_id)
    if row is None or release is None:
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "This request cannot be repeated. Start a new estimate.")
    return public_estimate(s, row, snap, release)


def _aware(at: datetime) -> datetime:
    return at if at.tzinfo else at.replace(tzinfo=UTC)


def create_public(s: Session, config: dict, *, ip, ua, request_id, idempotency_key: str | None = None) -> dict:
    """Price a customer configuration with the ACTIVE release; store the estimate and its configuration snapshot.
    With an idempotency key, a repeat of the same request returns this estimate (see `replay`) instead of a second."""
    with acting(
        s, ActorContext(actor_id=WEB_INTAKE_USER_ID, via="PUBLIC_FORM", request_id=request_id, ip=ip, user_agent=ua)
    ):
        release = _active(s)
        cat = _load(s, release)
        try:
            resolved = catalog_compile.resolve(cat, config, public=True)
        except catalog_compile.CompileError as err:
            raise _refused(err) from err
        if resolved.request.package == "LUXURY":  # ADR-012 D2, whatever the catalog says
            raise ApiError(422, "VALIDATION_FAILED", "Luxury is priced after a design consultation.")
        card_row, card = _card(s, release)
        est = estimator_service.calculate(card, resolved.request)
        row = estimator_service.store(s, card_row, resolved.request, est, origin="PUBLIC")
        snap = snapshot(s, release, resolved, estimate_id=row.id)
        if idempotency_key:
            snap.idempotency_key, snap.request_fingerprint = idempotency_key, fingerprint(config)
            try:
                s.flush()
            except IntegrityError as err:  # the same key arrived twice at once: one wins, the other is refused
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "This request is already being processed.") from err
        return public_estimate(s, row, snap, release)


def snapshot(s: Session, release: CatalogRelease, resolved: catalog_compile.Resolved, *, estimate_id=None):
    versions = {kind: dict(sorted(keys.items())) for kind, keys in sorted(resolved.versions.items())}
    row = CatalogConfiguration(
        configuration_reference=_reference(s),
        release_id=release.id,
        manifest_sha256=release.manifest_sha256,
        versions=versions,
        selections=resolved.configuration.model_dump(mode="json"),  # the allowlisted normal form only
        resolved_request=resolved.request.model_dump(mode="json"),
        estimate_id=estimate_id,
    )
    s.add(row)
    s.flush()
    return row


def preview(s: Session, release_id: str, config: dict, *, public: bool = True) -> dict:
    """Staff preview of any release (not stored): the customer view result and the staff breakdown. The release's
    card is compiled on the fly; nothing becomes customer-visible."""
    release = service.get_release(s, release_id)
    cat = catalog_compile.load_release(s, release)
    try:
        card = catalog_compile.compile_card(cat)
        resolved = catalog_compile.resolve(cat, config, public=public)
    except catalog_compile.CompileError as err:
        raise _refused(err) from err
    est = estimator_service.calculate(card, resolved.request)
    return {
        "release": release.release_code,
        "request": resolved.request.model_dump(mode="json"),
        "versions": resolved.versions,
        "estimate": {
            "range_low_minor": est.low_minor,
            "range_high_minor": est.high_minor,
            "rooms": [
                dict(r, amount_minor=engine.customer_amount(r["amount_minor"])) for r in est.staff_view()["rooms"]
            ],
        },
    }


def reopen(s: Session, reference: str) -> dict:
    """Staff: a stored configuration exactly as it was priced (its versions, selections and engine request)."""
    row = s.execute(
        sa.select(CatalogConfiguration).where(
            CatalogConfiguration.configuration_reference == reference, CatalogConfiguration.is_deleted.is_(False)
        )
    ).scalar_one_or_none()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "No such configuration.")
    release = s.get(CatalogRelease, row.release_id)
    if release is None:  # the foreign key makes this unreachable; refuse rather than guess
        raise ApiError(404, "NOT_FOUND", "No such configuration.")
    return {
        "configuration_reference": row.configuration_reference,
        "release": release.release_code,
        "manifest_sha256": row.manifest_sha256,
        "versions": row.versions,
        "selections": row.selections,
        "resolved_request": row.resolved_request,
        "estimate_id": row.estimate_id,
        "created_on": row.created_on.isoformat(),
    }


def defaults(s: Session, home: str, package: str) -> dict:
    from . import validation

    release = _active(s)
    cat = catalog_compile.load_release(s, release)
    home_model, package_model = cat.one(kinds.HomeConfig, home), cat.one(kinds.Package, package)
    if home_model is None or package_model is None:
        raise ApiError(404, "NOT_FOUND", "No such home or package.")
    ptype = cat.one(kinds.PropertyType, home_model.property_type)
    if ptype is None:
        raise ApiError(404, "NOT_FOUND", "No such home or package.")
    ctx = rules.Context(
        property_type=ptype.code,
        home_size=home_model.home_size,
        project_kind="NEW_HOME",
        package=package_model.engine_package,
    )
    out = validation.default_configuration(cat, home, package)
    out["preselected"] = sorted(rules.defaults(cat, ctx))
    return out


# --- analytics (staging validation only; counts, no person, no free text) --------------------------------------------
def record_event(s: Session, event: str, subject: str | None) -> None:
    if not settings().catalog_analytics_enabled or settings().is_production:
        return
    if event not in ANALYTICS_EVENTS:
        raise ApiError(422, "VALIDATION_FAILED", "Unknown event.")
    release = service.active_release(s)
    code = release.release_code if release else "-"
    subject = subject if isinstance(subject, str) and subject and len(subject) <= 100 else "-"
    if subject != "-" and not _known_subject(s, release, subject):
        subject = "-"  # only catalog keys are counted, never free text
    day = date.today().isoformat()
    row = s.execute(
        sa.select(CatalogAnalyticsDaily).where(
            CatalogAnalyticsDaily.day == day,
            CatalogAnalyticsDaily.event == event,
            CatalogAnalyticsDaily.subject == subject,
            CatalogAnalyticsDaily.release_code == code,
        )
    ).scalar_one_or_none()
    if row is None:
        s.add(CatalogAnalyticsDaily(day=day, event=event, subject=subject, release_code=code, count=1))
    else:
        row.count += 1


def _known_subject(s: Session, release, subject: str) -> bool:
    if release is None:
        return False
    return any(e["key"] == subject for e in release.manifest["entries"] if e["kind"] in ("room_template", "product",
               "extra", "media", "package"))  # fmt: skip


def analytics(s: Session, days: int = 30) -> list[dict]:
    rows = s.execute(
        sa.select(CatalogAnalyticsDaily).order_by(CatalogAnalyticsDaily.day.desc()).limit(min(days, 90) * 50)
    ).scalars()
    return [
        {"day": r.day, "event": r.event, "subject": r.subject, "release": r.release_code, "count": r.count}
        for r in rows
    ]


# --- retention (R7) -----------------------------------------------------------------------------------------------
def purge(s: Session, *, dry_run: bool = False) -> int:
    """Configuration snapshots follow their estimate's retention (ADR-012 D7): once the estimate is purged, the snapshot
    is soft-deleted too (audited like every soft delete) with a CONFIGURATION_PURGED event. A snapshot holds no personal
    data (an allowlisted configuration, record versions and the engine request), so an estimate that a lead still
    references keeps it."""
    rows = list(
        s.execute(
            sa.select(CatalogConfiguration)
            .join(BudgetEstimate, BudgetEstimate.id == CatalogConfiguration.estimate_id)
            .where(BudgetEstimate.is_deleted.is_(True), CatalogConfiguration.is_deleted.is_(False))
            .execution_options(include_deleted=True)  # the purged estimates are soft-deleted rows
        ).scalars()
    )
    if not dry_run:
        for row in rows:
            _delete(s, row, "estimate retention")
    return len(rows)


def delete(s: Session, reference: str, reason: str) -> None:
    """A deletion request for one stored configuration (staff, catalog.admin). The estimate it priced keeps its own
    snapshots; only the catalog configuration is removed."""
    if len((reason or "").strip()) < 10:
        raise ApiError(422, "VALIDATION_FAILED", "Say why the configuration is deleted (at least 10 characters).")
    row = s.execute(
        sa.select(CatalogConfiguration).where(
            CatalogConfiguration.configuration_reference == reference, CatalogConfiguration.is_deleted.is_(False)
        )
    ).scalar_one_or_none()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "No such configuration.")
    _delete(s, row, reason.strip()[:200])


def _delete(s: Session, row: CatalogConfiguration, reason: str) -> None:
    row.is_deleted, row.deleted_on = True, db.tx_time(s)
    s.add(CatalogEvent(event_type="CONFIGURATION_PURGED",
                       detail={"reference": row.configuration_reference, "reason": reason}))  # fmt: skip
