"""Sales & Customer Acquisition capabilities (SCA-001). Customers hold none.

``sales.pipeline.view`` is scoped like the lead's own read: ALL reaches every live lead, OWN the leads assigned to or
created by the actor. The funnel is an aggregate over every lead and is granted whole or not at all; the demo is a
synthetic page with no data in it. Default grants follow the sales roles: SALES_MANAGER and the founder see the whole
pipeline and the funnel; SALES sees its own pipeline and the demo; ACCOUNTANT, DESIGNER, SURVEYOR and ESTIMATOR hold
nothing (a commercial or site role is not a sales role); ADMIN mirrors the working roles.
"""

from veda.platform.rbac.registry_types import PermissionDef

PERMISSIONS: tuple[PermissionDef, ...] = (
    PermissionDef("sales.pipeline.view", "View the sales pipeline", "See leads with their evidence-derived sales stage, "
                  "consultation, measurement, quotation and proposal facts, follow-up state and acquisition channel",
                  True, None, "SCA-001"),
    PermissionDef("sales.funnel.view", "View the acquisition funnel", "See funnel counts from site visit to acceptance, "
                  "by stage, channel and lost reason, over every lead", False, None, "SCA-002"),
    PermissionDef("sales.demo.view", "View the customer-journey demo", "Open the synthetic, read-only demonstration of "
                  "the customer's proposal and project portal experience", False, None, "SCA-003"),
)  # fmt: skip

CODES = tuple(p.code for p in PERMISSIONS)
MATRIX: dict[str, dict[str, str]] = {
    "sales.pipeline.view": {"FOUNDER": "A", "ADMIN": "A", "SALES": "O", "SALES_MANAGER": "A"},
    "sales.funnel.view": {"FOUNDER": "✓", "ADMIN": "✓", "SALES_MANAGER": "✓"},
    "sales.demo.view": {"FOUNDER": "✓", "ADMIN": "✓", "SALES": "✓", "SALES_MANAGER": "✓"},
}
