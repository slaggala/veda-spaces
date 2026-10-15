# Customer Quotation Experience: staging enablement, validation checklist and rollback

Status: **prepared, not applied.** The three flags are planned `false` (`infra/config/staging-platform.json`
"customer_proposal"); `infra/config/customer-proposal-enablement-record.json` is a **DRAFT**. Nothing in this change
enables anything.

## 1. What the infrastructure change plans

`infra/terraform/envs/staging-core`: three SSM parameters under `/veda/staging/config`, each `false`:
`VEDA_CUSTOMER_PROPOSAL_ENABLED`, `VEDA_CUSTOMER_PROPOSAL_INTERACTION_ENABLED`,
`VEDA_CUSTOMER_QUOTATION_ACCEPTANCE_ENABLED`. **Expected plan: 3 to add, 0 to change, 0 to destroy.** Output
`customer_proposal` refuses: a bound digest without a flag; viewing without the B4 quotation flag; interaction without
viewing; acceptance without interaction; any flag without an APPROVED, staging-only, synthetic-customers-only record
bound by its SHA-256 whose scope names that capability and whose evidence is filled. Offline tests: 8 new runs in
`tests/core.tftest.hcl` (58 total pass). Apply only through the existing owner-controlled 11-infra-apply of a plan run on
main.

## 2. Enablement sequence (owner-controlled)

1. Merge the umbrella PR (independent review first). 2. Dispatch the plan on main; verify 3/0/0; approve and apply;
drift run clean. 3. Deploy (12-deploy); confirm migration head `0205_customer_proposal`; flags off: every CQX route
404. 4. Fill the record's evidence (review, CI, deploy-flags-off, migration verification, apply, drift, smoke test,
production isolation), set its scope (**viewing** first; interaction and acceptance testing only when they are to be
tested), the owner approves it (approver ≠ author). 5. A reviewed change sets the flag(s) and binds the record's SHA-256;
plan, apply, deploy. 6. Run the smoke checklist with synthetic customers only. 7. Schedule
`veda maintenance customer-proposal-housekeeping`.

Viewing shows something only once an issued quotation exists, which needs the commercial decisions of
[CQX-owner-decisions.md](CQX-owner-decisions.md) §2; digital acceptance additionally needs §1.

## 3. Staging validation checklist (synthetic customers, protected staging, Cloudflare Access)

- [ ] Flags off: `/api/v1/public/proposal`, `/api/v1/quotations/<id>/access-grants`, `/api/v1/customer-requests/x/respond` answer 404; `/auth/me` features show the three CQX features false.
- [ ] Viewing on: staff create a link (copied once); the link opens `/proposal`, the address bar shows no token; overview, rooms, specifications, pricing and terms match the issued document; staff preview is identical.
- [ ] Refusals: a guessed link, a revoked link, a rotated link's old token, an expired link and a superseded version each show their safe message.
- [ ] 360 px phone, tablet and desktop: no sideways scrolling; keyboard navigation; print.
- [ ] Interaction on: choose, drop and discuss an optional item; ask a question and a change request; staff answer and link a revised version; the customer sees the answer; staff notifications arrive once; no customer email is sent.
- [ ] Acceptance testing on (only if the record says so, with SYNTHETIC-only expectations): with the owner decisions still null the page says acceptance is not available and the API refuses it; staff evidence lists the blockers.
- [ ] Production isolation: no production parameter, stack or host touched; the API refuses every CQX flag in production.
- [ ] Rollback rehearsal (below), then re-enable; the template-v2 limitation (api-runbooks §2.4) acknowledged.
- [ ] `customer-proposal-housekeeping` scheduled (it is not scheduled by this change).
- [ ] Images: none are shown until the `/proposal` image policy (N10) is reviewed; placeholders only.
- [ ] Open findings respected (CQX-security-model §4): acceptance testing stays off while N7 is open; N9 blocks real
      customers only (synthetic staging may proceed under the record's scope); images off while N10 is open.

## 4. Evidence requirements (record fields)

`independent_review`, `ci_run_id`, `deploy_flags_off_run_id`, `migration_verification_run_id`, `infra_apply_run_id`,
`drift_run_id` (run ids: digits), `smoke_test` (the checklist outcome with transcripts), `production_isolation`.

## 5. Rollback runbook

1. Optional, to stop every link at once without a deploy: revoke the live links (staff panel), or
2. a reviewed change sets `proposal_enabled`, `interaction_enabled`, `acceptance_enabled` false and
   `enablement_record_sha256` null; approved 11-infra-apply changes the three parameters in place; the next 12-deploy
   renders them. Every CQX route then answers 404; no data is deleted.
3. Image rollback across this release is **not ordinarily safe** once any quotation was issued with template
   `mtq-quotation-html/2` (every issue from this release on): the previous image cannot render those documents and
   refuses them (fail closed). Check first (api-runbooks §2.4); if any exist, recover by **rolling forward** with a
   corrected image. Migration 0205 itself is expand-only (new tables; one CHECK widened to admit `CUSTOMER_DIGITAL`).
   This limitation must be acknowledged in the enablement record before viewing is enabled.

## 6. Production blockers

Production refuses all three flags at start (`veda/config.py`). See [CQX-owner-decisions.md](CQX-owner-decisions.md) §4.
