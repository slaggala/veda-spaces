"""Project lifecycle request bodies and queries. Closed: an unknown field is refused (422 UNKNOWN_FIELD)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, WithJsonSchema
from pydantic_core import PydanticCustomError

from veda.kernel.dto import CalendarDate, Closed, Id, Query, optional_text, text

from . import vocab as V


def one_of(values: tuple[str, ...]):
    """A code from a vocabulary tuple (the same tuple the CHECK constraint is built from); 422 INVALID_CHOICE."""

    def check(value: str) -> str:
        if value not in values:
            raise PydanticCustomError("INVALID_CHOICE", "Not one of the allowed values.")
        return value

    return AfterValidator(check)


def enum(values: tuple[str, ...]) -> WithJsonSchema:
    return WithJsonSchema({"type": "string", "enum": list(values)})


Stage = Annotated[str, one_of(V.STAGES), enum(V.STAGES)]
Responsibility = Annotated[str, one_of(V.RESPONSIBILITIES), enum(V.RESPONSIBILITIES)]
Party = Annotated[str, one_of(V.RESPONSIBLE_PARTIES), enum(V.RESPONSIBLE_PARTIES)]
Reason = Annotated[str, text(1000, min_len=5)]
Note = Annotated[str | None, optional_text(1000)]
Ref = Annotated[str | None, optional_text(200)]


class CreateIn(Closed):
    quotation_id: Id
    property_id: Id


class MemberIn(Closed):
    user_id: Id
    responsibility: Responsibility
    reason: Annotated[str | None, optional_text(500)] = None  # required when it replaces an owner


class RemoveIn(Closed):
    reason: Annotated[str, text(500, min_len=5)]


class TransitionIn(Closed):
    to_stage: Stage
    reason: Note = None


class DecisionIn(Closed):
    reason: Note = None


class ReasonIn(Closed):
    reason: Reason


class HandoverIn(Closed):
    handover_on: CalendarDate
    acknowledgement_reference: Ref = None
    evidence_attachment_id: Id | None = None
    observations: Annotated[str | None, optional_text(2000)] = None
    reason: Note = None


class ChecklistIn(Closed):
    state: Literal["DONE", "NOT_APPLICABLE"]
    note: Note = None
    not_applicable_reason: Note = None
    evidence_attachment_id: Id | None = None
    evidence_reference: Ref = None


class MilestoneIn(Closed):
    milestone_code: Annotated[str, one_of(V.MILESTONE_TYPES), enum(V.MILESTONE_TYPES)]
    label: Annotated[str, text(120, min_len=1)]
    customer_label: Annotated[str | None, optional_text(120)] = None
    description: Note = None
    stage_code: Stage
    planned_date: CalendarDate | None = None
    customer_promised_date: CalendarDate | None = None
    depends_on_milestone_id: Id | None = None
    owner_responsibility: Responsibility | None = None


class MilestonePatch(Closed):
    label: Annotated[str | None, optional_text(120)] = None
    customer_label: Annotated[str | None, optional_text(120)] = None
    description: Note = None
    planned_date: CalendarDate | None = None
    customer_promised_date: CalendarDate | None = None
    status: Literal["NOT_STARTED", "PLANNED", "IN_PROGRESS", "BLOCKED", "CANCELLED", "NOT_APPLICABLE"] | None = None
    status_reason: Annotated[str | None, optional_text(500)] = None
    depends_on_milestone_id: Id | None = None
    owner_responsibility: Responsibility | None = None


class MilestoneCompleteIn(Closed):
    actual_date: CalendarDate
    evidence_attachment_id: Id | None = None
    evidence_reference: Ref = None


class BlockerIn(Closed):
    category: Annotated[str, one_of(V.BLOCKER_CATEGORIES), enum(V.BLOCKER_CATEGORIES)]
    impact: Annotated[str, one_of(V.BLOCKER_IMPACTS), enum(V.BLOCKER_IMPACTS)]
    title: Annotated[str, text(160, min_len=3)]
    description: Annotated[str | None, optional_text(2000)] = None
    customer_action: Annotated[str | None, optional_text(300)] = None
    responsible_party: Party
    assigned_to: Id | None = None
    target_date: CalendarDate | None = None
    blocks_stage_code: Stage | None = None
    related_milestone_id: Id | None = None
    related_checklist_item_id: Id | None = None
    related_site_readiness_id: Id | None = None
    related_quotation_id: Id | None = None
    related_work_package_id: Id | None = None
    customer_summary: Annotated[str | None, optional_text(300)] = None


class BlockerPatch(Closed):
    status: Literal["OPEN", "IN_PROGRESS", "WAITING_CUSTOMER", "WAITING_VEDA"] | None = None
    description: Annotated[str | None, optional_text(2000)] = None
    customer_action: Annotated[str | None, optional_text(300)] = None
    responsible_party: Party | None = None
    assigned_to: Id | None = None
    target_date: CalendarDate | None = None
    customer_summary: Annotated[str | None, optional_text(300)] = None


class ResolutionIn(Closed):
    resolution: Reason


class ReadinessIn(Closed):
    kind: Annotated[str, one_of(V.READINESS_KINDS), enum(V.READINESS_KINDS)]
    category: Annotated[str, one_of(V.READINESS_CATEGORIES), enum(V.READINESS_CATEGORIES)]
    label: Annotated[str, text(160, min_len=3)]


class ReadinessPatch(Closed):
    status: Annotated[str, one_of(V.READINESS_STATUSES), enum(V.READINESS_STATUSES)] | None = None
    responsible_party: Party | None = None
    action: Annotated[str | None, optional_text(500)] = None
    customer_action: Annotated[str | None, optional_text(300)] = None
    due_date: CalendarDate | None = None
    note: Note = None
    evidence_attachment_id: Id | None = None
    evidence_reference: Ref = None


class QcIn(Closed):
    category: Annotated[str, one_of(V.QC_CATEGORIES), enum(V.QC_CATEGORIES)]
    result: Annotated[str, one_of(V.QC_RESULTS), enum(V.QC_RESULTS)]
    space_id: Id | None = None
    observation: Note = None
    evidence_attachment_id: Id | None = None
    evidence_reference: Ref = None
    recheck_of_id: Id | None = None
    qc_point_id: Id | None = None
    work_package_id: Id | None = None


class SnagIn(Closed):
    category: Annotated[str, one_of(V.SNAG_CATEGORIES), enum(V.SNAG_CATEGORIES)]
    customer_title: Annotated[str, text(160, min_len=3)]
    description: Annotated[str | None, optional_text(2000)] = None
    space_id: Id | None = None
    item_reference: Ref = None
    is_blocking: bool = True
    owner_user_id: Id | None = None
    responsible_party: Party = "VEDA"
    target_date: CalendarDate | None = None
    qc_check_id: Id | None = None
    evidence_attachment_id: Id | None = None
    evidence_reference: Ref = None
    work_package_id: Id | None = None
    priority: Annotated[str, one_of(V.SNAG_PRIORITIES), enum(V.SNAG_PRIORITIES)] = "NORMAL"
    customer_visible: bool = False


class SnagPatch(Closed):
    description: Annotated[str | None, optional_text(2000)] = None
    owner_user_id: Id | None = None
    responsible_party: Party | None = None
    target_date: CalendarDate | None = None
    evidence_attachment_id: Id | None = None
    evidence_reference: Ref = None
    work_package_id: Id | None = None
    priority: Annotated[str, one_of(V.SNAG_PRIORITIES), enum(V.SNAG_PRIORITIES)] | None = None
    customer_visible: bool | None = None


class SnagClassificationIn(Closed):
    is_blocking: bool
    reason: Annotated[str, text(500, min_len=5)]


class SnagStatusIn(Closed):
    status: Literal["IN_PROGRESS", "READY_FOR_RECHECK", "RESOLVED", "CLOSED"]
    note: Note = None
    closure_code: Annotated[str, one_of(V.SNAG_CLOSED_WITHOUT_FIX), enum(V.SNAG_CLOSED_WITHOUT_FIX)] | None = None
    evidence_attachment_id: Id | None = None  # the fix's evidence (READY_FOR_RECHECK)


# --- PEX: work packages, the QC plan, customer reports, the handover package ------------------------------------------
class WorkPackageIn(Closed):
    stage_code: Stage
    title: Annotated[str, text(160, min_len=3)]
    description: Annotated[str | None, optional_text(2000)] = None
    customer_label: Annotated[str | None, optional_text(120)] = None
    customer_visible: bool = False
    space_id: Id | None = None
    owner_user_id: Id | None = None
    depends_on_id: Id | None = None
    planned_start: CalendarDate | None = None
    planned_finish: CalendarDate | None = None


class WorkPackagePatch(Closed):
    title: Annotated[str | None, optional_text(160)] = None
    description: Annotated[str | None, optional_text(2000)] = None
    customer_label: Annotated[str | None, optional_text(120)] = None
    customer_visible: bool | None = None
    space_id: Id | None = None
    owner_user_id: Id | None = None
    depends_on_id: Id | None = None
    planned_start: CalendarDate | None = None
    planned_finish: CalendarDate | None = None
    reason: Note = None  # required when a planned date already set changes (a replan)


class WorkStartIn(Closed):
    actual_start: CalendarDate


class WorkCompleteIn(Closed):
    actual_finish: CalendarDate
    note: Note = None
    evidence_attachment_id: Id | None = None
    evidence_reference: Ref = None


class QcPointIn(Closed):
    category: Annotated[str, one_of(V.QC_CATEGORIES), enum(V.QC_CATEGORIES)]
    label: Annotated[str, text(160, min_len=3)]
    space_id: Id | None = None
    work_package_id: Id | None = None
    evidence_required: bool = False


class ProjectReportIn(Closed):
    """An issue in the customer's own words (the portal, or staff recording it on the customer's behalf)."""

    description: Annotated[str, text(2000, min_len=10)]
    area: Annotated[str | None, optional_text(120)] = None


class TriageIn(Closed):
    outcome: Literal["NEW_SNAG", "EXISTING_SNAG", "DECLINED"]
    snag: SnagIn | None = None
    snag_id: Id | None = None
    decline_code: Annotated[str, one_of(V.REPORT_DECLINE_CODES), enum(V.REPORT_DECLINE_CODES)] | None = None
    response: Annotated[str | None, optional_text(500)] = None  # customer-safe words


class HandoverAcknowledgementIn(Closed):
    package_id: Id
    content_sha256: Annotated[str, text(64, min_len=64)]


VIEWS = ("all", "mine", "blocked", "action_required", "site_readiness", "installation", "handover")


class ListQuery(Query):
    view: Annotated[str, one_of(VIEWS), enum(VIEWS)] = "all"
    q: Annotated[str | None, optional_text(40)] = None
    stage: Stage | None = None
    owner: Id | None = None
    blocker: Literal["gating", "any", "none"] | None = None
    readiness: Literal["ready", "blocked", "awaiting_approval"] | None = None
    milestone: Literal["overdue", "planned", "none"] | None = None
    handover: Literal["ready", "not_ready"] | None = None


class EvaluateQuery(Query):
    to_stage: Stage | None = None
