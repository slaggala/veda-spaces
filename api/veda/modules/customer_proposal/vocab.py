"""Frozen CQX vocabularies (instruction VEDA-SPACES-CUSTOMER-QUOTATION-EXPERIENCE-END-TO-END).

One source for the CHECK constraints and the request schemas; migration 0205 carries its own copy, which a test keeps
equal to this module. Values are only ever added by a later migration, never renamed.
"""

from __future__ import annotations

# --- CQX-01 access grants ---------------------------------------------------------------------------------------------
# CREATED: shared with staff, never opened. ACTIVE: opened at least once. EXPIRED: past its own expiry. REVOKED: by staff,
# by rotation (REPLACED), by a newer version shared to the same recipient (SUPERSEDED) or by lead erasure.
GRANT_STATUSES = ("CREATED", "ACTIVE", "EXPIRED", "REVOKED")
LIVE_GRANT_STATUSES = ("CREATED", "ACTIVE")
# Who the link is for. Never a name, phone or email: the person is the lead's; the grant names only the role they play.
RECIPIENT_KINDS = ("PRIMARY_CUSTOMER", "CO_OWNER", "FAMILY_MEMBER", "OTHER")
REVOKE_REASONS = ("STAFF_REVOKED", "ROTATED", "SUPERSEDED", "LEAD_ERASED", "LEAD_CLOSED")

# --- CQX-06 optional items --------------------------------------------------------------------------------------------
SELECTION_STATES = ("NOT_SELECTED", "SELECTED", "DESELECTED", "REQUESTED_FOR_DISCUSSION")

# --- CQX-07 questions and change requests -----------------------------------------------------------------------------
REQUEST_KINDS = ("QUESTION", "CHANGE_REQUEST")
REQUEST_CATEGORIES = (
    "LINE_QUESTION",  # a question about one quotation line
    "GENERAL_QUESTION",  # a general proposal question
    "ADD_ITEM",
    "REMOVE_ITEM",
    "CHANGE_QUANTITY",
    "CHANGE_MATERIAL",
    "CHANGE_FINISH",
    "DISCUSS_PRICE",
)
QUESTION_CATEGORIES = ("LINE_QUESTION", "GENERAL_QUESTION")
REQUEST_STATUSES = ("OPEN", "UNDER_REVIEW", "NEEDS_CLARIFICATION", "ACCEPTED_FOR_REVISION", "DECLINED", "RESOLVED")
OPEN_REQUEST_STATUSES = ("OPEN", "UNDER_REVIEW", "NEEDS_CLARIFICATION")

# --- CQX-09 acknowledgements ------------------------------------------------------------------------------------------
# The customer-safe sections of a frozen document that can be acknowledged (each by its own digest).
ACK_SECTIONS = (
    "SCOPE",
    "ASSUMPTIONS",
    "EXCLUSIONS",
    "PAYMENT_MILESTONES",
    "WARRANTY",
    "SERVICE_SUPPORT",
    "TERMS",
    "VALIDITY",
)

# --- CQX-10 acceptance ------------------------------------------------------------------------------------------------
ACCEPTANCE_DECISIONS = ("ACCEPTED", "DECLINED")

# --- CQX-11 the proposal's own event log (append-only by service rule) ------------------------------------------------
PROPOSAL_EVENTS = (
    "SHARED",
    "VIEWED",
    "ROTATED",
    "REVOKED",
    "EXPIRED",
    "SELECTION_CHANGED",
    "QUESTION_SUBMITTED",
    "CHANGE_REQUESTED",
    "REQUEST_UPDATED",
    "REQUEST_LINKED",
    "ACKNOWLEDGED",
    "ACCEPTED",
    "DECLINED",
    "ACCEPTANCE_REFUSED",
    "ACCESS_REFUSED",
)
