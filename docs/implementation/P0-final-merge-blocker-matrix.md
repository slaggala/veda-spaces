# P0 final merge-blocker remediation matrix

Targeted re-review: review/p0-independent-implementation-review @ 15d25a759cfc0342bdca45ba4a9c51550270f305 (verdict NOT CERTIFIED; IR-01 RESOLVED; no BLOCKER). Previous head `2f6b59a0a6a59dbc41a597dddc7e6512dcd581fe`. Branch `implementation/p0-foundation`.

> Every RR finding, RR advisory, non-resolved reconciliation item and owner decision is listed; none is downgraded (severities are the reviewer's). 'RESOLVED' means fixed in code with regression tests at this commit; it is not a certification, and the final targeted independent check decides. Nothing here approves an amendment, completes a gate, or authorizes merge or deployment.

> Owner decisions use the numbering of the remediation brief: OD-1 = re-review OD-1 + OD-2 (amendments; AM-7 rejected as written), OD-2 = re-review OD-3 (deleted-Founder restore), OD-3 = execution-time revalidation (new, RR-03), OD-4 = re-review OD-4 (TG-01, TG-08), OD-5 = re-review OD-5 (merge = site deploy). Re-review OD-6…OD-8 are unchanged and not decided.

## Findings

| ID | Severity | Status | Merge | Staging | Production | Amendment | Owner decision |
|---|---|---|---|---|---|---|---|
| [RR-01](#rr-01) | MAJOR | RESOLVED (verified locally; CI and final targeted check pending) | Cleared by the fix | Cleared | Cleared | No | No |
| [RR-02](#rr-02) | MAJOR | RESOLVED — AMENDMENT AM-12 PENDING OWNER DECISION | Cleared by the fix (OD-2 implemented); AM-12 decision pending | Cleared | Cleared | AM-12 (06 §7.2.2) | OD-2 given; AM-12 approval pending |
| [RR-03](#rr-03) | MAJOR | RESOLVED — AMENDMENT AM-13 PENDING OWNER DECISION | Cleared by the fix (OD-3 implemented); AM-13 decision pending | Cleared | Cleared | AM-13 (06 §7.4, 05 §8.6) | OD-3 given; AM-13 approval pending |
| [RR-04](#rr-04) | MAJOR | RESOLVED — AMENDMENT AM-7 (REWRITTEN) PENDING OWNER DECISION | Cleared by the fix; AM-7 decision pending | Real Turnstile keys and deployed proxy CIDR to be verified | Alarm on escalation to be configured (RG-5) | AM-7 (rewritten), DEV-007 | OD-1: AM-7 rejected as written; new AM-7 PROPOSED |
| [RR-05](#rr-05) | MAJOR | RESOLVED IN CODE — STAGING EVIDENCE (S3 OBJECT LOCK, WRITER/VERIFIER ROLES) REQUIRED | None | Real S3 Object Lock and role separation to be evidenced | Blocks until staging evidence | No | No |
| [RR-06](#rr-06) | MAJOR | RESOLVED IN CODE — STAGING EVIDENCE REQUIRED BEFORE ARCHIVAL IS ENABLED | None | Archival stays disabled until OWNER-INPUT-002 | Staging archival run required | No | No |
| [RR-07](#rr-07) | MAJOR | RESOLVED IN CODE — ALARM WIRING (RG-5) REQUIRED IN STAGING | None | Alarm acceptance (RG-5) | RG-5 | No | No |
| [RR-08](#rr-08) | MAJOR | RESOLVED | None | Cleared | Cleared | No | No |
| [RR-09](#rr-09) | MAJOR | OPEN — PRODUCTION BLOCKER (OWNER DECISION OD-6) | None | Rehearsal | Blocks (PG-BG) | 06 §7.5 wording (minor) | Re-review OD-6 (not decided) |
| [RR-10](#rr-10) | MINOR | RESOLVED | None | Cleared | Cleared | No | No |
| [RR-11](#rr-11) | MINOR | RESOLVED (verified locally; CI and final targeted check pending) | Cleared by the fix | Cleared | Cleared | No | No |
| [RR-12](#rr-12) | MINOR | OPEN — PRODUCTION BLOCKER | None | None | Blocks | AM-4 | AM-4 option (a)/(b) |
| [RR-13](#rr-13) | MINOR | OPEN — PRODUCTION BLOCKER | None | None | Blocks | AM-10 | Re-review OD-7 |
| [RR-14](#rr-14) | MINOR | RESOLVED IN CODE — STAGING DEPLOY EVIDENCE REQUIRED | None | Staging deploy evidence | Cleared after staging | No | No |
| [RR-15](#rr-15) | MINOR | OPEN — STAGING BLOCKER | None | Blocks (RG-1, RG-2) | Blocks | No | No |
| [RR-16](#rr-16) | MINOR | RESOLVED | None | Cleared | Cleared | No | No |
| [RR-17](#rr-17) | MINOR | RESOLVED IN CODE AND DOCUMENTATION — RG-7 REHEARSAL REQUIRED | None | RG-7 rehearsal | Blocks until RG-7 | AM-6, AM-11 | OD-1 (AM-6, AM-11) |
| [RR-18](#rr-18) | MINOR | OPEN — PRODUCTION BLOCKER | None | None | Blocks | No | No |

### RR-01

**MAJOR** — Site-wide CSP blocks the 404 page's inline stylesheet; because a push to main deploys dist/ to www.vedaspaces.com, merging ships a broken 404 page to production

| Field | Value |
|---|---|
| Evidence (re-review) | dist/_headers:2 — style-src 'self' https://fonts.googleapis.com (no 'unsafe-inline', no hash), applied to /*; dist/404.html:15-44 — inline <style> block, unchanged since 778aa8f; sha256-nsu5zW5KZLyHAh1E42iLcu9GL6H14jnCxGdJDe3Q5v4=; Chromium: style-src-elem violation on /404.html, /no-such-page and /privacy; page renders unstyled; 778aa8f renders correctly; README.md:43-45 and deployment.md:31 — a push to main deploys dist/ to production within a minute; site e2e checks CSP on index.html only (missed this) |
| Root cause | The 404 page kept an inline <style> block while the site CSP (style-src 'self' fonts) applies to every path; the site E2E checked only index.html. |
| Files changed | dist/404.html; dist/assets/404.css (new); app/e2e/site.e2e.mjs; app/e2e/axe.e2e.mjs |
| Requirements affected | SEC-003; Public site availability; deployment.md release checklist |
| Remediation | Styles moved verbatim to /assets/404.css; copper and footer text darkened to meet WCAG AA contrast (axe found 4 pre-existing contrast failures once the page rendered). No CSP directive changed; no unsafe-inline, hash or nonce added. Browser tests load /no-such-page (HTTP 404), /404.html and /privacy under the exact _headers and assert computed styles, zero inline style/script/handlers, 0 CSP violations, a single column at 360 px, keyboard focus ring, and that the homepage still loads its stylesheet; axe scans the 404 page. |
| Regression tests | app/e2e/site.e2e.mjs (404 cases, homepage check); app/e2e/axe.e2e.mjs ('404 page') |
| Amendment needed | No |
| Owner decision | No |
| Re-review blocking scope | merge (merge = production site deploy) |
| Merge impact | Cleared by the fix |
| Staging impact | Cleared |
| Production impact | Cleared |
| Status | RESOLVED (verified locally; CI and final targeted check pending) |
| Note | Real Cloudflare Pages preview not exercised; the static server applies _headers the same way (merge-safety plan §2). |

### RR-02

**MAJOR** — A single Founder can restore a Founder deleted through dual-Founder approval (G11 bypass; no governance record)

| Field | Value |
|---|---|
| Evidence (re-review) | api/veda/platform/rbac/users.py:253-262 — restore_user applies only G9 (passes Founder→Founder); no G3, no G11, no InvariantGuard, no security event; api/veda/platform/rbac/guards.py:176-192 — deleted Founder keeps FOUNDER user_role and protection_level; P11/N11: F1+F2 delete F3 (EXECUTED); F1 alone POST /users/{F3}/restore → 200; F3 back as DISABLED FOUNDER-protected account |
| Root cause | restore_user applied only G9, which passes Founder→Founder; deleted Founders keep FOUNDER protection and role, and no Founder-governed restore existed. |
| Files changed | api/veda/platform/rbac/users.py; api/veda/platform/rbac/governance.py; api/veda/platform/rbac/routes.py; app/src/modules/admin/founder-actions-page.ts; app/src/modules/admin/user-drawer.ts; api/openapi.snapshot.json |
| Requirements affected | RBAC-020; RBAC-021; 06 §7.1 G9/G11; 06 §7.2.2; 06 §7.2.6 |
| Remediation | OD-2 implemented: generic restore applies G3 and G11 (403 FOUNDER_PROTECTED + FOUNDER_GOVERNANCE_BYPASS_BLOCKED); FOUNDER_STATUS_CHANGE status=RESTORE via the canonical workflow (requester ≠ approver ≠ target, one decision, eligibility at request/approval/execution, execution re-validates deleted state and address, invariants re-checked); refused on single-Founder and custodian break-glass (SECOND_FOUNDER_REQUIRED). Audited (approver as actor) and security-logged (REQUESTED/APPROVED/TRANSITION RESTORE/EXECUTED). Generic status/unlock/roles/permissions/Founder actions address only live accounts (404). SPA: restore action on the Founder actions page; drawer links there for Founders. |
| Regression tests | api/tests/integration/test_final_merge_blockers.py::test_RR02_P11_single_founder_cannot_restore_a_deleted_founder; api/tests/integration/test_final_merge_blockers.py::test_RR02_generic_endpoints_cannot_restore_a_founder; api/tests/integration/test_final_merge_blockers.py::test_RR02_two_distinct_founders_restore_through_the_workflow; api/tests/integration/test_final_merge_blockers.py::test_RR02_single_eligible_founder_cannot_use_break_glass_to_restore; api/tests/integration/test_final_merge_blockers.py::test_RR02_custodian_break_glass_cannot_restore_a_founder; api/tests/integration/test_final_merge_blockers.py::test_RR02_revoked_approver_or_requester_eligibility_blocks_execution; api/tests/integration/test_final_merge_blockers.py::test_RR02_stale_restore_fails_closed; api/tests/integration/test_final_merge_blockers.py::test_RR02_concurrent_restore_requests_and_approvals; api/tests/integration/test_final_merge_blockers.py::test_RR02_standard_restore_unchanged_and_audited |
| Amendment needed | AM-12 (06 §7.2.2) |
| Owner decision | OD-2 given; AM-12 approval pending |
| Re-review blocking scope | merge (Founder-governance invariant; same class as IR-04) |
| Merge impact | Cleared by the fix (OD-2 implemented); AM-12 decision pending |
| Staging impact | Cleared |
| Production impact | Cleared |
| Status | RESOLVED — AMENDMENT AM-12 PENDING OWNER DECISION |

### RR-03

**MAJOR** — An executed STANDARD email change stays pending through GRANT_FOUNDER and can be verified on the new Founder

| Field | Value |
|---|---|
| Evidence (re-review) | api/veda/platform/rbac/governance.py:160-178,325 — only open STANDARD requests are cancelled on GRANT_FOUNDER; proposed_email is never cleared (no reference in governance.py); api/veda/platform/auth/service.py:887-923 — verify_email_change has no protection-level check; N17: ADMIN email change of ADMIN a2 executed → a2 promoted → anonymous POST /auth/email/verify 204 → Founder email = attacker address |
| Root cause | Only open STANDARD requests were cancelled on promotion; an executed request's email proposal persisted and verification had no governance check. |
| Files changed | api/veda/platform/rbac/governance.py; api/veda/platform/rbac/users.py; api/veda/platform/auth/service.py; api/veda/platform/rbac/guards.py; api/veda/kernel/db.py |
| Requirements affected | RBAC-020; USER-007; 06 §7.1 G11; 06 §7.2.2 FOUNDER_EMAIL_CHANGE |
| Remediation | OD-3 implemented: governance classes (STANDARD_CONTROL < DUAL_CONTROL < FOUNDER_GOVERNANCE); any class increase (GRANT_FOUNDER, roles, permissions) cancels open STANDARD requests (for Founders) and clears a pending non-self email proposal with its links, recording EMAIL_CHANGE_CANCELLED with reason and class transition; verification recomputes the proposal's authorising class (self / direct / EMAIL_CHANGE / FOUNDER_EMAIL_CHANGE) against the current class and refuses weaker authorisation or a disabled account (EMAIL_CHANGE_VERIFIED FAILURE, FOUNDER_GOVERNANCE_BYPASS_BLOCKED). Founder-level and break-glass requests re-validate the target at execution (existing, now tested for status and post-approval changes). Password reset and invitation acceptance already re-check account status; MFA reset executes atomically at approval under standard_still_permitted. Concurrency: verification takes the governance lock before touching rows, and on PostgreSQL a unit of work that has written nothing takes its single clock reading when it acquires the governance lock, so rows it updates are never stamped before rows committed by the transaction it waited for (found by the clean PostgreSQL run: a CheckViolation on user_action_token and a deadlock-driven 503 under concurrent promotion; fixed and looped 20× clean). |
| Regression tests | api/tests/integration/test_final_merge_blockers.py::test_RR03_N17_executed_standard_email_change_cannot_complete_after_promotion; api/tests/integration/test_final_merge_blockers.py::test_RR03_verify_fails_closed_even_without_the_cleanup; api/tests/integration/test_final_merge_blockers.py::test_RR03_standard_change_withdrawn_when_target_becomes_privileged; api/tests/integration/test_final_merge_blockers.py::test_RR03_privilege_via_role_definition_is_caught_at_verification; api/tests/integration/test_final_merge_blockers.py::test_RR03_self_and_founder_workflow_changes_still_complete; api/tests/integration/test_final_merge_blockers.py::test_RR03_mfa_reset_request_before_promotion_fails_closed; api/tests/integration/test_final_merge_blockers.py::test_RR03_founder_status_request_recalculated_when_target_changes; api/tests/integration/test_final_merge_blockers.py::test_RR03_approved_break_glass_recalculated_at_execution; api/tests/integration/test_final_merge_blockers.py::test_RR03_concurrent_promotion_and_verification; api/tests/integration/test_governance_remediation.py::test_IR04_* |
| Amendment needed | AM-13 (06 §7.4, 05 §8.6) |
| Owner decision | OD-3 given; AM-13 approval pending |
| Re-review blocking scope | merge (Founder-governance invariant) |
| Merge impact | Cleared by the fix (OD-3 implemented); AM-13 decision pending |
| Staging impact | Cleared |
| Production impact | Cleared |
| Status | RESOLVED — AMENDMENT AM-13 PENDING OWNER DECISION |

### RR-04

**MAJOR** — DEV-007 keys per-email login/forgot limits by (email, network), removing the only cross-network bound on password guessing for MFA holders and multiplying reset-email volume

| Field | Value |
|---|---|
| Evidence (re-review) | api/veda/kernel/ratelimit.py:22-33 — key email\|network; api/veda/platform/auth/service.py:407 — global lock applies only when the user has no factor (throttle.py:6-9); api/veda/platform/auth/service.py:464-473 — a correct password returns MFA_REQUIRED (password oracle); Probe: 40 guesses in one minute from 8 IPv6 /64s all evaluated (baseline: 5 then 429); 18 reset emails delivered vs 3 |
| Root cause | DEV-007 keyed the only per-email limits by network, and the certified global lock exempts MFA holders; nothing bounded cross-network guessing or reset-email volume. |
| Files changed | api/veda/platform/auth/throttle.py; api/veda/platform/auth/service.py; api/veda/kernel/ratelimit.py; api/veda/kernel/net.py; api/veda/platform/auth/routes.py; api/veda/config.py |
| Requirements affected | AUTH-010; SEC-011; 05 §4; 08 §12 |
| Remediation | Layered limiter (AM-7 rewritten): source IP and wide-network (/24, /48) limits; per-(email HMAC, network) limits kept (IR-23); account budget across networks (10 failures → Turnstile on every attempt, 20 → escalating spacing to 30 s, 429), not reset by success; aggregate escalation (200/5 min); ≤ 3 reset emails per account per hour; endpoint limits on MFA verify/recovery, enroll confirm, email verify/cancel; trusted proxies ≤ /24 or /64; tables capped at 50 000 keys; hashed identifiers only. Provider failure fails closed for escalated identifiers. |
| Regression tests | api/tests/integration/test_layered_limiter.py; api/tests/integration/test_auth_remediation.py::test_IR23_P5_third_party_cannot_rate_limit_the_victim_from_elsewhere; api/tests/unit/test_config_environments.py |
| Amendment needed | AM-7 (rewritten), DEV-007 |
| Owner decision | OD-1: AM-7 rejected as written; new AM-7 PROPOSED |
| Re-review blocking scope | merge (unapproved deviation that weakens authentication) / production |
| Merge impact | Cleared by the fix; AM-7 decision pending |
| Staging impact | Real Turnstile keys and deployed proxy CIDR to be verified |
| Production impact | Alarm on escalation to be configured (RG-5) |
| Status | RESOLVED — AMENDMENT AM-7 (REWRITTEN) PENDING OWNER DECISION |

### RR-05

**MAJOR** — A forged archive manifest written with the host credential hides deletion of any prefix of the security-event chain, including anchored rows

| Field | Value |
|---|---|
| Evidence (re-review) | api/veda/platform/maintenance.py:339-438 — verification trusts any manifest; no contiguity check, no export-file hash check, no SECURITY_LOG_ARCHIVED event correlation; Probe C11: manifest first_seq=1,last_seq=anchor+1 with dummy hash and nonexistent file, then delete rows → verify ok=True; Export file stays on local disk, not in Object Lock storage |
| Root cause | Verification trusted any archive manifest: no contiguity, export-hash or announcement check; exports lived only on the host. |
| Files changed | api/veda/platform/maintenance.py; api/veda/platform/anchor_store.py; api/veda/platform/auth/security_events.py |
| Requirements affected | SEVT-006; SEVT-007; 05 §9.6 |
| Remediation | Exports are written to the write-once store; verification accepts only finalised manifests that are contiguous from 1, match their export (SHA-256, count, range), whose exported rows recompute (HMAC chain from the previous segment to last_row_hash), that match any anchor inside the archived range, and that are announced by a SECURITY_LOG_ARCHIVED event (online or in a later export). An unreadable store is a verification failure. |
| Regression tests | api/tests/integration/test_archive_ordering.py::test_RR05_C11_forged_manifest_without_export_is_detected; api/tests/integration/test_archive_ordering.py::test_RR05_forged_export_that_drops_rows_is_detected; api/tests/integration/test_archive_ordering.py::test_RR05_unannounced_manifest_is_detected; api/tests/integration/test_archive_ordering.py::test_RR05_forgery_through_the_s3_store_is_detected; api/tests/integration/test_archive_ordering.py::test_RR05_genuine_archives_verify_through_the_s3_store; api/tests/integration/test_chain_integrity.py |
| Amendment needed | No |
| Owner decision | No |
| Re-review blocking scope | production (SEVT-006/007 claim) |
| Merge impact | None |
| Staging impact | Real S3 Object Lock and role separation to be evidenced |
| Production impact | Blocks until staging evidence |
| Status | RESOLVED IN CODE — STAGING EVIDENCE (S3 OBJECT LOCK, WRITER/VERIFIER ROLES) REQUIRED |
| Note | A host attacker holding the chain key can still recompute exports for rows after the latest anchor; anchoring cadence bounds this window (documented). |

### RR-06

**MAJOR** — Archival writes the write-once manifest before the database commit; any later failure produces a permanent false 'prefix removed' alarm and blocks archival forever

| Field | Value |
|---|---|
| Evidence (re-review) | api/veda/platform/maintenance.py:441-514 — manifest stored before DB delete/commit; Probe C12: simulated DB failure after manifest → verify reports prefix removed; re-archive refused |
| Root cause | The write-once manifest was written before the database transaction; a later failure left a manifest for rows still online. |
| Files changed | api/veda/platform/maintenance.py; api/veda/platform/anchor_store.py |
| Requirements affected | SEVT-004; SEVT-006; AUDIT-009 |
| Remediation | Two-phase ordering: export + pending manifest (idempotent writes) → DB transaction (announcement + delete) → final manifest. Pending manifests whose rows are online are ignored (no false alarm); committed-but-unfinalised shows as 'archive not finalised' (alarmed) and is repaired by the next run. SecurityLogArchivedRows / SecurityLogArchiveFailed metrics. |
| Regression tests | api/tests/integration/test_archive_ordering.py::test_RR06_C12_database_failure_after_the_pending_manifest_is_not_an_alarm; api/tests/integration/test_archive_ordering.py::test_RR06_failure_after_commit_is_alarmed_and_repaired; api/tests/integration/test_archive_ordering.py::test_RR06_anchor_store_outage_during_verification_is_a_failure |
| Amendment needed | No |
| Owner decision | No |
| Re-review blocking scope | production (before archival is enabled; archival refuses without OWNER-INPUT-002) |
| Merge impact | None |
| Staging impact | Archival stays disabled until OWNER-INPUT-002 |
| Production impact | Staging archival run required |
| Status | RESOLVED IN CODE — STAGING EVIDENCE REQUIRED BEFORE ARCHIVAL IS ENABLED |

### RR-07

**MAJOR** — CLI, scheduler and worker processes never configure logging, so every maintenance/worker metric (backup, chain, anchor, invariants, dead outbox) is dropped and the scheduler ignores job exit codes

| Field | Value |
|---|---|
| Evidence (re-review) | api/veda/app.py:111 — configure_logging is called only from create_app; no CLI path calls it; api/veda/cli/main.py (cmd_scheduler) — subprocess.run([...maintenance, job], check=False); exit codes discarded; Probe: disk-usage, snapshot, restore-verify, verify-chain, invariants → 0 EMF metric lines; anchor-store outage → verify raises with no event, metric or CRITICAL; Tests pass only because they run in-process with logging configured |
| Root cause | configure_logging was called only by create_app; CLI processes dropped EMF lines, and the scheduler discarded exit codes. |
| Files changed | api/veda/cli/main.py; api/veda/platform/maintenance.py |
| Requirements affected | LOG-006; OPS-009; SEVT-009; RG-5 |
| Remediation | _settings() configures JSON logging for every CLI subcommand (worker, scheduler, maintenance, break-glass); maintenance jobs catch exceptions → CRITICAL + MaintenanceJobFailed{Job}=1, exit 1, and emit MaintenanceJobFailed=0 on success; the scheduler runs jobs through run_scheduled_job (timeout 1 h) and emits ScheduledJobFailed{Job} with the exit code logged; verify-chain turns store errors into a recorded failure. Runbook §9 alarms updated. |
| Regression tests | api/tests/integration/test_archive_ordering.py::test_RR07_cli_jobs_emit_their_metrics; api/tests/integration/test_archive_ordering.py::test_RR07_failing_job_exits_non_zero_with_an_alarm_metric; api/tests/integration/test_archive_ordering.py::test_RR07_scheduler_records_exit_codes |
| Amendment needed | No |
| Owner decision | No |
| Re-review blocking scope | staging (alarm acceptance) / production (RG-5) |
| Merge impact | None |
| Staging impact | Alarm acceptance (RG-5) |
| Production impact | RG-5 |
| Status | RESOLVED IN CODE — ALARM WIRING (RG-5) REQUIRED IN STAGING |

### RR-08

**MAJOR** — Path A enrollment confirm retires the session's refresh tokens without a successor link, so a benign concurrent refresh is treated as token theft and revokes the just-elevated session

| Field | Value |
|---|---|
| Evidence (re-review) | api/veda/platform/auth/mfa.py:447-463 — _rotate_refresh sets used_on, never replaced_by_id; api/veda/platform/auth/service.py:588-610 — the 20 s grace window requires a linked successor; api/veda/platform/auth/service.py:728-741 — change_password has the same pattern |
| Root cause | Path-A confirm and change_password retired refresh tokens with used_on only; the grace window requires replaced_by_id. |
| Files changed | api/veda/platform/auth/service.py; api/veda/platform/auth/mfa.py |
| Requirements affected | AUTH-005; 05 §6.1 |
| Remediation | auth.service.rotate_session_refresh issues the successor first and links every retired live token of that session to it; used by path-A confirm and change_password. Only the rotating session is touched; no token material in events. |
| Regression tests | api/tests/integration/test_final_merge_blockers.py::test_RR08_path_a_enrollment_keeps_the_grace_window; api/tests/integration/test_final_merge_blockers.py::test_RR08_reuse_after_the_window_is_still_theft; api/tests/integration/test_final_merge_blockers.py::test_RR08_rotation_only_touches_the_rotating_session; api/tests/integration/test_final_merge_blockers.py::test_RR08_concurrent_refresh_yields_a_single_successor; api/tests/integration/test_auth.py::test_AUTH_005_* |
| Amendment needed | No |
| Owner decision | No |
| Re-review blocking scope | production |
| Merge impact | None |
| Staging impact | Cleared |
| Production impact | Cleared |
| Status | RESOLVED |

### RR-09

**MAJOR** — Break-glass STS identity check sees the host instance role, not the custodian, when the CLI runs via docker compose as the runbook prescribes; with no credentials it crashes without a failure event

| Field | Value |
|---|---|
| Evidence (re-review) | api/veda/platform/rbac/custodians.py:22-25 — default boto3 credential chain; api/deploy/deploy.sh:24-35 and docs/operations/api-runbooks.md:94-95 — CLI run inside the api container; N06: instance-role ARN → 403 not a registered custodian; no credentials → uncaught NoCredentialsError |
| Root cause | Default boto3 credential chain inside the container sees the instance role; NoCredentialsError uncaught. |
| Files changed | — |
| Requirements affected | RBAC-021; 06 §7.5 items 2 and 4; PG-BG |
| Remediation | Not changed in this workstream: needs the custodian credential model (re-review OD-6 / OWNER-INPUT-004) and a staging rehearsal with CloudTrail. |
| Regression tests | — |
| Amendment needed | 06 §7.5 wording (minor) |
| Owner decision | Re-review OD-6 (not decided) |
| Re-review blocking scope | production (PG-BG) |
| Merge impact | None |
| Staging impact | Rehearsal |
| Production impact | Blocks (PG-BG) |
| Status | OPEN — PRODUCTION BLOCKER (OWNER DECISION OD-6) |

### RR-10

**MINOR** — Environment validation accepts trusted-proxy CIDR 0.0.0.0/0 or ::/0, all-zero / dev-derived / duplicate 32-byte keys, and an unparsable JWT PEM

| Field | Value |
|---|---|
| Evidence (re-review) | api/veda/config.py:288-292, 332-341 |
| Root cause | Environment validation parsed CIDRs and key lengths only. |
| Files changed | api/veda/config.py; api/tests/unit/test_config_environments.py |
| Requirements affected | SEC-005; SEC-006; AUTH-010 |
| Remediation | Staging/production refuse trusted-proxy entries broader than /24 or /64, keys that are constant or two-symbol fillers, development-derived keys, duplicate keys, and a JWT key that is not an unencrypted P-256 private key. |
| Regression tests | api/tests/unit/test_config_environments.py::test_IR09_each_missing_or_weak_setting_is_reported |
| Amendment needed | No |
| Owner decision | No |
| Re-review blocking scope | staging |
| Merge impact | None |
| Staging impact | Cleared |
| Production impact | Cleared |
| Status | RESOLVED |

### RR-11

**MINOR** — With intake disabled the enquiry form is novalidate and skips client validation, so an empty submit opens WhatsApp with a blank enquiry (baseline 778aa8f blocked it)

| Field | Value |
|---|---|
| Evidence (re-review) | dist/index.html:168 (novalidate), :173-174 (required removed); dist/assets/app.js:166-169 |
| Root cause | Flag-off submit skipped clientValidate and opened WhatsApp directly. |
| Files changed | dist/assets/app.js; app/e2e/site.e2e.mjs; app/e2e/axe.e2e.mjs |
| Requirements affected | LEAD-019; Public site behaviour |
| Remediation | Validation runs before every hand-off (consent only when intake is enabled): name ≥ 2 characters; phone of digits and + ( ) - . space with 10–15 digits; optional email format. Errors: aria-invalid fields, per-field messages and a focused role=alert summary; values preserved. The WhatsApp text uses only trimmed visitor fields and option labels, URL-encoded; no honeypot, consent or API configuration. |
| Regression tests | app/e2e/site.e2e.mjs (flag-off: empty, missing name, missing phone, invalid phone, too-short phone, valid with special characters, keyboard Enter, mobile 360 px, no API call); app/e2e/axe.e2e.mjs ('website form, intake off (error state)') |
| Amendment needed | No |
| Owner decision | No |
| Re-review blocking scope | merge (ships to the live site on merge; cheap fix) |
| Merge impact | Cleared by the fix |
| Staging impact | Cleared |
| Production impact | Cleared |
| Status | RESOLVED (verified locally; CI and final targeted check pending) |

### RR-12

**MINOR** — DEV-004 residuals: alternating between published policy versions is accepted without withdrawal; consent history activity is mutable at DB level; staff create-time consent needs no note and writes no consent activity

| Field | Value |
|---|---|
| Evidence (re-review) | api/veda/modules/crm/leads/service.py:837, 552-556 |
| Root cause | DEV-004 residuals. |
| Files changed | — |
| Requirements affected | LEAD-012; LEAD-027 |
| Remediation | Not changed; AM-4 now states the target behaviour and the gap explicitly. |
| Regression tests | — |
| Amendment needed | AM-4 |
| Owner decision | AM-4 option (a)/(b) |
| Re-review blocking scope | production |
| Merge impact | None |
| Staging impact | None |
| Production impact | Blocks |
| Status | OPEN — PRODUCTION BLOCKER |

### RR-13

**MINOR** — Residual PII paths: Sentry transaction events carry request query strings (e.g. lead search by email); outbox_event.last_error stores provider errors containing recipient emails

| Field | Value |
|---|---|
| Evidence (re-review) | api/veda/app.py:117-125 (traces_sample_rate with before_send only); api/veda/platform/notifications/worker.py:119 |
| Root cause | Sentry transactions and outbox last_error carry PII. |
| Files changed | — |
| Requirements affected | LOG-003; SEC-009 |
| Remediation | Not changed; folded into AM-10 decision scope. |
| Regression tests | — |
| Amendment needed | AM-10 |
| Owner decision | Re-review OD-7 |
| Re-review blocking scope | production |
| Merge impact | None |
| Staging impact | None |
| Production impact | Blocks |
| Status | OPEN — PRODUCTION BLOCKER |

### RR-14

**MINOR** — Snapshot directory defaults to container storage and is not required in staging/production, so deploy.sh's pre-deploy snapshot in a --rm container is lost

| Field | Value |
|---|---|
| Evidence (re-review) | api/deploy/deploy.sh; api/veda/config.py (snapshot dir) |
| Root cause | Snapshot dir defaulted to container storage. |
| Files changed | api/veda/config.py; docs/operations/api-runbooks.md |
| Requirements affected | OPS-002; OPS-004 |
| Remediation | Staging/production require an absolute VEDA_SNAPSHOT_DIR inside the SQLite database volume; the pre-deploy snapshot therefore lands on the persistent volume. |
| Regression tests | api/tests/unit/test_config_environments.py (VEDA_SNAPSHOT_DIR cases) |
| Amendment needed | No |
| Owner decision | No |
| Re-review blocking scope | staging |
| Merge impact | None |
| Staging impact | Staging deploy evidence |
| Production impact | Cleared after staging |
| Status | RESOLVED IN CODE — STAGING DEPLOY EVIDENCE REQUIRED |

### RR-15

**MINOR** — Disaster-restore runbook does not work as written: restore-verify fails on a Litestream-restored file, Litestream is not stopped before the swap, one failure path emits no metric, the off-host replica is never verified

| Field | Value |
|---|---|
| Evidence (re-review) | docs/operations/api-runbooks.md §3; api/veda/platform/backups.py |
| Root cause | Disaster-restore runbook gaps. |
| Files changed | docs/operations/api-runbooks.md |
| Requirements affected | OPS-005; OPS-009; RG-1; RG-2 |
| Remediation | Runbook §3 references the gaps; restore-verify for Litestream files, stopping replication before the swap and replica verification are not implemented. |
| Regression tests | — |
| Amendment needed | No |
| Owner decision | No |
| Re-review blocking scope | staging |
| Merge impact | None |
| Staging impact | Blocks (RG-1, RG-2) |
| Production impact | Blocks |
| Status | OPEN — STAGING BLOCKER |

### RR-16

**MINOR** — mypy ratchet fails open: reports '0 errors OK' when mypy is missing or its config is broken; --update silently admits errors from new or renamed files

| Field | Value |
|---|---|
| Evidence (re-review) | api/tools/mypy_ratchet.py; api/tools/mypy-baseline.json (24 files, 157 errors) |
| Root cause | The ratchet counted errors from stdout without checking that mypy ran, and --update rewrote the baseline from current counts. |
| Files changed | api/tools/mypy_ratchet.py; api/tests/unit/test_mypy_ratchet.py |
| Requirements affected | 12 §5 types gate |
| Remediation | Fails closed (exit 2) when mypy is missing, crashes or rejects its config, when fewer source files are checked than the package holds, when the exit code and findings disagree, or when the baseline is malformed or exceeds the reviewed CEILING (157); fails on new/renamed/worse files and on broad suppressions (bare type: ignore, mypy: ignore-errors, ignore_errors / disable_error_code). --update refuses in CI, never admits or raises entries, and prints every change. |
| Regression tests | api/tests/unit/test_mypy_ratchet.py |
| Amendment needed | No |
| Owner decision | No |
| Re-review blocking scope | staging (CI gate integrity) |
| Merge impact | None |
| Staging impact | Cleared |
| Production impact | Cleared |
| Status | RESOLVED |

### RR-17

**MINOR** — Rollback documentation gaps: rollback of this release to 9236aa3 is never ready (and would reintroduce IR-01); readiness details are unreachable from the host under the compose topology; deploy.sh only checks the declaration line

| Field | Value |
|---|---|
| Evidence (re-review) | api/veda/platform/health.py:60-66; api/deploy/docker-compose.yml:10; api/deploy/deploy.sh:38; AM-6, AM-11 text |
| Root cause | Runbook and AM-6/AM-11 described an N-1 rollback that cannot pass readiness and would reintroduce IR-01; deploy.sh read readiness from the host and only checked that a declaration existed. |
| Files changed | docs/operations/api-runbooks.md; api/deploy/deploy.sh; api/veda/cli/main.py; api/veda/platform/health.py; docs/proposals/amendments/AM-6.md; docs/proposals/amendments/AM-11.md |
| Requirements affected | OPS-004; LOG-005 |
| Remediation | Rollback floor (0009_mfa_challenge_binding) enforced by deploy.sh through `veda schema-status --require-known`; revision and readiness read inside the container; the declared VEDA_SCHEMA_AHEAD_ACCEPTED value must equal the current revision. Runbook §2 defines the boundary, forward-fix criteria, DB compatibility, maintenance mode, snapshot dependency, post-rollback validation, owner category and evidence; rollback to 9236aa3 prohibited. No rehearsal claimed. |
| Regression tests | api/tests/integration/test_archive_ordering.py::test_RR17_schema_status_and_rollback_floor; api/tests/integration/test_archive_ordering.py::test_RR17_deploy_script_rollback_floor_is_the_ir01_revision |
| Amendment needed | AM-6, AM-11 |
| Owner decision | OD-1 (AM-6, AM-11) |
| Re-review blocking scope | production (RG-7) |
| Merge impact | None |
| Staging impact | RG-7 rehearsal |
| Production impact | Blocks until RG-7 |
| Status | RESOLVED IN CODE AND DOCUMENTATION — RG-7 REHEARSAL REQUIRED |

### RR-18

**MINOR** — Accessibility remnants: step-up dialog has no pre-expiry warning; command palette listbox/option semantics and vs-tabs tabpanel wiring unchanged; account menu stays open on outside click

| Field | Value |
|---|---|
| Evidence (re-review) | app/src/modules/auth/step-up-dialog.ts:71; command-palette.ts:79-80; design-system/components.ts:375-380; shell/app.ts:200-208 |
| Root cause | Accessibility remnants in the SPA. |
| Files changed | — |
| Requirements affected | UI-011; UI-016 (AX-06, AX-07, AX-09) |
| Remediation | Not changed. |
| Regression tests | — |
| Amendment needed | No |
| Owner decision | No |
| Re-review blocking scope | production |
| Merge impact | None |
| Staging impact | None |
| Production impact | Blocks |
| Status | OPEN — PRODUCTION BLOCKER |

## Advisories (RR-A01…RR-A25)

| ID | Text | Status | Action | Files |
|---|---|---|---|---|
| RR-A01 | IR-20 link invalidation written on the 409 path is rolled back with the error (mfa.py:330-334); no effect because confirm re-checks. | OPEN — TRACKED | Not changed in this workstream. | — |
| RR-A02 | PostgreSQL answers 409 VERSION_CONFLICT on concurrent auth writes where SQLite answers 401; PostgreSQL gate. | OPEN — TRACKED | Not changed in this workstream. | — |
| RR-A03 | tests/unit/test_totp_passwords.py fails 2 tests when run alone without VEDA_ENV=test (test isolation). | OPEN — TRACKED | Not changed in this workstream. | — |
| RR-A04 | Path C start password re-entry is not counted by any throttle (mfa.py:318-329). | OPEN — TRACKED | Not changed in this workstream. | — |
| RR-A05 | VEDA_ENV=local on a deployed host silently derives public development keys; nothing in gunicorn on_starting refuses local/test in the production image (config.py:190). | OPEN — TRACKED | Not changed in this workstream. | — |
| RR-A06 | An expired ENROLLMENT challenge leaves an inert PENDING factor (pre-existing). | OPEN — TRACKED | Not changed in this workstream. | — |
| RR-A07 | Break-glass CLI lets botocore exceptions escape without a FAILURE event. | OPEN | Folded into RR-09 (production). | — |
| RR-A08 | PostgreSQL: break_glass_execute racing a cancel-link raises StaleDataError and aborts the remaining due items that cycle (maintenance.py:588-591). | OPEN — TRACKED | Not changed in this workstream. | — |
| RR-A09 | OpenAPI snapshot documents 200 for cancel-link; the handler returns 204. | RESOLVED | cancel-link route declares status=204; OpenAPI snapshot updated. | api/veda/platform/rbac/routes.py; api/openapi.snapshot.json |
| RR-A10 | Stale approver with suspended user.founder.manage gets 403 PERMISSION_DENIED where TD-G G7 expects APPROVER_NOT_ELIGIBLE (pre-existing). | OPEN — TRACKED | Not changed in this workstream. | — |
| RR-A11 | Eligible Founders can deny PENDING custodian break-glass in-app but cannot cancel APPROVED ones except via the link; undocumented (fold into AM-5/AM-9). | DOCUMENTED | Veto semantics stated in AM-5. | docs/proposals/amendments/AM-5.md |
| RR-A12 | cancel_open_standard_requests records an event but sends no approval.decided notification. | OPEN — TRACKED | Not changed in this workstream. | — |
| RR-A13 | Anchor store: no writer/reader role separation; staging silently uses a same-host local store; verify_chain holds a write transaction for the whole recompute. | PARTIALLY ADDRESSED | Role separation documented as a staging requirement (runbook §5); staging local-store fallback and verify_chain write transaction unchanged. | docs/operations/api-runbooks.md |
| RR-A14 | Restore-verify chain check trusts the first online row (backups.py:146), so a prefix-deleted snapshot passes. | OPEN — TRACKED | Not changed in this workstream. | — |
| RR-A15 | CI residuals: postgres:16 service image not digest-pinned; built image never smoke-run; e2e uses Flask dev server; Trivy ignore-unfixed without recorded risk acceptance; 104 secrets-baseline entries none audited. (CI execution itself is now evidenced: run 36559966718.) | OPEN — TRACKED | Not changed in this workstream. | — |
| RR-A16 | Open-issue registry omits 9 advisories (IR-A03, A04, A05, A09, A13, A17, A19, A21, A25) contrary to its own note; IR-39 text mischaracterises the mypy backlog. | RESOLVED | Open-issue register now lists IR-A03, A04, A05, A09, A13, A17, A19, A21, A25 and every RR item. | docs/implementation/P0-open-issues.{md,json} |
| RR-A17 | Migration 0009 is chained after 0100_crm_leads, contradicting 02 §8.3 numbering; AM-11 does not amend 02 §8.3. | DOCUMENTED | AM-11 now amends 02 §8.3 migration placement. | docs/proposals/amendments/AM-11.md |
| RR-A18 | ESLint sink bans miss lit-html unsafe-html path, unsafe-mathml, .innerHTML=${} bindings, createContextualFragment, setHTMLUnsafe; site JS (dist/assets/app.js) is not linted. | OPEN — TRACKED | Not changed in this workstream. | — |
| RR-A19 | E2E remnants: axe site scan uses bypassCSP; focus assertion also passes on #outlet; test servers bind to all interfaces. | OPEN — TRACKED | Not changed in this workstream. | — |
| RR-A20 | DEV-004 register says superseded consent evidence is visible in the lead timeline; the SPA renders only subject and note. | OPEN — TRACKED | Not changed in this workstream. | — |
| RR-A21 | Route-focus hook moves focus to the MFA heading after sign-in instead of the code field. | OPEN — TRACKED | Not changed in this workstream. | — |
| RR-A22 | engines ^22 with engine-strict rejects Node 24 LTS; Node 22 EOL 2027-04-30. | OPEN — TRACKED | Not changed in this workstream. | — |
| RR-A23 | Proposed amendments are stored inside docs/architecture/amendments/ on the implementation branch. Certified files are unchanged and every proposal is marked PROPOSED, NOT APPROVED, but merging would place unapproved text inside the certified tree; consider docs/proposals/ or merge only after decisions. | RESOLVED | Amendments moved to docs/proposals/amendments (git mv); references updated. | docs/proposals/amendments/* |
| RR-A24 | Remediation evidence was generated from an uncommitted tree on top of 9236aa3 before 2f6b59a (per evidence README); CI logs are not publicly readable, so step-level conclusions (API) are the independent CI evidence. | ADDRESSED BY PROCESS | This workstream's evidence is generated from a clean copy of the exact committed tree. | — |
| RR-A25 | On e2e failure CI uploads e2e artefacts including founder.json (throwaway DB password and TOTP secret); harmless for ephemeral data but should be excluded. | RESOLVED | CI e2e artifact upload excludes founder.json. | .github/workflows/ci.yml |

## Reconciliation items not RESOLVED by the re-review (and those changed here)

| ID | Original severity | Status now | Re-review conclusion | Change in this workstream |
|---|---|---|---|---|
| IR-03 | MAJOR | CODE RESOLVED (RR-05/06/07); STAGING S3 EVIDENCE REQUIRED | See RR-05, RR-06, RR-07; S3 behaviour unexecuted | Not changed in this workstream. |
| IR-06 | MAJOR | ACCEPTABLY GATED FOR STAGING (unchanged) | Self-assertion closed; but in the deployed container topology STS sees the instance role (RR-09) | Not changed in this workstream. |
| IR-08 | MAJOR | RESOLVED BY RR-02 | IR-08 itself fixed; deleted Founders keep role/protection and one Founder can restore them (RR-02) | Deleted Founders are restored only by the dual-control workflow. |
| IR-11 | MAJOR | PARTIALLY RESOLVED (RR-14 fixed; RR-15 open) | Artefacts exist; off-host replica never verified; snapshot dir ephemeral | Not changed in this workstream. |
| IR-12 | MAJOR | CODE RESOLVED (RR-07); RG-5 REQUIRED | See RR-07 | Not changed in this workstream. |
| IR-18 | MAJOR | ACCEPTABLY GATED FOR PRODUCTION (unchanged) | Real-key run is an enablement step | Not changed in this workstream. |
| IR-23 | MINOR | RESOLVED BY RR-04 | See RR-04 | Layered limiter; AM-7 rewritten. |
| IR-26 | MINOR | RESOLVED BY RR-06 | Boundary loss fixed; the new manifest-before-commit ordering wedges archival (RR-06) | Two-phase archival ordering. |
| IR-27 | MINOR | PARTIALLY RESOLVED (unchanged) | See RR-13 | Not changed in this workstream. |
| IR-32 | MINOR | RESOLVED BY RR-01 | CSP sub-item regressed the live 404 page | 404 styles external; site CSP unchanged. |
| IR-33 | MINOR | ACCEPTABLY GATED FOR PRODUCTION (unchanged) | Tracked | Not changed in this workstream. |
| IR-34 | MINOR | NOT RESOLVED (unchanged) | Tracked, non-blocking | Not changed in this workstream. |
| IR-37 | MINOR | PARTIALLY RESOLVED (unchanged) | Author matrix overstates as RESOLVED (RR-18) | Not changed in this workstream. |
| IR-38 | MINOR | PARTIALLY RESOLVED (unchanged) | RR-A19 | Not changed in this workstream. |
| IR-A01 | ADVISORY | ACCEPTABLY GATED FOR PRODUCTION (unchanged) | — | Not changed in this workstream. |
| IR-A02 | ADVISORY | NOT RESOLVED (unchanged) | Accepted residual | Not changed in this workstream. |
| IR-A04 | ADVISORY | PARTIALLY RESOLVED (unchanged) | No practical impact | Not changed in this workstream. |
| IR-A05 | ADVISORY | RESOLVED | Latent | Startup refuses optional-auth or public routes that declare a permission, and unregistered public/optional routes (api/tests/unit/test_lint.py::test_IRA05_optional_and_public_routes_cannot_hide_a_permission). |
| IR-A06 | ADVISORY | NOT RESOLVED (unchanged) | Owner decision | Not changed in this workstream. |
| IR-A07 | ADVISORY | PARTIALLY RESOLVED (unchanged) | Decision: KEEP 403/404 DIFFERENCE (§9) | Not changed in this workstream. |
| IR-A08 | ADVISORY | NOT RESOLVED (unchanged) | — | Not changed in this workstream. |
| IR-A10 | ADVISORY | ACCEPTABLY GATED FOR STAGING (unchanged) | — | Not changed in this workstream. |
| IR-A11 | ADVISORY | NOT RESOLVED (unchanged) | Owner decision | Not changed in this workstream. |
| IR-A12 | ADVISORY | NOT RESOLVED (unchanged) | Accepted as correlation-only | Not changed in this workstream. |
| IR-A13 | ADVISORY | PARTIALLY RESOLVED (unchanged) | action not checked | Not changed in this workstream. |
| IR-A14 | ADVISORY | PARTIALLY RESOLVED (unchanged) | — | Not changed in this workstream. |
| IR-A15 | ADVISORY | NOT RESOLVED (unchanged) | Owner decision | Not changed in this workstream. |
| IR-A16 | ADVISORY | ACCEPTABLY GATED FOR PRODUCTION (unchanged) | — | Not changed in this workstream. |
| IR-A18 | ADVISORY | NOT RESOLVED (unchanged) | Tracked | Not changed in this workstream. |
| IR-A20 | ADVISORY | NOT RESOLVED (unchanged) | Tracked | Not changed in this workstream. |
| IR-A22 | ADVISORY | PARTIALLY RESOLVED (unchanged) | Owner decision | Not changed in this workstream. |
| IR-A23 | ADVISORY | NOT RESOLVED (unchanged) | Owner/legal decision | Not changed in this workstream. |
| IR-A24 | ADVISORY | NOT RESOLVED (unchanged) | Tracked non-blocker | Not changed in this workstream. |
| IR-A25 | ADVISORY | PARTIALLY RESOLVED (unchanged) | RR-A16, RR-A20 | Not changed in this workstream. |

## Owner decisions

| ID | Decision | Handling | Status | Merge impact |
|---|---|---|---|---|
| OD-1 | Amendments: AM-1/6/11 may be submitted only when complete, matching, explicit and reviewer-confirmed; correct AM-2/4/5/6/10/11; AM-7 rejected as written and replaced; AM-8/9/10 remain production amendments. | All amendments rewritten in docs/proposals/amendments; every one PROPOSED, NOT APPROVED; AM-7 replaced by the layered proposal; 'Approval readiness' field states which are ready for submission after the reviewer's confirmation (none marked approved). | APPLIED — NO AMENDMENT APPROVED | Owner approval still required for merge (re-review OD-1) |
| OD-2 | Deleted Founder restored only through the canonical Founder workflow with two distinct eligible humans. | Implemented (RR-02, AM-12, DEV-009). | IMPLEMENTED — AM-12 PENDING | AM-12 decision |
| OD-3 | Execution-time revalidation of identity/security requests against the target's current governance class. | Implemented (RR-03, AM-13, DEV-010). | IMPLEMENTED — AM-13 PENDING | AM-13 decision |
| OD-4 | TG-01 and TG-08 remain PENDING. | Not touched; no approval or authorization claimed. | PENDING (UNCHANGED) | Blocks merge |
| OD-5 | Merge deploys dist/ to the live site: no merge, no push to main, intake disabled, no DNS/Cloudflare change. | Complied; merge-safety plan written (docs/implementation/P0-merge-safety-plan.md), not executed; intake metas verified empty. | COMPLIED — PLAN AWAITS OWNER CHOICE | Blocks merge until a plan option is approved |
