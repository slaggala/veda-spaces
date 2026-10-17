"""Sales vocabulary (SCA): stage codes, the evidence that proves them, attention facts and acquisition channels.

Every code here is derived from records other modules own. None is stored on the lead, and none is a prediction: a
stage is the strongest fact on file, with the kind of record that proves it (its *basis*), so a stage claimed by a
staff status change and a stage proven by a quotation or acceptance record are always told apart.
"""

from __future__ import annotations

# Ordered: a later stage outranks an earlier one. The lead's CRM statuses map onto this ladder (LEAD_STATUS_STAGE).
STAGES: tuple[str, ...] = (
    "NEW",
    "CONTACTED",
    "CONSULTATION",
    "SITE_MEASUREMENT",
    "QUOTATION_PREPARATION",
    "QUOTATION_ISSUED",
    "CUSTOMER_CONSIDERING",
    "QUOTATION_DECLINED",
    "ACCEPTED",
    "WON",
    "LOST",
)
STAGE_LABELS: dict[str, str] = {
    "NEW": "New enquiry",
    "CONTACTED": "Contacted",
    "CONSULTATION": "Consultation held",
    "SITE_MEASUREMENT": "Site measurement",
    "QUOTATION_PREPARATION": "Quotation in preparation",
    "QUOTATION_ISSUED": "Quotation issued",
    "CUSTOMER_CONSIDERING": "Customer considering",
    "QUOTATION_DECLINED": "Quotation declined",
    "ACCEPTED": "Accepted by the customer",
    "WON": "Won",
    "LOST": "Lost",
}
# What proved the stage. LEAD_STATUS is a staff-recorded status (a claim, which the pipeline shows as such); the
# others are records written by the feature that owns the fact.
BASES: tuple[str, ...] = (
    "NONE",
    "LEAD_STATUS",
    "ACTIVITY",
    "MEASUREMENT_RECORD",
    "QUOTATION_RECORD",
    "PROPOSAL_RECORD",
)
BASIS_LABELS: dict[str, str] = {
    "NONE": "No evidence yet",
    "LEAD_STATUS": "Status recorded by staff",
    "ACTIVITY": "Logged activity",
    "MEASUREMENT_RECORD": "Measurement visit record",
    "QUOTATION_RECORD": "Quotation record",
    "PROPOSAL_RECORD": "Customer proposal record",
}
LEAD_STATUS_STAGE: dict[str, str] = {
    "NEW": "NEW",
    "CONTACTED": "CONTACTED",
    "SITE_VISIT": "SITE_MEASUREMENT",
    "QUOTATION_SENT": "QUOTATION_ISSUED",
    "NEGOTIATION": "CUSTOMER_CONSIDERING",
    "WON": "WON",
    "LOST": "LOST",
}
OPEN_STAGES: tuple[str, ...] = tuple(s for s in STAGES if s not in ("WON", "LOST"))

# Attention facts: deterministic, from dates and records only; never from browsing behaviour or inference.
ATTENTION: tuple[str, ...] = (
    "FOLLOW_UP_OVERDUE",
    "NO_FOLLOW_UP_PLANNED",
    "QUIET",
    "UNASSIGNED",
    "CUSTOMER_REQUEST_OPEN",
    "PROPOSAL_NOT_OPENED",
    "ACCEPTED_NOT_CLOSED",
    "DECLINED_STILL_OPEN",
)
ATTENTION_LABELS: dict[str, str] = {
    "FOLLOW_UP_OVERDUE": "Follow-up overdue",
    "NO_FOLLOW_UP_PLANNED": "No follow-up planned",
    "QUIET": "No activity for 14 days and nothing planned",
    "UNASSIGNED": "No owner",
    "CUSTOMER_REQUEST_OPEN": "Customer question or change request waiting",
    "PROPOSAL_NOT_OPENED": "Proposal link shared, not opened yet",
    "ACCEPTED_NOT_CLOSED": "Customer accepted: close the lead as won",
    "DECLINED_STILL_OPEN": "Quotation declined: record the outcome",
}
QUIET_DAYS = 14

# Acquisition channels, derived from the lead's source and attribution (``attribution.channel``). UNKNOWN is a valid
# answer and is never replaced by a guess.
CHANNELS: tuple[str, ...] = ("REFERRAL", "DIRECT", "SOCIAL", "PAID", "ORGANIC_SEARCH", "OTHER", "UNKNOWN")
CHANNEL_LABELS: dict[str, str] = {
    "REFERRAL": "Referral",
    "DIRECT": "Direct contact",
    "SOCIAL": "Social media",
    "PAID": "Paid campaign",
    "ORGANIC_SEARCH": "Organic search",
    "OTHER": "Other",
    "UNKNOWN": "Unknown",
}

# The site's anonymous funnel beacons (``analytics``): counts only, one per browser session per day.
EVENTS: tuple[str, ...] = ("site_visit", "estimator_started", "enquiry_started", "journey_viewed")
