"""Warranty and after-sales service capabilities (WSV-020). Customers hold none: they act through the portal session.

Every code supports scope. **ALL** reaches every entitlement and request; **OWN** reaches a request whose owner is the
actor, or a request (or entitlement) of a project whose team the actor is an active member of.

Default grants: FOUNDER (the business owner) holds every code, ALL. No other role holds one by default: not ACCOUNTANT
(commercial records are not customer care), not SALES_MANAGER, not ADMIN (it mirrors the working roles only). The
customer-care, service and quality personas have no repository role; their holders are granted the codes individually
(``user.permission.manage``). Verification is independent: never by the person who resolved the request.
"""

from veda.platform.rbac.registry_types import PermissionDef


def _p(code: str, name: str, description: str, requirement: str) -> PermissionDef:
    return PermissionDef(code, name, description, True, None, requirement)


PERMISSIONS: tuple[PermissionDef, ...] = (
    _p("warranty.view", "View warranties", "See warranty entitlements: what was promised at handover, its sources and "
       "coverage status", "WSV-001"),
    _p("warranty.manage", "Register warranties", "Register the warranty entitlement of a project handed over while the "
       "warranty capability was off (from its handover; idempotent)", "WSV-002"),
    _p("warranty.service.view", "View service requests", "See post-handover service requests, their evidence and "
       "history", "WSV-010"),
    _p("warranty.service.triage", "Triage service requests", "Record a request for a customer, ask the customer for "
       "information and triage requests", "WSV-011"),
    _p("warranty.service.assess", "Decide warranty coverage", "Record the coverage decision of a request (with its "
       "source and a customer explanation) and close a request without service", "WSV-012"),
    _p("warranty.service.assign", "Assign service requests", "Assign or reassign the owner of a request", "WSV-013"),
    _p("warranty.service.resolve", "Resolve service requests", "Plan and record visits and actions, attach evidence and "
       "record the resolution of a request you own", "WSV-014"),
    _p("warranty.service.verify", "Verify service resolutions", "Verify a resolution (never your own) and reopen a "
       "closed request, with a reason", "WSV-015"),
    _p("warranty.service.audit", "View service history", "See the full history of a request: who did what, when and "
       "why, including internal notes", "WSV-016"),
)  # fmt: skip

CODES = tuple(p.code for p in PERMISSIONS)
MATRIX: dict[str, dict[str, str]] = {code: {"FOUNDER": "A"} for code in CODES}
