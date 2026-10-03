"""Lead request DTOs (08 §8, §9). Closed schemas (SEC-004)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from veda.kernel.dto import CalendarDate, Closed, Email, Id, Instant, Phone, Query, optional_text, text

Priority = Literal["HIGH", "MEDIUM", "LOW"]
LeadStatus = Literal["NEW", "CONTACTED", "SITE_VISIT", "QUOTATION_SENT", "NEGOTIATION", "WON", "LOST"]


# --- public intake: loose types, validated in the service after idempotency and CAPTCHA (04 §5.1) ---


class PublicConsent(Closed):
    acknowledged: Any = None
    policy_version: Any = None


class PublicAttribution(Closed):
    utm_source: Any = None
    utm_medium: Any = None
    utm_campaign: Any = None
    utm_term: Any = None
    utm_content: Any = None
    landing_page: Any = None
    referrer_url: Any = None
    form_page: Any = None


class PublicLeadIn(Closed):
    name: Any = None
    phone: Any = None
    consent: PublicConsent | None = None
    email: Any = None
    city: Any = None
    project_type_code: Any = None
    budget_range_code: Any = None
    property_type_code: Any = None
    message: Any = None
    attribution: PublicAttribution | None = None
    turnstile_token: Any = None
    company_website_url: Any = None  # honeypot (04 §5.1)


# --- staff ------------------------------------------------------------------------------------


class ConsentCapture(Closed):
    """Consent captured by staff. WEBSITE_FORM is reserved for the public form, whose request context is the
    evidence; staff cannot assert it (IR-16)."""

    channel: Literal["PHONE_VERBAL", "IN_PERSON", "WHATSAPP", "EMAIL"]
    policy_version: Annotated[str, text(20, min_len=1)]


class ConsentRecapture(ConsentCapture):
    """Staff consent, at creation or as re-consent (04 §5.4, DEV-004, RR-12): how it was obtained, with a note."""

    note: Annotated[str, text(500, min_len=1)]


class LeadCreateIn(Closed):
    name: Annotated[str, text(150, min_len=1)]
    phone: Phone
    email: Email | None = None
    city: Annotated[str | None, optional_text(100)] = None
    locality: Annotated[str | None, optional_text(150)] = None
    project_type_code: str | None = None
    property_type_code: str | None = None
    budget_range_code: str | None = None
    message: Annotated[str | None, optional_text(4000)] = None
    source_code: Annotated[str, text(50, min_len=1)]
    source_detail: Annotated[str | None, optional_text(200)] = None
    priority: Priority = "MEDIUM"
    assigned_to: Id | None = None
    expected_close_on: CalendarDate | None = None
    initial_note: Annotated[str | None, optional_text(10000)] = None
    consent: ConsentRecapture | None = None  # staff capture: how it was obtained, with a note (RR-12, AM-4 b)


class LeadPatchIn(Closed):
    __not_updatable__ = frozenset(
        {
            "status",
            "assigned_to",
            "lead_number",
            "public_reference",
            "id",
            "created_on",
            "updated_on",
            "created_by",
            "updated_by",
            "is_deleted",
            "deleted_on",
            "deleted_by",
            "version",
            "duplicate_status",
            "duplicate_of_lead_id",
            "consent_contact",
            "consent_policy_version",
            "consent_captured_on",
            "consent_channel",
            "consent_source_page",
            "consent_ip_address",
            "consent_withdrawn_on",
            "consent_withdrawal_channel",
            "consent_withdrawal_note",
            "intake_idempotency_key",
            "intake_request_fingerprint",
            "spam_status",
            "won_on",
            "lost_on",
            "anonymized_on",
        }
    )
    name: Annotated[str | None, text(150, min_len=1)] = None
    phone: Phone | None = None
    email: Email | None = None
    city: Annotated[str | None, optional_text(100)] = None
    locality: Annotated[str | None, optional_text(150)] = None
    project_type_code: str | None = None
    property_type_code: str | None = None
    budget_range_code: str | None = None
    message: Annotated[str | None, optional_text(4000)] = None
    priority: Priority | None = None
    source_code: Annotated[str | None, text(50, min_len=1)] = None
    source_detail: Annotated[str | None, optional_text(200)] = None
    expected_close_on: CalendarDate | None = None
    consent: ConsentRecapture | None = None  # re-consent capture (04 §5.4, DEV-004)


class StatusChangeIn(Closed):
    to_status: LeadStatus
    comment: Annotated[str | None, optional_text(1000)] = None
    lost_reason_code: str | None = None
    lost_reason_note: Annotated[str | None, optional_text(1000)] = None
    won_on: Instant | None = None


class AssignIn(Closed):
    assigned_to: Id | None
    comment: Annotated[str | None, optional_text(1000)] = None


class DuplicateResolutionIn(Closed):
    resolution: Literal["CONFIRMED", "NOT_DUPLICATE"]
    duplicate_of_lead_id: Id | None = None


class SpamResolutionIn(Closed):
    resolution: Literal["NOT_SPAM", "CONFIRMED_SPAM"]


class ConsentWithdrawIn(Closed):
    channel: Literal["PHONE_VERBAL", "IN_PERSON", "WHATSAPP", "EMAIL", "WEBSITE"]
    note: Annotated[str | None, optional_text(500)] = None


class ErasureIn(Closed):
    request_ref: Annotated[str, text(100, min_len=1)]
    legal_basis: Annotated[str, text(200, min_len=1)]
    reason: Annotated[str, text(500, min_len=1, code_empty="REASON_REQUIRED")]


class DeleteIn(Closed):
    reason: Annotated[str | None, optional_text(500)] = None


class LeadListQuery(Query):
    q: str | None = None
    status: str | None = None
    open: bool | None = None
    assigned_to: str | None = None
    project_type: str | None = None
    budget_range: str | None = None
    property_type: str | None = None
    source: str | None = None
    priority: str | None = None
    city: str | None = None
    created_on_from: CalendarDate | None = None
    created_on_to: CalendarDate | None = None
    status_changed_on_from: CalendarDate | None = None
    status_changed_on_to: CalendarDate | None = None
    follow_up: Literal["overdue", "today", "this_week", "none"] | None = None
    duplicate_status: str | None = None
    spam_status: str | None = None
    consent: Literal["withdrawn"] | None = None
    include_deleted: bool = False
    deleted_only: bool = False
    sort: str | None = None
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=100)] = 25


class DuplicatesQuery(Query):
    phone: str | None = None
    email: str | None = None
    exclude_id: Id | None = None


class SummaryQuery(Query):
    period: Literal["today", "7d", "30d", "90d", "custom"] = "30d"
    from_: CalendarDate | None = Field(default=None, alias="from")
    to: CalendarDate | None = None


class CursorQuery(Query):
    cursor: str | None = None
    limit: Annotated[int, Field(ge=1, le=200)] = 50


# --- notes and activities -------------------------------------------------------------------------


class NoteIn(Closed):
    body: Annotated[str, text(10000, min_len=1)]
    is_pinned: bool = False
    visibility: Literal["INTERNAL", "CUSTOMER_VISIBLE"] = "INTERNAL"


class NotePatch(Closed):
    body: Annotated[str | None, text(10000, min_len=1)] = None
    is_pinned: bool | None = None


class NotesQuery(Query):
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=100)] = 50


ActivityType = Literal[
    "CALL",
    "WHATSAPP",
    "EMAIL",
    "MEETING",
    "SITE_VISIT",
    "QUOTATION",
    "FOLLOW_UP",
    "STATUS_CHANGE",
    "ASSIGNMENT",
    "SYSTEM",
]


class ActivityIn(Closed):
    activity_type: ActivityType
    activity_status: Literal["PLANNED", "COMPLETED"] = "COMPLETED"
    subject: Annotated[str, text(200, min_len=1)]
    description: Annotated[str | None, optional_text(4000)] = None
    direction: Literal["INBOUND", "OUTBOUND"] | None = None
    scheduled_on: Instant | None = None
    completed_on: Instant | None = None
    duration_minutes: Annotated[int | None, Field(default=None, ge=0, le=1440)] = None
    outcome_code: str | None = None
    owner_user_id: Id | None = None
    location: Annotated[str | None, optional_text(300)] = None


class ActivityPatch(Closed):
    __not_updatable__ = frozenset(
        {
            "activity_type",
            "activity_status",
            "is_system_generated",
            "lead_id",
            "from_status",
            "to_status",
            "completed_on",
        }
    )
    subject: Annotated[str | None, text(200, min_len=1)] = None
    description: Annotated[str | None, optional_text(4000)] = None
    scheduled_on: Instant | None = None
    duration_minutes: Annotated[int | None, Field(default=None, ge=0, le=1440)] = None
    location: Annotated[str | None, optional_text(300)] = None
    owner_user_id: Id | None = None


class ActivityComplete(Closed):
    completed_on: Instant | None = None
    outcome_code: str | None = None
    description: Annotated[str | None, optional_text(4000)] = None
    duration_minutes: Annotated[int | None, Field(default=None, ge=0, le=1440)] = None


class ActivityCancel(Closed):
    reason: Annotated[str | None, optional_text(300)] = None


class ActivitiesQuery(Query):
    type: str | None = None
    status: str | None = None
    cursor: str | None = None
    limit: Annotated[int, Field(ge=1, le=200)] = 50


class MyActivitiesQuery(Query):
    owner: str | None = "me"
    status: str | None = "PLANNED"
    scheduled_from: Instant | None = None
    scheduled_to: Instant | None = None
    overdue: bool | None = None
    cursor: str | None = None
    limit: Annotated[int, Field(ge=1, le=200)] = 50
