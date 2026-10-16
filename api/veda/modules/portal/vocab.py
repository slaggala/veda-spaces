"""Customer Project Portal vocabularies (CPP). Every tuple also builds the column's CHECK constraint."""

from __future__ import annotations

from veda.modules.customer_proposal import vocab as CQX

ACCOUNT_STATUSES = ("ACTIVE", "DISABLED")
ACCESS_STATUSES = ("ACTIVE", "REVOKED")
# The customer's relationship to the enquiry: the CQX recipient kinds, so one vocabulary describes a customer everywhere.
RELATIONSHIPS = CQX.RECIPIENT_KINDS
ACCESS_REVOKE_REASONS = ("STAFF_REVOKED", "LEAD_ERASED")
SIGN_IN_PURPOSES = ("INVITATION", "SIGN_IN")
SESSION_END_REASONS = ("SIGNED_OUT", "ACCESS_REVOKED", "ACCOUNT_DISABLED", "LEAD_ERASED")

EVENTS = (
    "ACCESS_GRANTED",
    "ACCESS_REVOKED",
    "SIGN_IN_LINK_SENT",
    "SIGNED_IN",
    "SIGN_IN_REFUSED",
    "SIGNED_OUT",
    "ACCOUNT_ERASED",
)

# Customer-facing states the portal shows; never an internal state name.
INFORMATION, ACTION_REQUIRED, COMPLETED, UPCOMING, IN_PROGRESS, NOT_YET_AVAILABLE = (
    "INFORMATION",
    "ACTION_REQUIRED",
    "COMPLETED",
    "UPCOMING",
    "IN_PROGRESS",
    "NOT_YET_AVAILABLE",
)
STEP_STATES = (COMPLETED, IN_PROGRESS, ACTION_REQUIRED, UPCOMING, NOT_YET_AVAILABLE)

# Quotation versions a customer may see: those issued to them (never a draft, review or internal approval).
CUSTOMER_VISIBLE_QUOTATIONS = ("ISSUED", "ACCEPTED", "REJECTED", "EXPIRED", "SUPERSEDED")
