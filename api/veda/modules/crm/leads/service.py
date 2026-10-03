"""Lead use cases (04). The service layer is the transaction boundary; the
kernel stamps contract columns and writes audit rows in the same transaction."""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import clock, db, outbox, sequences
from veda.kernel.audit_hook import write_explicit_audit
from veda.kernel.context import ActorContext, acting, current_actor
from veda.kernel.dto import EMAIL_RE, mask_email, normalize_email, parse_phone, single_line, strip_controls
from veda.kernel.errors import ApiError, field_error, not_found, validation_failed
from veda.kernel.ids import WEB_INTAKE_USER_ID
from veda.platform.auth import security_events
from veda.platform.auth.request_auth import record_sensitive_action, require_step_up
from veda.platform.identity.models import User
from veda.platform.lookups import service as lookups
from veda.platform.rbac.resolver import load_grants

from . import repository as repo
from .models import CONTACT_ACTIVITY_TYPES, LEAD_STATUSES, OPEN_STATUSES, Lead, LeadActivity, LeadNote

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
DUPLICATE_WINDOW = timedelta(days=180)
PUBLIC_MESSAGE = "Thank you. Our design team will call you within one working day."
LOOKUP_FIELDS = (
    ("project_type_code", "project_type_id", "PROJECT_TYPE"),
    ("property_type_code", "property_type_id", "PROPERTY_TYPE"),
    ("budget_range_code", "budget_range_id", "BUDGET_RANGE"),
)
ANONYMIZED = "[anonymized]"


# --- helpers ----------------------------------------------------------------------------------


def new_public_reference(s: Session) -> str:
    for _ in range(10):
        raw = "".join(secrets.choice(CROCKFORD) for _ in range(8))
        ref = f"{raw[:4]}-{raw[4:]}"
        exists = s.execute(
            sa.select(Lead.id).where(Lead.public_reference == ref).execution_options(include_deleted=True)
        ).first()
        if not exists:
            return ref
    raise RuntimeError("could not allocate a public reference")


def lookup_id(s: Session, category: str, code: str | None, field: str) -> str | None:
    if code is None:
        return None
    value = lookups.resolve_code(s, category, code)
    if value is None:
        raise validation_failed(
            [field_error(field, "INVALID_LOOKUP", f"Unknown {field.replace('_code', '').replace('_', ' ')}.")]
        )
    return value.id


def find_duplicate(s: Session, lead: Lead) -> Lead | None:
    """Another live lead with the same phone or email within 180 days (04 §7). Never rejects."""
    since = db.tx_time(s) - DUPLICATE_WINDOW
    conds = [Lead.phone == lead.phone] if lead.phone else []
    if lead.email_normalized:
        conds.append(Lead.email_normalized == lead.email_normalized)
    if not conds:
        return None
    q = sa.select(Lead).where(sa.or_(*conds), Lead.created_on >= since, Lead.anonymized_on.is_(None))
    if lead.id:
        q = q.where(Lead.id != lead.id)
    return s.execute(q.order_by(Lead.created_on.desc()).limit(1)).scalar_one_or_none()


def add_system_activity(
    s: Session,
    lead: Lead,
    activity_type: str,
    subject: str,
    *,
    owner: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    description: str | None = None,
    metadata: dict | None = None,
) -> LeadActivity:
    now = db.tx_time(s)
    act = LeadActivity(
        lead_id=lead.id,
        activity_type=activity_type,
        is_system_generated=True,
        activity_status="COMPLETED",
        subject=subject[:200],
        description=description,
        completed_on=now,
        owner_user_id=owner or current_actor().actor_id,
        from_status=from_status,
        to_status=to_status,
        metadata_=metadata,
    )
    s.add(act)
    lead.last_activity_on = now
    return act


def recompute_follow_up(s: Session, lead: Lead) -> None:
    """next_follow_up_on = min(scheduled_on) over PLANNED, non-deleted activities (04 §8)."""
    s.flush()
    lead.next_follow_up_on = s.execute(
        sa.select(sa.func.min(LeadActivity.scheduled_on)).where(
            LeadActivity.lead_id == lead.id, LeadActivity.activity_status == "PLANNED"
        )
    ).scalar()
    last = s.execute(
        sa.select(sa.func.max(LeadActivity.completed_on)).where(
            LeadActivity.lead_id == lead.id, LeadActivity.activity_status == "COMPLETED"
        )
    ).scalar()
    if last:
        lead.last_activity_on = last


def cancel_planned(s: Session, lead: Lead, reason: str, *, types: tuple[str, ...] | None = None) -> int:
    count = 0
    for act in s.execute(
        sa.select(LeadActivity).where(LeadActivity.lead_id == lead.id, LeadActivity.activity_status == "PLANNED")
    ).scalars():
        if types and act.activity_type not in types:
            continue
        act.activity_status = "CANCELLED"
        act.cancelled_reason = reason[:300]
        count += 1
    return count


def eligible_assignee(s: Session, user_id: str) -> bool:
    user = s.get(User, user_id)
    return bool(
        user
        and user.user_type == "HUMAN"
        and user.status == "ACTIVE"
        and "lead.read" in load_grants(s, user_id).granted
    )


# --- presentation (08 §8.1) --------------------------------------------------------------------------


def _user_ref(s: Session, user_id: str | None) -> dict | None:
    if not user_id:
        return None
    u = s.get(User, user_id, execution_options={"include_deleted": True})
    return {"id": user_id, "display_name": (u.display_name or u.full_name) if u else None}


def allowed_transitions(ctx, lead: Lead) -> list[str]:
    if lead.is_deleted or lead.anonymized_on:
        return []
    out = []
    if lead.status in OPEN_STATUSES:
        if not repo.in_scope(lead, ctx.scope("lead.status.change"), ctx.user.id):
            return []
        idx = OPEN_STATUSES.index(lead.status)
        out += list(OPEN_STATUSES[idx + 1 :])
        if idx > 0:
            out.append(OPEN_STATUSES[idx - 1])
        out += ["WON", "LOST"]
    elif repo.in_scope(lead, ctx.scope("lead.reopen"), ctx.user.id):
        out.append("CONTACTED" if lead.status == "LOST" else "NEGOTIATION")
    return out


def erasure_status(s: Session, lead: Lead) -> dict | None:
    from veda.platform.notifications.models import OutboxEvent

    if lead.anonymized_on is None:
        return None
    ev = s.execute(
        sa.select(OutboxEvent.status)
        .where(OutboxEvent.event_type == "lead.erasure_requested", OutboxEvent.aggregate_id == lead.id)
        .order_by(OutboxEvent.created_on.desc())
        .limit(1)
    ).scalar()
    if ev is None:
        return {"audit_status": "COMPLETED"}
    return {"audit_status": "COMPLETED" if ev == "DONE" else ("FAILED" if ev == "DEAD" else "PENDING")}


def present(s: Session, ctx, lead: Lead) -> dict:
    now = clock.now()
    duplicate_of = None
    if lead.duplicate_of_lead_id:
        dup = s.execute(
            repo.visible_select(ctx, include_deleted=True).where(Lead.id == lead.duplicate_of_lead_id)
        ).scalar_one_or_none()
        if dup is not None:
            duplicate_of = {"id": dup.id, "lead_number": dup.lead_number, "name": dup.name, "status": dup.status}
    return {
        "id": lead.id,
        "lead_number": lead.lead_number,
        "name": lead.name,
        "phone": lead.phone,
        "phone_raw": lead.phone_raw,
        "public_reference": lead.public_reference,
        "email": lead.email,
        "city": lead.city,
        "locality": lead.locality,
        "project_type": lookups.value_ref(s, lead.project_type_id),
        "property_type": lookups.value_ref(s, lead.property_type_id),
        "budget_range": lookups.value_ref(s, lead.budget_range_id),
        "message": lead.message,
        "status": lead.status,
        "status_changed_on": clock.to_rfc3339(lead.status_changed_on),
        "priority": lead.priority,
        "source": lookups.value_ref(s, lead.source_id),
        "source_detail": lead.source_detail,
        "attribution": {
            "utm_source": lead.utm_source,
            "utm_medium": lead.utm_medium,
            "utm_campaign": lead.utm_campaign,
            "utm_term": lead.utm_term,
            "utm_content": lead.utm_content,
            "landing_page": lead.landing_page,
            "referrer_url": lead.referrer_url,
        },
        "assigned_to": _user_ref(s, lead.assigned_to),
        "assigned_on": clock.to_rfc3339(lead.assigned_on),
        "next_follow_up_on": clock.to_rfc3339(lead.next_follow_up_on),
        "is_follow_up_overdue": bool(lead.next_follow_up_on and lead.next_follow_up_on < now),
        "last_activity_on": clock.to_rfc3339(lead.last_activity_on),
        "expected_close_on": lead.expected_close_on.isoformat() if lead.expected_close_on else None,
        "quoted": None,
        "won_on": clock.to_rfc3339(lead.won_on),
        "lost_on": clock.to_rfc3339(lead.lost_on),
        "lost_reason": lookups.value_ref(s, lead.lost_reason_id),
        "lost_reason_note": lead.lost_reason_note,
        "duplicate_status": lead.duplicate_status,
        "duplicate_of": duplicate_of,
        "spam_status": lead.spam_status,
        "consent": {
            "contact": lead.consent_contact,
            "policy_version": lead.consent_policy_version,
            "captured_on": clock.to_rfc3339(lead.consent_captured_on),
            "channel": lead.consent_channel,
            "source_page": lead.consent_source_page,
            "ip_address": _mask_ip(lead.consent_ip_address),
            "withdrawn_on": clock.to_rfc3339(lead.consent_withdrawn_on),
            "withdrawal_channel": lead.consent_withdrawal_channel,
            "withdrawal_note": lead.consent_withdrawal_note,
        },
        "intake_unmapped": lead.intake_unmapped,
        "allowed_transitions": allowed_transitions(ctx, lead),
        "anonymized_on": clock.to_rfc3339(lead.anonymized_on),
        "erasure": erasure_status(s, lead),
        "created_on": clock.to_rfc3339(lead.created_on),
        "created_by": _user_ref(s, lead.created_by),
        "updated_on": clock.to_rfc3339(lead.updated_on),
        "updated_by": _user_ref(s, lead.updated_by),
        "is_deleted": lead.is_deleted,
        "version": lead.version,
    }


def present_item(s: Session, lead: Lead) -> dict:
    now = clock.now()
    return {
        "id": lead.id,
        "lead_number": lead.lead_number,
        "name": lead.name,
        "phone": lead.phone,
        "city": lead.city,
        "locality": lead.locality,
        "project_type": lookups.value_ref(s, lead.project_type_id),
        "budget_range": lookups.value_ref(s, lead.budget_range_id),
        "status": lead.status,
        "priority": lead.priority,
        "source": lookups.value_ref(s, lead.source_id),
        "assigned_to": _user_ref(s, lead.assigned_to),
        "next_follow_up_on": clock.to_rfc3339(lead.next_follow_up_on),
        "is_follow_up_overdue": bool(lead.next_follow_up_on and lead.next_follow_up_on < now),
        "duplicate_status": lead.duplicate_status,
        "spam_status": lead.spam_status,
        "consent_withdrawn": lead.consent_withdrawn_on is not None,
        "is_deleted": lead.is_deleted,
        "created_on": clock.to_rfc3339(lead.created_on),
        "version": lead.version,
    }


def _mask_ip(ip: str | None) -> str | None:
    from veda.kernel.http import mask_ip

    return mask_ip(ip)


def conflict_extra(s: Session, lead: Lead) -> dict:
    return {
        "current_version": lead.version,
        "updated_by": _user_ref(s, lead.updated_by),
        "updated_on": clock.to_rfc3339(lead.updated_on),
    }


def check_version(s: Session, lead: Lead, if_match: int | None) -> None:
    from veda.kernel.http import check_version as _check

    _check(
        if_match,
        lead.version,
        conflict_extra=conflict_extra(s, lead) | {"title": "This lead was changed by someone else"},
    )


# --- public intake (04 §5.1, ADR-005) ---------------------------------------------------------------


def _clean_optional(value: Any, max_len: int, field: str, errors: list[dict]) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        errors.append(field_error(field, "INVALID", "Expected text."))
        return None
    v = strip_controls(value).strip()
    if len(v) > max_len:
        errors.append(field_error(field, "TOO_LONG", f"Must be at most {max_len} characters."))
        return None
    return v or None


def _attr(value: Any, max_len: int) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return strip_controls(value).strip()[:max_len]


def _strip_pii_query(url: str | None) -> str | None:
    """Keep path + attribution parameters only (landing_page is PII-stripped, 04 §2)."""
    if not url:
        return None
    from urllib.parse import parse_qsl, urlencode, urlsplit

    parts = urlsplit(url)
    keep = [(k, v) for k, v in parse_qsl(parts.query) if k.startswith("utm_") or k in ("gclid", "fbclid")]
    path = parts.path or "/"
    return (path + ("?" + urlencode(keep) if keep else ""))[:500]


def validate_public(body) -> dict:
    """Step 6: required name, phone and consent; optional fields; never INVALID_LOOKUP (LEAD-030)."""
    errors: list[dict] = []
    name = body.name
    if not isinstance(name, str) or not name.strip():
        errors.append(field_error("name", "REQUIRED", "Enter your name."))
    else:
        name = single_line(name)
        if len(name) > 150:
            errors.append(field_error("name", "TOO_LONG", "Must be at most 150 characters."))
        elif len(name) < 2 or not any(ch.isalpha() for ch in name):
            errors.append(field_error("name", "INVALID_NAME", "Enter your name."))
    phone_raw = body.phone
    phone = None
    if not isinstance(phone_raw, str) or not phone_raw.strip():
        errors.append(field_error("phone", "REQUIRED", "Enter a phone number."))
    elif len(phone_raw) > 30:
        errors.append(field_error("phone", "TOO_LONG", "Must be at most 30 characters."))
    else:
        try:
            phone = parse_phone(phone_raw)
        except ValueError:
            errors.append(field_error("phone", "INVALID_PHONE", "Enter a valid phone number."))
    email = _clean_optional(body.email, 254, "email", errors)
    if email and not EMAIL_RE.match(email):
        errors.append(field_error("email", "INVALID_EMAIL", "Enter a valid email address."))
    city = _clean_optional(body.city, 100, "city", errors)
    city = single_line(city) or None if city else city
    message = _clean_optional(body.message, 4000, "message", errors)
    codes = {}
    for field, _col, _cat in LOOKUP_FIELDS:
        value = getattr(body, field)
        codes[field] = value if isinstance(value, str) and value.strip() else None
    if errors:
        raise validation_failed(errors)
    consent = body.consent
    if consent is None or consent.acknowledged is not True:
        raise ApiError(
            422,
            "CONSENT_REQUIRED",
            "Please agree to be contacted.",
            errors=[field_error("consent.acknowledged", "CONSENT_REQUIRED", "Please agree to be contacted.")],
        )
    if consent.policy_version not in settings().published_policy_versions:
        raise ApiError(
            422,
            "UNKNOWN_POLICY_VERSION",
            "Refresh the page and try again.",
            errors=[field_error("consent.policy_version", "UNKNOWN_POLICY_VERSION", "Unknown privacy notice version.")],
        )
    return {
        "name": name,
        "phone": phone,
        "phone_raw": phone_raw.strip(),
        "email": email,
        "city": city,
        "message": message,
        "codes": codes,
        "policy_version": consent.policy_version,
    }


def find_by_idempotency_key(s: Session, key: str) -> Lead | None:
    return s.execute(
        sa.select(Lead).where(Lead.intake_idempotency_key == key).execution_options(include_deleted=True)
    ).scalar_one_or_none()


def create_public(
    s: Session, body, *, key: str, fingerprint: str, ip: str | None, ua: str | None, request_id: str | None
) -> dict:
    data = validate_public(body)
    with acting(
        s, ActorContext(actor_id=WEB_INTAKE_USER_ID, via="PUBLIC_FORM", request_id=request_id, ip=ip, user_agent=ua)
    ):
        now = db.tx_time(s)
        unmapped = {}
        ids = {}
        for field, col, cat in LOOKUP_FIELDS:
            code = data["codes"][field]
            value = lookups.resolve_code(s, cat, code) if code else None
            if code and value is None:
                unmapped[field] = code[:100]
            ids[col] = value.id if value else None
        source = lookups.resolve_code(s, "LEAD_SOURCE", "WEBSITE")
        attribution = body.attribution
        honeypot = body.company_website_url
        spam = (
            isinstance(honeypot, str)
            and honeypot.strip() != ""
            or (honeypot not in (None, "") and not isinstance(honeypot, str))
        )
        lead = Lead(
            lead_number=sequences.next_number(s, "LEAD"),
            public_reference=new_public_reference(s),
            name=data["name"],
            phone=data["phone"],
            phone_raw=data["phone_raw"][:30],
            email=data["email"],
            email_normalized=normalize_email(data["email"]) if data["email"] else None,
            city=data["city"],
            message=data["message"],
            status="NEW",
            status_changed_on=now,
            priority="MEDIUM",
            source_id=source.id,
            utm_source=_attr(attribution.utm_source, 100) if attribution else None,
            utm_medium=_attr(attribution.utm_medium, 100) if attribution else None,
            utm_campaign=_attr(attribution.utm_campaign, 100) if attribution else None,
            utm_term=_attr(attribution.utm_term, 100) if attribution else None,
            utm_content=_attr(attribution.utm_content, 100) if attribution else None,
            landing_page=_strip_pii_query(_attr(attribution.landing_page, 2000)) if attribution else None,
            referrer_url=_attr(attribution.referrer_url, 500) if attribution else None,
            consent_contact=True,
            consent_policy_version=data["policy_version"],
            consent_captured_on=now,
            consent_channel="WEBSITE_FORM",
            consent_source_page=_strip_pii_query(_attr(attribution.form_page, 2000)) if attribution else None,
            consent_ip_address=ip,
            intake_idempotency_key=key,
            intake_request_fingerprint=fingerprint,
            intake_unmapped=unmapped or None,
            spam_status="SUSPECTED" if spam else "NONE",
            currency="INR",
            **ids,
        )
        dup = find_duplicate(s, lead)
        if dup is not None:
            lead.duplicate_status, lead.duplicate_of_lead_id = "SUSPECTED", dup.id
        lead.search_text = repo.build_search_text(lead)
        s.add(lead)
        s.flush()
        add_system_activity(
            s, lead, "SYSTEM", "Enquiry received from the website", owner=WEB_INTAKE_USER_ID, description=None
        )
        if spam:
            security_events.record(
                s, "PUBLIC_INTAKE_QUARANTINED", "SUCCESS", target=("lead", lead.id), detail={"reason": "honeypot"}
            )
        else:
            outbox.enqueue(s, "lead.created", "lead", lead.id, lead_id=lead.id)
        return {"reference": lead.public_reference, "message": PUBLIC_MESSAGE}


# --- manual create (04 §5.2) ---------------------------------------------------------------------


def create_manual(s: Session, ctx, body) -> tuple[Lead, list[dict]]:
    if body.source_code == "WEBSITE":
        raise ApiError(
            422,
            "SOURCE_NOT_ALLOWED",
            "Website leads come only from the public form.",
            errors=[field_error("source_code", "SOURCE_NOT_ALLOWED", "Choose another source.")],
        )
    source_id = lookup_id(s, "LEAD_SOURCE", body.source_code, "source_code")
    ids = {col: lookup_id(s, cat, getattr(body, field), field) for field, col, cat in LOOKUP_FIELDS}
    assigned_to = body.assigned_to
    if assigned_to is None and ctx.scope("lead.read") == "OWN":
        assigned_to = ctx.user.id
    if assigned_to and assigned_to != ctx.user.id and not ctx.has("lead.assign"):
        raise ApiError(
            403,
            "PERMISSION_DENIED",
            "Requires lead.assign to assign to someone else.",
            extra={"permission": "lead.assign"},
        )
    if assigned_to and not eligible_assignee(s, assigned_to):
        raise ApiError(
            422,
            "INVALID_ASSIGNEE",
            "Choose an active team member who can view leads.",
            errors=[field_error("assigned_to", "INVALID_ASSIGNEE", "Not an eligible assignee.")],
        )
    now = db.tx_time(s)
    lead = Lead(
        lead_number=sequences.next_number(s, "LEAD", timezone=ctx.user.timezone),
        public_reference=new_public_reference(s),
        name=single_line(body.name),
        phone=parse_phone(body.phone),
        phone_raw=body.phone[:30],
        email=body.email,
        email_normalized=normalize_email(body.email) if body.email else None,
        city=single_line(body.city) or None if body.city else None,
        locality=single_line(body.locality) or None if body.locality else None,
        message=body.message,
        status="NEW",
        status_changed_on=now,
        priority=body.priority,
        source_id=source_id,
        source_detail=body.source_detail,
        assigned_to=assigned_to,
        assigned_on=now if assigned_to else None,
        expected_close_on=body.expected_close_on,
        currency="INR",
        consent_contact=False,
        spam_status="NONE",
        **ids,
    )
    if body.consent:
        _require_published(body.consent.policy_version)
        lead.consent_contact, lead.consent_policy_version = True, body.consent.policy_version
        lead.consent_captured_on, lead.consent_channel = now, body.consent.channel
    dup = find_duplicate(s, lead)
    if dup is not None:
        lead.duplicate_status, lead.duplicate_of_lead_id = "SUSPECTED", dup.id
    lead.search_text = repo.build_search_text(lead)
    s.add(lead)
    s.flush()
    add_system_activity(s, lead, "SYSTEM", "Lead created")
    if body.consent:
        _add_consent_evidence(s, lead, body.consent, previous=None, now=now)  # RR-12 (b): same evidence as PATCH
    if assigned_to:
        add_system_activity(
            s,
            lead,
            "ASSIGNMENT",
            f"Assigned to {_user_ref(s, assigned_to)['display_name']}",
            metadata={"to": assigned_to},
        )
        if assigned_to != ctx.user.id:
            outbox.enqueue(s, "lead.assigned", "lead", lead.id, lead_id=lead.id, assignee_id=assigned_to)
    if body.initial_note:
        s.add(LeadNote(lead_id=lead.id, body=body.initial_note, is_pinned=False, visibility="INTERNAL"))
    s.flush()
    return lead, possible_duplicates(s, ctx, lead)


def possible_duplicates(s: Session, ctx, lead: Lead) -> list[dict]:
    since = db.tx_time(s) - DUPLICATE_WINDOW
    conds = [Lead.phone == lead.phone]
    if lead.email_normalized:
        conds.append(Lead.email_normalized == lead.email_normalized)
    rows = (
        s.execute(
            repo.visible_select(ctx)
            .where(sa.or_(*conds), Lead.id != lead.id, Lead.created_on >= since)
            .order_by(Lead.created_on.desc())
            .limit(10)
        )
        .scalars()
        .all()
    )
    return [{"id": r.id, "lead_number": r.lead_number, "name": r.name, "status": r.status} for r in rows]


# --- enrichment (04 §5.3) --------------------------------------------------------------------------


def update(s: Session, ctx, lead: Lead, body) -> Lead:
    with s.no_autoflush:  # one logical change → one UPDATE and one audit row
        return _update(s, ctx, lead, body)


def _update(s: Session, ctx, lead: Lead, body) -> Lead:
    provided = body.provided()
    if lead.anonymized_on is not None:
        raise ApiError(409, "INVALID_STATE", "This lead's personal data was erased.")
    if "name" in provided:
        if not body.name:
            raise validation_failed([field_error("name", "REQUIRED", "Name is required.")])
        lead.name = single_line(body.name)
    if "phone" in provided:
        if not body.phone:
            raise validation_failed([field_error("phone", "REQUIRED", "Phone is required.")])
        lead.phone, lead.phone_raw = parse_phone(body.phone), body.phone[:30]
    if "email" in provided:
        lead.email = body.email
        lead.email_normalized = normalize_email(body.email) if body.email else None
    for field in ("city", "locality"):
        if field in provided:
            value = getattr(body, field)
            setattr(lead, field, single_line(value) or None if value else None)
    for field in ("message", "source_detail", "expected_close_on"):
        if field in provided:
            setattr(lead, field, getattr(body, field))
    if "priority" in provided and body.priority:
        lead.priority = body.priority
    if "source_code" in provided and body.source_code:
        if body.source_code == "WEBSITE" and lookups.value_ref(s, lead.source_id)["code"] != "WEBSITE":
            raise ApiError(422, "SOURCE_NOT_ALLOWED", "Website is reserved for the public form.")
        lead.source_id = lookup_id(s, "LEAD_SOURCE", body.source_code, "source_code")
    for field, col, cat in LOOKUP_FIELDS:
        if field in provided:
            setattr(lead, col, lookup_id(s, cat, getattr(body, field), field))
            if lead.intake_unmapped and field in lead.intake_unmapped:
                remaining = {k: v for k, v in lead.intake_unmapped.items() if k != field}
                lead.intake_unmapped = remaining or None
    if "consent" in provided and body.consent is not None:
        record_reconsent(s, lead, body.consent)
    if {"phone", "email"} & provided:
        dup = find_duplicate(s, lead)
        if dup is not None and lead.duplicate_status == "NONE":
            lead.duplicate_status, lead.duplicate_of_lead_id = "SUSPECTED", dup.id
    lead.search_text = repo.build_search_text(lead)
    return lead


# --- status machine (04 §3) --------------------------------------------------------------------------


def change_status(s: Session, ctx, lead: Lead, body) -> LeadActivity:
    to = body.to_status
    frm = lead.status
    now = db.tx_time(s)
    if to == frm:
        raise ApiError(422, "NO_OP_TRANSITION", "The lead is already in this status.")
    reopen = frm in ("WON", "LOST")
    permission = "lead.reopen" if reopen else "lead.status.change"
    repo.require_scope(ctx, lead, permission)
    comment = body.comment
    if reopen:
        valid = (frm == "LOST" and to == "CONTACTED") or (frm == "WON" and to == "NEGOTIATION")
        if not valid:
            raise ApiError(
                422,
                "INVALID_STATUS_TRANSITION",
                "Reopen first.",
                extra={"allowed_transitions": allowed_transitions(ctx, lead)},
            )
        if not comment:
            raise ApiError(422, "COMMENT_REQUIRED", "Explain why the lead is reopened.")
    elif to in OPEN_STATUSES:
        fi, ti = OPEN_STATUSES.index(frm), OPEN_STATUSES.index(to)
        if ti < fi - 1:
            raise ApiError(
                422,
                "INVALID_STATUS_TRANSITION",
                "Only one step back is allowed.",
                extra={"allowed_transitions": allowed_transitions(ctx, lead)},
            )
        if ti == fi - 1 and not comment:
            raise ApiError(422, "COMMENT_REQUIRED", "Explain why the lead moves back.")
    elif to == "WON":
        if frm not in ("NEGOTIATION", "QUOTATION_SENT") and not comment:
            raise ApiError(422, "COMMENT_REQUIRED", "Add a comment when winning from an early stage.")
    elif to == "LOST":
        if not body.lost_reason_code:
            raise ApiError(
                422,
                "LOST_REASON_REQUIRED",
                "Choose why the lead was lost.",
                errors=[field_error("lost_reason_code", "REQUIRED", "Choose a reason.")],
            )
        if body.lost_reason_code == "OTHER" and not body.lost_reason_note:
            raise ApiError(
                422,
                "LOST_REASON_REQUIRED",
                "Describe the reason.",
                errors=[field_error("lost_reason_note", "REQUIRED", "Describe the reason.")],
            )
    lost_reason_id = lookup_id(s, "LOST_REASON", body.lost_reason_code, "lost_reason_code") if to == "LOST" else None
    lead.status = to
    lead.status_changed_on = now
    if to == "WON":
        won_on = body.won_on or now
        if won_on > now + timedelta(minutes=5):
            raise validation_failed([field_error("won_on", "OUT_OF_RANGE", "Can't be in the future.")])
        lead.won_on = won_on
        cancel_planned(s, lead, "Lead won")
        outbox.enqueue(s, "lead.won", "lead", lead.id, lead_id=lead.id)
    elif to == "LOST":
        lead.lost_on = now
        lead.lost_reason_id = lost_reason_id
        lead.lost_reason_note = body.lost_reason_note
        cancel_planned(s, lead, "Lead lost")
    elif reopen:
        if frm == "LOST":
            lead.lost_on = lead.lost_reason_id = lead.lost_reason_note = None
        else:
            lead.won_on = None
        outbox.enqueue(s, "lead.reopened", "lead", lead.id, lead_id=lead.id)
    label = {s_: s_.replace("_", " ").capitalize() for s_ in LEAD_STATUSES}
    act = add_system_activity(
        s,
        lead,
        "STATUS_CHANGE",
        f"Status changed: {label[frm]} → {label[to]}",
        from_status=frm,
        to_status=to,
        description=comment,
    )
    recompute_follow_up(s, lead)
    return act


def planned_count(s: Session, lead: Lead) -> int:
    return int(
        s.execute(
            sa.select(sa.func.count())
            .select_from(LeadActivity)
            .where(LeadActivity.lead_id == lead.id, LeadActivity.activity_status == "PLANNED")
        ).scalar()
        or 0
    )


# --- assignment (04 §6) -----------------------------------------------------------------------------------


def assign(s: Session, ctx, lead: Lead, assigned_to: str | None, comment: str | None) -> None:
    repo.require_scope(ctx, lead, "lead.assign")
    if assigned_to == lead.assigned_to:
        raise ApiError(422, "NO_OP_ASSIGNMENT", "The lead is already assigned this way.")
    if assigned_to and not eligible_assignee(s, assigned_to):
        raise ApiError(
            422,
            "INVALID_ASSIGNEE",
            "Choose an active team member who can view leads.",
            errors=[field_error("assigned_to", "INVALID_ASSIGNEE", "Not an eligible assignee.")],
        )
    now = db.tx_time(s)
    previous = lead.assigned_to
    lead.assigned_to = assigned_to
    lead.assigned_on = now if assigned_to else None
    subject = f"Assigned to {_user_ref(s, assigned_to)['display_name']}" if assigned_to else "Unassigned"
    add_system_activity(
        s, lead, "ASSIGNMENT", subject, description=comment, metadata={"from": previous, "to": assigned_to}
    )
    if assigned_to:
        outbox.enqueue(s, "lead.assigned", "lead", lead.id, lead_id=lead.id, assignee_id=assigned_to)


# --- duplicate / spam / consent ------------------------------------------------------------------------------


def resolve_duplicate(s: Session, ctx, lead: Lead, resolution: str, duplicate_of_lead_id: str | None) -> None:
    repo.require_scope(ctx, lead, "lead.update")
    if duplicate_of_lead_id:
        if duplicate_of_lead_id == lead.id:
            raise validation_failed([field_error("duplicate_of_lead_id", "INVALID", "A lead can't duplicate itself.")])
        target = s.execute(repo.visible_select(ctx).where(Lead.id == duplicate_of_lead_id)).scalar_one_or_none()
        if target is None:
            raise not_found()  # outside scope behaves as not found (A-07)
        lead.duplicate_of_lead_id = target.id
    if resolution == "CONFIRMED":
        if lead.duplicate_of_lead_id is None:
            raise validation_failed([field_error("duplicate_of_lead_id", "REQUIRED", "Choose the original lead.")])
        lead.duplicate_status = "CONFIRMED"
    else:
        lead.duplicate_status = "NOT_DUPLICATE"
    add_system_activity(s, lead, "SYSTEM", f"Duplicate review: {resolution.replace('_', ' ').lower()}")


def resolve_spam(s: Session, ctx, lead: Lead, resolution: str) -> None:
    repo.require_scope(ctx, lead, "lead.update")
    if lead.spam_status != "SUSPECTED":
        raise ApiError(409, "INVALID_STATE", "Only leads in the spam review queue can be resolved.")
    lead.spam_status = resolution
    add_system_activity(
        s, lead, "SYSTEM", "Released from spam review" if resolution == "NOT_SPAM" else "Confirmed as spam"
    )
    if resolution == "NOT_SPAM":
        outbox.enqueue(s, "lead.created", "lead", lead.id, lead_id=lead.id)


def withdraw_consent(s: Session, ctx, lead: Lead, channel: str, note: str | None) -> int:
    repo.require_scope(ctx, lead, "lead.update")
    if lead.consent_withdrawn_on is not None:
        raise ApiError(409, "INVALID_STATE", "Consent is already withdrawn.")
    now = db.tx_time(s)
    lead.consent_contact = False
    lead.consent_withdrawn_on = now
    lead.consent_withdrawal_channel = channel
    lead.consent_withdrawal_note = note
    cancelled = cancel_planned(s, lead, "CONSENT_WITHDRAWN", types=CONTACT_ACTIVITY_TYPES)
    lead.next_follow_up_on = None
    add_system_activity(s, lead, "SYSTEM", "Consent to contact withdrawn", description=note)
    recompute_follow_up(s, lead)
    return cancelled


def _require_published(version: str) -> None:
    if version not in settings().published_policy_versions:
        raise ApiError(422, "UNKNOWN_POLICY_VERSION", "Unknown privacy notice version.")


def policy_rank(version: str | None) -> int:
    """Publication order of a privacy-notice version (AM-4 rule a, RR-12).

    VEDA_PUBLISHED_POLICY_VERSIONS lists the published notices oldest first. A version that is no longer listed
    (or none at all) counts as the earliest."""
    versions = settings().published_policy_versions
    return versions.index(version) if version in versions else -1


def _add_consent_evidence(s: Session, lead: Lead, capture, *, previous: dict | None, now) -> None:
    """The consent-history entry of the lead timeline: read-only in the API, guarded in the database (0010)."""
    add_system_activity(
        s,
        lead,
        "SYSTEM",
        "Consent to contact recorded again" if previous else "Consent to contact recorded",
        description=capture.note,
        metadata={
            "consent_event": "RECAPTURED" if previous else "CAPTURED",
            "previous": previous,
            "recorded": {
                "policy_version": capture.policy_version,
                "channel": capture.channel,
                "captured_on": clock.to_rfc3339(now),
            },
        },
    )


def record_reconsent(s: Session, lead: Lead, capture) -> None:
    """Staff re-consent (04 §5.4; DEV-004 as corrected for IR-16 and RR-12, AM-4).

    * Accepted when consent was withdrawn or never captured, or for a LATER published privacy-notice version
      (policy_rank). Re-recording the same version, or going back to an earlier one, would only overwrite
      evidence: 409 INVALID_STATE. An earlier version is refused even after a withdrawal.
    * The consent evidence it supersedes, including the withdrawal note, is first written to a consent-history
      system activity (append-only, guarded in the database), and the full prior row values stay in audit_log.
    * The new capture carries its own provenance: the staff channel and note, with no web IP or source page.
    """
    _require_published(capture.policy_version)
    withdrawn = lead.consent_withdrawn_on is not None
    never_captured = lead.consent_captured_on is None
    recorded, offered = policy_rank(lead.consent_policy_version), policy_rank(capture.policy_version)
    if not never_captured and offered < recorded:
        raise ApiError(409, "INVALID_STATE", "Consent is already recorded for a later privacy notice version.")
    if not (withdrawn or never_captured or offered > recorded):
        raise ApiError(409, "INVALID_STATE", "Consent is already recorded for this privacy notice version.")
    now = db.tx_time(s)
    previous = (
        None
        if never_captured
        else {
            "policy_version": lead.consent_policy_version,
            "channel": lead.consent_channel,
            "captured_on": clock.to_rfc3339(lead.consent_captured_on),
            "source_page": lead.consent_source_page,
            "ip_address_recorded": lead.consent_ip_address is not None,
            "withdrawn_on": clock.to_rfc3339(lead.consent_withdrawn_on),
            "withdrawal_channel": lead.consent_withdrawal_channel,
            "withdrawal_note": lead.consent_withdrawal_note,
        }
    )
    _add_consent_evidence(s, lead, capture, previous=previous, now=now)
    lead.consent_contact, lead.consent_policy_version = True, capture.policy_version
    lead.consent_captured_on, lead.consent_channel = now, capture.channel
    lead.consent_source_page = lead.consent_ip_address = None
    lead.consent_withdrawn_on = lead.consent_withdrawal_channel = lead.consent_withdrawal_note = None


# --- delete / restore -----------------------------------------------------------------------------------


def delete(s: Session, ctx, lead: Lead, reason: str | None) -> None:
    repo.require_scope(ctx, lead, "lead.delete")
    lead.is_deleted = True
    record_sensitive_action(s, ctx, "lead.delete", action="delete_lead", target=("lead", lead.id))


def restore(s: Session, ctx, lead: Lead) -> None:
    if not lead.is_deleted:
        raise ApiError(409, "INVALID_STATE", "The lead is not deleted.")
    lead.is_deleted = False


# --- erasure (04 §14.2, 07 §8.2) ------------------------------------------------------------------------

PII_PLACEHOLDERS = {
    "name": "Anonymized lead",
    "phone": "",
    "phone_raw": "",
    "email": None,
    "email_normalized": None,
    "city": None,
    "locality": None,
    "message": None,
    "consent_ip_address": None,
    "consent_source_page": None,
    "consent_withdrawal_note": None,
    "intake_unmapped": None,
}


def anonymize(s: Session, lead: Lead, *, legal_basis: str, request_ref: str | None) -> list[str]:
    """Replace PII of the live lead and its children through the ORM (07 §8.2 steps 1 and 5)."""
    erasure = s.info.setdefault("erasure_entities", set())
    erasure.add(lead.id)
    changed = []
    for field, placeholder in PII_PLACEHOLDERS.items():
        if getattr(lead, field) != placeholder:
            setattr(lead, field, placeholder)
            changed.append(field)
    lead.search_text = repo.fold(" ".join(p for p in (lead.lead_number, lead.public_reference) if p))
    lead.anonymized_on = db.tx_time(s)
    s.flush()  # the consent-evidence guard (0010) admits the erasure rewrite only once the lead is anonymized
    for note in s.execute(
        sa.select(LeadNote).where(LeadNote.lead_id == lead.id).execution_options(include_deleted=True)
    ).scalars():
        erasure.add(note.id)
        note.body = ANONYMIZED
    for act in s.execute(
        sa.select(LeadActivity).where(LeadActivity.lead_id == lead.id).execution_options(include_deleted=True)
    ).scalars():
        erasure.add(act.id)
        if act.description:
            act.description = ANONYMIZED
        if act.location:
            act.location = ANONYMIZED
        meta = act.metadata_ or {}
        previous = meta.get("previous") if "consent_event" in meta else None
        if previous and (previous.get("withdrawal_note") or previous.get("source_page")):
            # Personal text copied into the consent-history snapshot (RR-12 c); the rest of the evidence stays.
            scrubbed = {**previous, "source_page": None}
            if previous.get("withdrawal_note"):
                scrubbed["withdrawal_note"] = ANONYMIZED
            act.metadata_ = {**meta, "previous": scrubbed}
    write_explicit_audit(
        s,
        entity_type="lead",
        entity_id=lead.id,
        action="ANONYMIZE",
        new_value={"fields": sorted(PII_PLACEHOLDERS), "legal_basis": legal_basis, "request_ref": request_ref},
        changed_fields=sorted(PII_PLACEHOLDERS),
    )
    return changed


def erase(s: Session, ctx, lead: Lead, body) -> None:
    require_step_up(ctx)
    if lead.anonymized_on is not None:
        raise ApiError(409, "INVALID_STATE", "This lead was already erased.")
    blocked = settings_blocked_statuses()
    if lead.status in blocked:
        # Deferred: the refusal raises, and the evidence must survive the rolled-back transaction (IR-25, SEVT-011).
        security_events.defer(
            "SENSITIVE_ACTION",
            "FAILURE",
            subject_user_id=ctx.user.id,
            permission_code="lead.erase",
            target=("lead", lead.id),
            detail={"action": "erase_refused", "reason": "retention"},
        )
        raise ApiError(
            422,
            "ERASURE_BLOCKED",
            "A legal hold or retention need applies to this lead.",
            extra={"basis": f"Lead status {lead.status} is under the configured retention hold."},
        )
    from veda.kernel.context import reason as with_reason

    with with_reason(body.reason):
        anonymize(s, lead, legal_basis=body.legal_basis, request_ref=body.request_ref)
        record_sensitive_action(s, ctx, "lead.erase", action="erase", target=("lead", lead.id))
        # The application process never issues DDL: the maintenance CLI rewrites audit payloads (07 §8.2 step 6).
        outbox.enqueue(s, "lead.erasure_requested", "lead", lead.id, lead_id=lead.id)
    # Operational rows for the lead are purged (07 §8.2 step 4): unread notifications that deep-link to it.
    from veda.platform.notifications.models import Notification

    for n in s.execute(
        sa.select(Notification).where(Notification.entity_type == "lead", Notification.entity_id == lead.id)
    ).scalars():
        n.is_deleted = True


def settings_blocked_statuses() -> frozenset[str]:
    import os

    raw = os.environ.get("VEDA_ERASURE_BLOCKED_STATUSES", "")
    return frozenset(v.strip() for v in raw.split(",") if v.strip())


def masked_contact(lead: Lead) -> str:
    return mask_email(lead.email) or ""
