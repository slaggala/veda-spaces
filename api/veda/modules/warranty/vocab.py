"""Warranty and service vocabulary (WSV). Codes only; customer wording lives beside each code."""

from __future__ import annotations

# --- warranty coverage status (computed on read, never stored) ---------------------------------------------------------
ACTIVE, EXPIRED, NOT_STARTED, NOT_RECORDED = "ACTIVE", "EXPIRED", "NOT_STARTED", "NOT_RECORDED"
COVERAGE_STATUS_WORDS = {
    ACTIVE: "Active",
    EXPIRED: "Expired",
    NOT_STARTED: "Not yet active",
    NOT_RECORDED: "Not recorded in your portal",
}
TRIGGERS = ("HANDOVER",)  # the only start trigger an authoritative record can name today (WSV-D01)

# --- service requests --------------------------------------------------------------------------------------------------
REPORTED = "REPORTED"
INFORMATION_REQUESTED = "INFORMATION_REQUESTED"
TRIAGED = "TRIAGED"
ASSESSED = "ASSESSED"
IN_PROGRESS = "IN_PROGRESS"
AWAITING_COMMERCIAL_AGREEMENT = "AWAITING_COMMERCIAL_AGREEMENT"
RESOLVED = "RESOLVED"
CLOSED = "CLOSED"
REQUEST_STATES = (REPORTED, INFORMATION_REQUESTED, TRIAGED, ASSESSED, AWAITING_COMMERCIAL_AGREEMENT, IN_PROGRESS,
                  RESOLVED, CLOSED)  # fmt: skip
INFORMATION_FROM = (REPORTED, TRIAGED, ASSESSED, IN_PROGRESS)
WITHDRAWABLE = (REPORTED, INFORMATION_REQUESTED, TRIAGED, ASSESSED, AWAITING_COMMERCIAL_AGREEMENT)
OPEN_STATES = tuple(x for x in REQUEST_STATES if x != CLOSED)
CHANNELS = ("PORTAL", "STAFF")
PRIORITIES = ("HIGH", "NORMAL", "LOW")

# What kind of problem, in the customer's terms: never a finding about cause or responsibility.
CATEGORIES = {
    "DOOR_OR_DRAWER": "A door, shutter or drawer",
    "HARDWARE": "Handles, hinges, channels or locks",
    "SURFACE_OR_FINISH": "A surface, edge or finish",
    "ALIGNMENT_OR_GAP": "Alignment, gaps or something loose",
    "WATER_OR_DAMP": "Water, damp or swelling",
    "LIGHT_OR_ELECTRICAL_FITTING": "A light or electrical fitting we installed",
    "APPLIANCE": "An appliance",
    "OTHER": "Something else",
}

# Coverage decision (explicit, by an assessor; never inferred from the customer's words or photos).
COVERED = "COVERED"
NOT_COVERED = "NOT_COVERED"
OUTSIDE_WARRANTY_PERIOD = "OUTSIDE_WARRANTY_PERIOD"
INSPECTION_REQUIRED = "INSPECTION_REQUIRED"
INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
MANUFACTURER_WARRANTY = "MANUFACTURER_WARRANTY"
OUTCOMES = (COVERED, NOT_COVERED, OUTSIDE_WARRANTY_PERIOD, MANUFACTURER_WARRANTY, INSPECTION_REQUIRED,
            INSUFFICIENT_INFORMATION)  # fmt: skip
# What a coverage decision rests on. A manufacturer note, an exclusion or estimator copy is never a basis for COVERED.
BASES = ("COVERAGE_CLASS", "WARRANTY_STATEMENT", "SERVICE_SUPPORT_STATEMENT", "EXCLUSION", "MANUFACTURER_NOTE",
         "ASSESSMENT")  # fmt: skip
COVERED_BASES = ("COVERAGE_CLASS", "WARRANTY_STATEMENT", "SERVICE_SUPPORT_STATEMENT")
OUTCOME_WORDS = {
    COVERED: "Covered by your warranty",
    NOT_COVERED: "Not covered by your warranty",
    OUTSIDE_WARRANTY_PERIOD: "Outside the warranty period",
    INSPECTION_REQUIRED: "We need to inspect it first",
    INSUFFICIENT_INFORMATION: "We need more information",
    MANUFACTURER_WARRANTY: "Covered by the manufacturer's warranty",
}
WARRANTY, CHARGEABLE, NOT_SERVICEABLE = "WARRANTY", "CHARGEABLE", "NOT_SERVICEABLE"
SERVICE_CLASSES = (WARRANTY, CHARGEABLE, NOT_SERVICEABLE)

CLOSURE_CODES = ("SERVICED", "DUPLICATE", "NOT_COVERED", "REFERRED_TO_MANUFACTURER", "CHARGEABLE_NOT_AGREED",
                 "CUSTOMER_WITHDREW", "CANNOT_SERVICE")  # fmt: skip
STAFF_CLOSURES = ("DUPLICATE", "NOT_COVERED", "REFERRED_TO_MANUFACTURER", "CHARGEABLE_NOT_AGREED", "CANNOT_SERVICE")
VERIFIED_BY = ("CUSTOMER", "STAFF")

VISIT_KINDS = ("INSPECTION", "SERVICE")
VISIT_STATES = ("PLANNED", "DONE", "CANCELLED")

NOTE_KINDS = ("INFORMATION_REQUEST", "CUSTOMER_INFORMATION", "INTERNAL", "REJECTION", "REOPEN", "CLOSURE",
              "WITHDRAWAL")  # fmt: skip
NOTE_VISIBILITIES = ("CUSTOMER", "INTERNAL")

MAX_CUSTOMER_PHOTOS = 6
MAX_OPEN_PER_ACCOUNT = 10  # per account and project
MAX_REJECTIONS = 2

# The immutable request timeline. Codes, ids, states and digests only: free text lives on the request and visit rows
# (erasable), never in an event.
EVENTS = (
    "SUBMITTED",
    "INFORMATION_REQUESTED",
    "INFORMATION_ADDED",
    "TRIAGED",
    "ASSESSED",
    "ASSIGNED",
    "VISIT_PLANNED",
    "VISIT_DONE",
    "VISIT_CANCELLED",
    "PHOTO_ADDED",
    "EVIDENCE_ADDED",
    "RESOLVED",
    "RESOLUTION_REJECTED",
    "VERIFIED",
    "CLOSED",
    "WITHDRAWN",
    "REOPENED",
    "NOTE_ADDED",
)
