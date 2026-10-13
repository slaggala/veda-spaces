"""Permission registry entries owned by MTQ B2-B4 (blueprint §15.2, least privilege per role).

Scope (blueprint §15.3): every row hangs off a lead; OWN means the actor owns the lead (assigned to or created by them)
or is assigned a measurement visit on it. ESTIMATOR and SALES_MANAGER work across leads (ALL). Approvals are separate
codes from the actions they approve, and the services refuse an approver acting on their own proposal where the
blueprint asks for four-eyes (discounts, discounted quotations).

No code here carries a sensitivity class: the permission table only admits the platform's four classes, none of which
fits commercial approval. Approvers are protected by role-level MFA instead (SALES_MANAGER, FOUNDER, ADMIN all require
MFA). Unit rates and pricing provenance need ``cost_estimate.rate.view``; SALES, DESIGNER and SURVEYOR never hold it.
"""

from veda.platform.rbac.registry_types import PermissionDef


def _p(code: str, name: str, description: str, requirement: str) -> PermissionDef:
    return PermissionDef(code, name, description, True, None, requirement)


PERMISSIONS: tuple[PermissionDef, ...] = (
    # B2 scope and BOQ
    _p("scope.read", "View scope", "View requirements and scope revisions, within scope", "SCOPE-001"),
    _p(
        "scope.edit",
        "Edit scope",
        "Seed, accept, reject, add and exclude requirements; draft and edit scope revisions",
        "SCOPE-002",
    ),  # fmt: skip
    _p("scope.confirm", "Confirm scope", "Confirm a scope revision against the verified measurements", "SCOPE-003"),
    _p("boq.read", "View BOQ", "View BOQ revisions, quantities and their derivations, within scope", "BOQ-001"),
    _p("boq.generate", "Generate BOQ", "Generate a BOQ revision from a confirmed scope", "BOQ-002"),
    _p("boq.override", "Override BOQ quantities", "Override a calculated quantity with a stated reason", "BOQ-003"),
    _p("boq.review", "Review BOQ", "Review a BOQ revision and seal it for pricing", "BOQ-004"),
)

_ALL_COMMERCIAL = {"FOUNDER": "A", "ADMIN": "A", "SALES_MANAGER": "A"}

MATRIX: dict[str, dict[str, str]] = {
    "scope.read": {**_ALL_COMMERCIAL, "ESTIMATOR": "A", "SALES": "O", "DESIGNER": "O"},
    "scope.edit": {**_ALL_COMMERCIAL, "ESTIMATOR": "A", "SALES": "O", "DESIGNER": "O"},
    "scope.confirm": {**_ALL_COMMERCIAL, "ESTIMATOR": "A", "DESIGNER": "O"},
    "boq.read": {**_ALL_COMMERCIAL, "ESTIMATOR": "A", "SALES": "O", "DESIGNER": "O"},
    "boq.generate": {**_ALL_COMMERCIAL, "ESTIMATOR": "A", "DESIGNER": "O"},
    "boq.override": {**_ALL_COMMERCIAL, "ESTIMATOR": "A"},
    "boq.review": {**_ALL_COMMERCIAL, "ESTIMATOR": "A"},
}
