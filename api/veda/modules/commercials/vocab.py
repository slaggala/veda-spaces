"""Project Commercials vocabularies (PCM). Every tuple also builds the column's CHECK constraint; migration 0210 builds
its constraints from these tuples through the models. Values are only ever added by a later migration, never renamed."""

from __future__ import annotations

# One currency: the quotation's (INR). A second currency is a schema change, never a silent default.
CURRENCIES = ("INR",)

BASELINE_KINDS = ("ORIGINAL", "VARIATION")
SCHEDULE_STATUSES = ("CURRENT", "SUPERSEDED")
# QUOTATION_MILESTONES: built at opening from the accepted base quotation's frozen milestones. REVISION: by staff.
SCHEDULE_SOURCES = ("QUOTATION_MILESTONES", "REVISION")

# Ways money reached Veda Spaces outside this system. Recording one is staff's statement that the money was received;
# it is never a confirmation from a bank or a payment provider.
PAYMENT_METHODS = ("BANK_TRANSFER", "UPI", "CHEQUE", "CASH", "OTHER")
METHOD_LABELS = {"BANK_TRANSFER": "Bank transfer", "UPI": "UPI", "CHEQUE": "Cheque", "CASH": "Cash", "OTHER": "Other"}

# Why a recorded payment was reversed (the correction; the payment row itself never changes).
REVERSAL_REASONS = ("RECORDED_IN_ERROR", "DUPLICATE", "PAYMENT_RETURNED", "OTHER")
REVERSAL_CUSTOMER_TEXT = {
    "RECORDED_IN_ERROR": "This payment was recorded in error and has been corrected.",
    "DUPLICATE": "This payment was recorded twice; the duplicate record has been corrected.",
    "PAYMENT_RETURNED": "This payment did not reach Veda Spaces (for example, a cheque that did not clear).",
    "OTHER": "This payment record was corrected by Veda Spaces.",
}

INVOICE_STATUSES = ("DRAFT", "ISSUED", "CANCELLED")
LIVE_INVOICE_STATUSES = ("DRAFT", "ISSUED")

# Derived instalment states (never stored): see position.py.
PAID, OVERDUE, PARTIALLY_PAID, DUE, UPCOMING = "PAID", "OVERDUE", "PARTIALLY_PAID", "DUE", "UPCOMING"
INSTALMENT_STATES = (PAID, OVERDUE, PARTIALLY_PAID, DUE, UPCOMING)
INSTALMENT_LABELS = {PAID: "Paid", OVERDUE: "Overdue", PARTIALLY_PAID: "Partly paid", DUE: "Due", UPCOMING: "Upcoming"}

# Derived schedule state: IN_BALANCE (adds up to the current value), REVISION_REQUIRED (an accepted variation changed
# the value), NONE (no schedule yet).
SCHEDULE_STATES = ("IN_BALANCE", "REVISION_REQUIRED", "NONE")

EVENTS = (
    "ACCOUNT_OPENED",
    "BASELINE_RECORDED",
    "SCHEDULE_CREATED",
    "SCHEDULE_REVISED",
    "PAYMENT_REQUESTED",
    "PAYMENT_RECORDED",
    "RECEIPT_ISSUED",
    "PAYMENT_REVERSED",
    "INVOICE_DRAFTED",
    "INVOICE_DISCARDED",
    "INVOICE_ISSUED",
    "INVOICE_CANCELLED",
    "DOCUMENT_REDACTED",
)

MAX_INSTALMENTS = 24
