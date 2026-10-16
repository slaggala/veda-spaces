"""Project Commercials capabilities (PCM-020). Customers hold none of these; they read through the portal session.

Every code supports scope through the account's lead (``mtq.scope``): ALL reaches every account; OWN reaches an account
whose lead the actor owns (assigned to or created by them) or has a measurement visit on.

Default grants (owner decision PCM-D01, 2026-10-16; migration ``0211_accountant_role``):

- ACCOUNTANT (the operational financial role; MFA required): every code, ALL. It opens commercial records, manages
  payment schedules and requests, records payments (issuing their receipts), reverses payments recorded in error,
  issues invoices and reads the commercial history. Reversal stays four-eyes: never by the person who recorded the
  payment, so a reversal needs a second accountant or the founder.
- FOUNDER (the business owner): every code, for oversight.
- SALES_MANAGER: ``commercials.view`` only. Its earlier grant of every code was a temporary mapping (decision log 44);
  the five mutation codes are withdrawn by ``0211``. It still sees the position of the projects it sells.
- ADMIN, SALES, ESTIMATOR, DESIGNER, SURVEYOR: nothing. ADMIN administers accounts; the escalation guard refuses an
  administrator who lacks a code the managed account holds, so an accountant's account is managed by the founder. A
  person outside these roles who needs a capability is granted that code individually (``user.permission.manage``).
- No role holds a ``project.*`` code because it holds a commercial one: the ACCOUNTANT role has no execution, quality
  or handover capability.
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
MATRIX: dict[str, dict[str, str]] = {
    code: {"FOUNDER": "A", "ACCOUNTANT": "A", **({"SALES_MANAGER": "A"} if code == "commercials.view" else {})}
    for code in CODES
}
# What 0211 withdrew from SALES_MANAGER (the temporary mapping of decision log 44).
WITHDRAWN_FROM_SALES_MANAGER = tuple(code for code in CODES if code != "commercials.view")
