"""Project lifecycle vocabularies (migration 0208_project_lifecycle). Frozen lists: every one is a CHECK constraint.

Stage codes are those of the lifecycle definition (``lifecycle.py``); the definition, not this module, says what each
stage means, in which order, and what is checked in it. Site-readiness categories and statuses reuse the Customer
Promise vocabulary (``mtq_commercial.customer_pack``) so a project's observation of an item is the same concept the
customer was promised, never a second one.
"""

from __future__ import annotations

from typing import get_args

from veda.modules.mtq_commercial import customer_pack as CP

PROJECT_STATUSES = ("ACTIVE", "HANDED_OVER")
SOURCES = ("ACCEPTED_QUOTATION",)  # PLB-01: the only way a project comes to exist

STAGES = (
    "BOOKED",
    "DESIGN_FINALISATION",
    "SCOPE_FROZEN",
    "SITE_READINESS",
    "PRODUCTION_READINESS",
    "IN_PRODUCTION",
    "READY_FOR_INSTALLATION",
    "INSTALLATION",
    "QUALITY_CHECK",
    "SNAGGING",
    "READY_FOR_HANDOVER",
    "HANDED_OVER",
)
STAGE_STATUSES = ("NOT_STARTED", "ACTIVE", "COMPLETED")

BASELINE_KINDS = ("ORIGINAL", "VARIATION")

# PLB-08: ownership concepts. Each is a responsibility on the project, never a company role.
RESPONSIBILITIES = ("COMMERCIAL", "DESIGN", "PROJECT", "SITE", "QUALITY", "HANDOVER", "MEMBER")
OWNER_RESPONSIBILITIES = tuple(r for r in RESPONSIBILITIES if r != "MEMBER")  # one active holder each

# PLB-06: a transition request and what became of it.
TRANSITION_OUTCOMES = ("REFUSED", "AWAITING_APPROVAL", "COMPLETED", "REJECTED", "WITHDRAWN")
TRANSITION_KINDS = ("STAGE", "HANDOVER")

CHECKLIST_STATES = ("OPEN", "DONE", "NOT_APPLICABLE")

# PLB-13/14.
MILESTONE_TYPES = (
    "DESIGN_SIGN_OFF",
    "SCOPE_FREEZE",
    "SITE_READY",
    "PRODUCTION_RELEASE",
    "PRODUCTION_COMPLETE",
    "DELIVERY_TO_SITE",
    "INSTALLATION_START",
    "INSTALLATION_COMPLETE",
    "QUALITY_CHECK_COMPLETE",
    "HANDOVER",
    "OTHER",
)
MILESTONE_STATES = ("NOT_STARTED", "PLANNED", "IN_PROGRESS", "BLOCKED", "COMPLETED", "CANCELLED", "NOT_APPLICABLE")
MILESTONE_CLOSED = ("COMPLETED", "CANCELLED", "NOT_APPLICABLE")

# PLB-20: who must act. Stored as a code, never only as free text.
RESPONSIBLE_PARTIES = ("CUSTOMER", "VEDA", "THIRD_PARTY", "TO_BE_CONFIRMED")

# PLB-18/19.
BLOCKER_CATEGORIES = (
    "DESIGN",
    "CUSTOMER_DECISION",
    "SITE",
    "ACCESS",
    "MATERIAL_SPECIFICATION",
    "COMMERCIAL",
    "PRODUCTION",
    "INSTALLATION",
    "QUALITY",
    "OTHER",
)
BLOCKER_SOURCES = ("STAFF", "SITE_READINESS", "QUALITY_CHECK", "SNAG", "VARIATION")
BLOCKER_IMPACTS = ("GATING", "INFORMATIONAL")
BLOCKER_STATUSES = ("OPEN", "IN_PROGRESS", "WAITING_CUSTOMER", "WAITING_VEDA", "RESOLVED", "CANCELLED")
BLOCKER_OPEN = ("OPEN", "IN_PROGRESS", "WAITING_CUSTOMER", "WAITING_VEDA")

# PLB-16/17: the Customer Promise readiness and responsibility vocabularies, plus VEDA_ACTION_REQUIRED (an operational
# observation the customer-facing promise never states).
READINESS_KINDS = ("READINESS", "RESPONSIBILITY")
READINESS_SOURCES = ("CUSTOMER_PROMISE", "STAFF")
READINESS_CATEGORIES = tuple(dict.fromkeys((*get_args(CP.ReadinessCategory), *get_args(CP.ResponsibilityCategory))))
READINESS_STATUSES = (*CP.READINESS_STATUSES[:3], "VEDA_ACTION_REQUIRED", *CP.READINESS_STATUSES[3:])
READINESS_SATISFIED = ("READY", "NOT_APPLICABLE")

# PLB-26.
QC_CATEGORIES = (
    "DIMENSIONS_AND_ALIGNMENT",
    "FINISH_AND_SURFACES",
    "HARDWARE_AND_OPERATION",
    "SERVICES_FITMENT",
    "CLEANLINESS_AND_PROTECTION",
    "OTHER",
)
QC_RESULTS = ("PASS", "FAIL", "NOT_APPLICABLE", "TO_BE_CONFIRMED")

# PLB-27.
SNAG_CATEGORIES = (
    "CARPENTRY",
    "FINISH",
    "HARDWARE",
    "ALIGNMENT",
    "DAMAGE",
    "SERVICES_FITMENT",
    "CLEANING",
    "MISSING_ITEM",
    "OTHER",
)
SNAG_STATUSES = ("OPEN", "IN_PROGRESS", "READY_FOR_RECHECK", "RESOLVED", "CLOSED")
SNAG_OPEN = ("OPEN", "IN_PROGRESS", "READY_FOR_RECHECK")

# PLB-12: the timeline. Codes, ids and states only: an event never carries free text, so it never needs erasing.
EVENTS = (
    "PROJECT_CREATED",
    "BASELINE_RECORDED",
    "VARIATION_ACCEPTED",
    "MEMBER_ASSIGNED",
    "OWNER_ASSIGNED",
    "MEMBER_REMOVED",
    "TRANSITION_REFUSED",
    "TRANSITION_AWAITING_APPROVAL",
    "TRANSITION_REJECTED",
    "TRANSITION_WITHDRAWN",
    "STAGE_COMPLETED",
    "STAGE_ENTERED",
    "CHECKLIST_ITEM_COMPLETED",
    "CHECKLIST_ITEM_NOT_APPLICABLE",
    "CHECKLIST_ITEM_REOPENED",
    "MILESTONE_ADDED",
    "MILESTONE_CHANGED",
    "BLOCKER_RAISED",
    "BLOCKER_UPDATED",
    "BLOCKER_RESOLVED",
    "BLOCKER_CANCELLED",
    "SITE_READINESS_ADDED",
    "SITE_READINESS_UPDATED",
    "QC_RECORDED",
    "SNAG_RAISED",
    "SNAG_UPDATED",
    "SNAG_RESOLVED",
    "SNAG_CLOSED",
    "HANDOVER_READY",
    "HANDED_OVER",
)
# PLB-10 "last material change": what moves a project's situation (not every note or reassignment).
MATERIAL_EVENTS = (
    "PROJECT_CREATED",
    "VARIATION_ACCEPTED",
    "TRANSITION_REFUSED",
    "STAGE_ENTERED",
    "BLOCKER_RAISED",
    "BLOCKER_RESOLVED",
    "SITE_READINESS_UPDATED",
    "QC_RECORDED",
    "SNAG_RAISED",
    "SNAG_RESOLVED",
    "HANDOVER_READY",
    "HANDED_OVER",
)
