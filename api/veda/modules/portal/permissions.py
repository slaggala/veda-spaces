"""Staff permissions of the Customer Project Portal (CPP). Customers hold none of these.

A customer reaches the portal only through a portal session, and reaches data only through an ACTIVE ``portal_access``
row that staff granted for one enquiry (lead). Granting access lets a customer see what that enquiry's issued
quotations already show them, so the grants mirror the CQX sharing codes (``proposal.share`` /
``proposal.access.revoke``): the same people who may share a proposal link may give portal access.

Scope: every access row hangs off a lead; OWN means the actor owns the lead or is assigned a visit on it.
"""

from veda.platform.rbac.registry_types import PermissionDef


def _p(code: str, name: str, description: str, requirement: str) -> PermissionDef:
    return PermissionDef(code, name, description, True, None, requirement)


PERMISSIONS: tuple[PermissionDef, ...] = (
    _p("portal.access.view", "View customer portal access",
       "See who has customer portal access to an enquiry, within scope", "CPP-002"),
    _p("portal.access.grant", "Give customer portal access",
       "Invite a customer to the portal for an enquiry (sends a sign-in link), within scope", "CPP-002"),
    _p("portal.access.revoke", "Revoke customer portal access",
       "End a customer's portal access to an enquiry at once, within scope", "CPP-002"),
)  # fmt: skip

CODES = tuple(p.code for p in PERMISSIONS)
_ALL = {"FOUNDER": "A", "ADMIN": "A", "SALES_MANAGER": "A"}
MATRIX: dict[str, dict[str, str]] = {code: {**_ALL, "SALES": "O"} for code in CODES}
