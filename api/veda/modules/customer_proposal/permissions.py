"""Staff permissions of the customer quotation experience (CQX). Customers hold none of these.

A customer reaches a proposal only through an access grant (an opaque link), never through staff RBAC, and a grant
reaches exactly one quotation version. Staff codes are separate from the quotation codes they sit beside, so a role can
share or review proposals without preparing, pricing or approving quotations. None of them reveals internal pricing:
the preview is the customer projection, and requests and evidence carry no rate, margin or lineage. Variations are
raised with the existing ``quotation.variation.create``.

Scope (blueprint §15.3): every row hangs off a lead; OWN means the actor owns the lead or is assigned a visit on it.
"""

from veda.platform.rbac.registry_types import PermissionDef


def _p(code: str, name: str, description: str, requirement: str) -> PermissionDef:
    return PermissionDef(code, name, description, True, None, requirement)


PERMISSIONS: tuple[PermissionDef, ...] = (
    _p("proposal.preview", "Preview proposals",
       "See a quotation exactly as its customer sees it (customer-safe projection), within scope", "CQX-001"),
    _p("proposal.share", "Share proposals",
       "Create, rotate and list secure proposal links for issued quotations, within scope", "CQX-002"),
    _p("proposal.access.revoke", "Revoke proposal links", "Revoke a secure proposal link at once, within scope",
       "CQX-003"),
    _p("proposal.request.review", "Review customer requests",
       "Read and answer customer questions, change requests and optional-item choices, within scope", "CQX-004"),
    _p("proposal.acceptance.review", "Review acceptance evidence",
       "Read the evidence of a customer's digital acceptance or decline, within scope", "CQX-005"),
)  # fmt: skip

_ALL = {"FOUNDER": "A", "ADMIN": "A", "SALES_MANAGER": "A"}

MATRIX: dict[str, dict[str, str]] = {
    "proposal.preview": {**_ALL, "ESTIMATOR": "A", "SALES": "O"},
    "proposal.share": {**_ALL, "SALES": "O"},
    "proposal.access.revoke": {**_ALL, "SALES": "O"},
    "proposal.request.review": {**_ALL, "ESTIMATOR": "A", "SALES": "O"},
    "proposal.acceptance.review": {**_ALL, "SALES": "O"},
}
