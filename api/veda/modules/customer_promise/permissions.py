"""Customer Promise capabilities (CPA-15). Capabilities, not people: a persona is a set of these codes.

Separate duties: drafting, editing (ordinary sections, contacts, warranty, payment safety), submitting, reviewing
(ordinary and sensitive sections), approving and publishing are different codes, and the service refuses anyone who
saved a section or submitted the version from reviewing or approving it (four-eyes, every section). Approving,
publishing and reviewing sensitive sections are ACCESS_CONTROL: they take effect only in an MFA-verified session.
None of these codes is lead-scoped (the pack is one company-wide document) and none reveals a customer, a lead or a
quotation's content: usage is shown as counts.

Default grants follow the existing roles only where their meaning fits (repository roles, not an invented org chart):

- FOUNDER (the business owner): every code.
- SALES_MANAGER (commercial approvals): the commercial author and ordinary reviewer: view, draft, edit ordinary
  sections, submit, review ordinary sections, preview, history.
- ADMIN (operations administrator of the platform): view only, as for the catalog.
- SALES, ESTIMATOR, DESIGNER, SURVEYOR: nothing.

The operations, catalogue/product, customer-experience and legal/control personas have no repository role: their
holders are granted the codes individually (user.permission.manage), as catalog duties are. See
docs/implementation/customer-promise/CPA-persona-capability-map.md.
"""

from veda.platform.rbac.registry_types import PermissionDef


def _p(code: str, name: str, description: str, requirement: str, sensitivity: str | None = None) -> PermissionDef:
    return PermissionDef(code, name, description, False, sensitivity, requirement)


PERMISSIONS: tuple[PermissionDef, ...] = (
    _p("customer_promise.view", "View the Customer Promise",
       "See the published Customer Promise Pack, drafts, versions, reviews and completeness", "CPA-001"),
    _p("customer_promise.draft.create", "Start Customer Promise drafts",
       "Start a new draft version (from the published pack or, as a rollback, from an earlier approved version) and "
       "discard an unwanted draft", "CPA-002"),
    _p("customer_promise.edit", "Edit Customer Promise sections",
       "Edit inclusions, customer responsibilities, site readiness, site-dependent work, handover, care and next steps "
       "in a draft", "CPA-003"),
    _p("customer_promise.contacts.edit", "Edit Customer Promise contacts",
       "Edit the Veda Spaces business contacts, support and escalation path and service guidance in a draft", "CPA-004"),
    _p("customer_promise.warranty.edit", "Edit Customer Promise warranty",
       "Edit the manufacturer-warranty note and the warranty exclusions in a draft", "CPA-005"),
    _p("customer_promise.payment_safety.edit", "Edit Customer Promise payment safety",
       "Edit the payment-safety wording in a draft (never account details)", "CPA-006"),
    _p("customer_promise.submit", "Submit Customer Promise drafts", "Submit a draft for review", "CPA-007"),
    _p("customer_promise.review", "Review Customer Promise sections",
       "Approve or request changes to ordinary sections of a submitted version (never one you saved or submitted)",
       "CPA-008"),
    _p("customer_promise.review.sensitive", "Review sensitive Customer Promise sections",
       "Approve or request changes to customer responsibilities, site-dependent work, warranty, warranty exclusions "
       "and payment safety (never one you saved or submitted)", "CPA-009", "ACCESS_CONTROL"),
    _p("customer_promise.approve", "Approve Customer Promise versions",
       "Approve a fully reviewed version for publication (never one you contributed to)", "CPA-010", "ACCESS_CONTROL"),
    _p("customer_promise.publish", "Publish Customer Promise versions",
       "Publish an approved version (the published one is superseded, never deleted)", "CPA-011", "ACCESS_CONTROL"),
    _p("customer_promise.preview", "Preview the Customer Promise as a customer",
       "See a version exactly as customers would (marked PREVIEW / NOT PUBLISHED)", "CPA-012"),
    _p("customer_promise.audit.read", "View Customer Promise history",
       "See the full event history of every version (who did what, when, with digests)", "CPA-013"),
)  # fmt: skip

_COMMERCIAL = ("customer_promise.view", "customer_promise.draft.create", "customer_promise.edit",
               "customer_promise.submit", "customer_promise.review", "customer_promise.preview",
               "customer_promise.audit.read")  # fmt: skip

MATRIX: dict[str, dict[str, str]] = {
    p.code: {"FOUNDER": "✓", **({"SALES_MANAGER": "✓"} if p.code in _COMMERCIAL else {}),
             **({"ADMIN": "✓"} if p.code == "customer_promise.view" else {})}
    for p in PERMISSIONS
}  # fmt: skip
