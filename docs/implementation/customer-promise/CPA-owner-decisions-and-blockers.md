# Customer Promise: owner decisions, staging validation and blockers

Nothing below is decided by engineering. Every item is the owner's (Veda Spaces), recorded through the existing
owner-decision registers and reviewed pull requests.

## 1. Owner decisions

| Code | Decision | Until it is recorded |
|---|---|---|
| OI-MTQ-18 | Record the Customer Promise portal as the governed source of the customer information pack: `{"source": "CUSTOMER_PROMISE_ADMIN", "register_reference": "<register entry>", "decided_on": "<date>"}` in `commercial-policy.json` (reviewed pull request, register row updated) | Quotations show every customer-information section "to be confirmed", whatever is published in the portal |
| CPA-D01 | The content of each section (contacts, inclusions, responsibilities, readiness, site-dependent work and its approval rule, manufacturer-warranty note, exclusions, service guidance, handover, care, next steps and any approved durations, payment-safety wording), authored and approved in the portal | Sections stay empty ("to be confirmed") |
| CPA-D02 | Who holds the individually granted personas (operations, catalogue/product, customer experience, legal/control, publisher) | Only FOUNDER can review sensitive sections, approve and publish |
| CPA-D03 | Which sections a real-customer launch requires (the portal requires none: OI-MTQ-18 keeps every section optional) | The CQX trust checklist stays advisory |
| CPA-D04 | Legal review of warranty exclusions, customer responsibilities, site-dependent work and payment-safety wording before approval (the sensitive-review capability holder) | Sensitive sections can still be reviewed by a FOUNDER who did not write them; the legal review itself is not evidenced |
| CPA-D05 | Whether scheduled (future-effective) publication is wanted | Publication is immediate |
| OI-MTQ-09 | Veda Spaces' own service and workmanship commitments (`service_support`), with warranty and terms | Area 7 shows "to be confirmed" |

## 2. Staging validation (when enabled)

1. Owner records the persona holders (CPA-D02); a second staff account exists for four-eyes.
2. `VEDA_CUSTOMER_PROMISE_ADMIN_ENABLED=true` in staging (a staging wiring change and plan/apply, as for the other
   flags; not part of this pull request).
3. Author a SYNTHETIC test pack, review it with a different account, approve, publish; check the preview at mobile,
   tablet and desktop widths; check history, semantic changes and the event trail.
4. With a SYNTHETIC OI-MTQ-18 delegation **only in a test environment**, the binding is proven by the automated suite
   (`test_customer_promise_binding.py`); staging records the real delegation only after the owner's decision.
5. Evidence: the deploy run, the migration head `0207_customer_promise`, the screenshots and the API trail.

## 3. Staging-enablement blockers

- The flag is not wired to staging (no SSM parameter, no enablement record); a wiring change is required.
- CPA-D02 persona holders and a second account for four-eyes.
- This pull request's independent review.

## 4. Real-customer blockers

- OI-MTQ-18 delegation recorded by the owner, and a published pack whose content the owner approved (CPA-D01,
  CPA-D04).
- The existing CQX real-customer blockers (CQX-security-model §4 N9 and the CQX owner decisions) are unchanged.

## 5. Production blockers

- Production refuses `VEDA_CUSTOMER_PROMISE_ADMIN_ENABLED` (config), as it refuses the MTQ and CQX flags; no
  production decision exists for MTQ B2-B4, CQX or this portal.
