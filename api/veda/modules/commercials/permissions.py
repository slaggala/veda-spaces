"""Project Commercials capabilities (PCM-020). Customers hold none of these; they read through the portal session.

Every code supports scope through the account's lead (``mtq.scope``): ALL reaches every account; OWN reaches an account
whose lead the actor owns (assigned to or created by them) or has a measurement visit on.

Default grants, and why they are the minimum safe mapping:

- FOUNDER (the business owner): every code.
- SALES_MANAGER (commercial approvals and quotation release; MFA required): every code. It already approves
  discounts and issues the quotations these records start from, and is the only working role that signs in with MFA.
  Reversal is four-eyes: never by the person who recorded the payment.
- ADMIN, SALES, ESTIMATOR, DESIGNER, SURVEYOR: nothing. No role is given money it does not handle. ADMIN administers
  accounts; the escalation guard needs ADMIN to hold whatever the working roles it manages hold, and none of them holds
  a ``commercials.*`` code. A consultant (SALES) or an accounts person who needs a capability is granted that code
  individually (``user.permission.manage``), at OWN or ALL scope.
"""

from veda.platform.rbac.registry_types import PermissionDef


def _p(code: str, name: str, description: str, requirement: str) -> PermissionDef:
    return PermissionDef(code, name, description, True, None, requirement)


PERMISSIONS: tuple[PermissionDef, ...] = (
    _p("commercials.view", "View project commercials", "See a project's commercial value, payment schedule, recorded "
       "payments, invoices, receipts and outstanding balance, within scope", "PCM-020"),
    _p("commercials.schedule.manage", "Manage payment schedules", "Open the commercial record of an accepted quotation, "
       "revise its payment schedule and request instalments from the customer", "PCM-021"),
    _p("commercials.payment.record", "Record payments", "Record a payment the customer made outside the system (bank "
       "transfer, UPI, cheque, cash); issues its receipt", "PCM-022"),
    _p("commercials.payment.reverse", "Reverse payments", "Reverse a payment recorded in error, with a reason (never one "
       "you recorded)", "PCM-023"),
    _p("commercials.invoice.issue", "Issue invoices", "Draft, issue and cancel customer invoices for instalments",
       "PCM-024"),
    _p("commercials.audit.view", "View commercial history", "See the full commercial history: who did what, when and "
       "why", "PCM-025"),
)  # fmt: skip

CODES = tuple(p.code for p in PERMISSIONS)
MATRIX: dict[str, dict[str, str]] = {code: {"FOUNDER": "A", "SALES_MANAGER": "A"} for code in CODES}
