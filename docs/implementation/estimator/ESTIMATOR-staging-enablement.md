# Budgetary Estimate: staging-only enablement package

**Instruction:** `VEDA-SPACES-ESTIMATOR-STAGING-VALIDATION` (owner, 2026-10-08).

**Branch:** `feature/estimator-staging-enable`. It is prepared, **not applied**.

**Scope:** staging only, behind Cloudflare Access.

**Never touched:**
- public intake (ADR-011 E7);
- anonymous public access;
- production.

## 1. Order of changes

| # | Change | Contents | State |
|---|---|---|---|
| 1 | Sign-off PR (`feature/estimator-signoff`) | D3 offered scope (3 BHK apartments only), decision records 19–20, staging validation plan, sign-off package | Ready to merge; awaits authorisation |
| 2 | Prerequisites (`feature/estimator-staging-prereqs`) | **S4:** the aggregate limit counts only successful (Turnstile-verified) requests. **U7:** the error summary links to fields; `aria-invalid`; per-field messages. **S2 follow-through:** customer room subtotals rounded in the public API response | Ready to review. Stacked on 1 |
| 3 | Enablement (`feature/estimator-staging-enable`) | `estimator_enabled` for staging, with the warranty policy link; plan precondition; API guard; tests | Prepared, not applied. Stacked on 2. **Blocked on the policy link (§4)** |

## 2. The enablement change

| File | Change |
|---|---|
| `infra/config/staging-platform.json` | `ssm.estimator_enabled: true`, with the owner decision (decision log 20) appended to the reviewed `ssm` decision text |
| `infra/terraform/envs/staging-core/main.tf` | When enabled, `VEDA_ESTIMATOR_ENABLED = "true"` and `VEDA_WARRANTY_POLICY_URL = var.warranty_policy_url` join the staging app configuration (SSM `/veda/staging/config/…`) |
| `…/staging-core/variables.tf` | `warranty_policy_url`: empty, or an `https` page on a `vedaspaces.com` host. No placeholder |
| `…/staging-core/outputs.tf` | Output `estimator` with a precondition: **an enabled estimator without a policy link fails the plan** |
| `…/staging-core/tests/core.tftest.hcl` | Three runs: <ul><li>enabled with its link reaches SSM;</li><li>enabled without a link is refused;</li><li>a non-vedaspaces or plain-http link is refused</li></ul> |
| `.github/workflows/10-infra-plan.yml` | `TF_VAR_warranty_policy_url` from the `WARRANTY_POLICY_URL` variable of the `staging-plan` environment |
| `api/veda/config.py` | In a deployed environment an enabled estimator requires a real `https` policy link. **Production still refuses the estimator** |
| `api/tests/unit/test_config_environments.py`, `test_governance_docs.py` | <ul><li>The link guard, and the production refusal kept.</li><li>Only the staging core configuration can set the flag; no workflow sets it directly</li></ul> |

## 3. Plan expectations (`10-infra-plan`, core stack)

| Expected | Not expected |
|---|---|
| Two SSM parameters **created**: `/veda/staging/config/VEDA_ESTIMATOR_ENABLED` = `true` and `/veda/staging/config/VEDA_WARRANTY_POLICY_URL` = the approved link | Any other resource change. Any production resource. Any change to Access, the tunnel, DNS or the public-intake hostname |
| The `estimator` output: `{ enabled = true, warranty_policy_url = "<link>" }` | A rate, a card or any customer data. The card never goes through Terraform |
| **Until the link is set,** the plan fails with "The estimator is enabled … but no warranty policy link is set". This is the expected blocker | A plan that succeeds without the link |

**Plan observed on the PR:** the read-only `10-infra-plan` check on the PR showed `Plan: 3 to add`, then failed on
the precondition as designed (no link set). The three additions are:
- the two SSM parameters above;
- `module.monitoring.aws_sns_topic_subscription.owner`, which was **already pending on `main` before this change**
  (the last successful plan, on another PR, showed `1 to add`, that subscription). Applying the enablement plan also
  applies it, unless it is applied separately first.

**Apply path:** owner approval, then `11-infra-apply` (the saved plan), then `12-deploy`. The host re-reads SSM, and the
API then answers the two public estimator routes, still behind Access.

## 4. Warranty policy link (Phase 3): **STAGING BLOCKER**

| Requirement | Status |
|---|---|
| A staging-reachable page with the approved Warranty, Service & Customer Care Policy | **Not available.** No policy page exists in the site. The approved text is a customer-specific template (v1.0) with a note that it needs legal and tax review before it becomes standard |
| No broken or placeholder link | **Enforced.** The page shows the link only when it is set. The plan and the API both refuse an enabled estimator without a real `https` link |
| Estimator shows only the concise summary | **Verified.** The summary is five items filtered to the selection, plus the note that manufacturer warranties do not extend Veda Spaces workmanship or free service. It matches policy clauses 1.1–1.5 and 6.1, and states plywood more conservatively |
| Full exclusions only through the link | **By design.** The exclusions are in the policy (clauses 2, 6.2) |
| Public enablement blocked until legal review is recorded | **Held.** D8, decision log 19 |

**To clear the blocker (owner):**
1. Choose where the policy page lives on a `vedaspaces.com` host reachable during protected validation. A staging-only
   page must not reach the production site.
2. Approve its text. A de-identified copy of the v1.0 template is in the owner's private folder, not in the
   repository.
3. Set `WARRANTY_POLICY_URL` in the `staging-plan` environment.

Publishing the policy text in this public repository is a separate owner decision, because its legal review is
pending.

## 5. The private card is never exposed

| Channel | Control |
|---|---|
| Frontend bundles and source maps | The wizard and the staff app hold no rates. The staging-build test refuses a rate table in the page script. Prices come only from the API |
| Public API responses | Allow-listed customer view: totals, rounded room subtotals, the grouped package and the allowance range. No lines, rates, quantities, components or percentages. Tested |
| Staff responses | Line rates only with `estimate.read` (Founder, Admin, Sales) and lead visibility. The card has no API route |
| Audit log | The card document is excluded. Flattened rate items and estimate lines are audited and readable only with `audit.read` (Founder, Admin) |
| Logs | Request logs record route, status and source network, never bodies. The CLI prints a card's version and SHA-256 only |
| CI artifacts and plan artifacts | No card in the repository or in Terraform. The plan shows only the flag and the policy link |
| Loading | The owner runs `validate-card`, `load-card` and `activate-card` on the host (runbook §6.8), then deletes the file |
| Backups | The card lives in the staging database, so it is in its encrypted snapshots (KMS), like all staging data |

## 6. Staging validation checklist (after 1–3 are approved and the link exists)

Steps and pass criteria are in the [staging validation plan](ESTIMATOR-staging-validation-plan.md) (V1–V12). Each
owner item is mapped below to the plan case that checks it, and to the evidence already in hand.

| # | Item | Plan case | Evidence before staging |
|---|---|---|---|
| 1 | Only 3 BHK Apartment offered | V1 | e2e offered-scope check; local rehearsal: every other size and Villa refused |
| 2 | Essential pricing works | V2 | Rehearsal: a full home priced |
| 3 | Premium unavailable | V5 | Rehearsal: `PACKAGE_UNAVAILABLE`; the page shows "pricing coming soon" |
| 4 | Luxury: no price, consultation | V6 | Rehearsal: refused by the API; e2e: the exact label and the consultation path |
| 5 | Customer measurements calculate correctly | V2, V4 | Engine tests; E6 measured results |
| 6 | Typical sizes shown as assumptions | V3 | Rehearsal; engine tests |
| 7 | Every product calculates | V2 | Rehearsal: 18 of 18 priced |
| 8 | Soft-close only in the approved products | V8 | Rehearsal: kitchen, wardrobe and TV unit only |
| 9 | Package holds exactly the six components | V2, V8 | Rehearsal; schema refuses others |
| 10 | Allowance separate, a range, stored | V2, V8 | Rehearsal: customer fields, stored low ≤ mid ≤ high |
| 11 | GST separate | V2 | Rehearsal |
| 12 | Room totals rounded | V2 | Rehearsal after the S2 follow-through fix; API test |
| 13 | Internal rates not exposed | V2, V9 | Rehearsal: no restricted field, no card rate among customer numbers |
| 14 | Validity 30 days | V2 | Rehearsal: 30 days |
| 15 | Unlinked retention 90 days from creation | V11 | API test: kept at day 89, removed at day 91, never while valid |
| 16 | No personal data needed | V2 | Closed request schema; tests |
| 17 | Linking is atomic | V7 | API test (both databases) |
| 18 | Concurrent enquiries never lose a lead | V7 | API test of the race (both databases) |
| 19 | Notification carries the estimate summary | V7 | API test |
| 20 | Staff see assumptions and the snapshot | V8 | Rehearsal: assumption details; snapshot recomputes identically |
| 21 | Warranty summary and policy link | V2 | Summary verified. **Link blocked (§4)** |
| 22 | No production endpoint or dependency | V12 | Staging build refuses the production API; the API refuses the estimator in production |
| 23 | Public intake disabled | V12 | Committed pages off; governance test |
| 24 | Accessibility, including the error summary | V10 | e2e: axe on every screen and on the error state; linked summary (U7) |
| 25 | Rate limiting safe, including the aggregate | V9 | API test: 612 unverified requests from 102 networks cannot lock out a verified customer (S4) |

## 7. Rollback

1. **Site:** clear `STAGING_ESTIMATOR` in the Pages project and retry. The page shows "coming soon".
2. **API:** set `ssm.estimator_enabled` to `false` (or remove it) in `infra/config/staging-platform.json` in a
   reviewed PR. Then plan (expected: both SSM parameters destroyed), apply and `12-deploy`. Both public estimator
   routes then answer `404`.
3. **Card (optional):** `veda estimator rollback-card --approval "<reason>"`.
4. **Data:** nothing to undo. Estimates hold no personal data, and unlinked ones are removed 90 days after creation.
