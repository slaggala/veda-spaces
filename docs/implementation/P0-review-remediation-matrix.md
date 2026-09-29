# P0 review remediation matrix

Independent review: review/p0-independent-implementation-review @ 1aaf019b6c872a075d13e9b3a2a2e9c16489f6f4 (verdict **NOT CERTIFIED**, {'BLOCKER': 1, 'MAJOR': 18, 'MINOR': 20, 'ADVISORY': 25}).
Reviewed implementation `9236aa3ade38c33d03a57cf7a064ece29937b109`; certified architecture `778aa8fdd918da48340319696ada3ff673e9fb8e`.

Every finding of the review is listed with its original ID, severity and title; none is combined, renamed or downgraded. Blocker columns are the reviewer's classification; *Status* and *Residual* are this remediation's.

## Status summary

| Severity | Status | Count |
|---|---|---|
| BLOCKER | RESOLVED — AMENDMENT PENDING OWNER DECISION | 1 |
| MAJOR | PARTIALLY RESOLVED | 4 |
| MAJOR | RESOLVED | 11 |
| MAJOR | RESOLVED — AMENDMENT PENDING OWNER DECISION | 3 |
| MINOR | OPEN — TRACKED | 2 |
| MINOR | PARTIALLY RESOLVED | 2 |
| MINOR | RESOLVED | 15 |
| MINOR | RESOLVED — AMENDMENT PENDING OWNER DECISION | 1 |
| ADVISORY | OPEN — OWNER DECISION REQUIRED | 5 |
| ADVISORY | OPEN — TRACKED | 9 |
| ADVISORY | PARTIALLY RESOLVED | 2 |
| ADVISORY | RESOLVED | 9 |

## Findings

| ID | Severity | Title | Merge | Staging | Prod | Status | Residual | Re-review |
|---|---|---|---|---|---|---|---|---|
| IR-01 | BLOCKER | MFA enrollment confirmation is not bound to the caller: a bearer token plus any unbound enrollment challenge grants MFA verification and ste | Yes | Yes | Yes | RESOLVED — AMENDMENT PENDING OWNER DECISION |  | Yes — security re-review of the enrollment/step-up state machine |
| IR-02 | MAJOR | Cloudflare Turnstile siteverify (up to 5 s network I/O) runs while the database-wide SQLite write lock is held (public intake and CAPTCHA-ga | No | No | Yes | RESOLVED |  | Targeted |
| IR-03 | MAJOR | Security-event chain verification never consults the external anchor and accepts deletion of the anchored prefix and tail truncation | No | No | Yes | PARTIALLY RESOLVED | Code complete; the S3 Object Lock read/write roles and bucket must be verified in staging (OI-6). | Targeted |
| IR-04 | MAJOR | A STANDARD dual-control request survives the target's promotion to Founder and then executes against the Founder (G11 time-of-check/time-of- | Yes | Yes | Yes | RESOLVED |  | Targeted |
| IR-05 | MAJOR | Custodians can initiate full break-glass while eligible Founders exist (no operating-mode check) | No | No | Yes | RESOLVED |  | Targeted |
| IR-06 | MAJOR | Break-glass CLI trusts a caller-supplied --principal-arn (two-person control is self-asserted) | No | No | Yes | PARTIALLY RESOLVED | Real STS/SSM identity must be exercised in staging (PG-BG gate). | Targeted |
| IR-07 | MAJOR | Break-glass cancel link targets a non-existent SPA route; the 06 §7.5 notified-party veto is unusable end-to-end | No | No | Yes | RESOLVED — AMENDMENT PENDING OWNER DECISION |  | Targeted |
| IR-08 | MAJOR | FOUNDER_STATUS_CHANGE with DELETED always fails (I3 evaluation drops soft-deleted users but keeps their live FOUNDER role row) | Yes | Yes | Yes | RESOLVED |  | Targeted |
| IR-09 | MAJOR | Production-safety validation is fail-open: any VEDA_ENV other than exactly 'production' (including staging, unset, 'prod') runs with publicl | No | Yes | Yes | RESOLVED |  | Targeted |
| IR-10 | MAJOR | Readiness gate requires DB revision == image head exactly, so the architecture's normal rollback (redeploy N-1 on the migrated schema) alway | No | No | Yes | RESOLVED — AMENDMENT PENDING OWNER DECISION | RG-7 rollback rehearsal not executed (production gate). | Targeted |
| IR-11 | MAJOR | Backup (Litestream config, nightly snapshot), restore verification and API deploy/migrate runbooks are absent from the deliverable | No | No | Yes | PARTIALLY RESOLVED | RG-1, RG-2 and RG-7 (replication, restore and rollback rehearsals on the real host) not executed; RPO/RTO owner input (OWNER-INPUT-001) pending. | Operational readiness review |
| IR-12 | MAJOR | No metrics, no alert routing, error tracker optional (LOG-006 is mandatory in P0) | No | No | Yes | PARTIALLY RESOLVED | CloudWatch agent/alarms/SNS routing are deployment configuration; RG-5 test-fire not executed. | Operational readiness review |
| IR-13 | MAJOR | Runtime Python dependencies are open ranges with no lockfile or hashes; container base image floats | Yes | Yes | Yes | RESOLVED |  | Targeted |
| IR-14 | MAJOR | CI workflow has never executed and omits PR gates required by 12 §5 (types, N-1 test, OpenAPI diff, dependency/image/secret scan, E2E smoke  | Yes | Yes | Yes | RESOLVED |  | Yes (evidence: CI run URL) |
| IR-15 | MAJOR | Lead edit 'Re-apply mine' after a version conflict silently reverts the other writer's committed changes | No | No | Yes | RESOLVED |  | Targeted |
| IR-16 | MAJOR | DEV-004 staff re-consent overwrites consent evidence, mixes provenance and is accepted without prior withdrawal | Yes | Yes | Yes | RESOLVED — AMENDMENT PENDING OWNER DECISION |  | Yes (DEV-004) |
| IR-17 | MAJOR | Enquiry form remains visible after success/fallback ([hidden] overridden by .contact-form{display:grid}); resubmission reports a false failu | No | No | No | RESOLVED |  | Targeted |
| IR-18 | MAJOR | Turnstile token is never reset; after any server-side 422 the corrected resubmission reuses a spent token and fails CAPTCHA | No | No | No | RESOLVED | A run with the real Cloudflare test keys is part of intake enablement. | Targeted |
| IR-19 | MAJOR | SPA route changes never update the document title nor move focus/announce navigation (WCAG 2.4.2 Level A) | No | No | Yes | RESOLVED | Manual NVDA/VoiceOver script is a production gate. | Targeted |
| IR-20 | MINOR | Path C (emailed enrollment link + password) replaces an existing ACTIVE factor without step-up by that factor; open enrollment links survive | No | No | Yes | RESOLVED |  | Targeted |
| IR-21 | MINOR | Resending an invitation does not revoke earlier invite_context challenges; link replay mints parallel contexts and overwrites the password | No | No | Yes | RESOLVED |  | Targeted |
| IR-22 | MINOR | IPv6 /64 network grouping is string-based and breaks on compressed addresses, defeating per-network throttle and CAPTCHA and causing false g | No | No | Yes | RESOLVED |  | Targeted |
| IR-23 | MINOR | Certified 5/min per-email login limit lets anyone lock a known account out from every network | No | No | Yes | RESOLVED — AMENDMENT PENDING OWNER DECISION |  | Targeted |
| IR-24 | MINOR | Password re-entry (reauth) and change-password are not throttled; password guessing with a stolen bearer then satisfies password-based step- | No | No | Yes | RESOLVED |  | Targeted |
| IR-25 | MINOR | Security-event gaps: no event on MFA-path invite password set, invalid action tokens, CSRF-rejected refresh, MFA throttle and per-network th | No | No | Yes | RESOLVED |  | Targeted |
| IR-26 | MINOR | Security-log archival deletes events it never exported when event time and chain order disagree near the cutoff | No | No | Yes | RESOLVED |  | Targeted |
| IR-27 | MINOR | Unhandled exceptions and DB errors log raw PII (stdlib loggers bypass structlog masking; engine lacks hide_parameters) | No | No | Yes | RESOLVED |  | Targeted |
| IR-28 | MINOR | An erased (anonymised) lead still accepts notes, activities and status changes, re-introducing PII after erasure is reported complete | No | No | Yes | RESOLVED |  | Targeted |
| IR-29 | MINOR | Plain-text staff notification emails can be content-spoofed via newlines in public form fields | No | No | Yes | RESOLVED |  | Targeted |
| IR-30 | MINOR | Outbox retry resends email to recipients who already received it | No | No | Yes | RESOLVED |  | Targeted |
| IR-31 | MINOR | UNKNOWN_POLICY_VERSION is shown as an inline field error with no WhatsApp route | No | No | No | RESOLVED |  | Targeted |
| IR-32 | MINOR | Enquiry-form prerequisites absent: /privacy page missing, no site CSP, Turnstile site key unset, showErrors() uses innerHTML with server str | No | No | No | PARTIALLY RESOLVED | Privacy Notice page (v2026-09-v1) and the Turnstile site key are owner/legal inputs; intake stays disabled until both exist. | Yes (intake enablement) |
| IR-33 | MINOR | PostgreSQL immutability guard is bypassable (user-settable GUC veda.maintenance, no TRUNCATE trigger) and app/retention roles are never prov | No | No | No | OPEN — TRACKED | Before PGM-1: BEFORE TRUNCATE trigger, role-based bypass, provisioned roles. | Yes (PG gate) |
| IR-34 | MINOR | Historical migrations import the live permission registry and role matrix, so freshly built environments drift from upgraded ones | No | No | No | OPEN — TRACKED |  | No |
| IR-35 | MINOR | Single-process/instance constraint is enforced only by a text match on gunicorn.conf.py; client IP trusted from CF-Connecting-IP without a t | No | No | Yes | RESOLVED | The proxy/tunnel address is a deployment input (RG-3, RG-6 on the real host). | Targeted |
| IR-36 | MINOR | 'Sign out everywhere' leaves the user on /profile with stale personal data displayed | No | No | Yes | RESOLVED |  | Targeted |
| IR-37 | MINOR | Accessibility gaps: 360 px status stepper not keyboard-scrollable (axe serious), unreliable toast announcements, no MFA-timeout warning, win | No | No | Yes | RESOLVED | Manual screen-reader script and Firefox/WebKit/200 % zoom checks are production gates. | Targeted |
| IR-38 | MINOR | Browser E2E evidence overstates coverage and security-critical modules have the lowest coverage | No | No | Yes | PARTIALLY RESOLVED | Firefox and WebKit legs (12 §4.8 browser matrix) not added. | Targeted |
| IR-39 | MINOR | No Python formatter or type checker enforced, no ESLint/Prettier; frontend dev toolchain carries dev-only advisories (upgrade needs Node ≥ 2 | No | Yes | Yes | RESOLVED | mypy backlog of 157 findings tracked for burn-down (OI-RM-3). | No |
| IR-A01 | ADVISORY | PostgreSQL concurrency: refresh rotation, recovery-code consumption and challenge attempt counting are read-then-write without row locks/con | No | No | PG release gate | OPEN — TRACKED | PostgreSQL release gate (PGM-1): row locks/conditional updates for refresh rotation, recovery codes and attempt counting. Enrollment confirmation already takes a row lock (IR-01). | No |
| IR-A02 | ADVISORY | Login timing delta ≈1.2–1.6 ms known vs unknown account (extra post-request write) — auth/service.py:266-283. | No | No | No | OPEN — TRACKED | Accepted residual (~1.5 ms); revisit with the P1 breached-password work. | No |
| IR-A03 | ADVISORY | Refresh/logout CSRF origin allow-list includes public-site origins (auth/service.py:334); mitigated by CORS preflight; tighten to app_origin | No | No | No | RESOLVED |  | No |
| IR-A04 | ADVISORY | Password reset does not invalidate open MFA challenges / enrollment links (auth/service.py:443-459). | No | No | No | RESOLVED |  | No |
| IR-A05 | ADVISORY | Startup route-declaration check is presence-only; RBX ids/paths not validated against the 06 §11 register; public route with a permission wo | No | No | No | RESOLVED |  | No |
| IR-A06 | ADVISORY | PATCH /roles/{id} lacks a self-held-role check and accepts mfa_required (not in 08 §6.1) — rbac/roles.py:70-89. | No | No | No | OPEN — OWNER DECISION REQUIRED | PATCH /roles self-held-role check and the mfa_required field (not in 08 §6.1) need an owner decision; unchanged. | No |
| IR-A07 | ADVISORY | Approval deny/cancel emit no SENSITIVE_ACTION; invite with sensitive role sends no rbac.sensitive_grant email; approve/deny return 403 where | No | No | No | PARTIALLY RESOLVED | SENSITIVE_ACTION now recorded on deny and cancel (test_governance_remediation.py::test_IRA07_*). The 403-vs-404 existence oracle is required by 08 §4 / 12 TD-G G9 and was left unchanged pending an owner decision. Invite-with-sensitive-role email not added. | No |
| IR-A08 | ADVISORY | 08 §12 per-user 600 req/5 min limit not implemented; token endpoints unthrottled (entropy makes brute force infeasible). | No | No | No | OPEN — TRACKED | 08 §12 per-user 600 req/5 min limit not implemented. | No |
| IR-A09 | ADVISORY | HMAC/action/chain keys have no minimum-length check in production (config.py:212-219). Folded into IR-09 remediation. | No | No | No | RESOLVED |  | No |
| IR-A10 | ADVISORY | Cancel-link binding depends on outbox_event rows surviving retention purge (<3 days breaks live links, fail closed). | No | No | No | OPEN — TRACKED | Cancel-link binding still relies on outbox rows; recorded in AM-5 (retention must exceed the break-glass window; retention is unset, so nothing is purged today). | No |
| IR-A11 | ADVISORY | A hostile sole Founder can repeatedly cancel custodian break-glass (architecture residual of 06 §7.5; needs owner decision). | No | No | No | OPEN — OWNER DECISION REQUIRED | AM-9. | No |
| IR-A12 | ADVISORY | Client-supplied X-Request-ID / CF-Ray adopted as request_id; fine for correlation, not trustworthy as evidence (http.py:133-143). | No | No | No | OPEN — TRACKED | Accepted: client X-Request-ID/CF-Ray are correlation ids, not evidence; documented. | No |
| IR-A13 | ADVISORY | Turnstile siteverify hostname/action not checked (turnstile.py:42). | No | No | No | RESOLVED |  | No |
| IR-A14 | ADVISORY | DEAD outbox rows alert only via log.error; /health ignores DEAD; erasure-audit job lacks per-event failure handling (worker.py:97,122-126; m | No | No | No | PARTIALLY RESOLVED | DEAD outbox count is a metric, an ERROR log and a readiness degraded signal (never failing readiness); erasure-audit per-event failure handling unchanged. | No |
| IR-A15 | ADVISORY | IP/user-agent retained in audit_log/security_event_log after lead erasure; several free-text fields not in pii_fields (07 §2 gap). | No | No | No | OPEN — OWNER DECISION REQUIRED | AM-10. | No |
| IR-A16 | ADVISORY | PostgreSQL concurrent duplicate Idempotency-Key returns 409 instead of the original 201 (lead stored once). | No | No | PG release gate | OPEN — TRACKED | PostgreSQL release gate. | No |
| IR-A17 | ADVISORY | /health/ready publicly exposes migration/guard/outbox state (health.py:36-62). | No | No | No | RESOLVED |  | No |
| IR-A18 | ADVISORY | No SQLite format CHECK on UTCDATETIME columns; three CODE(n) columns lack enum CHECKs (event_type, failure_reason, status_reason). | No | No | No | OPEN — TRACKED | Additional SQLite CHECKs are a schema change; post-production follow-up. | No |
| IR-A19 | ADVISORY | sync-permissions CLI labels audit rows performed_via=MIGRATION (migration_support.py:117). | No | No | No | RESOLVED |  | No |
| IR-A20 | ADVISORY | TOTP AES-GCM AAD is constant (crypto.py:120,128); bind to user_id‖factor_id. | No | No | No | OPEN — TRACKED | Binding AES-GCM AAD to user_id‖factor_id needs a re-encryption migration; tracked. | No |
| IR-A21 | ADVISORY | App CSP: styleMap first render raises one style-src-attr violation (components.ts:291); production sourcemaps published (vite.config.ts:8);  | No | No | No | RESOLVED |  | No |
| IR-A22 | ADVISORY | HMAC-derived action tokens (OI-3): acceptable; residual — K_action compromise plus row ids yields every live link; document in 05/03. | No | No | No | OPEN — OWNER DECISION REQUIRED | AM-8. | No |
| IR-A23 | ADVISORY | WhatsApp fallback URL carries enquirer PII to wa.me (pre-existing, user-initiated); mention in Privacy Notice. | No | No | No | OPEN — OWNER DECISION REQUIRED | Privacy Notice content (owner/legal). | No |
| IR-A24 | ADVISORY | 18 pre-existing public-site contrast nodes outside the form (OI-11); highest priority .portfolio-head > p at 2.40:1. | No | No | No | OPEN — TRACKED | 18 pre-existing marketing-site contrast nodes, tracked (OI-11). | No |
| IR-A25 | ADVISORY | Implementation report/register accuracy: DEV-004 claims a UI control that does not exist; ruff format count 82 vs 83; npm critical count 17  | No | No | No | RESOLVED |  | No |

## Detail

### IR-01 · BLOCKER · MFA enrollment confirmation is not bound to the caller: a bearer token plus any unbound enrollment challenge grants MFA verification and step-up to the token's session

- **Reviewer evidence (REPRODUCED (SQLite and PostgreSQL); source confirmed by lead reviewer):** api/veda/platform/auth/mfa.py:259 — challenge/session binding is enforced only when ch.session_id is not None; ctx.user.id is never compared with ch.user_id; api/veda/platform/auth/mfa.py:280 — enrollment path is chosen from the presence of a bearer context (path A) rather than from the challenge; api/veda/platform/auth/mfa.py:297-301 — path A sets auth_methods='pwd+totp' and mfa_verified_on on the CALLER's session while the factor promoted belongs to ch.user_id; api/veda/platform/auth/routes.py:289 — POST /auth/mfa/enroll/confirm declared auth='optional'; Contrast: api/veda/platform/auth/mfa.py:328 (step-up) correctly requires ch.user_id == ctx.user.id and ch.session_id == ctx.session.id; Probe P1b output: 'admin regenerate codes w/o fresh step-up: 403 STEP_UP_REQUIRED' → 'cross confirm using admin bearer: 200 AUTHENTICATED' → 'admin regenerate codes after cross confirm: 200 [codes]'; Probe P1: a password-only session of a user holding an MFA-gated sensitive grant went from 403 MFA_REQUIRED to 200 on GET /api/v1/audit-logs
- **Affected files:** `api/veda/platform/auth/mfa.py`, `api/veda/platform/auth/service.py`, `api/veda/platform/auth/models.py`, `api/migrations/versions/0009_mfa_challenge_binding.py`, `api/tools/render_migrations.py`
- **Requirement IDs:** MFA-011, MFA-012, MFA-014, AUTH-015, 05 §11.3, 05 §11.6, 06 §3.2 (G10)
- **Root cause:** enroll_confirm chose the enrollment path from the presence of a bearer token (path A) instead of from the challenge; ctx.user.id was never compared with ch.user_id, and an unbound (path B/C) challenge accepted any bearer. The PENDING factor was found by user, not bound to the transaction.
- **Remediation:** Every ENROLLMENT challenge now records its enrollment_path (INVITE_CONTEXT, PATH_A..PATH_D) and the factor_id it may promote (migration 0009, DEV-006/AM-11). Confirm derives the path from the challenge and requires: paths A/D — caller user == challenge user AND caller session == challenge session AND session type matches (FULL for A, RECOVERY for D); paths B/C — no bearer at all; factor still PENDING and owned by the challenge user; eligibility re-checked (account state, live invitation for B, N-A1 for A, no ACTIVE factor for C). Binding failures count against the transaction, record a redacted MFA_CHALLENGE FAILURE (reason BINDING_MISMATCH) and answer like an unknown challenge. Only the initiating session is elevated and its refresh token rotated; other sessions keep their assurance. Success ends every other open enrollment transaction and MFA_ENROLLMENT link. Concurrent confirms serialise on a row lock (PostgreSQL) / write lock (SQLite). Start refuses a bearer on paths B/C. Reviewed flows with the same shape: step-up (already bound to user+session), login and recovery challenges (pre-session, principal from the challenge), password reset, email verify/cancel and cancel-link (token names the principal, no bearer used), approvals and break-glass (principal from the authenticated context or STS) — no further confusion found.
- **Tests:** `api/tests/integration/test_mfa_binding.py (19 tests: P1, P1b, path-D variant, attacker/victim bearer, same user other session, revoked/disabled session, stale eligibility, expired, replay, wrong factor, wrong purpose, invitation context, recovery transaction, parallel confirms, failure half-way, failed replacement, refresh rotation)`; `api/tests/integration/test_mfa.py`; `api/tests/integration/test_schema.py`
- **Architecture amendment required:** Yes — AM-11 (mfa_challenge.factor_id, enrollment_path; migration 0009). Reviewer listed none; added because the fix extends the certified mfa_challenge table.
- **Merge / staging / production blocker (reviewer):** Yes / Yes / Yes
- **Status:** RESOLVED — AMENDMENT PENDING OWNER DECISION
- **Re-review required:** Yes — security re-review of the enrollment/step-up state machine

### IR-02 · MAJOR · Cloudflare Turnstile siteverify (up to 5 s network I/O) runs while the database-wide SQLite write lock is held (public intake and CAPTCHA-gated login)

- **Reviewer evidence (REPRODUCED (public intake); login path SOURCE-INSPECTED):** api/veda/kernel/http.py:425,464 — every non-GET route opens db.new_session(write=True) before the handler runs; api/veda/kernel/db.py:46-51 — write sessions issue BEGIN IMMEDIATE (global SQLite write lock); busy_timeout 5000 ms; api/veda/modules/crm/leads/routes.py:69 — turnstile.verify() inside the write unit of work; api/veda/platform/auth/service.py:229 — login calls turnstile.verify() inside the write unit of work when captcha_required; api/veda/kernel/turnstile.py:41 — urlopen(..., timeout=5); Probe Q5: 3 s verify delay → concurrent staff POST /leads waited 2.77 s; 6 s delay → staff write returned 503 after 5.19 s
- **Affected files:** `api/veda/kernel/http.py`, `api/veda/modules/crm/leads/routes.py`, `api/veda/platform/auth/routes.py`, `api/veda/platform/auth/service.py`
- **Requirement IDs:** LEAD-018, AUTH-010, NFR-003, ADR-008, 04 §5.1 (transaction covers steps 6–11 only)
- **Root cause:** The dispatcher opens the write unit of work (BEGIN IMMEDIATE on SQLite) before the handler, and the intake and CAPTCHA-gated login handlers called Turnstile siteverify inside it.
- **Remediation:** RouteSpec gained a prepare step (public routes only) that runs before the write transaction with a read-only session. Intake: idempotency replay and siteverify run there; the key is re-checked inside the write transaction. Login: a presented Turnstile token is verified there and the handler only consumes the result.
- **Tests:** `api/tests/integration/test_intake_lock.py (slow verifier writes from another connection mid-verify; pre-fix run against 9236aa3: 3 failed with 503 after the 5 s busy timeout; post-fix: 3 passed)`; `api/tests/integration/test_leads.py`; `api/tests/integration/test_auth.py`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes · public-intake feature gate
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-03 · MAJOR · Security-event chain verification never consults the external anchor and accepts deletion of the anchored prefix and tail truncation

- **Reviewer evidence (REPRODUCED locally on SQLite and PostgreSQL; S3 path SOURCE-INSPECTED):** api/veda/platform/maintenance.py:240-245 — latest_anchor() reads only local anchors.jsonl; api/veda/platform/maintenance.py:277-283 — production anchor_chain() writes only to S3, never the local file; api/veda/platform/maintenance.py:316-320 — archival anchors are written only locally; api/veda/platform/maintenance.py:253-259 — a missing anchored row is assumed archived; no manifest/hash check; Probe Q4: deleting rows ≤ anchor seq → verify ok=True; deleting the head row → verify ok=True (both engines)
- **Affected files:** `api/veda/platform/anchor_store.py`, `api/veda/platform/maintenance.py`, `api/veda/platform/auth/security_events.py`
- **Requirement IDs:** SEVT-006, SEVT-007, 05 §9.6, 11 §4 A2
- **Root cause:** Verification read only a local anchors.jsonl, production anchors went only to S3, archival anchors only to the local file, and a missing anchored row was assumed archived; truncation below the anchor went unnoticed.
- **Remediation:** New anchor store (local directory or S3 Object Lock, write-once) holds anchors and archive manifests. verify_chain reads the latest anchor and all archive manifests from the store and fails on: prefix removed (first online seq ≠ last archived + 1, or not chained to the archived last hash), truncation below the anchor, anchored row missing and not archived, anchor hash mismatch, gap, modified row. Anchoring writes outside the database transaction; failure raises, logs CRITICAL, emits ChainAnchorFailed and records a FAILURE event.
- **Tests:** `api/tests/integration/test_chain_integrity.py (Q4 prefix deletion, oldest rows, tail truncation, head deletion, gap, modified anchored row, emptied log, anchor failure alert, S3 store with stubbed client)`; `api/tests/integration/test_audit_security.py`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** PARTIALLY RESOLVED — Code complete; the S3 Object Lock read/write roles and bucket must be verified in staging (OI-6).
- **Re-review required:** Targeted

### IR-04 · MAJOR · A STANDARD dual-control request survives the target's promotion to Founder and then executes against the Founder (G11 time-of-check/time-of-use bypass)

- **Reviewer evidence (REPRODUCED (SQLite and PostgreSQL)):** api/veda/platform/rbac/governance.py:70-75 — _open_request_guard is scoped per class, so STANDARD and FOUNDER requests coexist on one target; api/veda/platform/rbac/governance.py:100-108 — _execute_standard runs start_email_change / admin_reset without re-checking protection_level/G11; Probe P10: ADMIN raises EMAIL_CHANGE on ADMIN a2 → a2 promoted to Founder → a Founder approves the stale STANDARD request → 200 EXECUTED, Founder's proposed_email = attacker-controlled address
- **Affected files:** `api/veda/platform/rbac/governance.py`
- **Requirement IDs:** RBAC-020, RBAC-021, USER-007, MFA-007, 06 §7.1 G11, 06 §7.4 (eligibility re-checked at execution)
- **Root cause:** _execute_standard ran email change / MFA reset without re-applying G11 or the requester's G9; STANDARD and FOUNDER request guards are per class, so a STANDARD request survived the target's promotion.
- **Remediation:** G11 and requester G9 are re-evaluated when a STANDARD request executes (FAILED FOUNDER_PROTECTED / ESCALATION_DENIED); GRANT_FOUNDER execution cancels the target's open STANDARD requests (TARGET_BECAME_FOUNDER). Founder actions re-validate their preconditions at execution. Approve and deny re-read the request after taking the governance lock, so a decision racing a promotion sees the cancellation (found by the clean-environment PostgreSQL 16 run).
- **Tests:** `api/tests/integration/test_governance_remediation.py::test_IR04_P10_promotion_cancels_open_standard_requests`; `api/tests/integration/test_governance_remediation.py::test_IR04_execution_time_G11_fails_a_stale_standard_request`; `api/tests/integration/test_governance_remediation.py::test_IR04_requester_G9_rechecked_at_execution`; `api/tests/integration/test_governance_remediation.py::test_IR04_concurrent_promotion_and_standard_approval`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** Yes / Yes / Yes
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-05 · MAJOR · Custodians can initiate full break-glass while eligible Founders exist (no operating-mode check)

- **Reviewer evidence (REPRODUCED (SQLite and PostgreSQL)):** api/veda/platform/rbac/governance.py:387-408 — break_glass_request validates action, target and open-request guard but never checks that no eligible Founder exists; Probe P13: with two eligible Founders present, custodians K1+K2 granted FOUNDER to a SALES user after the 24 h delay
- **Affected files:** `api/veda/platform/rbac/governance.py`
- **Requirement IDs:** RBAC-021, 06 §7.2.2, 06 §7.2.4
- **Root cause:** break_glass_request never checked the operating mode (no eligible Founder other than the target).
- **Remediation:** Custodian requests are refused (409 INVALID_STATE, reason FOUNDER_AVAILABLE, BREAK_GLASS_REQUESTED FAILURE event) while an eligible Founder other than the target exists; re-checked at custodian approval and at execution (FAILED).
- **Tests:** `api/tests/integration/test_governance_remediation.py::test_IR05_P13_custodian_request_refused_while_founders_are_eligible`; `api/tests/integration/test_governance_remediation.py::test_IR05_custodian_path_available_when_no_founder_is_eligible_and_rechecked_at_execution`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-06 · MAJOR · Break-glass CLI trusts a caller-supplied --principal-arn (two-person control is self-asserted)

- **Reviewer evidence (REPRODUCED):** api/veda/cli/main.py:253 — --principal-arn argument passed straight through (main.py:189-197); api/veda/platform/rbac/governance.py:380-384 — custodian_human only looks the ARN up in configuration; no STS/SSM identity check anywhere; Probe P13: one shell ran 'request --principal-arn K1' and 'approve --principal-arn K2'; approval accepted and recorded
- **Affected files:** `api/veda/platform/rbac/custodians.py`, `api/veda/cli/main.py`, `api/veda/platform/rbac/governance.py`, `api/veda/config.py`
- **Requirement IDs:** RBAC-021, 06 §7.5 items 2 and 4 (ARNs verified from SSM session identity / CloudTrail)
- **Root cause:** The CLI passed a caller-supplied --principal-arn straight through; nothing verified the caller's identity.
- **Remediation:** The CLI derives the principal from sts:GetCallerIdentity (the SSM session's credentials). --principal-arn is only an assertion that must match (else refused + FAILURE event). The full STS ARN (with session name) is stored as the external reference; assumed-role sessions map to the registered role ARN. VEDA_BREAK_GLASS_IDENTITY=asserted exists for local/test only and is refused elsewhere.
- **Tests:** `api/tests/integration/test_governance_remediation.py::test_IR06_P13_single_operator_cannot_assert_a_second_custodian (STS stubbed)`; `api/tests/integration/test_governance_remediation.py::test_IR06_asserted_identity_refused_outside_local_and_test`; `api/tests/unit/test_config_environments.py`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** PARTIALLY RESOLVED — Real STS/SSM identity must be exercised in staging (PG-BG gate).
- **Re-review required:** Targeted

### IR-07 · MAJOR · Break-glass cancel link targets a non-existent SPA route; the 06 §7.5 notified-party veto is unusable end-to-end

- **Reviewer evidence (SOURCE-INSPECTED; emailed URL REPRODUCED (P12); API endpoint REPRODUCED working):** api/veda/platform/notifications/handlers.py:309 — link built as {app_origin}/approvals/cancel#token=…; app/src/core/router/routes.ts:20-50 — no /approvals/cancel route (falls through to not-found); no SPA code calls /api/v1/approvals/cancel-link; api/veda/platform/rbac/routes.py:371-379 — POST /api/v1/approvals/cancel-link (RBX-003) works: 256-bit HMAC token, hash-only storage, single use with sibling invalidation (P12: invalid 400 / extra field 422 / valid 204 / replay 400); docs/architecture/08-api-design.md §1 — no break-glass cancel row; #47 POST /approvals/{id}/cancel is implemented (rbac/routes.py:363-368); docs/architecture/06-rbac.md §11 — RBX-003 register does not list cancel-link
- **Affected files:** `app/src/modules/auth/approval-cancel-page.ts`, `app/src/core/router/routes.ts`, `api/veda/app.py`
- **Requirement IDs:** RBAC-021, 06 §7.5 step 5, 12 TD-G G12, PG-BG
- **Root cause:** The emailed link pointed to /approvals/cancel, which the SPA did not route; no client called the endpoint.
- **Remediation:** Public SPA page /approvals/cancel reads the fragment token, scrubs it, and cancels only on an explicit confirmation (mail scanners open links). Endpoint registered as DEV-005 and in the startup RBX register (RBX-003) pending AM-5.
- **Tests:** `app/e2e/access.e2e.mjs: break-glass cancel link works end to end from the email`; `api/tests/integration/test_founder_governance.py::test_G12_cancel_link_by_notified_party`; `app/test/router.test.ts (route title)`
- **Architecture amendment required:** Yes — AM-5 (08 §1 row, 06 §11 RBX-003 entry, 09 page)
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED — AMENDMENT PENDING OWNER DECISION
- **Re-review required:** Targeted

### IR-08 · MAJOR · FOUNDER_STATUS_CHANGE with DELETED always fails (I3 evaluation drops soft-deleted users but keeps their live FOUNDER role row)

- **Reviewer evidence (REPRODUCED (SQLite and PostgreSQL)):** api/veda/platform/rbac/guards.py:148-152 — holders = live FOUNDER user_role rows; protected = users via soft-delete-filtered query; api/veda/platform/rbac/users.py:144-150 — DELETE sets is_deleted but leaves FOUNDER user_role live; api/veda/platform/rbac/governance.py:241-248 — request marked FAILED FOUNDER_STATE_INCONSISTENT; Probe P11/P16: approved DELETE → FAILED; workaround REVOKE_FOUNDER then DELETE → 204
- **Affected files:** `api/veda/platform/rbac/guards.py`
- **Requirement IDs:** RBAC-021, USER-001, 06 §7.2.2
- **Root cause:** I3 compared live FOUNDER role rows (including those of soft-deleted users) with protection_level of non-deleted users only, so deleting a Founder always looked inconsistent.
- **Remediation:** I3 is evaluated over the same population on both sides: live (not soft-deleted) accounts. A deleted Founder keeps its role row and protection level as history.
- **Tests:** `api/tests/integration/test_governance_remediation.py::test_IR08_P16_founder_delete_executes_and_invariants_hold (nightly job agrees)`; `api/tests/integration/test_governance_remediation.py::test_IR08_last_founder_still_cannot_be_deleted`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** Yes / Yes / Yes
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-09 · MAJOR · Production-safety validation is fail-open: any VEDA_ENV other than exactly 'production' (including staging, unset, 'prod') runs with publicly derivable dev keys, local KMS, capture email and the accept-anything CAPTCHA verifier; production validation is also incomplete

- **Reviewer evidence (REPRODUCED):** api/veda/config.py:132-143 — keys fall back to values derived from the public constant 'local-development-only'; api/veda/config.py:207-210 — validate_production returns [] unless settings.is_production; api/veda/platform/auth/jwt_tokens.py:54-60 — non-production JWT key derived from sha256('veda-dev-jwt::' + env); api/veda/kernel/turnstile.py:37-38 — non-cloudflare mode accepts any token not starting with 'fail'; Probe P6b: env='staging' → validate_production [] and a JWT forged with the derivable key verifies; DB/ops probe: env 'production' still accepts rate limits disabled, 1-byte HMAC keys, placeholder KMS ARN, localhost origins, relative SQLite path, jwt_kid=dev-1, no Sentry/anchor bucket; cmd_migrate skips validation (cli/main.py:42-52)
- **Affected files:** `api/veda/config.py`, `api/veda/app.py`, `api/veda/cli/main.py`, `api/veda/platform/auth/jwt_tokens.py`, `api/veda/kernel/turnstile.py`, `api/veda/platform/auth/crypto.py`
- **Requirement IDs:** SEC-005, PLAT-008, OPS-003, LOG-004, AUTH-004, 02 §11.4
- **Root cause:** validate_production returned [] for any VEDA_ENV other than exactly 'production'; unset defaulted to local; keys, JWT signing key, KMS, email and CAPTCHA fell back to development implementations.
- **Remediation:** VEDA_ENV must be one of local/test/staging/production (ConfigError otherwise, including unset). Only local and test derive development keys; staging and production run the full validation: required secrets, ≥32-byte keys, non-dev kid/labels, real KMS ARN, SES, Cloudflare Turnstile, secure cookies, rate limits on, Argon2 floor, public https origins, absolute DB path, STS custodian identity, trusted proxy CIDRs; production also requires Sentry, anchor bucket and snapshot bucket. create_app, every CLI command and migrate refuse on any problem. Defence in depth: the dev JWT key, local KMS and dev CAPTCHA verifier refuse outside local/test.
- **Tests:** `api/tests/unit/test_config_environments.py (unknown/unset env, each missing or weak setting, staging and production, create_app and migrate refusal, P6b dev key/verifier/KMS unavailable)`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / Yes / Yes
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-10 · MAJOR · Readiness gate requires DB revision == image head exactly, so the architecture's normal rollback (redeploy N-1 on the migrated schema) always reports not-ready

- **Reviewer evidence (REPRODUCED):** api/veda/platform/health.py:43-45 — checks['migrations'] = 'head' if current == head else 'behind'; ok &= current == head; Probe: DB at 0100_crm_leads with N-1 image head 0008_account_security → 503 {"migrations":"behind"} (label also wrong: DB is ahead)
- **Affected files:** `api/veda/platform/health.py`, `api/veda/config.py`
- **Requirement IDs:** OPS-004, LOG-005, 02 §12.4, 11 §2 B3
- **Root cause:** Readiness required DB revision == image head exactly, so the N-1 image on a migrated schema was never ready (and the state was mislabelled 'behind').
- **Remediation:** Readiness distinguishes head, behind (known older revision: not ready), ahead (revision unknown to the image and declared expand-only compatible by the operator in VEDA_SCHEMA_AHEAD_ACCEPTED: ready) and ahead_undeclared (not ready). Downgrade stays refused; the rollback boundary is documented in the runbook.
- **Tests:** `api/tests/integration/test_ops_remediation.py (head, N-1 image with and without declaration, behind, divergent, downgrade refused and schema unchanged)`
- **Architecture amendment required:** Yes — AM-6 (LOG-005, 08 §3, 02 §12.4); DEV-008
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED — AMENDMENT PENDING OWNER DECISION — RG-7 rollback rehearsal not executed (production gate).
- **Re-review required:** Targeted

### IR-11 · MAJOR · Backup (Litestream config, nightly snapshot), restore verification and API deploy/migrate runbooks are absent from the deliverable

- **Reviewer evidence (SOURCE-INSPECTED):** api/deploy/docker-compose.yml references /etc/veda/litestream.yml which is not in the repository; No VACUUM INTO / snapshot job and no restore-verification job anywhere in api/ (grep); deployment.md covers only the marketing site; no API runbooks (11 §8); Implementation report §16/§17 acknowledge these gates were not executed
- **Affected files:** `api/deploy/litestream.yml`, `api/deploy/docker-compose.yml`, `api/deploy/deploy.sh`, `api/veda/platform/backups.py`, `api/veda/cli/main.py`, `docs/operations/api-runbooks.md`
- **Requirement IDs:** OPS-002, OPS-004, OPS-005, OPS-007, OPS-009, RG-1, RG-2, RG-7
- **Root cause:** Litestream config, snapshot job, restore verification, deploy/migrate automation and API runbooks were absent.
- **Remediation:** Committed: Litestream config (env-parameterised bucket/retention, metrics port), compose wiring with digest-pinned image, nightly VACUUM INTO snapshot job with manifest checksum and optional Object Lock upload, automated restore-verification job (checksum, integrity_check, foreign_key_check, schema revision, conformance, security chain), disk-usage metric, deploy.sh implementing 02 §12.4 (pre-flight, snapshot, quiesce, migrate, ready gate, resume; rollback mode), and the API runbooks (deploy/migrate, rollback, disaster restore, restore verification, key rotation, break-glass, incident, alerts).
- **Tests:** `api/tests/integration/test_backups.py (snapshot, restore verification pass/fail/no snapshot, pruning, disk metric)`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** PARTIALLY RESOLVED — RG-1, RG-2 and RG-7 (replication, restore and rollback rehearsals on the real host) not executed; RPO/RTO owner input (OWNER-INPUT-001) pending.
- **Re-review required:** Operational readiness review

### IR-12 · MAJOR · No metrics, no alert routing, error tracker optional (LOG-006 is mandatory in P0)

- **Reviewer evidence (SOURCE-INSPECTED):** No metrics emission anywhere in api/veda (grep); Alerts are stdlib log lines: maintenance.py:265,343,345,406; security_events.py:311; worker.py:97; Sentry DSN not required in production (config.py validate_production); Implementation report OI-7
- **Affected files:** `api/veda/kernel/metrics.py`, `api/veda/kernel/logging.py`, `api/veda/platform/notifications/worker.py`, `api/veda/platform/maintenance.py`, `api/veda/platform/auth/security_events.py`, `api/veda/config.py`
- **Requirement IDs:** LOG-004, LOG-006, OPS-009, SEVT-009, RG-5
- **Root cause:** No metrics were emitted, alerts were stdlib log lines only, and Sentry was optional in production.
- **Remediation:** CloudWatch Embedded Metric Format on log lines: request count/latency by templated route and status class, security events by type and outcome, writer failures, outbox depth/age/dead, chain verification and anchor failures, governance invariant failures, snapshot/restore results, disk usage. Sentry DSN required in production (with scrubbing, IR-27). Alarm definitions and routing documented in the runbook.
- **Tests:** `api/tests/unit/test_logging_pii.py`; `api/tests/integration/test_backups.py`; `api/tests/integration/test_chain_integrity.py`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** PARTIALLY RESOLVED — CloudWatch agent/alarms/SNS routing are deployment configuration; RG-5 test-fire not executed.
- **Re-review required:** Operational readiness review

### IR-13 · MAJOR · Runtime Python dependencies are open ranges with no lockfile or hashes; container base image floats

- **Reviewer evidence (SOURCE-INSPECTED; drift REPRODUCED (ruff format count 83 vs reported 82 under ruff 0.16.9; resolved SQLAlchemy 2.1.1, Flask-Limiter 4.1.1)):** api/requirements.txt — 10 of 14 packages have no upper bound; no lock/constraints file; no hashes; api/deploy/Dockerfile — floating python:3.13-slim and pip install -r requirements.txt at build time; .github/workflows/ci.yml:26 — CI installs a different set from requirements-dev.txt; Implementation report records no resolved package versions
- **Affected files:** `api/requirements.in`, `api/requirements.txt`, `api/requirements-dev.in`, `api/requirements-dev.txt`, `api/deploy/Dockerfile`, `api/deploy/docker-compose.yml`, `.github/workflows/ci.yml`
- **Requirement IDs:** SEC-007, OPS-001, PLAT-008, 11 §5 X11
- **Root cause:** Open version ranges, no lock, no hashes; floating base image; CI installed a different set.
- **Remediation:** requirements.in/requirements-dev.in keep the declared ranges; requirements.txt (41 packages) and requirements-dev.txt (84) are pip-compile hash locks. CI and the image install with --require-hashes; the image uses python:3.13-slim pinned by digest and Litestream is pinned by digest; pip-audit runs on the lock.
- **Tests:** `.github/workflows/ci.yml (install --require-hashes, pip-audit on the lock, Trivy image scan)`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** Yes / Yes / Yes
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-14 · MAJOR · CI workflow has never executed and omits PR gates required by 12 §5 (types, N-1 test, OpenAPI diff, dependency/image/secret scan, E2E smoke + axe)

- **Reviewer evidence (SOURCE-INSPECTED):** .github/workflows/ci.yml:1-49 — api job: ruff check, pytest, deploy-check; app job: typecheck, lint:tokens, contrast, unit tests, build; docs/architecture/12-test-strategy.md:342-348 — PR gates list types, migration N-1 test, OpenAPI diff, dependency + image scan, secret scan, E2E smoke + axe; Implementation report OI-9: 'CI workflow was written but not executed'; api/veda/cli/main.py:226-231 — deploy-check is a substring match on the gunicorn config (probe: GUNICORN_CMD_ARGS=--workers=4 still reports OK)
- **Affected files:** `.github/workflows/ci.yml`, `api/tools/mypy_ratchet.py`, `api/tools/openapi_check.py`, `api/openapi.snapshot.json`, `api/tools/secret_scan.sh`, `.secrets.baseline`, `app/e2e/run-all.sh`
- **Requirement IDs:** OPS-001, DATA-011, SEC-007, 12 §5
- **Root cause:** The workflow never ran (triggers: PRs and main only) and lacked the 12 §5 gates.
- **Remediation:** CI runs on pushes to implementation/** and PRs. Jobs: api (SQLite and PostgreSQL 16 service: ruff, ruff format --check, mypy ratchet, full pytest incl. N-1 migration and conformance, OpenAPI diff, deploy-check), security (secret scan against the reviewed baseline, pip-audit, bandit medium+, npm audit, image build + Trivy), app (ESLint, typecheck, token lint, contrast, unit tests, build), e2e (workspace, access, site, axe on a live stack). Actions pinned to commit SHAs. Every job is mandatory.
- **Tests:** `First CI run on the pushed remediation commit (see the report for its result)`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** Yes / Yes / Yes
- **Status:** RESOLVED
- **Re-review required:** Yes (evidence: CI run URL)

### IR-15 · MAJOR · Lead edit 'Re-apply mine' after a version conflict silently reverts the other writer's committed changes

- **Reviewer evidence (REPRODUCED (browser probe + audit log); source confirmed by lead reviewer):** app/src/modules/leads/lead-form.ts:153-181 — on reapply, saveEdit(values, {...original, ...fresh}, fresh.version) diffs the entire stale form against fresh, so every field the other user changed is sent with its old value; Probe: other client PATCHes city/priority; UI user edits only message and re-applies → server city/priority reverted; audit changed_fields [city, message, priority]
- **Affected files:** `app/src/modules/leads/lead-form.ts`, `app/src/modules/leads/edits.ts`
- **Requirement IDs:** UI-005, DATA-006, 12 §4.12 TD-F step 4 ('no data loss'), 09 §3.2
- **Root cause:** Re-apply diffed the whole stale form against the fresh record, sending every field the other writer changed back with its old value.
- **Remediation:** The user's own edits are computed once against the record as loaded; re-apply sends exactly those against the fresh version.
- **Tests:** `app/test/leads-logic.test.ts (3 tests)`; `app/e2e/access.e2e.mjs: conflict re-apply keeps the other writer's changes (TD-F step 4)`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-16 · MAJOR · DEV-004 staff re-consent overwrites consent evidence, mixes provenance and is accepted without prior withdrawal

- **Reviewer evidence (REPRODUCED):** api/veda/modules/crm/leads/service.py:462-468 — re-consent overwrites consent_* in the row and clears withdrawal fields; api/veda/modules/crm/leads/schemas.py:48-50,95 — staff may choose channel WEBSITE_FORM; Probe P3: after re-consent row shows channel=PHONE_VERBAL with original website ip and source_page retained; Probe: three consecutive re-consent PATCHes without withdrawal all 200; original survives only in audit_log UPDATE old_value; SALES /history → 403; Probe P3b: SALES with OWN scope re-consents a withdrawn lead (200); no system activity/timeline entry, reason=None; Deviation register claims a lead-drawer UI control; app/src contains none
- **Affected files:** `api/veda/modules/crm/leads/service.py`, `api/veda/modules/crm/leads/schemas.py`, `api/veda/modules/crm/leads/activities.py`
- **Requirement IDs:** LEAD-012, LEAD-024, LEAD-027, 04 §5.4, 08 §8.5, ADR-005
- **Root cause:** Re-consent overwrote the row's consent evidence, kept web provenance for staff captures, allowed WEBSITE_FORM, needed no reason and wrote no timeline entry.
- **Remediation:** DEV-004 corrected: staff channels only (WEBSITE_FORM refused, also on staff create); a note is required; accepted only after withdrawal, when never captured, or for a new published notice version (else 409); the superseded evidence is written first to a read-only system activity (consent_evidence, visible in the timeline to anyone who can read the lead) and remains in audit_log; the new capture carries no web IP or source page. Erasure blanks the note.
- **Tests:** `api/tests/integration/test_consent_dev004.py (13 tests: provenance, history, refusal without withdrawal, new version, WEBSITE_FORM/note/policy validation, raw fields and public re-consent rejected, staff create, scope, duplicate detection, audit immutability, erasure)`
- **Architecture amendment required:** Yes — AM-4 (04 §5.4 vs 08 §8.5; in-row + timeline activity vs a dedicated append-only table)
- **Merge / staging / production blocker (reviewer):** Yes / Yes / Yes
- **Status:** RESOLVED — AMENDMENT PENDING OWNER DECISION
- **Re-review required:** Yes (DEV-004)

### IR-17 · MAJOR · Enquiry form remains visible after success/fallback ([hidden] overridden by .contact-form{display:grid}); resubmission reports a false failure

- **Reviewer evidence (REPRODUCED; CSS source confirmed by lead reviewer):** dist/assets/app.js:122-123 — contactForm.hidden = true; dist/assets/styles.css (pre-existing) — .contact-form{display:grid} with no [hidden] override; Probe: after 201 the form computes display:grid (737 px) beside the success panel; resubmitting → 422 IDEMPOTENCY_KEY_REUSED → 'Something went wrong on our side' while the lead is stored; app/e2e/site.e2e.mjs:38-41 — success check does not assert the form is hidden
- **Affected files:** `dist/assets/enhancements.css`, `app/e2e/site.e2e.mjs`
- **Requirement IDs:** LEAD-001, LEAD-019, 09 §4.11, AX-08
- **Root cause:** [hidden] lost to .contact-form{display:grid}.
- **Remediation:** [hidden] rules win for the form, panels and form children; the site E2E asserts the form is hidden after success and after fallback.
- **Tests:** `app/e2e/site.e2e.mjs checks 5 and 7`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / No · public-intake feature gate
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-18 · MAJOR · Turnstile token is never reset; after any server-side 422 the corrected resubmission reuses a spent token and fails CAPTCHA

- **Reviewer evidence (SOURCE-INSPECTED (precondition REPRODUCED: server-side field 422 after client validation passes)):** api/veda/modules/crm/leads/routes.py:69,72-74 — CAPTCHA verified before validation, consuming the single-use token; dist/assets/app.js:135,175 — client re-reads the same widget response; no turnstile.reset() anywhere; 'no-widget' sent when absent
- **Affected files:** `dist/assets/app.js`, `app/e2e/site.e2e.mjs`
- **Requirement IDs:** LEAD-001, LEAD-019, 04 §5.1, 02 §2 intake step 3
- **Root cause:** The Turnstile widget was never reset after a non-201 and 'no-widget' was submitted when absent.
- **Remediation:** Widget id tracked; reset after every non-201 and on network failure; no submission without a token (fallback instead); intake runs only when both the API base and the site key are set.
- **Tests:** `app/e2e/site.e2e.mjs check 3 (server 422 → reset → corrected 201)`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / No · public-intake feature gate
- **Status:** RESOLVED — A run with the real Cloudflare test keys is part of intake enablement.
- **Re-review required:** Targeted

### IR-19 · MAJOR · SPA route changes never update the document title nor move focus/announce navigation (WCAG 2.4.2 Level A)

- **Reviewer evidence (REPRODUCED):** app/index.html:8 — static <title>; no document.title assignment in app/src; app/src/shell/app.ts:91-94 — location change only updates pathname; <main id=outlet tabindex=-1> (app.ts:185) is never focused
- **Affected files:** `app/src/core/router/routes.ts`, `app/src/shell/app.ts`
- **Requirement IDs:** UI-011, UI-016 (AX-01), 09 §5
- **Root cause:** Static document title; location changes did not move focus or announce.
- **Remediation:** Per-route titles; after in-app navigation focus moves to the page h1 (or the main region) and the page name is announced in a polite live region.
- **Tests:** `app/test/router.test.ts (route titles)`; `app/e2e/access.e2e.mjs: route change updates the title and moves focus`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED — Manual NVDA/VoiceOver script is a production gate.
- **Re-review required:** Targeted

### IR-20 · MINOR · Path C (emailed enrollment link + password) replaces an existing ACTIVE factor without step-up by that factor; open enrollment links survive enrollment by another path

- **Reviewer evidence (REPRODUCED):** api/veda/platform/auth/mfa.py:222-239 — path C never checks for an ACTIVE factor; mfa.py enroll_confirm does not invalidate open MFA_ENROLLMENT tokens; Probe P2/P2b: factor REPLACED while ACTIVE; old link valid after path-A enrollment (200)
- **Affected files:** `api/veda/platform/auth/mfa.py`, `api/veda/platform/auth/service.py`
- **Requirement IDs:** MFA-014, 05 §11.3, DEV-001
- **Root cause:** Path C did not check for an ACTIVE factor and confirm did not end other enrollment links.
- **Remediation:** Path C start refuses (409 MFA_ALREADY_ENROLLED) when an ACTIVE factor exists, and re-checks at confirm; any confirm invalidates open MFA_ENROLLMENT links and enrollment transactions.
- **Tests:** `api/tests/integration/test_auth_remediation.py::test_IR20_*`
- **Architecture amendment required:** No (AM-1 condition)
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-21 · MINOR · Resending an invitation does not revoke earlier invite_context challenges; link replay mints parallel contexts and overwrites the password

- **Reviewer evidence (REPRODUCED):** api/veda/platform/rbac/users.py:95-109 — resend invalidates INVITE tokens only; api/veda/platform/auth/service.py:511-516 — each MFA-path accept creates a new ENROLLMENT challenge; Probe P3: old invite_context after resend → start 200 → confirm 200 AUTHENTICATED ACTIVE
- **Affected files:** `api/veda/platform/auth/service.py`, `api/veda/platform/rbac/users.py`, `api/veda/platform/auth/mfa.py`
- **Requirement IDs:** AUTH-011, MFA-014, DEV-002
- **Root cause:** Resend and repeated acceptance left earlier invite contexts live.
- **Remediation:** Each MFA-path acceptance and each resend ends every open enrollment context and PENDING factor; path B also requires a live INVITE token at start and confirm.
- **Tests:** `api/tests/integration/test_auth_remediation.py::test_IR21_P3_resend_revokes_earlier_invitation_contexts`; `api/tests/integration/test_mfa_binding.py::test_IR01_invitation_context_is_single_account_and_unauthenticated`
- **Architecture amendment required:** No (AM-2 condition)
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-22 · MINOR · IPv6 /64 network grouping is string-based and breaks on compressed addresses, defeating per-network throttle and CAPTCHA and causing false global lockouts

- **Reviewer evidence (REPRODUCED):** api/veda/kernel/http.py:152-158 and kernel/logging.py:57-63 — ':'.join(ip.split(':')[:4]); Probe P4: 12 failures from one /64 never set captcha_required; account globally throttled instead
- **Affected files:** `api/veda/kernel/net.py`, `api/veda/kernel/http.py`, `api/veda/kernel/logging.py`, `api/veda/kernel/ratelimit.py`
- **Requirement IDs:** AUTH-010, SEC-011, DEV-003
- **Root cause:** Networks were computed by splitting strings, so compressed IPv6 forms of one /64 looked different.
- **Remediation:** ipaddress-based /24 and /64 grouping (IPv4-mapped IPv6 treated as IPv4); the per-IP limiter keys IPv6 clients by /64.
- **Tests:** `api/tests/integration/test_auth_remediation.py::test_IR22_*`
- **Architecture amendment required:** No (AM-3 condition)
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-23 · MINOR · Certified 5/min per-email login limit lets anyone lock a known account out from every network

- **Reviewer evidence (REPRODUCED):** api/veda/platform/auth/routes.py:43-44; kernel/ratelimit.py:20-26 — key is email only; Probe P5: five requests from another network → victim's own login 429
- **Affected files:** `api/veda/kernel/ratelimit.py`
- **Requirement IDs:** AUTH-010, SEC-011, 05 §4 A-01, 08 §12
- **Root cause:** The certified per-email login limit is keyed on the email alone.
- **Remediation:** The per-email limits (login 5/min, forgot 3/hour) are keyed on (email, client network); the per-account throttles of 05 §4 still bound distributed guessing.
- **Tests:** `api/tests/integration/test_auth_remediation.py::test_IR23_P5_third_party_cannot_rate_limit_the_victim_from_elsewhere`
- **Architecture amendment required:** Yes — AM-7 (08 §12); DEV-007
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED — AMENDMENT PENDING OWNER DECISION
- **Re-review required:** Targeted

### IR-24 · MINOR · Password re-entry (reauth) and change-password are not throttled; password guessing with a stolen bearer then satisfies password-based step-up

- **Reviewer evidence (SOURCE-INSPECTED):** api/veda/platform/auth/service.py:462-470, 489-495 — no throttle.record_password_failure / account counter
- **Affected files:** `api/veda/platform/auth/throttle.py`, `api/veda/platform/auth/service.py`
- **Requirement IDs:** AUTH-010, MFA-011
- **Root cause:** reauth and change-password failures were not counted.
- **Remediation:** 10 failures per account in 15 minutes throttle both for 15 minutes (429, ACCOUNT_THROTTLED scope reauth).
- **Tests:** `api/tests/integration/test_auth_remediation.py::test_IR24_reauth_and_change_password_guessing_is_throttled`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-25 · MINOR · Security-event gaps: no event on MFA-path invite password set, invalid action tokens, CSRF-rejected refresh, MFA throttle and per-network throttle activation; erasure refusal event rolled back

- **Reviewer evidence (SOURCE-INSPECTED; erasure part REPRODUCED):** api/veda/platform/auth/service.py:511-516, 186-194; api/veda/platform/auth/routes.py:49-51; api/veda/platform/auth/throttle.py:70-77,111-121 (return value ignored at mfa.py:110,140,273,338); api/veda/modules/crm/leads/service.py:665-668 — record() then raise; probe P6: 0 ERASURE_BLOCKED events persisted
- **Affected files:** `api/veda/platform/auth/service.py`, `api/veda/platform/auth/routes.py`, `api/veda/platform/auth/mfa.py`, `api/veda/modules/crm/leads/service.py`
- **Requirement IDs:** AUTH-013, MFA-006, SEVT-002, SEVT-011, LEAD-029
- **Root cause:** Several failure paths wrote no event; the erasure refusal used record() and was rolled back.
- **Remediation:** INVITE_ACCEPTED (stage password_set) on the MFA path; FAILURE events for invalid, reused or expired single-use links (per purpose); TOKEN_REFRESH FAILURE on CSRF rejection; ACCOUNT_THROTTLED on MFA, network-pair and reauth throttle activation; ERASURE refusal deferred so it survives.
- **Tests:** `api/tests/integration/test_auth_remediation.py::test_IR25_*`; `api/tests/integration/test_leads.py (erasure blocked)`
- **Architecture amendment required:** No (AM-2 condition)
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-26 · MINOR · Security-log archival deletes events it never exported when event time and chain order disagree near the cutoff

- **Reviewer evidence (REPRODUCED):** api/veda/platform/maintenance.py:303-304 selects occurred_on < cutoff; :327 deletes chain_seq <= last.chain_seq; Probe Q3 (both engines): row exported? False; still in DB? False; verify ok=True
- **Affected files:** `api/veda/platform/maintenance.py`
- **Requirement IDs:** SEVT-004, AUDIT-009
- **Root cause:** Archival selected by event time but deleted by chain sequence.
- **Remediation:** Archive the contiguous chain-sequence prefix whose rows are all older than the cutoff, verify the segment, record its manifest in the anchor store, delete exactly that range and compare counts.
- **Tests:** `api/tests/integration/test_chain_integrity.py::test_IR26_*`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-27 · MINOR · Unhandled exceptions and DB errors log raw PII (stdlib loggers bypass structlog masking; engine lacks hide_parameters)

- **Reviewer evidence (REPRODUCED):** api/veda/kernel/logging.py:30-43 — scrub applies only to structlog events; api/veda/app.py:134-137 — log.exception on stdlib logger; api/veda/kernel/db.py:56-64 — create_engine without hide_parameters=True; Probe Q6: forced NOT NULL violation on public intake logs enquirer name, email and message; api/veda/app.py:58-62 — Sentry initialised without before_send scrubbing
- **Affected files:** `api/veda/kernel/logging.py`, `api/veda/kernel/db.py`, `api/veda/app.py`
- **Requirement IDs:** LOG-001, LOG-003, SEC-009
- **Root cause:** stdlib loggers bypassed masking, exceptions logged messages with row values, the engine logged bound parameters and Sentry had no scrubbing.
- **Remediation:** All stdlib records go through the masked JSON formatter; exceptions are logged as type, fingerprint and stack frames (no message); engines use hide_parameters=True; Sentry uses before_send scrubbing, no local variables and no request bodies.
- **Tests:** `api/tests/unit/test_logging_pii.py (Q6 failing-row message, stdlib arguments, structlog exception, Sentry event, hide_parameters)`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-28 · MINOR · An erased (anonymised) lead still accepts notes, activities and status changes, re-introducing PII after erasure is reported complete

- **Reviewer evidence (REPRODUCED):** api/veda/modules/crm/leads/activities.py:32-37,101-127; service.py:479-537 — no anonymized_on check; Probe P4: note with phone 201, activity with email 201, NEW→CONTACTED 200 while allowed_transitions=[]
- **Affected files:** `api/veda/modules/crm/leads/routes.py`
- **Requirement IDs:** LEAD-029, AUDIT-011, NOTE-001, ACT-001
- **Root cause:** No write route checked anonymized_on.
- **Remediation:** Every lead, note and activity write on an erased lead answers 409 INVALID_STATE.
- **Tests:** `api/tests/integration/test_leads_remediation.py::test_IR28_P4_erased_lead_refuses_every_write`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-29 · MINOR · Plain-text staff notification emails can be content-spoofed via newlines in public form fields

- **Reviewer evidence (REPRODUCED):** api/veda/kernel/dto.py:31 — strip_controls keeps \n\r\t; api/veda/modules/crm/leads/events.py:35-57 — public name/city flow into text part; Probe: forged 'Open the lead:' line above the genuine link; HTML part escaped correctly
- **Affected files:** `api/veda/kernel/dto.py`, `api/veda/modules/crm/leads/service.py`, `api/veda/modules/crm/leads/events.py`, `api/veda/platform/notifications/templates/lead_notification.v1.jinja`
- **Requirement IDs:** NOTIF-005
- **Root cause:** Single-line public fields kept line breaks, which plain-text email rendered verbatim.
- **Remediation:** Names, city and locality are collapsed to one line at intake and in the notification summary; the text part labels the value.
- **Tests:** `api/tests/integration/test_leads_remediation.py::test_IR29_*`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-30 · MINOR · Outbox retry resends email to recipients who already received it

- **Reviewer evidence (REPRODUCED):** api/veda/platform/notifications/worker.py:78-79; Probe P5: sends [u1, u2, u1, u2]
- **Affected files:** `api/veda/platform/notifications/worker.py`
- **Requirement IDs:** NOTIF-004, 02 §10.1
- **Root cause:** A retry re-sent every email of the event.
- **Remediation:** Each delivered message is recorded on the event (hash of template and recipients); a retry skips delivered messages.
- **Tests:** `api/tests/integration/test_leads_remediation.py::test_IR30_P5_retry_does_not_resend_delivered_email`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-31 · MINOR · UNKNOWN_POLICY_VERSION is shown as an inline field error with no WhatsApp route

- **Reviewer evidence (SOURCE-INSPECTED):** dist/assets/app.js:198-201
- **Affected files:** `dist/assets/app.js`
- **Requirement IDs:** LEAD-019, 04 §5.1
- **Root cause:** UNKNOWN_POLICY_VERSION was treated as a field error.
- **Remediation:** It now shows the WhatsApp fallback with a reload prompt.
- **Tests:** `app/e2e/site.e2e.mjs check 6`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / No · public-intake feature gate
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-32 · MINOR · Enquiry-form prerequisites absent: /privacy page missing, no site CSP, Turnstile site key unset, showErrors() uses innerHTML with server strings, #form-note contrast 4.06:1

- **Reviewer evidence (REPRODUCED):** dist/index.html:179 links /privacy (not present); dist/_headers has no Content-Security-Policy (pre-existing); dist/assets/app.js:94-105 innerHTML sink (not exploitable today: messages are static server literals); #form-note #746e66 on #f1e5d7 = 4.06:1 (needs 4.5:1)
- **Affected files:** `dist/assets/app.js`, `dist/index.html`, `dist/assets/enhancements.css`, `dist/_headers`, `app/e2e/static-server.mjs`
- **Requirement IDs:** LEAD-001, SEC-003, SEC-009, AX-05, AX-08, OI-5
- **Root cause:** Prerequisites for intake were absent and the summary used innerHTML.
- **Remediation:** Error summary built with DOM nodes and textContent; #form-note 5.76:1; site Content-Security-Policy added and verified in the browser (0 violations in both modes); consent block, Turnstile container and the Privacy Notice link appear only when intake is enabled, so the flag-off site shows no link to the missing page.
- **Tests:** `app/e2e/site.e2e.mjs (flag-off hides consent/link, no CSP violations)`; `app/e2e/axe.e2e.mjs (form scope: 0 serious)`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / No · public-intake feature gate
- **Status:** PARTIALLY RESOLVED — Privacy Notice page (v2026-09-v1) and the Turnstile site key are owner/legal inputs; intake stays disabled until both exist.
- **Re-review required:** Yes (intake enablement)

### IR-33 · MINOR · PostgreSQL immutability guard is bypassable (user-settable GUC veda.maintenance, no TRUNCATE trigger) and app/retention roles are never provisioned

- **Reviewer evidence (REPRODUCED):** api/veda/kernel/migration_support.py:327-351, 387-403; PG16.4 probe: TRUNCATE succeeded; SET LOCAL veda.maintenance='on' + DELETE removed 206 audit rows; non-owner role with GUC succeeded
- **Affected files:** `api/veda/kernel/migration_support.py`
- **Requirement IDs:** 07 §6.2, AUDIT-004, SEVT-006, DATA-014
- **Root cause:** GUC bypass and no TRUNCATE trigger on PostgreSQL.
- **Remediation:** Not changed in this workstream: PostgreSQL release gate (PGM-1) item.
- **Tests:** `—`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / No · PostgreSQL release gate
- **Status:** OPEN — TRACKED — Before PGM-1: BEFORE TRUNCATE trigger, role-based bypass, provisioned roles.
- **Re-review required:** Yes (PG gate)

### IR-34 · MINOR · Historical migrations import the live permission registry and role matrix, so freshly built environments drift from upgraded ones

- **Reviewer evidence (SOURCE-INSPECTED):** api/veda/kernel/migration_support.py:165-167, 204-206; api/veda/cli/main.py:101-107 — sync-permissions does not sync role_permission
- **Affected files:** `api/veda/kernel/migration_support.py`, `api/migrations/versions/0003_rbac.py`
- **Requirement IDs:** PLAT-005, RBAC-018, OPS-004
- **Root cause:** Historical migrations import the live registry.
- **Remediation:** Not changed: post-production follow-up; required before the first registry change.
- **Tests:** `—`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / No
- **Status:** OPEN — TRACKED
- **Re-review required:** No

### IR-35 · MINOR · Single-process/instance constraint is enforced only by a text match on gunicorn.conf.py; client IP trusted from CF-Connecting-IP without a trusted-proxy check

- **Reviewer evidence (REPRODUCED):** api/veda/cli/main.py:226-231 — probe: GUNICORN_CMD_ARGS=--workers=4 → 'deploy-check: OK'; api/veda/kernel/http.py:146-149; kernel/ratelimit.py:17 — CF-Connecting-IP trusted unconditionally
- **Affected files:** `api/veda/kernel/net.py`, `api/veda/kernel/single_instance.py`, `api/deploy/gunicorn.conf.py`, `api/veda/cli/main.py`, `api/veda/config.py`
- **Requirement IDs:** OPS-006, OPS-010, RG-3, RG-6, SEC-006, AUTH-010
- **Root cause:** deploy-check was a text match; CF-Connecting-IP was trusted from any peer.
- **Remediation:** CF-Connecting-IP only from VEDA_TRUSTED_PROXY_CIDRS peers (required in staging/production); deploy-check evaluates the effective gunicorn config including GUNICORN_CMD_ARGS; the on_starting hook enforces one gthread worker and takes an exclusive lock beside the database.
- **Tests:** `api/tests/unit/test_single_instance.py`; `api/tests/integration/test_auth_remediation.py::test_IR35_*`; `api/tests/unit/test_config_environments.py`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED — The proxy/tunnel address is a deployment input (RG-3, RG-6 on the real host).
- **Re-review required:** Targeted

### IR-36 · MINOR · 'Sign out everywhere' leaves the user on /profile with stale personal data displayed

- **Reviewer evidence (REPRODUCED):** app/src/modules/auth/profile-page.ts:198 — session.logout(true) without navigate('/login')
- **Affected files:** `app/src/modules/auth/profile-page.ts`
- **Requirement IDs:** UI-015, AUTH-007
- **Root cause:** logout(true) without navigation.
- **Remediation:** Navigates to /login.
- **Tests:** `app/e2e/access.e2e.mjs: "Sign out everywhere" lands on sign-in`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED
- **Re-review required:** Targeted

### IR-37 · MINOR · Accessibility gaps: 360 px status stepper not keyboard-scrollable (axe serious), unreliable toast announcements, no MFA-timeout warning, window.prompt for sensitive reason, incomplete listbox/menu/tab semantics

- **Reviewer evidence (REPRODUCED):** app/src/design-system/components.ts:36,147; app/src/modules/admin/user-drawer.ts:264; app/src/shell/app.ts:171-181
- **Affected files:** `app/src/design-system/components.ts`, `app/src/shell/app.ts`, `app/src/modules/auth/mfa-pages.ts`, `app/src/core/auth/session.ts`, `app/src/modules/admin/user-drawer.ts`
- **Requirement IDs:** UI-011, UI-016 (AX-03, AX-06, AX-07, AX-09)
- **Root cause:** Five separate accessibility gaps.
- **Remediation:** Stepper is a focusable labelled region; toasts use persistent live regions created at start-up; the MFA challenge warns one minute before expiry and states expiry; window.prompt replaced by an inline reason form; the account menu uses disclosure semantics and returns focus on Escape.
- **Tests:** `app/e2e/axe.e2e.mjs (10 screens, 0 serious)`; `typecheck/ESLint`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** RESOLVED — Manual screen-reader script and Firefox/WebKit/200 % zoom checks are production gates.
- **Re-review required:** Targeted

### IR-38 · MINOR · Browser E2E evidence overstates coverage and security-critical modules have the lowest coverage

- **Reviewer evidence (REPRODUCED):** app/e2e/access.e2e.mjs:90-91 — 'API 401/403' check sends no bearer (proves 401 only); :102-103 hard-codes reloadSignedOut = true; Chromium-only; no forgot/reset, approvals, email-change, role-edit or TD-F step-4 journeys; Coverage (SQLite, branch): total 85%; rbac/governance.py 73%, kernel/ratelimit.py 57%, identity/service.py 74%; No existing test exercised cross-user enroll/confirm (IR-01), Founder DELETE (IR-08) or STANDARD→Founder TOCTOU (IR-04)
- **Affected files:** `app/e2e/access.e2e.mjs`, `app/e2e/site.e2e.mjs`, `app/e2e/axe.e2e.mjs`, `app/e2e/run-all.sh`
- **Requirement IDs:** 12 §4.8, 12 §6, OPS-001
- **Root cause:** Two checks asserted nothing; missing journeys and negative tests.
- **Remediation:** 403 proven with a real Sales token (and 401 without); reload check measured; logout proven by a refused refresh; journeys added for TD-F step 4, cancel link, sign-out-everywhere and route focus; negative suites for IR-01/04/08 added; E2E runs in CI.
- **Tests:** `app/e2e/*.mjs (47 checks)`; `api/tests/integration/test_mfa_binding.py`; `api/tests/integration/test_governance_remediation.py`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / No / Yes
- **Status:** PARTIALLY RESOLVED — Firefox and WebKit legs (12 §4.8 browser matrix) not added.
- **Re-review required:** Targeted

### IR-39 · MINOR · No Python formatter or type checker enforced, no ESLint/Prettier; frontend dev toolchain carries dev-only advisories (upgrade needs Node ≥ 20.19)

- **Reviewer evidence (REPRODUCED):** ruff format --check: 83 files would be reformatted (report says 82; unpinned ruff); No mypy configuration; no ESLint/Prettier binaries or config; npm audit (configured Nexus feed): 195 advisories (JSON metadata 19 critical / 5 high / 171 low; text summary says 17 critical); public GHSA feed: 7 (6 high, 1 moderate: esbuild via vite 5.4.21, extract-zip via @web/test-runner); --omit=dev: 0 in both feeds
- **Affected files:** `api/pyproject.toml`, `api/tools/mypy_ratchet.py`, `api/tools/mypy-baseline.json`, `app/package.json`, `app/package-lock.json`, `app/eslint.config.js`, `app/.nvmrc`, `app/.npmrc`
- **Requirement IDs:** SEC-007, 12 §5, OI-8, OI-10
- **Root cause:** No enforced formatter, type checker or ESLint; dev toolchain pinned below the advisory fixes.
- **Remediation:** ruff format applied and enforced; mypy configured and enforced as a ratchet (157 pre-existing Optional-narrowing findings recorded per file, none new allowed); ESLint (typescript-eslint, lit, wc, unsafe-HTML and sink bans); Node 22 LTS, Vite 7.3, Web Test Runner 1.0; npm audit 0 (full and runtime) on the public registry; lockfile regenerated against registry.npmjs.org.
- **Tests:** `CI app and api jobs`
- **Architecture amendment required:** No
- **Merge / staging / production blocker (reviewer):** No / Yes / Yes
- **Status:** RESOLVED — mypy backlog of 157 findings tracked for burn-down (OI-RM-3).
- **Re-review required:** No

## Advisories

| ID | Reviewer note | Status | Remediation / tracking |
|---|---|---|---|
| IR-A01 | PostgreSQL concurrency: refresh rotation, recovery-code consumption and challenge attempt counting are read-then-write without row locks/conditional updates (safe on SQLite via BEGIN IMMEDIATE) — auth/service.py:358-374, mfa.py:70-88,133-147. Fix before PGM-1. | OPEN — TRACKED | PostgreSQL release gate (PGM-1): row locks/conditional updates for refresh rotation, recovery codes and attempt counting. Enrollment confirmation already takes a row lock (IR-01). |
| IR-A02 | Login timing delta ≈1.2–1.6 ms known vs unknown account (extra post-request write) — auth/service.py:266-283. | OPEN — TRACKED | Accepted residual (~1.5 ms); revisit with the P1 breached-password work. |
| IR-A03 | Refresh/logout CSRF origin allow-list includes public-site origins (auth/service.py:334); mitigated by CORS preflight; tighten to app_origin. | RESOLVED | Refresh/logout CSRF origin check accepts only the workspace origin (test_auth_remediation.py::test_IRA03_*). |
| IR-A04 | Password reset does not invalidate open MFA challenges / enrollment links (auth/service.py:443-459). | RESOLVED | Password reset ends open MFA challenges and enrollment transactions (test_auth_remediation.py::test_IRA04_*). |
| IR-A05 | Startup route-declaration check is presence-only; RBX ids/paths not validated against the 06 §11 register; public route with a permission would be silently unenforced (app.py:41-49, http.py:69-70,465-474). No current route affected. | RESOLVED | Startup validates RBX exceptions against the 06 §11 register and refuses permissions on public routes (test_lint.py::test_IRA05_*). |
| IR-A06 | PATCH /roles/{id} lacks a self-held-role check and accepts mfa_required (not in 08 §6.1) — rbac/roles.py:70-89. | OPEN — OWNER DECISION REQUIRED | PATCH /roles self-held-role check and the mfa_required field (not in 08 §6.1) need an owner decision; unchanged. |
| IR-A07 | Approval deny/cancel emit no SENSITIVE_ACTION; invite with sensitive role sends no rbac.sensitive_grant email; approve/deny return 403 where GET returns 404 (existence oracle). | PARTIALLY RESOLVED | SENSITIVE_ACTION now recorded on deny and cancel (test_governance_remediation.py::test_IRA07_*). The 403-vs-404 existence oracle is required by 08 §4 / 12 TD-G G9 and was left unchanged pending an owner decision. Invite-with-sensitive-role email not added. |
| IR-A08 | 08 §12 per-user 600 req/5 min limit not implemented; token endpoints unthrottled (entropy makes brute force infeasible). | OPEN — TRACKED | 08 §12 per-user 600 req/5 min limit not implemented. |
| IR-A09 | HMAC/action/chain keys have no minimum-length check in production (config.py:212-219). Folded into IR-09 remediation. | RESOLVED | Folded into IR-09 (≥32-byte keys). |
| IR-A10 | Cancel-link binding depends on outbox_event rows surviving retention purge (<3 days breaks live links, fail closed). | OPEN — TRACKED | Cancel-link binding still relies on outbox rows; recorded in AM-5 (retention must exceed the break-glass window; retention is unset, so nothing is purged today). |
| IR-A11 | A hostile sole Founder can repeatedly cancel custodian break-glass (architecture residual of 06 §7.5; needs owner decision). | OPEN — OWNER DECISION REQUIRED | AM-9. |
| IR-A12 | Client-supplied X-Request-ID / CF-Ray adopted as request_id; fine for correlation, not trustworthy as evidence (http.py:133-143). | OPEN — TRACKED | Accepted: client X-Request-ID/CF-Ray are correlation ids, not evidence; documented. |
| IR-A13 | Turnstile siteverify hostname/action not checked (turnstile.py:42). | RESOLVED | siteverify must report one of our hostnames (test_config_environments.py::test_IRA13_*). |
| IR-A14 | DEAD outbox rows alert only via log.error; /health ignores DEAD; erasure-audit job lacks per-event failure handling (worker.py:97,122-126; maintenance.py:161-207). | PARTIALLY RESOLVED | DEAD outbox count is a metric, an ERROR log and a readiness degraded signal (never failing readiness); erasure-audit per-event failure handling unchanged. |
| IR-A15 | IP/user-agent retained in audit_log/security_event_log after lead erasure; several free-text fields not in pii_fields (07 §2 gap). | OPEN — OWNER DECISION REQUIRED | AM-10. |
| IR-A16 | PostgreSQL concurrent duplicate Idempotency-Key returns 409 instead of the original 201 (lead stored once). | OPEN — TRACKED | PostgreSQL release gate. |
| IR-A17 | /health/ready publicly exposes migration/guard/outbox state (health.py:36-62). | RESOLVED | Readiness returns check details only to direct local callers (test_ops_remediation.py::test_IRA17_*); DEV-008. |
| IR-A18 | No SQLite format CHECK on UTCDATETIME columns; three CODE(n) columns lack enum CHECKs (event_type, failure_reason, status_reason). | OPEN — TRACKED | Additional SQLite CHECKs are a schema change; post-production follow-up. |
| IR-A19 | sync-permissions CLI labels audit rows performed_via=MIGRATION (migration_support.py:117). | RESOLVED | sync-permissions CLI audit rows are labelled CLI. |
| IR-A20 | TOTP AES-GCM AAD is constant (crypto.py:120,128); bind to user_id‖factor_id. | OPEN — TRACKED | Binding AES-GCM AAD to user_id‖factor_id needs a re-encryption migration; tracked. |
| IR-A21 | App CSP: styleMap first render raises one style-src-attr violation (components.ts:291); production sourcemaps published (vite.config.ts:8); e2e scripts import undeclared playwright/axe-core. | RESOLVED | styleMap replaced by a CSSOM binding, production source maps off, playwright/axe-core declared. |
| IR-A22 | HMAC-derived action tokens (OI-3): acceptable; residual — K_action compromise plus row ids yields every live link; document in 05/03. | OPEN — OWNER DECISION REQUIRED | AM-8. |
| IR-A23 | WhatsApp fallback URL carries enquirer PII to wa.me (pre-existing, user-initiated); mention in Privacy Notice. | OPEN — OWNER DECISION REQUIRED | Privacy Notice content (owner/legal). |
| IR-A24 | 18 pre-existing public-site contrast nodes outside the form (OI-11); highest priority .portfolio-head > p at 2.40:1. | OPEN — TRACKED | 18 pre-existing marketing-site contrast nodes, tracked (OI-11). |
| IR-A25 | Implementation report/register accuracy: DEV-004 claims a UI control that does not exist; ruff format count 82 vs 83; npm critical count 17 (text) vs 19 (JSON); PostgreSQL 16 not executed by the author (now reproduced by this review). | RESOLVED | Report and register corrected (DEV-004 UI claim removed, counts restated from command output). |

## Review open issues OI-1..OI-11

| OI | Review assessment | Remediation status |
|---|---|---|
| OI-1 | Deviations DEV-001…DEV-004 need an architecture decision (MAJOR) | Decisions recorded (reviewer); DEV-004 corrected; DEV-005 registered; owner decisions pending (AM-1..AM-5, AM-11). |
| OI-2 | Break-glass cancel-link not in 08 index (MAJOR) | Page added and E2E-tested; AM-5 pending. |
| OI-3 | HMAC-derived single-use action tokens (ADVISORY) | AM-8 proposed. |
| OI-4 | No legal-hold data model; erasure blocking via env var (MINOR) | Unchanged; owner/legal decision. |
| OI-5 | Privacy Notice missing; Turnstile site key and site CSP not configured (MINOR (feature-gated)) | Site CSP added and verified; Privacy Notice and site key outstanding; intake disabled. |
| OI-6 | AWS adapters (SES, KMS, S3 Object Lock anchor) untested (MAJOR (production)) | Stubbed-client tests for the S3 anchor store; staging verification of SES/KMS/S3 pending. |
| OI-7 | Alerts are log lines; unseen-network enrollment alert missing (MAJOR (production)) | Metrics emitted (EMF); alarms/routing are deployment steps; unseen-network enrollment alert not implemented. |
| OI-8 | No formatter/type checker; no ESLint (MINOR) | Resolved (ruff format, mypy ratchet, ESLint). |
| OI-9 | Browser E2E not in CI; CI never executed (MAJOR) | CI workflow with every gate; first run on the pushed commit. |
| OI-10 | Dev toolchain advisories; upgrade needs Node ≥ 20.19 (MINOR) | Resolved (Node 22, Vite 7.3, WTR 1.0; npm audit 0). |
| OI-11 | Pre-existing public-site contrast (19 nodes) (ADVISORY (18) / MINOR (#form-note)) | #form-note fixed; 18 marketing nodes tracked. |

## Gates

Merge, staging and production blockers as listed by the review (§18), with their state after this remediation, are in [P0-open-issues.md](P0-open-issues.md).
