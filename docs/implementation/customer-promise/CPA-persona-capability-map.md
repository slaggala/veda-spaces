# Customer Promise: personas and capabilities (CPA-15, CPA-16)

Permissions are capabilities, never people (`api/veda/modules/customer_promise/permissions.py`, migration
`0207_customer_promise`). A persona is a set of capabilities. None is lead-scoped; none exposes a customer, a lead or a
quotation's content.

## 1. Capabilities

| Code | Allows | Sensitivity |
|---|---|---|
| `customer_promise.view` | The landing page, versions, reviews, completeness, semantic changes | — |
| `customer_promise.draft.create` | Start a draft (from the published version, or an earlier one as a rollback), change its summary, discard it | — |
| `customer_promise.edit` | Edit inclusions, customer responsibilities, site readiness, site-dependent work, handover, care, next steps | — |
| `customer_promise.contacts.edit` | Edit contacts, support and escalation, service guidance | — |
| `customer_promise.warranty.edit` | Edit the manufacturer-warranty note and warranty exclusions | — |
| `customer_promise.payment_safety.edit` | Edit the payment-safety wording | — |
| `customer_promise.submit` | Submit a draft for review; return a version to draft | — |
| `customer_promise.review` | Review ordinary sections | — |
| `customer_promise.review.sensitive` | Review customer responsibilities, site-dependent work, warranty, exclusions, payment safety | ACCESS_CONTROL (MFA) |
| `customer_promise.approve` | Approve a fully reviewed version; return it to draft | ACCESS_CONTROL (MFA) |
| `customer_promise.publish` | Publish an approved version (supersedes the published one) | ACCESS_CONTROL (MFA) |
| `customer_promise.preview` | Preview a version as customers would see it | — |
| `customer_promise.audit.read` | Read every version's full event history | — |

The instruction's `supersede` capability is folded into `publish` (superseding without a replacement would leave no
current pack); `view_audit` is `audit.read`; `create_draft` is `draft.create`; `manage_*` are the `*.edit` codes.

## 2. Default grants (repository roles, not an invented organisation)

| Role | Grants | Why |
|---|---|---|
| FOUNDER | all thirteen | The business owner |
| SALES_MANAGER | view, draft.create, edit, submit, review, preview, audit.read | Commercial approvals role: the commercial author and ordinary reviewer |
| ADMIN | view | Platform operations administrator: sees, does not author (as for the catalog) |
| SALES, ESTIMATOR, DESIGNER, SURVEYOR | none | Ordinary sales, estimating and site roles |

## 3. Persona map

| Persona (instruction) | Repository role | Capabilities |
|---|---|---|
| Commercial / business owner | SALES_MANAGER (by default) | view, draft.create, edit, submit, review, preview, audit.read |
| Operations owner | **none exists**: granted individually | view, draft.create, edit, submit, review, preview |
| Catalogue / product owner | **none exists** (catalog duties are granted individually): granted individually | view, warranty.edit, preview |
| Customer experience / support owner | **none exists**: granted individually | view, contacts.edit, submit, preview |
| Legal / control approver | **none exists**: granted individually | view, review.sensitive (MFA) |
| Publisher / authorised approver | FOUNDER (by default); others individually | approve and/or publish (MFA) |
| Viewer | ADMIN | view |

Individual grants go through `user.permission.manage` (ACCESS_CONTROL, audited). The owner decides who holds the
individually granted personas (owner decision CPA-D02, [owner decisions](CPA-owner-decisions-and-blockers.md)).

## 4. Four-eyes

Enforced in the service for **every** section (stronger than the instruction's sensitive-only minimum):

- a section is reviewed by someone who did not save it, did not submit the version and did not restore it by a
  rollback;
- a version is approved by someone who contributed to none of its changed sections and did not submit it;
- contributors come from the stored list *and* the event trail; clearing either never opens approval;
- no super-user bypass exists in the UI or the API; FOUNDER is subject to the same rules.

Nobody completes a cycle alone: at least two people are needed, the author and someone else who reviews and approves
(a reviewer may also approve, since reviewing is not contributing). Sensitive sections need a holder of
`review.sensitive`. This is the second-staff-account prerequisite already recorded for staging four-eyes.

## 5. Verified by tests

`api/tests/integration/test_customer_promise.py`: viewer only; author; reviewer; legal (sensitive) reviewer; approver;
publisher; unauthorised SALES, ESTIMATOR and DESIGNER (403 everywhere); a SALES_MANAGER without contacts, warranty or
payment-safety grants (403 on those sections); author self-review and self-approval (409 `FOUR_EYES_REQUIRED`); reviewer
publishing (403); direct API publish of an unapproved version (409); a cleared contributor list (still refused); a
customer without a staff session (401).
