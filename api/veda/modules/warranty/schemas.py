"""Warranty and service request bodies and queries. Closed: an unknown field is refused (422 UNKNOWN_FIELD). No body
carries a status: every change is a command."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from veda.kernel.dto import CalendarDate, Closed, Id, Query, optional_text, text
from veda.modules.attachments.models import MAX_OBJECT_BYTES
from veda.modules.attachments.schemas import ImageMime, Sha256
from veda.modules.project.schemas import enum, one_of

from . import vocab as V

Category = Annotated[str, one_of(tuple(V.CATEGORIES)), enum(tuple(V.CATEGORIES))]
Priority = Annotated[str, one_of(V.PRIORITIES), enum(V.PRIORITIES)]


class WarrantyRegisterIn(Closed):
    project_id: Id


class ServiceRequestIn(Closed):
    """A problem the customer noticed after handover, in their words (portal, or staff on their behalf)."""

    project_id: Id
    category: Category
    description: Annotated[str, text(2000, min_len=10)]
    area: Annotated[str | None, optional_text(120)] = None
    space_id: Id | None = None
    noticed_on: CalendarDate | None = None
    related_request_id: Id | None = None


class ServiceStaffRequestIn(ServiceRequestIn):
    property_id: Id


class ServiceInformationRequestIn(Closed):
    question: Annotated[str, text(1000, min_len=10)]


class ServiceInformationIn(Closed):
    text: Annotated[str, text(2000, min_len=3)]


class ServiceTriageIn(Closed):
    category: Category | None = None
    priority: Priority = "NORMAL"
    space_id: Id | None = None
    note: Annotated[str | None, optional_text(2000)] = None  # internal


class ServiceAssessIn(Closed):
    outcome: Annotated[str, one_of(V.OUTCOMES), enum(V.OUTCOMES)]
    coverage_class: Annotated[str | None, optional_text(40)] = None
    basis_path: Annotated[str | None, optional_text(120)] = None
    service_class: Literal["CHARGEABLE", "NOT_SERVICEABLE"] | None = None
    explanation: Annotated[str, text(1000, min_len=10)]  # customer-safe
    internal_reason: Annotated[str, text(2000, min_len=10)]
    period_basis: Annotated[str | None, optional_text(1000)] = None  # internal


class ServiceAssignIn(Closed):
    owner_user_id: Id


class ServiceEvidenceIn(Closed):
    attachment_id: Id
    customer_visible: bool = False
    caption: Annotated[str | None, optional_text(160)] = None  # customer-safe when shown


class ServiceVisitIn(Closed):
    kind: Literal["INSPECTION", "SERVICE"]
    planned_on: CalendarDate
    customer_note: Annotated[str | None, optional_text(1000)] = None
    internal_note: Annotated[str | None, optional_text(2000)] = None


class ServiceVisitDoneIn(Closed):
    done_on: CalendarDate
    customer_note: Annotated[str | None, optional_text(1000)] = None
    internal_note: Annotated[str | None, optional_text(2000)] = None
    evidence: list[ServiceEvidenceIn] = Field(default_factory=list, max_length=12)


class ServiceReasonIn(Closed):
    reason: Annotated[str, text(1000, min_len=5)]


class ServiceResolveIn(Closed):
    summary: Annotated[str, text(1000, min_len=10)]  # customer-safe
    internal_note: Annotated[str | None, optional_text(2000)] = None
    evidence: list[ServiceEvidenceIn] = Field(default_factory=list, max_length=12)


class ServiceCloseIn(Closed):
    closure_code: Annotated[str, one_of(V.STAFF_CLOSURES), enum(V.STAFF_CLOSURES)]
    explanation: Annotated[str, text(1000, min_len=10)]  # customer-safe
    internal_reason: Annotated[str | None, optional_text(2000)] = None
    duplicate_of_id: Id | None = None


class ServiceWithdrawIn(Closed):
    reason: Annotated[str | None, optional_text(1000)] = None


class ServiceRejectIn(Closed):
    reason: Annotated[str, text(1000, min_len=10)]


class ServicePhotoIn(Closed):
    mime_type: ImageMime
    byte_size: Annotated[int, Field(ge=1, le=MAX_OBJECT_BYTES)]
    sha256: Sha256
    filename: Annotated[str | None, optional_text(255)] = None


class ServicePhotoContentIn(Closed):
    data_base64: Annotated[str, Field(min_length=1)]


class ServiceImageQuery(Query):
    variant: Literal["thumb", "mobile", "desktop"] = "mobile"


class ServiceListQuery(Query):
    status: Literal["OPEN", "CLOSED", "ALL", "MINE", "WAITING_FOR_CUSTOMER", "AWAITING_VERIFICATION",
                    "AWAITING_COMMERCIAL_AGREEMENT"] = "OPEN"  # fmt: skip
    project_id: Id | None = None
