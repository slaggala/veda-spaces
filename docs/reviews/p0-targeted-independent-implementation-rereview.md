# Veda Spaces P0 — Targeted Independent Implementation Re-review

**Review ID:** VEDA-SPACES-P0-TARGETED-INDEPENDENT-IMPLEMENTATION-REREVIEW-01
**Date:** 2026-09-29
**Final verdict:** **NOT CERTIFIED**

**IR-01: RESOLVED.** No BLOCKER remains. Merge is still blocked by:
- **four merge-blocking MAJOR findings**, two of them regressions introduced by the remediation;
- one merge-scoped MINOR finding;
- absent owner decisions;
- owner gates TG-01 and TG-08, which are still pending.

> This document covers technical artifacts only.
> - It modifies no implementation, architecture or `dist/` file.
> - It approves no architecture amendment and fixes nothing.
> - It authorizes no merge, staging or production step.
> - It complements, and does not replace, [p0-independent-implementation-review.md](p0-independent-implementation-review.md) (review commit `1aaf019`).

| Item | Value |
|---|---|
| Repository | `git@github.com:slaggala/veda-spaces.git` |
| Certified architecture SHA | `778aa8fdd918da48340319696ada3ff673e9fb8e` |
| Original reviewed SHA | `9236aa3ade38c33d03a57cf7a064ece29937b109` |
| Original review commit | `1aaf019b6c872a075d13e9b3a2a2e9c16489f6f4` (unchanged) |
| **Target reviewed (remote head of `implementation/p0-foundation`)** | **`2f6b59a0a6a59dbc41a597dddc7e6512dcd581fe`** |
| Included commits | `6fd249c10b72b112c83f86cc2705736a59db28be` (remediation), `2f6b59a0a6a59dbc41a597dddc7e6512dcd581fe` (runtime image) |
| Machine-readable twin | [p0-targeted-independent-implementation-rereview.json](p0-targeted-independent-implementation-rereview.json) |

## Contents

1. [Method](#1-method)
2. [Scope and commit verification](#2-scope-and-commit-verification-phase-1)
3. [Author claims ledger](#3-author-claims-ledger)
4. [IR-01 re-review](#4-ir-01-re-review-phases-23)
5. [Original finding reconciliation](#5-original-finding-reconciliation-phase-4)
6. [Founder governance](#6-founder-governance-phase-5)
7. [Tamper-evident audit chain](#7-tamper-evident-audit-chain-phase-6)
8. [Deviation decisions](#8-deviation-decisions-dev-001-to-dev-008-phase-7)
9. [Proposed architecture amendments](#9-proposed-architecture-amendments-am-1-to-am-11-phase-8)
10. [API and RBAC regression; IR-A07](#10-api-and-rbac-regression-ir-a07-phase-9)
11. [Database and migrations](#11-database-and-migrations-phase-10)
12. [Test and CI reproduction](#12-test-and-ci-reproduction-phase-11)
13. [Quality and security tooling](#13-quality-and-security-tooling-phase-12)
14. [Public form safety](#14-public-form-safety-phase-13)
15. [Staging-only findings](#15-staging-only-findings-phase-14)
16. [Open-issue and gate registry](#16-open-issue-and-gate-registry-phase-15)
17. [New regressions](#17-new-regressions-phase-16)
18. [New findings](#18-new-findings)
19. [Blockers by stage and owner decisions](#19-blockers-by-stage-and-owner-decisions)
20. [Final report A–AG](#20-final-report-aag)
- [Appendices](#appendices)

---

## 1. Method

- **Isolated checkouts.** The target was checked out as a detached git worktree at `2f6b59a`. The original `9236aa3` worktree was kept for baseline reproduction. `git status` was clean on both before and after the review.
- **Six review streams.** The lead reviewer covered Phase 1 scope, backend suites on three engines, CI evidence, the hygiene and secret scans, amendments and consolidation. Five independent domain re-reviewers covered:
  - auth/MFA and IR-01;
  - governance, RBAC and API;
  - leads, audit chain and notifications;
  - database, operations, CI and tooling;
  - frontend, site and browser.
- **Probes ran on copies.** Every probe ran against copies of the tree. Where the concurrency or engine matters, probes ran on SQLite and PostgreSQL.
- **Nothing trusted by default.** The author's remediation matrix, register text and evidence files were treated as claims.
- **Decision-driving findings re-verified.** The lead reviewer re-verified each of these directly in source: IR-01, RR-01, RR-02, RR-03, RR-04 and RR-07.
- **Toolchains.**
  - Python 3.13.7 in a fresh venv, installed with `pip install --require-hashes -r requirements-dev.txt`.
  - Node **22.23.3** (the pinned version), downloaded from nodejs.org with its SHA-256 checked against `SHASUMS256.txt`.
  - PostgreSQL **16.4** (standalone) and **18.4** (embedded).
  - SQLite 3.50.4.
  - Playwright Chromium.
- **No infrastructure touched.** No AWS, Cloudflare or production system was contacted. The GitHub REST API was read anonymously for CI run metadata only.

## 2. Scope and commit verification (Phase 1)

| Check | Result | Evidence |
|---|---|---|
| Remote head of `implementation/p0-foundation` | `2f6b59a0a6a59dbc41a597dddc7e6512dcd581fe` | `git rev-parse origin/implementation/p0-foundation` after `git fetch --prune` |
| Both remediation commits present | Yes | `git log 9236aa3..origin/implementation/p0-foundation` = `6fd249c` (parent `9236aa3`), `2f6b59a` (parent `6fd249c`) |
| Descend from original reviewed SHA | Yes | `git merge-base --is-ancestor 9236aa3 <commit>` for both |
| No force push altered history | Yes | Linear parents; remote-tracking reflog `9236aa3 → 6fd249c → 2f6b59a`, each "update by push" (fast-forward) |
| No later unreviewed commit | Yes | Head equals `2f6b59a` |
| Certified architecture documents unchanged | **Yes** (no certified file modified or deleted) | `git diff --diff-filter=MDR 778aa8f 2f6b59a -- docs/architecture` is empty. **13 files were added** under `docs/architecture/amendments/`, all marked PROPOSED, NOT APPROVED (RR-A23) |
| Original review artifacts unchanged | Yes | `origin/review/p0-independent-implementation-review` = `1aaf019`; implementation branch has no `docs/reviews/` |
| Working tree clean | Yes | `git status --short` empty |
| Diff `9236aa3..6fd249c` | 223 files (96 added, 127 modified), +41 143 / −5 905 | `git diff --stat` |
| Diff `6fd249c..2f6b59a` | 1 file: `api/deploy/Dockerfile` (+4/−1) | **Genuinely limited** to the runtime image: `python -m pip uninstall -y pip` after the hash-locked install. CI evidence: run on `6fd249c` failed only at "Container image scan" |
| DB files, env files, keys, dependency dirs, screenshots | None | Pattern scan of the 223 changed paths |
| Credentials, tokens, TOTP secrets, recovery codes, private keys | None real | Regex scan of added lines plus `detect-secrets` on all changed files. Hits: test-fixture passwords, `.secrets.baseline` hashes, fixed test UUIDs, error titles, alphabets, the ephemeral CI Postgres credential. IR-01 evidence files redact tokens as `<access-token>`; the adjacent hex is a user id |
| Production lead API activation | None | `dist/index.html:11-12`: `veda-api-base` and `veda-turnstile-sitekey` both empty (§14) |

## 3. Author claims ledger

| # | Author claim | Independent result |
|---|---|---|
| 1 | IR-01 is fixed | **Confirmed.** IR-01 RESOLVED (§4) |
| 2 | No BLOCKER remains in code | **Confirmed.** No new BLOCKER was found |
| 3 | IR-02, 04, 05, 08, 09, 13, 14, 15, 17, 18, 19 resolved | **Mostly confirmed.** IR-08 fix **introduced** RR-02. IR-04 has an adjacent open path (RR-03). IR-18 is complete but gated on a real-key run. IR-14 is confirmed by the CI run in §12 |
| 4 | IR-07, 10, 16 fixed but need amendments | **Confirmed.** Amendments AM-5, AM-6 and AM-4 are incomplete (§9) |
| 5 | IR-03, 06, 11, 12 need real staging infrastructure | **Partly incorrect.** IR-03 and IR-12 also have **repository** defects (RR-05, RR-06, RR-07). IR-06 has a topology defect (RR-09) |
| 6 | DEV-004 corrected | **Confirmed** (acceptable with amendment), with residuals RR-12 |
| 7 | PostgreSQL 16 and 18.4 tests pass | **Confirmed:** 427 passed / 8 skipped on both |
| 8 | SQLite tests pass | **Confirmed:** 435 passed |
| 9 | Five CI jobs pass | **Confirmed** via the GitHub API. Run 36559966718 on `2f6b59a`: all 5 jobs `success`. Logs are not publicly readable |
| 10 | Public submission remains disabled | **Confirmed** (§14) |
| 11 | No secrets committed | **Confirmed** (§2) |
| 12 | AM-1 … AM-11 PROPOSED, not approved | **Confirmed.** Every file and `amendments.json` says so |
| 13 | DEV-001 … DEV-003 await owner approval | **Confirmed.** Status is "PENDING ARCHITECTURE-OWNER DECISION"; none is represented as approved |
| 14 | DEV-005 … DEV-008 newly recorded | **Confirmed** |
| 15 | No production gate executed | **Confirmed.** All 27 gates Pending/Blocked; TG-01 and TG-08 Pending |

## 4. IR-01 re-review (Phases 2–3)

**Verdict: IR-01 RESOLVED.**

**Baseline.** The original exploit was re-confirmed at `9236aa3` on SQLite and PostgreSQL:
- cross-user confirm → 200;
- `/audit-logs` 403 → 200;
- the Admin's recovery codes regenerated without step-up (403 → 200).

**Head.** The same attacks return `401 MFA_CHALLENGE_INVALID`. The victim's sessions and factors are unchanged.

**Fix (read directly by the lead reviewer).** `api/veda/platform/auth/mfa.py` `_bound_transaction` and `_require_eligible`:
- The path is taken from `mfa_challenge.enrollment_path`, which is server state, never from the presence of a bearer token.
- Paths A and D require `ctx.user.id == ch.user_id` and `ctx.session.id == ch.session_id`, and the right session type.
- Paths B and C refuse **any** bearer token.
- The factor must be `ch.factor_id`, belong to `ch.user_id`, and be PENDING.
- The challenge row is locked `FOR UPDATE`, and completion is re-checked after the lock.
- Eligibility is re-checked at confirm: account state, invitation liveness, and "path C never replaces an ACTIVE factor".
- Migration `0009_mfa_challenge_binding` adds `factor_id` and `enrollment_path` (DEV-006 / AM-11).

**All 20 required items** pass on SQLite and PostgreSQL (49/49 probes per engine). The full item table is in Appendix B.1. Items of note:
- **Items 1, 2, 4:** cross-user substitution in either direction and unrelated bearers on paths B/C → 401, with an identical body for every case.
- **Item 12:** parallel confirmations → exactly one success on both engines.
- **Item 13:** an injected failure after flush leaves no ACTIVE factor and no elevated session.
- **Items 15 and 16:** only the initiating session is elevated; other sessions are unchanged, consistent with 05 §11.3.
- **Item 17:** the refresh token rotates. The rotation lacks a successor link, which is new finding RR-08.
- **Item 20:** failure responses do not distinguish account, transaction or factor ownership.

**Adjacent flows (Phase 3).** No confused-deputy or transaction-binding defect was found in these flows (table in Appendix B.2):
- initial and invitation enrollment;
- replacement and recovery re-enrollment;
- restricted recovery sessions and Founder recovery;
- step-up and reauth, MFA verify at login;
- password reset;
- email change verify and cancel;
- invitation accept;
- logout everywhere;
- refresh rotation.

The attempts covered cross-user, cross-session and cross-purpose substitution, stale tokens and authorization, replay, concurrency, caller-supplied ownership fields (rejected as unknown fields) and transaction-id enumeration.

Approval execution and break-glass are covered in §6. Related new defects in adjacent areas are **RR-04** (limiter keying) and **RR-08** (refresh successor link).

## 5. Original finding reconciliation (Phase 4)

All 64 original findings are reconciled: 1 BLOCKER, 18 MAJOR, 20 MINOR and 25 ADVISORY.

Status counts:
- **RESOLVED:** 30 (BLOCKER 1, MAJOR 12, MINOR 12, ADVISORY 5)
- **PARTIALLY RESOLVED:** 13 (BLOCKER 0, MAJOR 3, MINOR 3, ADVISORY 7)
- **NOT RESOLVED:** 11 (BLOCKER 0, MAJOR 0, MINOR 1, ADVISORY 10)
- **ACCEPTABLY GATED FOR STAGING:** 2 (BLOCKER 0, MAJOR 1, MINOR 0, ADVISORY 1)
- **ACCEPTABLY GATED FOR PRODUCTION:** 4 (BLOCKER 0, MAJOR 1, MINOR 1, ADVISORY 2)
- **REGRESSION INTRODUCED:** 4 (BLOCKER 0, MAJOR 1, MINOR 3, ADVISORY 0)

| ID | Orig. severity | Remediation at head | Evidence | **Status** | Arch amendment | Blocking scope now | Conclusion |
|---|---|---|---|---|---|---|---|
| IR-01 | BLOCKER | auth/mfa.py:218-248,287-304,377-555 (_bound_transaction, _require_eligible); auth/models.py:192-202; migration 0009_mfa_challenge_binding | Baseline 9236aa3: P1/P1b bypass re-confirmed on SQLite + PG (403→200). Head: same attacks → 401 MFA_CHALLENGE_INVALID; 20/20 binding items pass on both engines (49/49 probes each); lead reviewer read the fix | **RESOLVED** | AM-11 (DEV-006) | None for IR-01 itself; AM-11 owner decision before merge | Transaction bound to principal, session, factor, path, state, expiry, single use; row lock on confirm; B/C refuse any bearer |
| IR-02 | MAJOR | kernel/http.py:546-576; leads/routes.py:75-117; auth/routes.py:44-68 | Slow-verifier probe: concurrent staff writes 0.01–0.04 s for intake and login (was 503 after 5.19 s) | **RESOLVED** | No | — | Verification now outside the write unit of work; idempotency re-checked inside |
| IR-03 | MAJOR | platform/anchor_store.py; maintenance.py:339-438 | Q4 cases (prefix delete, tail truncation, middle gap, modification) now detected on both engines; forged manifest (C11) and manifest-before-commit (C12) fail; CLI alarms absent | **PARTIALLY RESOLVED** | No | Production (SEVT-006/007 claim); S3 Object Lock staging evidence | See RR-05, RR-06, RR-07; S3 behaviour unexecuted |
| IR-04 | MAJOR | rbac/governance.py:141-157 (standard_still_permitted), :160-178, :325, :404-409 | P10, N01–N03, N14 on both engines | **RESOLVED** | No | — | Original reproduction fails closed; the adjacent executed-email-change path remains open (RR-03). Original MINOR→MAJOR upgrade confirmed justified |
| IR-05 | MAJOR | rbac/governance.py:633-642 require_break_glass_mode; used at :651-662, :699-701, :314-315 | P13, N04 | **RESOLVED** | No | — | Full break-glass refused while an eligible Founder other than the target exists |
| IR-06 | MAJOR | rbac/custodians.py:22-59 (STS GetCallerIdentity); cli/main.py:223-230; config.py asserted mode refused outside local/test | N06, N07; STS stubbed in tests | **ACCEPTABLY GATED FOR STAGING** | Clarify 06 §7.5 mechanism (minor) | Production (PG-BG); staging rehearsal | Self-assertion closed; but in the deployed container topology STS sees the instance role (RR-09) |
| IR-07 | MAJOR | app/src/core/router/routes.ts:34; app/src/modules/auth/approval-cancel-page.ts:25-47; handlers.py:447; app.py:60-68 (RBX register) | P12, N08, N10; SPA source; FE reviewer: page exists, POSTs only on explicit confirm, bad/missing token handled | **RESOLVED** | AM-5 (DEV-005) | AM-5 owner decision before merge; PG-BG for production | Veto usable end-to-end |
| IR-08 | MAJOR | rbac/guards.py:176-192 (I3 over non-deleted users) | P11, P16 on both engines: Founder DELETE executes | **REGRESSION INTRODUCED** | No (unless workflow-restore chosen) | Merge (via RR-02) | IR-08 itself fixed; deleted Founders keep role/protection and one Founder can restore them (RR-02) |
| IR-09 | MAJOR | config.py:21-23,176-190,280-352 (ENVIRONMENTS, MIN_KEY_BYTES, validate_environment for staging+production); app.py:107; cli/main.py:29,51 | Unset/prod/Staging/dev → ConfigError; staging/production with missing/weak values refused (17/20 problems); migrate validates | **RESOLVED** | No | — | Residual advisories RR-A05 (local env on deployed host) and RR-10 (CIDR/key-quality) |
| IR-10 | MAJOR | platform/health.py:50-58,85; runbook §2; deploy/deploy.sh:36-40 | Readiness: head ready; declared-ahead ready; older not ready. Real N-1 (9236aa3) on migrated schema → 503 | **RESOLVED** | AM-6 (DEV-008) | AM-6 owner decision before merge; RG-7 for production | Mechanism works for future releases; first-release rollback = snapshot restore, undocumented (RR-17) |
| IR-11 | MAJOR | deploy/litestream.yml; docker-compose.yml:27-33; platform/backups.py; cli/main.py:177-205; deploy/deploy.sh; docs/operations/api-runbooks.md | Pip-less CLI snapshot / restore-verify / disk-usage rc 0; runbook defects reproduced; no rehearsal | **PARTIALLY RESOLVED** | No | Staging (RR-14, RR-15); production RG-1/RG-2/RG-7 | Artefacts exist; off-host replica never verified; snapshot dir ephemeral |
| IR-12 | MAJOR | kernel/metrics.py; kernel/logging.py:64-70 (EMF); config.py:341-342 (Sentry required in production); runbook §9 | API process emits EMF; every CLI/scheduler/worker metric dropped (0 EMF lines) | **PARTIALLY RESOLVED** | No | Staging alarm acceptance (RR-07); production RG-5 | See RR-07 |
| IR-13 | MAJOR | api/requirements.txt (41 pkgs hashed), requirements-dev.txt (84 hashed); Dockerfile FROM python:3.13-slim@sha256:7c61…; --require-hashes --no-deps; Litestream digest-pinned | Hash-locked install reproduced by lead reviewer; pip-audit --require-hashes clean | **RESOLVED** | No | — | Residual: CI postgres:16 service image not digest-pinned (RR-A15) |
| IR-14 | MAJOR | .github/workflows/ci.yml (5 jobs, SHA-pinned actions, no continue-on-error/\|\| true) | GitHub API: run 36559966718 (push, attempt 1) on 2f6b59a — api (sqlite), api (postgresql), security, app, browser e2e + axe all success; 6fd249c run failed only at 'Container image scan'. Logs not readable anonymously | **RESOLVED** | No | — | Author's OI-RM-1 ('first CI run') can close with this run URL |
| IR-15 | MAJOR | app/src/modules/leads/edits.ts:17-21; lead-form.ts:143-172 | Original lost-update probe re-run: other writer's city/priority preserved; history changed_fields=['message'] | **RESOLVED** | No | — | Advisory: flag overlapping fields as true conflicts |
| IR-16 | MAJOR | leads/service.py:824-873; leads/schemas.py:52-63; leads/activities.py:98-104 | D01–D05 both engines: 409 without withdrawal/new version; WEBSITE_FORM 422; note required; no web IP/page on staff capture; activity + audit written | **RESOLVED** | AM-4 (DEV-004) | AM-4 owner decision before merge | Residuals RR-12 |
| IR-17 | MAJOR | dist/assets/enhancements.css ([hidden] display:none !important); site.e2e success/fallback checks | site.e2e: form hidden after success and fallback | **RESOLVED** | No | Feature: public intake | — |
| IR-18 | MAJOR | dist/assets/app.js:147-150,172-177,219,232 (widget id, reset on every non-201, no submit without token); app.js:58 requires both metas | Stub E2E reset→201; real Turnstile script + public test key under production CSP: 0 violations; real-key 422→reset→201 not run | **ACCEPTABLY GATED FOR PRODUCTION** | No | Feature: public-intake enablement | Real-key run is an enablement step |
| IR-19 | MAJOR | app/src/core/router/routes.ts:23-62; shell/app.ts:101-123,227 | All 8 routes + Back: correct title, h1 focused (production build, app CSP) | **RESOLVED** | No | Production: manual screen-reader pass | Side effect RR-A21 |
| IR-20 | MINOR | auth/mfa.py:330-334, 436-437, 503-504 | Probe: path C with ACTIVE factor → 409; confirm ends other links/transactions | **RESOLVED** | AM-1 | — | RR-A01: invalidation on 409 path rolled back (no effect) |
| IR-21 | MINOR | rbac/users.py:127-131; auth/service.py:775-780; auth/mfa.py:294-301,431 | P3: replayed/resend-superseded context → 401 | **RESOLVED** | AM-2 note | — | Replay before activation still overwrites the password (document in AM-2) |
| IR-22 | MINOR | kernel/net.py:17-43; kernel/logging.py:153-156 | Compressed/expanded/upper-case/IPv4-mapped/zone-id forms group correctly | **RESOLVED** | No | — | — |
| IR-23 | MINOR | kernel/ratelimit.py:22-33 (key email\|network) | Victim in another network 200 while attacker 429 — but 40 guesses/min from 8 /64s all evaluated; 18 vs 3 reset emails | **REGRESSION INTRODUCED** | AM-7 must be revised | Merge (DEV-007 requires implementation change) / production | See RR-04 |
| IR-24 | MINOR | auth/service.py:694-756; throttle.py:36-38,134-150 | 10 failed reauth → 429 even with correct password + ACCOUNT_THROTTLED scope=reauth | **RESOLVED** | No | — | Path C password re-entry still unthrottled (RR-A04) |
| IR-25 | MINOR | auth/service.py:274-292,781-783; auth/routes.py:74-78; mfa.py:85-93; service.py:413-416; leads/service.py:947-957 | All listed events present; ERASURE_BLOCKED persisted (1 event) on both engines | **RESOLVED** | No | — | — |
| IR-26 | MINOR | maintenance.py:441-514 (contiguous prefix, count assertion) | Original Q3 + C10: nothing unexported deleted; verify ok | **REGRESSION INTRODUCED** | No | Production (before archival is enabled) | Boundary loss fixed; the new manifest-before-commit ordering wedges archival (RR-06) |
| IR-27 | MINOR | kernel/db.py:61,65 (hide_parameters); kernel/logging.py:44-61,98-150; app.py:117-125 | Q6: no name/email/message in structured stdout; Sentry transaction events carry query strings; outbox_event.last_error stores recipient emails | **PARTIALLY RESOLVED** | No | Production logging | See RR-13 |
| IR-28 | MINOR | leads/routes.py:289-294 | P4: note/activity/status/re-consent/assign/delete on erased lead → 409 on both engines | **RESOLVED** | No | — | — |
| IR-29 | MINOR | kernel/dto.py:41-44 (single_line); leads/events.py:35-44; leads/service.py:531-537 | CRLF name renders on one labelled line; genuine link on its own line | **RESOLVED** | No | — | — |
| IR-30 | MINOR | notifications/worker.py:67-104 (per-message delivery keys) | P5: sends [u1, u2✗, u2] — u1 not re-sent | **RESOLVED** | No | — | Residual at-least-once window accepted |
| IR-31 | MINOR | dist/assets/app.js:220-230 | site.e2e: UNKNOWN_POLICY_VERSION → fallback with reload prompt, no inline field error | **RESOLVED** | No | Feature: public intake | — |
| IR-32 | MINOR | dist/assets/app.js:97-120 (textContent); enhancements.css (#form-note colour); index.html:179-180 (consent/Turnstile hidden unless intake on); dist/_headers:2 (site CSP) | innerHTML and contrast fixed; /privacy absent (gated); site CSP blocks inline <style> of dist/404.html | **REGRESSION INTRODUCED** | No | Merge (merge to main deploys dist/ to production; RR-01) | CSP sub-item regressed the live 404 page |
| IR-33 | MINOR | none | PG16.4: TRUNCATE, GUC bypass and non-owner GUC bypass still succeed | **ACCEPTABLY GATED FOR PRODUCTION** | No | PostgreSQL release gate (PGM-1); SQLite is the P0 production engine | Tracked |
| IR-34 | MINOR | none (migration_support.py:299,390) | No drift today | **NOT RESOLVED** | No | Before the first registry change (post-production follow-up) | Tracked, non-blocking |
| IR-35 | MINOR | kernel/net.py:51-62; kernel/single_instance.py; deploy/gunicorn.conf.py:12-17; cmd_deploy_check; config.py:332-333 | GUNICORN_CMD_ARGS=--workers=4 → deploy-check rc 1 and gunicorn refuses; second instance locked out; CF header ignored from untrusted peers | **RESOLVED** | No | — | Residual RR-10 (0.0.0.0/0 accepted) |
| IR-36 | MINOR | app/src/modules/auth/profile-page.ts:198 | Lands on /login; Back shows no stale data; other session 401 | **RESOLVED** | No | — | — |
| IR-37 | MINOR | components.ts:48-55,158-178; mfa-pages.ts:34-53,90; user-drawer.ts:266-269; app.ts:200-208 | Stepper, toasts, prompt fixed; step-up dialog has no expiry warning; command palette and vs-tabs semantics unchanged | **PARTIALLY RESOLVED** | No | Production | Author matrix overstates as RESOLVED (RR-18) |
| IR-38 | MINOR | access.e2e.mjs:93-100,120-124,141-145; new journeys; e2e in CI (ci.yml e2e job) | 47/47 reproduced; Chromium only; focus assertion accepts #outlet; site CSP check covers index only; axe site scan bypasses CSP | **PARTIALLY RESOLVED** | No | Production (browser matrix) | RR-A19 |
| IR-39 | MINOR | pyproject [tool.mypy]; tools/mypy_ratchet.py; tools/mypy-baseline.json; app/eslint.config.js; app/.nvmrc 22.23.3; Vite 7.3.6; WTR 1.0; public npm lockfile | ruff check/format clean; ratchet 157=157 OK; ESLint 0; npm audit 0 (full and runtime); 476/476 packages from registry.npmjs.org | **RESOLVED** | No | — | New: ratchet fails open (RR-16); ESLint sink gaps (RR-A18) |
| IR-A01 | ADVISORY | enroll confirm row lock only (mfa.py:401-409) | PG: refresh / recovery-code double use → 409 (version column); per-challenge attempts exceeded (9 of 9 parallel guesses vs limit 5) | **ACCEPTABLY GATED FOR PRODUCTION** | No | PostgreSQL cut-over | — |
| IR-A02 | ADVISORY | none | Timing delta 0.93 ms (head) vs 0.79 ms (baseline) | **NOT RESOLVED** | No | — | Accepted residual |
| IR-A03 | ADVISORY | auth/service.py:535-540 | Public-site origin → 403 on refresh/logout; app origin 200 | **RESOLVED** | No | — | — |
| IR-A04 | ADVISORY | auth/service.py:686-689 | Challenges end on reset; MFA_ENROLLMENT link survives (usable only with the new password) | **PARTIALLY RESOLVED** | No | — | No practical impact |
| IR-A05 | ADVISORY | app.py:53-102 | auth='optional' + permission still starts and runs unchecked for anonymous callers (probe); no current route affected | **PARTIALLY RESOLVED** | No | — | Latent |
| IR-A06 | ADVISORY | none (rbac/roles.py) | ADMIN PATCH own role mfa_required=false → 200 | **NOT RESOLVED** | Possibly (08 §6.1) | — | Owner decision |
| IR-A07 | ADVISORY | governance.py:494-501,530-539 (SENSITIVE_ACTION on deny/cancel); rbac/routes.py:436-458 (403/404 kept) | N16; events added; sensitive-grant email on invite not added | **PARTIALLY RESOLVED** | No | — | Decision: KEEP 403/404 DIFFERENCE (§9) |
| IR-A08 | ADVISORY | none | Source | **NOT RESOLVED** | No | Production traffic hardening | — |
| IR-A09 | ADVISORY | config.py:23,293-300 (MIN_KEY_BYTES) | Short keys refused in staging/production | **RESOLVED** | No | — | Key quality residual RR-10 |
| IR-A10 | ADVISORY | none (governance.py:589-620 still binds via outbox_event) | Retention unset ⇒ nothing purged | **ACCEPTABLY GATED FOR STAGING** | Text in AM-5 | Production: config check retention ≥ 3× break-glass delay | — |
| IR-A11 | ADVISORY | none | P14 [204, 204] | **NOT RESOLVED** | AM-9 (incomplete) | Production (PG-BG policy) | Owner decision |
| IR-A12 | ADVISORY | none (kernel/http.py:151-160) | Source | **NOT RESOLVED** | No | — | Accepted as correlation-only |
| IR-A13 | ADVISORY | kernel/turnstile.py:49-57 (hostname checked) | Source | **PARTIALLY RESOLVED** | No | — | action not checked |
| IR-A14 | ADVISORY | worker.py:155-181 (OutboxDead metric); health.py:102 | Worker metric dropped (RR-07); erasure-audit per-event handling unchanged | **PARTIALLY RESOLVED** | No | Production alerting | — |
| IR-A15 | ADVISORY | none | — | **NOT RESOLVED** | AM-10 | Production (DPDP erasure completeness) | Owner decision |
| IR-A16 | ADVISORY | none | PG: 201 + 409 DUPLICATE, 1 lead | **ACCEPTABLY GATED FOR PRODUCTION** | No | PostgreSQL release gate | — |
| IR-A17 | ADVISORY | platform/health.py:60-66,112-113 | Edge gets {status} only; no secrets | **RESOLVED** | AM-6 | — | Details unreachable from host in compose topology (RR-17) |
| IR-A18 | ADVISORY | none | Bad datetime inserts succeed on SQLite; no enum CHECKs on 3 columns | **NOT RESOLVED** | No | Post-production | Tracked |
| IR-A19 | ADVISORY | cli/main.py:130-131 via='CLI'; 0005_audit.py:119 | sync-permissions audit row via CLI | **RESOLVED** | No | — | — |
| IR-A20 | ADVISORY | none (crypto.py:126,133) | Source | **NOT RESOLVED** | No | Post-production | Tracked |
| IR-A21 | ADVISORY | components.ts:311 (CSSOM); vite.config.ts:8 sourcemap false; playwright/axe-core devDependencies | 0 app CSP violations; no maps in build | **RESOLVED** | No | — | — |
| IR-A22 | ADVISORY | AM-8 drafted | Source | **PARTIALLY RESOLVED** | AM-8 | — | Owner decision |
| IR-A23 | ADVISORY | none | Source | **NOT RESOLVED** | No | Production (Privacy Notice) | Owner/legal decision |
| IR-A24 | ADVISORY | none (OI-11) | axe: 18 pre-existing nodes outside the form | **NOT RESOLVED** | No | — | Tracked non-blocker |
| IR-A25 | ADVISORY | Report and registers corrected (DEV-004 UI claim, counts) | New inaccuracies: IR-37 and the site-CSP '0 violations' claim overstated; registry omits 9 advisories; DEV-004 'visible in timeline' overstated | **PARTIALLY RESOLVED** | No | — | RR-A16, RR-A20 |

**Author claim "all repository-fixable MAJOR findings addressed".** This is **largely true**, but three qualifications apply:
1. IR-03 and IR-12 retain repository-fixable defects (RR-05, RR-06, RR-07).
2. The IR-08 fix enabled RR-02.
3. The IR-23 fix (DEV-007) weakened authentication (RR-04).

**Original severity upgrades revisited.**
- **IR-04 (MINOR→MAJOR): justified.** It broke explicit 06 §7.2.3 and §7.4 requirements and G11, with an observable end state. RR-03 is its sibling.
- **IR-16 (MINOR→MAJOR): justified.** The fix required a substantive redesign, and the consent-provenance defect was real.
- **IR-14 (ADVISORY→MAJOR): justified.** Every other gate depends on CI, and CI had never run. It is now resolved.

## 6. Founder governance (Phase 5)

The original probes P01–P17 were ported and pass 22/22. The new probes N01–N17 pass 17/17 on SQLite. The concurrency and state probes were re-run on PostgreSQL with the same outcomes.

| Control | Result |
|---|---|
| Requester, target and duplicate approver cannot approve | Held |
| Founder powers via generic user/role/permission APIs, direct `user.founder.manage` grant, role copy | Blocked (403 FOUNDER_GOVERNANCE_REQUIRED / IMMUTABLE_FIELD) |
| Bootstrap creates only the first Founder | Held |
| Single-Founder recovery follows break-glass | Held; full break-glass only when no other eligible Founder (IR-05) |
| Last Founder cannot be removed; last administrator protected | Held (409 LAST_FOUNDER / I2) |
| Execution-time and stale eligibility | Held for requests (IR-04). **Not held** for an already-executed email change (RR-03) or for restore (RR-02) |
| Concurrent requests | Serialised on both engines |
| Break-glass cancellation | Policy, single use, sibling invalidation, audit and security events correct. The endpoint is registered in the RBX register and OpenAPI, and the page exists (IR-07). The OpenAPI status code is wrong (RR-A09) |
| Custodian identity | Self-assertion closed, but the deployed topology yields the instance role (RR-09) |

## 7. Tamper-evident audit chain (Phase 6)

Local probes, both engines (Appendix D.1):

| Check | Result |
|---|---|
| Modification, middle deletion (gap), anchored-prefix deletion, tail truncation below anchor, emptied log | **Detected** |
| Rows after the latest anchor deleted | Not detected (accepted architecture residual) |
| Archive-boundary continuity, legitimate archival | No false positive |
| Multi-thread / multi-process writers (4 × 20) | Clean chain, no fork |
| Transaction rollback | No gap |
| **Forged archive manifest** | **Not detected: RR-05 (MAJOR)** |
| **Manifest written before DB commit** | **False alarm and permanent wedge: RR-06 (MAJOR, regression)** |
| Anchor store unavailable | Verification raises (fails closed) but emits no event, metric or CRITICAL log (RR-07) |
| Restore-verify chain check | Trusts the first online row (RR-A14) |

**S3 Object Lock anchoring.**
- The code is real: COMPLIANCE mode with 3650-day retention.
- It is tested only against an in-memory fake that does not enforce write-once behaviour.
- There is no writer/verifier role separation.
- Staging falls back to a same-host local store.
- **Classification:** repository behaviour partially resolved (RR-05 and RR-06 open); **staging evidence required**; **production gate required** before SEVT-006/007 can be claimed. AWS behaviour was **not executed**.

## 8. Deviation decisions: DEV-001 to DEV-008 (Phase 7)

None of DEV-001 to DEV-008 is owner-approved. The register shows "PENDING ARCHITECTURE-OWNER DECISION" (DEV-004: "CORRECTED — PENDING RE-REVIEW AND ARCHITECTURE-OWNER DECISION").

| Deviation | Subject | Decision | Amendment | Basis |
|---|---|---|---|---|
| DEV-001 | MFA factor uniqueness (PENDING + ACTIVE coexist) | **ACCEPTABLE WITH ARCHITECTURE AMENDMENT** | AM-1 | IR-20 condition met; only one ACTIVE factor; PENDING never authenticates |
| DEV-002 | Invitation acceptance returns MFA_ENROLLMENT_REQUIRED | **ACCEPTABLE WITH ARCHITECTURE AMENDMENT** | AM-2 | Conditions IR-01, IR-21, IR-25 met; AM-2 must state that link replay before activation overwrites the password |
| DEV-003 | Optional login CAPTCHA token | **ACCEPTABLE WITH ARCHITECTURE AMENDMENT** | AM-3 | Conditions IR-22, IR-09, IR-02 met |
| DEV-004 | Staff lead re-consent (corrected) | **ACCEPTABLE WITH ARCHITECTURE AMENDMENT** | AM-4 | Corrected behaviour verified on both engines; residuals RR-12 |
| DEV-005 | Break-glass cancel link endpoint and page | **ACCEPTABLE WITH ARCHITECTURE AMENDMENT** | AM-5 | Endpoint, page, authorization, replay prevention, events, RBX registration verified; OpenAPI status code RR-A09 |
| DEV-006 | mfa_challenge binding columns (IR-01) | **ACCEPTABLE WITH ARCHITECTURE AMENDMENT** | AM-11 | Expand-only; no schema/authz/replay/migration regression; AM-11 incomplete (rollback reintroduces IR-01; 02 §8.3 placement) |
| DEV-007 | Per-email limits keyed by (email, network) | **REQUIRES IMPLEMENTATION CHANGE** | AM-7 (revise) | Removes cross-network guessing bound for MFA holders and reset-email cap (RR-04) |
| DEV-008 | Readiness accepts declared newer schema; edge sees {status} | **ACCEPTABLE WITH ARCHITECTURE AMENDMENT** | AM-6 | Safe; no secrets; AM-6 must state that rollback of this release is snapshot restore (RR-17) |

**DEV-004 verification:**
- Re-consent without withdrawal or a new version → 409.
- Staff channel `WEBSITE_FORM` → 422.
- A note is required.
- The staff capture carries no web IP or source page.
- A system activity and an audit row are written.
- SALES is limited to its own scope.
- Superseded evidence is preserved in `consent_evidence` activities plus the immutable `audit_log`.
- **Residuals (RR-12):**
  - alternating between published versions is accepted;
  - activity rows are mutable at DB level;
  - staff create-time consent needs no note.

**DEV-005.**
- Endpoint: correct.
- Page `/approvals/cancel`: POSTs only on an explicit click.
- Authorization: anonymous with a token, correct.
- Replay: prevented.
- Audit and security events: present.
- RBX-003 registration: in the runtime register and the OpenAPI snapshot.

**DEV-006.** Migration `0009` is expand-only. It adds two nullable columns, one FK (RESTRICT) and CHECKs. It introduces no authorization, replay or migration regression. The only issue is chain placement against 02 §8.3 (RR-A17).

**DEV-007** requires an implementation change:
- User enumeration: none; the response is uniform.
- Cardinality: bounded by in-memory limiter storage.
- Proxy-IP spoofing: governed by the trusted-proxy CIDRs (RR-10).
- Privacy: no leakage.
- Victim DoS: **fixed**.
- **But:** the cross-network guessing bound for MFA holders and the reset-email cap are **removed** (RR-04).

**DEV-008.** Readiness is safe:
- The edge gets `{status}` only; details go to loopback callers only; no secrets.
- It is architecture-compatible with AM-6, subject to the documentation gaps in RR-17.

## 9. Proposed architecture amendments: AM-1 to AM-11 (Phase 8)

All 11 amendments are marked **PROPOSED, NOT APPROVED** in `docs/architecture/amendments/AM-*.md` and `amendments.json`. None is approved by this review.

| Amendment | Subject | Assessment | Owner approval needed before | Gaps |
|---|---|---|---|---|
| AM-1 | 03 §5.5 factor index | Technically sound | Merge | — |
| AM-2 | 08 §4.5 / 05 §11.3 invite MFA response | Technically sound; incomplete | Merge | Add: link replay before activation overwrites the password (path B second proof = link possession) |
| AM-3 | 08 §4.1/§4.7 optional CAPTCHA input | Technically sound | Merge | — |
| AM-4 | 04 §5.4 vs 08 §8.5 re-consent | Technically sound; incomplete | Merge | Define 'new version' as later; create-time staff consent; DB-level immutability or dedicated append-only table |
| AM-5 | 08 §1 / 06 §11 / 09 break-glass cancellation | Technically sound; incomplete | Merge | Rollback text contradicts 06 §7.5; does not enforce outbox retention ≥ break-glass window (IR-A10); document in-app deny vs link cancel (RR-A11) |
| AM-6 | LOG-005 / 08 §3 / 02 §12.4 readiness and rollback | Technically sound; incomplete | Merge | State that rollback of this release is snapshot restore; details unreachable from host under compose (RR-17) |
| AM-7 | 08 §12 per-email limits | **Technically unsound as written; conflicts with certified 05 §4 intent** | Merge (revise, do not approve) | Its security-impact statement is false for MFA holders and reset-email volume (RR-04) |
| AM-8 | 05/03 HMAC-derived action tokens | Technically sound (documentation) | Production | — |
| AM-9 | 06 §7.5 hostile sole-Founder veto | Incomplete | Production | Lists options without a decision; option 3 misses the notified-Founder case (P14); ignores IR-05 interplay (custodians cannot remove an eligible hostile Founder) |
| AM-10 | 07 §2 PII fields / IP retention | Technically sound; incomplete | Production | Omits consent_evidence metadata, outbox_event.last_error, user_agent |
| AM-11 | 03 §5.7 / 05 §11.3 MFA transaction binding | Technically sound; incomplete | Merge | Must warn that rollback to 9236aa3 reintroduces IR-01; document binding and refresh-rotation rules; amend 02 §8.3 migration placement (RR-A17) |

**Before merge (owner approval required):** AM-1, AM-2, AM-3, AM-4, AM-5, AM-6 and AM-11. Each describes behaviour the merged code already implements.
- AM-7 must be **revised, not approved**, together with the DEV-007 fix.

**Before production:** AM-8, AM-9 and AM-10.

**Topics with no amendment:**
- Approval existence hiding (IR-A07): decision below, no amendment needed.
- MFA transaction binding: AM-11.
- Migration rollback strategy: AM-6 and AM-11, incomplete per RR-17.

## 10. API and RBAC regression; IR-A07 (Phase 9)

- **Route count.** 105 routes at runtime (107 `url_map` rules including `static` and non-production `openapi.json`), unchanged from `9236aa3`. The 08 index differences are unchanged: `cancel-link` extra, `leads/exports` (P1) absent.
- **Startup validation:**
  - It now rejects unregistered RBX ids, a public route that declares a permission, and paths not in the RBX register.
  - **Still accepted:** a route with `auth="optional"` plus a permission starts up, and anonymous callers bypass the permission (IR-A05, latent; no current route is affected).
- **Core rules at runtime, all held under the probe set:**
  - default deny, DENY-over-GRANT;
  - direct, role and scoped permissions;
  - MFA for sensitive permissions;
  - session and `authz_version` invalidation on the next request;
  - horizontal and vertical authorization, IDOR (404s);
  - mass assignment (422);
  - Founder-power isolation;
  - the public exception registry;
  - no lead enumeration.

**IR-A07 decision: KEEP 403/404 DIFFERENCE.**
- It is what the certified 08 §5.11 and 12 TD-G specify. Normalizing would itself deviate.
- Only callers already holding an approvals permission (admin class) can observe the difference. SALES receives 403 either way.
- Approval ids are UUIDv7 with 74 random bits, so they cannot be guessed.
- The same ids are already visible to those callers in security events and audit logs.
- **Architecture impact:** none.

## 11. Database and migrations (Phase 10)

| Check | SQLite 3.50.4 | PostgreSQL 16.4 | PostgreSQL 18.4 |
|---|---|---|---|
| Revisions / heads | 10 / 1 (`0009_mfa_challenge_binding`) | same | same |
| Fresh upgrade | OK | OK | OK |
| Tables / columns / FKs / indexes / triggers | 24 / 504 / 108 / 72 / 4 | 24 / 504 / 108 / 72 / 4 | same |
| CHECK constraints | 498 | 164 | 164 |
| Seeds | 3 system users; no human users; deterministic across fresh DBs | same | same |
| Upgrade with data from `9236aa3` head | Schema identical to a fresh install | identical | — |
| Downgrade | Refused (`NotImplementedError`), DB unchanged | same | — |
| Immutable logs | Triggers block UPDATE/DELETE | TRUNCATE and GUC bypass still succeed (IR-33, gated to PGM-1) | — |

**Other properties**
- UUIDv7, the nine audit columns, version columns, constraints and FK RESTRICT all verified.
- `0009` is expand-only, and the `9236aa3` application writes correctly on the migrated schema.
- The edits to revisions 0001–0008 and 0100 are reformatting only; the schema is identical.

**Forward-fix and rollback.**
- The implementation matches AM-6 and DEV-008 for *future* releases.
- **Rollback of this release to `9236aa3` is never ready**: 503 `behind`. It would also reintroduce the IR-01 BLOCKER. Rollback of this release is therefore snapshot restore, and the runbook, AM-6 and AM-11 do not say so (RR-17).
- **No rollback rehearsal occurred.** RG-7 is Pending.

## 12. Test and CI reproduction (Phase 11)

| Suite | Author | This review | Command / note |
|---|---|---|---|
| Backend SQLite (full) | 435 passed | **435 passed, 0 skipped** (25.3 s) | `VEDA_TEST_ENGINES=sqlite python -m pytest -q -rs` |
| Backend PostgreSQL 16.4 (full) | 427 / 8 skipped | **427 passed, 8 skipped** (81.4 s) | standalone 16.4 via `VEDA_TEST_DATABASE_URL_PG` |
| Backend PostgreSQL 18.4 (full) | 427 / 8 skipped | **427 passed, 8 skipped** (78.5 s) | embedded 18.4 |
| Skips (both PG) | — | 6 × `test_backups.py` (SQLite snapshots), `test_schema.py:93` (pragma), `test_schema.py:354` (SQLite format CHECKs) | legitimate |
| Security/remediation suites (SQLite) | — | auth 168 (test_auth 23, test_mfa 15, test_mfa_binding 19, test_auth_remediation 18, test_audit_security 17, config 59); governance 60 + lint 9; leads/audit 113 | domain reviewers |
| Security/remediation suites (PostgreSQL) | — | auth integration 92/92; governance integration 60; leads/audit 106 | embedded PG |
| Frontend `npm ci` (Node 22.23.3) | pass | pass; 476/476 packages from registry.npmjs.org | — |
| ESLint / lint:tokens / typecheck / contrast / build | pass | all exit 0; contrast 58 pairs | — |
| Frontend unit tests | 52 | **52 passed** (6 files) | — |
| `npm audit` / `--omit=dev` | 0 / 0 | **0 / 0** | — |
| Prettier | not configured | not configured | not required |
| Browser `run-all.sh` | 47/47 | **47/47** (workspace 7, access 16, site 14, axe 10) | covers invitation, MFA, recovery, approvals, cancel page, logout-everywhere, route focus, TD-F step 4, session expiry, 360 px |
| Reviewer browser probes | — | titles and focus on 8 routes; logout-everywhere; IR-15 lost update fixed; cancel page; app CSP 0 violations; **site CSP breaks 404 (RR-01)** | production build under the app CSP |
| Not covered | — | Firefox/WebKit; manual screen reader; re-consent UI (none in P0) | IR-38 |

**CI (inspected and evidenced).**
- The workflow has 5 jobs:
  - `api (sqlite)` and `api (postgresql)`: service `postgres:16` (floating tag); ruff; format; mypy ratchet; pytest; OpenAPI diff; deploy-check.
  - `security`: secret scan, pip-audit with hashes, bandit, npm audit, image build, Trivy (CRITICAL/HIGH, `ignore-unfixed`).
  - `app`: lint, typecheck, tokens, contrast, test, build.
  - `browser e2e + axe`.
- No `continue-on-error` or `|| true` anywhere, so every step is mandatory. Actions are pinned by commit SHA.
- **GitHub API:** run **36559966718** (push, attempt 1) on `2f6b59a`: all 5 jobs `success`, with the JUnit artifacts `pytest-sqlite` and `pytest-postgresql`. On `6fd249c`, only "Container image scan" failed, which matches the stated reason for `2f6b59a`.
- The PostgreSQL leg's "PostgreSQL server version" step ran. Logs require authentication, so the printed version was not independently read.
- **Container scan.** It passes because pip (vendored msgpack/setuptools) was removed. `ignore-unfixed` has no recorded risk acceptance (RR-A15).
- **Removing pip.** Verified in a simulated no-pip environment: `migrate`, `bootstrap-founder`, `maintenance`, `worker`, `scheduler`, `deploy-check` and gunicorn all run. No runbook step uses pip.

## 13. Quality and security tooling (Phase 12)

| Tool | Result |
|---|---|
| ruff check / ruff format --check | clean (137 files formatted) |
| mypy ratchet | 157 errors = baseline 157, OK. A new error fails. **Fails open** when mypy is missing or misconfigured, and `--update` admits new or renamed files (RR-16) |
| ESLint | 0 errors. Sink bans narrower than claimed; site JS not linted (RR-A18) |
| Node | 22.23.3 (Maintenance LTS); `engine-strict` rejects 24 (RR-A22) |
| npm lockfile | public registry only |
| Dependency advisories | pip-audit 0 (hash-locked); npm 0/0 |
| Secret scan | `api/tools/secret_scan.sh` clean against `.secrets.baseline` (104 entries, none marked audited: RR-A15) |
| Bandit (-ll -ii) | clean |
| Container scan | pass (see §12) |
| Route-exception validation | Stronger. Residual IR-A05 |
| Migration validation | Conformance, order and upgrade-with-data tests on both engines |
| Browser tests in CI | Yes (`e2e` job) |

**Hostname-dependent JavaScript fixtures.**
- No committed file has a hostname in its name.
- The coupling is inside `app/e2e/static-server.mjs`: string replacements of `.test` addresses that fail loudly.
- No personal or secret data; deterministic.
- Running them from public history alone needs the Python API venv, Node 22, Playwright Chromium and free ports, but no secrets.
- **Advisory:** the CI failure artifact upload includes `founder.json`, which holds a throwaway password and TOTP secret (RR-A25).

## 14. Public form safety (Phase 13)

| Check | Result |
|---|---|
| `veda-api-base` | empty (`dist/index.html:11`) |
| `veda-turnstile-sitekey` | empty (`dist/index.html:12`) |
| JavaScript requires both | Yes (`dist/assets/app.js:58`) |
| Network API call with feature disabled | **None.** A browser submit opens only the `wa.me` window; 0 API requests |
| Consent block / Turnstile block | Hidden (`data-intake-only hidden`) |
| Visible link to nonexistent `/privacy` | None visible (the link sits inside the hidden consent label) |
| WhatsApp fallback | Works |
| Public site behaviour vs `778aa8f` | Changed. **The new site CSP breaks the 404 page (RR-01).** With the flag off, an empty submit now opens WhatsApp with a blank enquiry (RR-11, dating from `9236aa3`) |

**Required before enabling the form:**

| Prerequisite | Category |
|---|---|
| Privacy Notice published at `/privacy` (v2026-09-v1) | privacy gate (PG-PRIV) |
| Production Turnstile site key and secret | Turnstile setup |
| Site CSP `connect-src` for the chosen API origin; the 404 CSP fix (RR-01) | CSP |
| API endpoint live with production config | API endpoint |
| CORS `public_site_origins` | CORS |
| Rate limits and trusted-proxy CIDRs (RR-10) | rate limiting |
| Staging run with real keys, including 422 → reset → 201 (IR-18) | staging verification |
| Production approval | production approval |

## 15. Staging-only findings (Phase 14)

None of these is production-resolved. Unit tests with stubbed AWS clients do not count as evidence. The full table is in Appendix E.3.

| Item | Code ready for staging? | Acceptance criteria | Evidence required | Owner | Failure behaviour | Re-review |
|---|---|---|---|---|---|---|
| IR-03 S3 Object Lock anchor | Code ready with design residuals (latest-anchor only; one shared role). **Repository defects RR-05 and RR-06 first** | Daily anchor in a bucket with Object Lock COMPLIANCE and versioning; delete or overwrite refused; separate writer and verifier roles; tamper drill detected | Bucket config, CloudTrail, drill output | Ops + Security | Store error: verify raises, fails closed but **silently** (RR-07) | Yes |
| IR-06 STS custodian | **Not ready as documented** (RR-09) | Two distinct custodian ARNs from STS in one drill; mismatched assertion refused with a FAILURE event | Drill log plus CloudTrail | Security Owner (OWNER-INPUT-004) | Instance role → 403 not registered; no credentials → uncaught exception | Yes |
| IR-11 replication / restore / rollback | Partially ready (RR-14, RR-15) | Litestream lag within RPO; restore from S3 to a new host passes restore-verify; timed RTO; rollback rehearsal | RG-1, RG-2, RG-7, OWNER-INPUT-001 | Ops | Restore-verify failure metric dropped (RR-07) | Yes |
| IR-12 alarm routing / test-fire | **Not ready** (RR-07) | Every runbook §9 alarm test-fired end-to-end | RG-5 alarm history | Ops + Engineering | No metrics from CLI jobs | Yes |
| SES | Code ready | Verified domain, DKIM/SPF/DMARC, out of sandbox, bounce events, staging send | Console/CLI evidence | Ops | Retry → dead-letter (metric dropped) | Targeted |
| KMS | Code ready | Real CMK enrollment; decrypt after rotation; least-privilege key policy | Key policy, CloudTrail | Ops + Engineering | 500 on enrollment/verify (fails closed) | Targeted |
| S3 snapshots | Code ready; snapshot dir not enforced (RR-14) | COMPLIANCE upload plus 35-day retention | Object retention headers | Ops | Exception, no metric | Targeted |
| Readiness | Code ready; host sees `{status}` only (RR-17) | External check alarms; deploy gate uses status | Deploy logs | Ops | 503 → deploy stops | — |
| Cross-cutting | — | IMDSv2 hop limit ≥ 2; `/var/lib/veda` owned by uid 10001 | Instance metadata, `ls -ln` | Ops | All AWS adapters fail | — |

## 16. Open-issue and gate registry (Phase 15)

`docs/implementation/P0-open-issues.{md,json}` holds 106 items.

| Required content | Present? |
|---|---|
| Every original finding | **Partial.** All IR-01 to IR-39 present with correct severities. **Only 16 of 25 advisories**: IR-A03, A04, A05, A09, A13, A17, A19, A21 and A25 are missing, contrary to the registry's own note (RR-A16) |
| Every current finding | Not yet (this re-review's RR-* findings must be added) |
| 8 deviations | Yes |
| 11 proposed amendments | Yes, all PROPOSED, NOT APPROVED |
| 27 gates | Yes. They match `docs/architecture/gate-registry.json` exactly (unchanged since `778aa8f`) |
| Remediation items | Yes (OI-RM-1 to OI-RM-5) |
| Owner categories, acceptance criteria, evidence, blocking scope, status | Yes on every item |
| Production gate incorrectly closed | **None.** All RG-* and PG-* are Pending or Blocked |
| TG-01 / TG-08 | **Pending** (no owner evidence). Both block merge |

**Inconsistencies:**
- IR-14 is shown RESOLVED while OI-RM-1 ("first CI run") is OPEN. OI-RM-1 can now be closed with run 36559966718.
- IR-37 is overstated as RESOLVED.
- The IR-39 text mischaracterises the mypy backlog.

## 17. New regressions (Phase 16)

| Area searched | Result |
|---|---|
| MFA enrollment deadlocks, invitation failures, recovery lockout | None found (race runs on both engines, no 500s) |
| Token rotation errors | **RR-08** (MAJOR) |
| Authorization-cache errors | None |
| Inconsistent HTTP responses | PostgreSQL 409 vs SQLite 401 under concurrency (RR-A02); OpenAPI 200 vs 204 (RR-A09) |
| Unusable break-glass links | Fixed (page exists). Custodian identity topology **RR-09** |
| Tamper-chain false confidence | **RR-05** (forged manifest), **RR-06** (false alarm and wedge) |
| Migration incompatibility | None (upgrade with data identical to fresh install) |
| SQLite/PostgreSQL differences | IR-33, IR-A01, IR-A16 (PostgreSQL gate) |
| Proxy/IP rate-limit bypass | **RR-04** (network-keyed per-email limit); **RR-10** (0.0.0.0/0 accepted) |
| Readiness leaking secrets | None |
| CI-only behaviour differing from production | Tests run CLI jobs in-process with logging configured, masking **RR-07**; e2e uses the Flask dev server (RR-A15) |
| Site CSP breakage | **RR-01** (404 page) |
| Public-form accidental activation | None |
| Governance regressions | **RR-02** (restore), **RR-03** (email change after promotion) |

## 18. New findings

Severity counts: **BLOCKER 0 · MAJOR 9 · MINOR 9 · ADVISORY 25**.

Following the brief's rule, every new authentication, authorization, audit-integrity or data-loss defect is rated at least MAJOR.

| ID | Severity | Title | Origin | Verification | Blocking scope |
|---|---|---|---|---|---|
| RR-01 | **MAJOR** | Site-wide CSP blocks the 404 page's inline stylesheet; because a push to main deploys dist/ to www.vedaspaces.com, merging ships a broken 404 page to production | Regression introduced by remediation (IR-32 site CSP) | REPRODUCED (Chromium, exact _headers) | merge (merge = production site deploy) |
| RR-02 | **MAJOR** | A single Founder can restore a Founder deleted through dual-Founder approval (G11 bypass; no governance record) | Regression enabled by the IR-08 fix | REPRODUCED (SQLite and PostgreSQL) | merge (Founder-governance invariant; same class as IR-04) |
| RR-03 | **MAJOR** | An executed STANDARD email change stays pending through GRANT_FOUNDER and can be verified on the new Founder | Residual of IR-04 not covered by the remediation | REPRODUCED (SQLite and PostgreSQL) | merge (Founder-governance invariant) |
| RR-04 | **MAJOR** | DEV-007 keys per-email login/forgot limits by (email, network), removing the only cross-network bound on password guessing for MFA holders and multiplying reset-email volume | Regression introduced by DEV-007 (IR-23 fix) | REPRODUCED (SQLite) | merge (unapproved deviation that weakens authentication) / production |
| RR-05 | **MAJOR** | A forged archive manifest written with the host credential hides deletion of any prefix of the security-event chain, including anchored rows | Defect in the new IR-03 design | REPRODUCED (SQLite and PostgreSQL) | production (SEVT-006/007 claim) |
| RR-06 | **MAJOR** | Archival writes the write-once manifest before the database commit; any later failure produces a permanent false 'prefix removed' alarm and blocks archival forever | Regression introduced by the IR-03/IR-26 remediation | REPRODUCED (SQLite and PostgreSQL) | production (before archival is enabled; archival refuses without OWNER-INPUT-002) |
| RR-07 | **MAJOR** | CLI, scheduler and worker processes never configure logging, so every maintenance/worker metric (backup, chain, anchor, invariants, dead outbox) is dropped and the scheduler ignores job exit codes | Defect in IR-12 remediation | REPRODUCED (0 EMF lines from CLI jobs | staging (alarm acceptance) / production (RG-5) |
| RR-08 | **MAJOR** | Path A enrollment confirm retires the session's refresh tokens without a successor link, so a benign concurrent refresh is treated as token theft and revokes the just-elevated session | New token-rotation defect (path A confirm); same pattern pre-exists in change_password | REPRODUCED | production |
| RR-09 | **MAJOR** | Break-glass STS identity check sees the host instance role, not the custodian, when the CLI runs via docker compose as the runbook prescribes; with no credentials it crashes without a failure event | Residual of IR-06 in the deployed topology | SOURCE-INSPECTED + REPRODUCED (N06) | production (PG-BG) |
| RR-10 | **MINOR** | Environment validation accepts trusted-proxy CIDR 0.0.0.0/0 or ::/0, all-zero / dev-derived / duplicate 32-byte keys, and an unparsable JWT PEM | Residual of IR-09/IR-35 | REPRODUCED (config probe) / SOURCE-INSPECTED | staging |
| RR-11 | **MINOR** | With intake disabled the enquiry form is novalidate and skips client validation, so an empty submit opens WhatsApp with a blank enquiry (baseline 778aa8f blocked it) | Introduced at 9236aa3, not caught in the original review | REPRODUCED | merge (ships to the live site on merge; cheap fix) |
| RR-12 | **MINOR** | DEV-004 residuals: alternating between published policy versions is accepted without withdrawal; consent history activity is mutable at DB level; staff create-time consent needs no note and writes no consent activity | DEV-004 residual | REPRODUCED | production |
| RR-13 | **MINOR** | Residual PII paths: Sentry transaction events carry request query strings (e.g. lead search by email); outbox_event.last_error stores provider errors containing recipient emails | IR-27 residual | REPRODUCED | production |
| RR-14 | **MINOR** | Snapshot directory defaults to container storage and is not required in staging/production, so deploy.sh's pre-deploy snapshot in a --rm container is lost | IR-11 residual | SOURCE-INSPECTED + config probe | staging |
| RR-15 | **MINOR** | Disaster-restore runbook does not work as written: restore-verify fails on a Litestream-restored file, Litestream is not stopped before the swap, one failure path emits no metric, the off-host replica is never verified | IR-11 residual | REPRODUCED (a) / SOURCE-INSPECTED | staging |
| RR-16 | **MINOR** | mypy ratchet fails open: reports '0 errors OK' when mypy is missing or its config is broken; --update silently admits errors from new or renamed files | IR-39 residual | REPRODUCED | staging (CI gate integrity) |
| RR-17 | **MINOR** | Rollback documentation gaps: rollback of this release to 9236aa3 is never ready (and would reintroduce IR-01); readiness details are unreachable from the host under the compose topology; deploy.sh only checks the declaration line | IR-10 residual | REPRODUCED | production (RG-7) |
| RR-18 | **MINOR** | Accessibility remnants: step-up dialog has no pre-expiry warning; command palette listbox/option semantics and vs-tabs tabpanel wiring unchanged; account menu stays open on outside click | IR-37 residual; author matrix overstates | REPRODUCED / SOURCE-INSPECTED | production |

### 18.1 Detail

#### RR-01 · MAJOR · Site-wide CSP blocks the 404 page's inline stylesheet; because a push to main deploys dist/ to www.vedaspaces.com, merging ships a broken 404 page to production

- **Origin:** Regression introduced by remediation (IR-32 site CSP) (working-paper ID RR-FE-1)
- **Verification:** REPRODUCED (Chromium, exact _headers); lead reviewer confirmed source and computed the same hash
- **Evidence:**
  - dist/_headers:2 — style-src 'self' https://fonts.googleapis.com (no 'unsafe-inline', no hash), applied to /*
  - dist/404.html:15-44 — inline <style> block, unchanged since 778aa8f; sha256-nsu5zW5KZLyHAh1E42iLcu9GL6H14jnCxGdJDe3Q5v4=
  - Chromium: style-src-elem violation on /404.html, /no-such-page and /privacy; page renders unstyled; 778aa8f renders correctly
  - README.md:43-45 and deployment.md:31 — a push to main deploys dist/ to production within a minute
  - site e2e checks CSP on index.html only (missed this)
- **Affected requirements:** SEC-003, Public site availability, deployment.md release checklist
- **Exploit / failure scenario:** Branch is merged to main; Cloudflare Pages deploys; every mistyped or stale URL on the live site renders an unstyled page.
- **Required remediation:** Move the 404 styles to /assets/404.css, or add the sha256 hash to style-src; add every dist/*.html page to the site CSP E2E.
- **Validation:** Browser run of every dist page under the exact _headers with 0 CSP violations.
- **Architecture amendment required:** No
- **Owner decision required:** No
- **Blocking scope:** merge (merge = production site deploy)
- **Re-review requirement:** Targeted re-review of the fix

#### RR-02 · MAJOR · A single Founder can restore a Founder deleted through dual-Founder approval (G11 bypass; no governance record)

- **Origin:** Regression enabled by the IR-08 fix (working-paper ID RR-RBAC-1)
- **Verification:** REPRODUCED (SQLite and PostgreSQL); lead reviewer confirmed source
- **Evidence:**
  - api/veda/platform/rbac/users.py:253-262 — restore_user applies only G9 (passes Founder→Founder); no G3, no G11, no InvariantGuard, no security event
  - api/veda/platform/rbac/guards.py:176-192 — deleted Founder keeps FOUNDER user_role and protection_level
  - P11/N11: F1+F2 delete F3 (EXECUTED); F1 alone POST /users/{F3}/restore → 200; F3 back as DISABLED FOUNDER-protected account
- **Affected requirements:** RBAC-020, RBAC-021, 06 §7.1 G9/G11, 06 §7.2.2, 06 §7.2.6
- **Exploit / failure scenario:** One Founder unilaterally reverses a dual-control deletion; reactivation still needs a second Founder, but the dual-control decision is undone without trace.
- **Required remediation:** Apply G11 (403 FOUNDER_PROTECTED + BYPASS_BLOCKED event) and G3 in restore_user; either declare deleted Founders unrestorable or add a RESTORE status to FOUNDER_STATUS_CHANGE (owner choice).
- **Validation:** P11/N11 → 403 FOUNDER_PROTECTED on both engines; TD-G case.
- **Architecture amendment required:** Only if workflow restore is chosen (06 §7.2.2)
- **Owner decision required:** Yes — unrestorable vs workflow restore
- **Blocking scope:** merge (Founder-governance invariant; same class as IR-04)
- **Re-review requirement:** Targeted re-review of the fix

#### RR-03 · MAJOR · An executed STANDARD email change stays pending through GRANT_FOUNDER and can be verified on the new Founder

- **Origin:** Residual of IR-04 not covered by the remediation (working-paper ID RR-RBAC-2)
- **Verification:** REPRODUCED (SQLite and PostgreSQL); lead reviewer confirmed source
- **Evidence:**
  - api/veda/platform/rbac/governance.py:160-178,325 — only open STANDARD requests are cancelled on GRANT_FOUNDER; proposed_email is never cleared (no reference in governance.py)
  - api/veda/platform/auth/service.py:887-923 — verify_email_change has no protection-level check
  - N17: ADMIN email change of ADMIN a2 executed → a2 promoted → anonymous POST /auth/email/verify 204 → Founder email = attacker address
- **Affected requirements:** RBAC-020, USER-007, 06 §7.1 G11, 06 §7.2.2 FOUNDER_EMAIL_CHANGE
- **Exploit / failure scenario:** Malicious ADMIN pre-stages an email change on a colleague about to be promoted; after promotion the attacker verifies from their mailbox and future reset links go to the attacker (MFA still guards sign-in).
- **Required remediation:** Clear the proposal and invalidate EMAIL_VERIFICATION/EMAIL_CHANGE_CANCEL tokens on GRANT_FOUNDER (event reason TARGET_BECAME_FOUNDER), or refuse GRANT_FOUNDER while a proposal is pending; make verify refuse for FOUNDER-protected users whose proposal was not self-requested.
- **Validation:** N17 → verify 400, Founder email unchanged, on both engines.
- **Architecture amendment required:** No
- **Owner decision required:** No
- **Blocking scope:** merge (Founder-governance invariant)
- **Re-review requirement:** Targeted re-review of the fix

#### RR-04 · MAJOR · DEV-007 keys per-email login/forgot limits by (email, network), removing the only cross-network bound on password guessing for MFA holders and multiplying reset-email volume

- **Origin:** Regression introduced by DEV-007 (IR-23 fix) (working-paper ID RR-AUTH-1)
- **Verification:** REPRODUCED (SQLite); lead reviewer confirmed source
- **Evidence:**
  - api/veda/kernel/ratelimit.py:22-33 — key email|network
  - api/veda/platform/auth/service.py:407 — global lock applies only when the user has no factor (throttle.py:6-9)
  - api/veda/platform/auth/service.py:464-473 — a correct password returns MFA_REQUIRED (password oracle)
  - Probe: 40 guesses in one minute from 8 IPv6 /64s all evaluated (baseline: 5 then 429); 18 reset emails delivered vs 3
- **Affected requirements:** AUTH-010, SEC-011, 05 §4, 08 §12
- **Exploit / failure scenario:** Attacker rotating networks guesses a Founder's password without any global bound, learns it from MFA_REQUIRED, then targets the second factor or reuses the password elsewhere; a victim's mailbox can be flooded with reset emails.
- **Required remediation:** Keep the network-keyed limit for lockout fairness and add a global per-email failure budget (or per-account password-failure counter that applies to MFA holders without locking them out, e.g. CAPTCHA/delay escalation); cap reset emails per email globally.
- **Validation:** Rotating-network probe bounded; P5 lockout fairness still holds.
- **Architecture amendment required:** AM-7 must be revised before approval
- **Owner decision required:** Yes — AM-7 as revised
- **Blocking scope:** merge (unapproved deviation that weakens authentication) / production
- **Re-review requirement:** Targeted re-review of the fix

#### RR-05 · MAJOR · A forged archive manifest written with the host credential hides deletion of any prefix of the security-event chain, including anchored rows

- **Origin:** Defect in the new IR-03 design (working-paper ID RR-LEAD-1)
- **Verification:** REPRODUCED (SQLite and PostgreSQL)
- **Evidence:**
  - api/veda/platform/maintenance.py:339-438 — verification trusts any manifest; no contiguity check, no export-file hash check, no SECURITY_LOG_ARCHIVED event correlation
  - Probe C11: manifest first_seq=1,last_seq=anchor+1 with dummy hash and nonexistent file, then delete rows → verify ok=True
  - Export file stays on local disk, not in Object Lock storage
- **Affected requirements:** SEVT-006, SEVT-007, 05 §9.6
- **Exploit / failure scenario:** Host-level attacker (the threat anchoring exists for) writes a manifest, deletes incriminating events, nightly verify reports ok.
- **Required remediation:** Require contiguous manifests chained to anchors, verify export-file hash from write-once storage, correlate with SECURITY_LOG_ARCHIVED events; separate writer/verifier roles.
- **Validation:** C11 → ok=False on both engines; stub-S3 test of manifest forgery.
- **Architecture amendment required:** No
- **Owner decision required:** No
- **Blocking scope:** production (SEVT-006/007 claim)
- **Re-review requirement:** Targeted re-review of the fix

#### RR-06 · MAJOR · Archival writes the write-once manifest before the database commit; any later failure produces a permanent false 'prefix removed' alarm and blocks archival forever

- **Origin:** Regression introduced by the IR-03/IR-26 remediation (working-paper ID RR-LEAD-2)
- **Verification:** REPRODUCED (SQLite and PostgreSQL)
- **Evidence:**
  - api/veda/platform/maintenance.py:441-514 — manifest stored before DB delete/commit
  - Probe C12: simulated DB failure after manifest → verify reports prefix removed; re-archive refused
- **Affected requirements:** SEVT-004, SEVT-006, AUDIT-009
- **Exploit / failure scenario:** A transient DB error during the first production archival wedges the security-log lifecycle and raises a false tamper alarm nightly.
- **Required remediation:** Two-phase: write a pending manifest keyed by run id, commit DB, then finalise; verification ignores unfinalised manifests whose rows are still online.
- **Validation:** C12 → no false alarm, archive retry succeeds.
- **Architecture amendment required:** No
- **Owner decision required:** No
- **Blocking scope:** production (before archival is enabled; archival refuses without OWNER-INPUT-002)
- **Re-review requirement:** Targeted re-review of the fix

#### RR-07 · MAJOR · CLI, scheduler and worker processes never configure logging, so every maintenance/worker metric (backup, chain, anchor, invariants, dead outbox) is dropped and the scheduler ignores job exit codes

- **Origin:** Defect in IR-12 remediation (working-paper ID RR-LEAD-3 + RR-OPS-1)
- **Verification:** REPRODUCED (0 EMF lines from CLI jobs; only a plain stderr line from logging.lastResort); lead reviewer confirmed source
- **Evidence:**
  - api/veda/app.py:111 — configure_logging is called only from create_app; no CLI path calls it
  - api/veda/cli/main.py (cmd_scheduler) — subprocess.run([...maintenance, job], check=False); exit codes discarded
  - Probe: disk-usage, snapshot, restore-verify, verify-chain, invariants → 0 EMF metric lines; anchor-store outage → verify raises with no event, metric or CRITICAL
  - Tests pass only because they run in-process with logging configured
- **Affected requirements:** LOG-006, OPS-009, SEVT-009, RG-5
- **Exploit / failure scenario:** Backups stop, the chain breaks or the outbox dead-letters; no CloudWatch alarm ever fires because no metric is emitted.
- **Required remediation:** Call configure_logging in veda.cli main for every subcommand; scheduler records non-zero exits as metrics/alerts; verify-chain catches store errors and emits CHAIN_VERIFY_FAILED.
- **Validation:** Subprocess test asserting EMF lines for each job and an alarm metric on non-zero exit.
- **Architecture amendment required:** No
- **Owner decision required:** No
- **Blocking scope:** staging (alarm acceptance) / production (RG-5)
- **Re-review requirement:** Targeted re-review of the fix

#### RR-08 · MAJOR · Path A enrollment confirm retires the session's refresh tokens without a successor link, so a benign concurrent refresh is treated as token theft and revokes the just-elevated session

- **Origin:** New token-rotation defect (path A confirm); same pattern pre-exists in change_password (working-paper ID RR-AUTH-2)
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/platform/auth/mfa.py:447-463 — _rotate_refresh sets used_on, never replaced_by_id
  - api/veda/platform/auth/service.py:588-610 — the 20 s grace window requires a linked successor
  - api/veda/platform/auth/service.py:728-741 — change_password has the same pattern
- **Affected requirements:** AUTH-005, 05 §6.1
- **Exploit / failure scenario:** A second tab refreshes with the old cookie right after enrollment; the session is revoked and a CRITICAL REFRESH_REUSE_DETECTED event and email are raised (false positive).
- **Required remediation:** Link replaced_by_id on rotation in both paths so the grace window applies.
- **Validation:** Probe: old cookie within 20 s → access token only; after 20 s → reuse detection.
- **Architecture amendment required:** No
- **Owner decision required:** No
- **Blocking scope:** production
- **Re-review requirement:** Targeted re-review of the fix

#### RR-09 · MAJOR · Break-glass STS identity check sees the host instance role, not the custodian, when the CLI runs via docker compose as the runbook prescribes; with no credentials it crashes without a failure event

- **Origin:** Residual of IR-06 in the deployed topology (working-paper ID RR-RBAC-3)
- **Verification:** SOURCE-INSPECTED + REPRODUCED (N06)
- **Evidence:**
  - api/veda/platform/rbac/custodians.py:22-25 — default boto3 credential chain
  - api/deploy/deploy.sh:24-35 and docs/operations/api-runbooks.md:94-95 — CLI run inside the api container
  - N06: instance-role ARN → 403 not a registered custodian; no credentials → uncaught NoCredentialsError
- **Affected requirements:** RBAC-021, 06 §7.5 items 2 and 4, PG-BG
- **Exploit / failure scenario:** In an emergency break-glass cannot be used (fails closed), or an operator registers the instance role and two-person control collapses to one identity.
- **Required remediation:** Pass per-custodian credentials (assume-role with MFA) into the container or run via an SSM document with session credentials; refuse the instance-profile ARN; catch botocore errors and record BREAK_GLASS_* FAILURE; rehearse in staging with two principals and CloudTrail.
- **Validation:** Staging rehearsal with CloudTrail evidence.
- **Architecture amendment required:** 06 §7.5 mechanism wording (minor)
- **Owner decision required:** Yes — custodian credential model (OWNER-INPUT-004)
- **Blocking scope:** production (PG-BG)
- **Re-review requirement:** Yes, with staging evidence

#### RR-10 · MINOR · Environment validation accepts trusted-proxy CIDR 0.0.0.0/0 or ::/0, all-zero / dev-derived / duplicate 32-byte keys, and an unparsable JWT PEM

- **Origin:** Residual of IR-09/IR-35 (working-paper ID RR-AUTH-3 + RR-OPS-6)
- **Verification:** REPRODUCED (config probe) / SOURCE-INSPECTED
- **Evidence:**
  - api/veda/config.py:288-292, 332-341
- **Affected requirements:** SEC-005, SEC-006, AUTH-010
- **Exploit / failure scenario:** A mis-set proxy CIDR lets any client choose its IP, defeating per-IP/network limits and forging IP evidence.
- **Required remediation:** Reject CIDRs broader than /24 or /64 (or require an explicit list), reject weak/duplicate/dev-derived keys, load the ES256 key at startup.
- **Validation:** Config unit tests for each case.
- **Architecture amendment required:** No
- **Owner decision required:** No
- **Blocking scope:** staging
- **Re-review requirement:** Targeted re-review of the fix

#### RR-11 · MINOR · With intake disabled the enquiry form is novalidate and skips client validation, so an empty submit opens WhatsApp with a blank enquiry (baseline 778aa8f blocked it)

- **Origin:** Introduced at 9236aa3, not caught in the original review (working-paper ID RR-FE-2)
- **Verification:** REPRODUCED
- **Evidence:**
  - dist/index.html:168 (novalidate), :173-174 (required removed); dist/assets/app.js:166-169
- **Affected requirements:** LEAD-019, Public site behaviour
- **Exploit / failure scenario:** Visitors send blank WhatsApp enquiries after merge (live site).
- **Required remediation:** Run clientValidate before the WhatsApp hand-off when intake is disabled.
- **Validation:** site.e2e: empty flag-off submit shows errors.
- **Architecture amendment required:** No
- **Owner decision required:** No
- **Blocking scope:** merge (ships to the live site on merge; cheap fix)
- **Re-review requirement:** Targeted re-review of the fix

#### RR-12 · MINOR · DEV-004 residuals: alternating between published policy versions is accepted without withdrawal; consent history activity is mutable at DB level; staff create-time consent needs no note and writes no consent activity

- **Origin:** DEV-004 residual (working-paper ID RR-LEAD-4)
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/modules/crm/leads/service.py:837, 552-556
- **Affected requirements:** LEAD-012, LEAD-027
- **Exploit / failure scenario:** Consent evidence churns without a real new notice; create-time staff consent lacks provenance.
- **Required remediation:** Accept only a later version; require note on create-time staff consent; decide DB-level immutability or a dedicated append-only table (AM-4).
- **Validation:** D02/D05 variants.
- **Architecture amendment required:** AM-4 completion
- **Owner decision required:** Yes (AM-4)
- **Blocking scope:** production
- **Re-review requirement:** Targeted re-review of the fix

#### RR-13 · MINOR · Residual PII paths: Sentry transaction events carry request query strings (e.g. lead search by email); outbox_event.last_error stores provider errors containing recipient emails

- **Origin:** IR-27 residual (working-paper ID RR-LEAD-5)
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/app.py:117-125 (traces_sample_rate with before_send only)
  - api/veda/platform/notifications/worker.py:119
- **Affected requirements:** LOG-003, SEC-009
- **Exploit / failure scenario:** Customer emails reach Sentry and an unmasked DB column.
- **Required remediation:** Add before_send_transaction scrubbing (or disable tracing), redact last_error.
- **Validation:** Probe asserts no PII in Sentry payloads or last_error.
- **Architecture amendment required:** No
- **Owner decision required:** No
- **Blocking scope:** production
- **Re-review requirement:** Targeted re-review of the fix

#### RR-14 · MINOR · Snapshot directory defaults to container storage and is not required in staging/production, so deploy.sh's pre-deploy snapshot in a --rm container is lost

- **Origin:** IR-11 residual (working-paper ID RR-OPS-2)
- **Verification:** SOURCE-INSPECTED + config probe
- **Evidence:**
  - api/deploy/deploy.sh
  - api/veda/config.py (snapshot dir)
- **Affected requirements:** OPS-002, OPS-004
- **Exploit / failure scenario:** A pre-deploy snapshot needed for rollback does not exist.
- **Required remediation:** Require an absolute snapshot dir on the persistent volume in staging/production.
- **Validation:** Config test + staging deploy evidence.
- **Architecture amendment required:** No
- **Owner decision required:** No
- **Blocking scope:** staging
- **Re-review requirement:** Targeted re-review of the fix

#### RR-15 · MINOR · Disaster-restore runbook does not work as written: restore-verify fails on a Litestream-restored file, Litestream is not stopped before the swap, one failure path emits no metric, the off-host replica is never verified

- **Origin:** IR-11 residual (working-paper ID RR-OPS-3)
- **Verification:** REPRODUCED (a) / SOURCE-INSPECTED
- **Evidence:**
  - docs/operations/api-runbooks.md §3
  - api/veda/platform/backups.py
- **Affected requirements:** OPS-005, OPS-009, RG-1, RG-2
- **Exploit / failure scenario:** Restore under pressure fails or restores unverified data.
- **Required remediation:** Fix restore-verify for Litestream files, stop replication before swap, verify from the S3 replica on schedule.
- **Validation:** RG-1/RG-2 rehearsal evidence.
- **Architecture amendment required:** No
- **Owner decision required:** No
- **Blocking scope:** staging
- **Re-review requirement:** Targeted re-review of the fix

#### RR-16 · MINOR · mypy ratchet fails open: reports '0 errors OK' when mypy is missing or its config is broken; --update silently admits errors from new or renamed files

- **Origin:** IR-39 residual (working-paper ID RR-OPS-4)
- **Verification:** REPRODUCED
- **Evidence:**
  - api/tools/mypy_ratchet.py
  - api/tools/mypy-baseline.json (24 files, 157 errors)
- **Affected requirements:** 12 §5 types gate
- **Exploit / failure scenario:** Typing regressions pass CI.
- **Required remediation:** Fail when mypy is unavailable or reports a config error; forbid baseline growth and new-file entries in --update; key by content not path.
- **Validation:** Negative tests for each case.
- **Architecture amendment required:** No
- **Owner decision required:** No
- **Blocking scope:** staging (CI gate integrity)
- **Re-review requirement:** Targeted re-review of the fix

#### RR-17 · MINOR · Rollback documentation gaps: rollback of this release to 9236aa3 is never ready (and would reintroduce IR-01); readiness details are unreachable from the host under the compose topology; deploy.sh only checks the declaration line

- **Origin:** IR-10 residual (working-paper ID RR-OPS-5)
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/platform/health.py:60-66
  - api/deploy/docker-compose.yml:10
  - api/deploy/deploy.sh:38
  - AM-6, AM-11 text
- **Affected requirements:** OPS-004, LOG-005
- **Exploit / failure scenario:** Operators attempt an N-1 rollback that cannot pass readiness and would restore a BLOCKER-vulnerable image.
- **Required remediation:** State in runbook, AM-6 and AM-11 that rollback of this release is snapshot restore; read revision inside the container in deploy.sh.
- **Validation:** RG-7 rehearsal.
- **Architecture amendment required:** AM-6/AM-11 text
- **Owner decision required:** Yes (AM-6, AM-11)
- **Blocking scope:** production (RG-7)
- **Re-review requirement:** Targeted re-review of the fix

#### RR-18 · MINOR · Accessibility remnants: step-up dialog has no pre-expiry warning; command palette listbox/option semantics and vs-tabs tabpanel wiring unchanged; account menu stays open on outside click

- **Origin:** IR-37 residual; author matrix overstates (working-paper ID RR-FE-3)
- **Verification:** REPRODUCED / SOURCE-INSPECTED
- **Evidence:**
  - app/src/modules/auth/step-up-dialog.ts:71
  - command-palette.ts:79-80
  - design-system/components.ts:375-380
  - shell/app.ts:200-208
- **Affected requirements:** UI-011, UI-016 (AX-06, AX-07, AX-09)
- **Exploit / failure scenario:** Keyboard and screen-reader users cannot operate these controls reliably.
- **Required remediation:** Implement the listed ARIA patterns and the step-up expiry warning.
- **Validation:** axe + manual SR script.
- **Architecture amendment required:** No
- **Owner decision required:** No
- **Blocking scope:** production
- **Re-review requirement:** Targeted re-review of the fix


### 18.2 Advisories

- **RR-A01** (RR-AUTH-4): IR-20 link invalidation written on the 409 path is rolled back with the error (mfa.py:330-334); no effect because confirm re-checks.
- **RR-A02** (RR-AUTH-5): PostgreSQL answers 409 VERSION_CONFLICT on concurrent auth writes where SQLite answers 401; PostgreSQL gate.
- **RR-A03** (RR-AUTH-6): tests/unit/test_totp_passwords.py fails 2 tests when run alone without VEDA_ENV=test (test isolation).
- **RR-A04** (RR-AUTH-7): Path C start password re-entry is not counted by any throttle (mfa.py:318-329).
- **RR-A05** (RR-AUTH-8): VEDA_ENV=local on a deployed host silently derives public development keys; nothing in gunicorn on_starting refuses local/test in the production image (config.py:190).
- **RR-A06** (RR-AUTH-9): An expired ENROLLMENT challenge leaves an inert PENDING factor (pre-existing).
- **RR-A07** (RR-RBAC-A1): Break-glass CLI lets botocore exceptions escape without a FAILURE event.
- **RR-A08** (RR-RBAC-A2): PostgreSQL: break_glass_execute racing a cancel-link raises StaleDataError and aborts the remaining due items that cycle (maintenance.py:588-591).
- **RR-A09** (RR-RBAC-A3): OpenAPI snapshot documents 200 for cancel-link; the handler returns 204.
- **RR-A10** (RR-RBAC-A4): Stale approver with suspended user.founder.manage gets 403 PERMISSION_DENIED where TD-G G7 expects APPROVER_NOT_ELIGIBLE (pre-existing).
- **RR-A11** (RR-RBAC-A5): Eligible Founders can deny PENDING custodian break-glass in-app but cannot cancel APPROVED ones except via the link; undocumented (fold into AM-5/AM-9).
- **RR-A12** (RR-RBAC-A6): cancel_open_standard_requests records an event but sends no approval.decided notification.
- **RR-A13** (RR-LEAD-6): Anchor store: no writer/reader role separation; staging silently uses a same-host local store; verify_chain holds a write transaction for the whole recompute.
- **RR-A14** (RR-LEAD-7): Restore-verify chain check trusts the first online row (backups.py:146), so a prefix-deleted snapshot passes.
- **RR-A15** (RR-OPS-7): CI residuals: postgres:16 service image not digest-pinned; built image never smoke-run; e2e uses Flask dev server; Trivy ignore-unfixed without recorded risk acceptance; 104 secrets-baseline entries none audited. (CI execution itself is now evidenced: run 36559966718.)
- **RR-A16** (RR-OPS-8): Open-issue registry omits 9 advisories (IR-A03, A04, A05, A09, A13, A17, A19, A21, A25) contrary to its own note; IR-39 text mischaracterises the mypy backlog.
- **RR-A17** (RR-OPS-9): Migration 0009 is chained after 0100_crm_leads, contradicting 02 §8.3 numbering; AM-11 does not amend 02 §8.3.
- **RR-A18** (RR-FE-4): ESLint sink bans miss lit-html unsafe-html path, unsafe-mathml, .innerHTML=${} bindings, createContextualFragment, setHTMLUnsafe; site JS (dist/assets/app.js) is not linted.
- **RR-A19** (RR-FE-5): E2E remnants: axe site scan uses bypassCSP; focus assertion also passes on #outlet; test servers bind to all interfaces.
- **RR-A20** (RR-FE-6): DEV-004 register says superseded consent evidence is visible in the lead timeline; the SPA renders only subject and note.
- **RR-A21** (RR-FE-7): Route-focus hook moves focus to the MFA heading after sign-in instead of the code field.
- **RR-A22** (RR-FE-8): engines ^22 with engine-strict rejects Node 24 LTS; Node 22 EOL 2027-04-30.
- **RR-A23** (lead): Proposed amendments are stored inside docs/architecture/amendments/ on the implementation branch. Certified files are unchanged and every proposal is marked PROPOSED, NOT APPROVED, but merging would place unapproved text inside the certified tree; consider docs/proposals/ or merge only after decisions.
- **RR-A24** (lead): Remediation evidence was generated from an uncommitted tree on top of 9236aa3 before 2f6b59a (per evidence README); CI logs are not publicly readable, so step-level conclusions (API) are the independent CI evidence.
- **RR-A25** (FE): On e2e failure CI uploads e2e artefacts including founder.json (throwaway DB password and TOTP secret); harmless for ephemeral data but should be excluded.

## 19. Blockers by stage and owner decisions

**Merge blockers**
- **RR-01** (MAJOR) Site-wide CSP blocks the 404 page's inline stylesheet; because a push to main deploys dist/ to www.vedaspaces.com, merging ships a broken 404 page to production
- **RR-02** (MAJOR) A single Founder can restore a Founder deleted through dual-Founder approval (G11 bypass; no governance record)
- **RR-03** (MAJOR) An executed STANDARD email change stays pending through GRANT_FOUNDER and can be verified on the new Founder
- **RR-04** (MAJOR) DEV-007 keys per-email login/forgot limits by (email, network), removing the only cross-network bound on password guessing for MFA holders and multiplying reset-email volume
- **RR-11** (MINOR) With intake disabled the enquiry form is novalidate and skips client validation, so an empty submit opens WhatsApp with a blank enquiry (baseline 778aa8f blocked it)
- Owner approval (or rejection with rework) of AM-1, AM-2, AM-3, AM-4, AM-5, AM-6 and AM-11, which are the deviations the merged code implements. AM-7 must be revised with the DEV-007 fix.
- Owner decision on RR-02 (unrestorable vs workflow restore).
- TG-01 (owner approval of the architecture) and TG-08 (owner authorization of the implementation), both Pending.
- The owner must acknowledge that **merging to `main` deploys `dist/` to production** (README.md:43-45). The merge decision therefore needs site-production approval.

**Staging blockers**
- All merge blockers, plus:
- **RR-07** (MAJOR) CLI, scheduler and worker processes never configure logging, so every maintenance/worker metric (backup, chain, anchor, invariants, dead outbox) is dropped and the scheduler ignores job exit codes
- **RR-10** (MINOR) Environment validation accepts trusted-proxy CIDR 0.0.0.0/0 or ::/0, all-zero / dev-derived / duplicate 32-byte keys, and an unparsable JWT PEM
- **RR-14** (MINOR) Snapshot directory defaults to container storage and is not required in staging/production, so deploy.sh's pre-deploy snapshot in a --rm container is lost
- **RR-15** (MINOR) Disaster-restore runbook does not work as written: restore-verify fails on a Litestream-restored file, Litestream is not stopped before the swap, one failure path emits no metric, the off-host replica is never verified
- **RR-16** (MINOR) mypy ratchet fails open: reports '0 errors OK' when mypy is missing or its config is broken; --update silently admits errors from new or renamed files

**Production blockers**
- All merge and staging blockers, plus:
- **RR-05** (MAJOR) A forged archive manifest written with the host credential hides deletion of any prefix of the security-event chain, including anchored rows
- **RR-06** (MAJOR) Archival writes the write-once manifest before the database commit; any later failure produces a permanent false 'prefix removed' alarm and blocks archival forever
- **RR-08** (MAJOR) Path A enrollment confirm retires the session's refresh tokens without a successor link, so a benign concurrent refresh is treated as token theft and revokes the just-elevated session
- **RR-09** (MAJOR) Break-glass STS identity check sees the host instance role, not the custodian, when the CLI runs via docker compose as the runbook prescribes; with no credentials it crashes without a failure event
- **RR-12** (MINOR) DEV-004 residuals: alternating between published policy versions is accepted without withdrawal; consent history activity is mutable at DB level; staff create-time consent needs no note and writes no consent activity
- **RR-13** (MINOR) Residual PII paths: Sentry transaction events carry request query strings (e.g. lead search by email); outbox_event.last_error stores provider errors containing recipient emails
- **RR-17** (MINOR) Rollback documentation gaps: rollback of this release to 9236aa3 is never ready (and would reintroduce IR-01); readiness details are unreachable from the host under the compose topology; deploy.sh only checks the declaration line
- **RR-18** (MINOR) Accessibility remnants: step-up dialog has no pre-expiry warning; command palette listbox/option semantics and vs-tabs tabpanel wiring unchanged; account menu stays open on outside click
- Partially resolved or gated original findings: IR-03, IR-06, IR-11, IR-12, IR-27, IR-37, IR-38, IR-A10, IR-A14.
- Owner decisions AM-8, AM-9 and AM-10; IR-A06, IR-A11, IR-A15 and IR-A23.
- All 27 gates, including OWNER-INPUT-001..004, RG-1..9, PG-DAST, PG-RET, PG-BG, PG-EMAIL and PG-PRIV.

**Public-intake enablement** (additionally): IR-18 real-key run, IR-17, IR-31 and IR-32 prerequisites (§14).

**PostgreSQL release gate (PGM-1):** IR-33, IR-A01, IR-A16, RR-A02 and RR-A08.

**Required owner decisions:**

| # | Decision | Owner category | Needed before |
|---|---|---|---|
| OD-1 | Approve, reject or return AM-1, AM-2, AM-3, AM-4, AM-5, AM-6, AM-11 (DEV-001..006, DEV-008) | Architecture Owner (AM-4 with Data Protection lead; AM-6 with Operations) | Merge |
| OD-2 | Reject AM-7 as written; approve a revised limiter design (RR-04) | Architecture Owner, Security | Merge |
| OD-3 | Deleted-Founder restore policy (RR-02) | Architecture Owner / Founders | Merge |
| OD-4 | TG-01 and TG-08 | Product Owner | Merge |
| OD-5 | Site production deployment of `dist/` changes (merge = deploy) | Product Owner | Merge |
| OD-6 | Custodian credential model (RR-09), OWNER-INPUT-004 | Security Owner | Production |
| OD-7 | AM-8, AM-9 (break-glass veto policy), AM-10 (erasure scope) | Architecture Owner, Security, Data Protection | Production |
| OD-8 | IR-A06 (role self-edit), IR-A15, IR-A23 (Privacy Notice content) | Architecture Owner, Privacy | Production |

## 20. Final report (A–AG)

| Key | Item | Result |
|---|---|---|
| A | Branch-head SHA reviewed | `2f6b59a0a6a59dbc41a597dddc7e6512dcd581fe` |
| B | Included remediation commits | `6fd249c10b72b112c83f86cc2705736a59db28be`, `2f6b59a0a6a59dbc41a597dddc7e6512dcd581fe` |
| C | Review branch | `review/p0-independent-implementation-review` |
| D | Review commit SHA | The commit adding this file (see branch log) |
| E | IR-01 verdict | **IR-01 RESOLVED** |
| F | IR-01 exploit reproduction | Baseline `9236aa3`: bypass reproduced (SQLite and PG). Head: 401 on every variant; 20/20 items on both engines |
| G | Adjacent-flow regression | No confused-deputy or binding defect. New: RR-04 (limiter), RR-08 (refresh successor) |
| H | Original finding reconciliation | 64/64 reconciled. RESOLVED 30 · PARTIALLY RESOLVED 13 · NOT RESOLVED 11 · ACCEPTABLY GATED FOR STAGING 2 · ACCEPTABLY GATED FOR PRODUCTION 4 · REGRESSION INTRODUCED 4 |
| I | Founder governance | IR-04, IR-05, IR-08 fixed; IR-07 page added. **New MAJOR RR-02, RR-03**; RR-09 production gate |
| J | Audit chain | Original tamper cases detected. **RR-05, RR-06** (MAJOR); RR-07 alerting; S3 staging/production gated |
| K | DEV decisions | DEV-001, 002, 003, 004, 005, 006, 008: ACCEPTABLE WITH ARCHITECTURE AMENDMENT. **DEV-007: REQUIRES IMPLEMENTATION CHANGE** |
| L | AM assessment | Sound: AM-1, AM-3, AM-8. Sound but incomplete: AM-2, AM-4, AM-5, AM-6, AM-10, AM-11. Incomplete: AM-9. **Unsound as written and conflicting with 05 §4: AM-7** |
| M | API/RBAC | 105 routes; core RBAC held; startup validation strengthened (IR-A05 residual). IR-A07: **KEEP 403/404 DIFFERENCE** |
| N | Database/migrations | 10 revisions, 1 head, 24 tables (504 columns, 108 FKs); fresh and with-data upgrades identical on SQLite/PG16/PG18; downgrade refused; no rehearsal |
| O | SQLite evidence | 435 passed, 0 skipped |
| P | PostgreSQL 16 evidence | 16.4: 427 passed, 8 skipped (legitimate); CI `postgres:16` leg green |
| Q | PostgreSQL 18 evidence | 18.4: 427 passed, 8 skipped |
| R | Frontend evidence | Node 22.23.3; npm ci, ESLint, tokens, typecheck, 52 tests, contrast, build all pass; audit 0/0 |
| S | Browser evidence | run-all 47/47; reviewer probes confirm IR-15, IR-19, IR-36, cancel page; **RR-01** site CSP |
| T | CI evidence | Run 36559966718: 5/5 jobs success on `2f6b59a`; `6fd249c` failed only at the image scan; logs not publicly readable |
| U | Security tooling | ruff, format, ratchet (fails open, RR-16), ESLint, bandit, pip-audit, npm audit, secret scan, Trivy all pass |
| V | Public-form disablement | Proven: both metas empty, JS requires both, 0 API requests, consent hidden, WhatsApp works |
| W | Staging-only findings | §15. IR-06 and IR-12 not ready; IR-03 and IR-11 partially ready; SES, KMS, S3 and readiness code ready |
| X | Remaining BLOCKER findings | None |
| Y | Remaining MAJOR findings | New: RR-01 … RR-09. Original MAJORs not fully resolved: IR-03, IR-11, IR-12 (partially resolved); IR-06 (gated for staging); IR-18 (gated for intake); IR-08 (fixed, but regression RR-02) |
| Z | Remaining MINOR findings | New: RR-10 … RR-18. Original: IR-23, IR-26, IR-32 (regressions tracked as RR-04, RR-06, RR-01); IR-27, IR-37, IR-38 (partially resolved); IR-33 (PGM-1); IR-34 (follow-up) |
| AA | Required owner decisions | OD-1 … OD-8 (§19) |
| AB | Required architecture amendments | AM-1 … AM-6 and AM-11 before merge (AM-7 revised); AM-8 … AM-10 before production; plus text for RR-02 (option b), RR-09 (06 §7.5), RR-A17 (02 §8.3) |
| AC | Merge blockers | RR-01, RR-02, RR-03, RR-04, RR-11; OD-1 … OD-5 (incl. TG-01, TG-08) |
| AD | Staging blockers | Merge blockers + RR-07, RR-10, RR-14, RR-15, RR-16 |
| AE | Production blockers | Staging blockers + RR-05, RR-06, RR-08, RR-09, RR-12, RR-13, RR-17, RR-18; IR-03, 06, 11, 12, 27, 37, 38; all 27 gates |
| AF | Exact next authorized action | **Owner decision only.** No merge, staging or production step is authorized. Next: the owner decides whether to authorize a further remediation increment on `implementation/p0-foundation` (new commits, no history rewrite). Merge scope: RR-01, RR-02, RR-03, RR-04 and RR-11, with RR-07 recommended. The Architecture Owner records OD-1 to OD-3, and the Product Owner OD-4 and OD-5. A targeted re-review of the resulting frozen SHA then follows |
| AG | Final verdict | **NOT CERTIFIED** |

### Verdict rationale

**NOT CERTIFIED.**

- **The main aim of the remediation is achieved.** IR-01 is independently resolved, and no BLOCKER remains. 30 of 64 original findings are fully resolved, including 12 of the 18 original MAJORs.
- **But merge-blocking MAJOR findings remain:**
  - **RR-01:** because merging deploys `dist/` to production, the site CSP regression ships immediately.
  - **RR-02** and **RR-03:** Founder-governance invariants, one of them introduced by the IR-08 fix.
  - **RR-04:** an unapproved deviation (DEV-007) that weakens authentication.
- **Owner decisions required for merge are absent:** AM approvals, TG-01 and TG-08.

CERTIFIED WITH CONDITIONS is unavailable because these blockers are code or governance defects, not infrastructure-only or bounded MINOR conditions.

---

## Appendices

Appendices B to F are the domain re-reviewers' working tables, included verbatim as evidence. Their local IDs map to consolidated IDs as follows.

| Local ID | Consolidated ID |
|---|---|
| RR-FE-1 | RR-01 |
| RR-RBAC-1 | RR-02 |
| RR-RBAC-2 | RR-03 |
| RR-AUTH-1 | RR-04 |
| RR-LEAD-1 | RR-05 |
| RR-LEAD-2 | RR-06 |
| RR-LEAD-3 and RR-OPS-1 | RR-07 |
| RR-AUTH-2 | RR-08 |
| RR-RBAC-3 | RR-09 |
| RR-AUTH-3 and RR-OPS-6 | RR-10 |
| RR-FE-2 | RR-11 |
| RR-LEAD-4 | RR-12 |
| RR-LEAD-5 | RR-13 |
| RR-OPS-2 | RR-14 |
| RR-OPS-3 | RR-15 |
| RR-OPS-4 | RR-16 |
| RR-OPS-5 | RR-17 |
| RR-FE-3 | RR-18 |
| RR-AUTH-4 … RR-AUTH-9 | RR-A01 … RR-A06 |
| RR-RBAC-A1 … RR-RBAC-A6 | RR-A07 … RR-A12 |
| RR-LEAD-6, RR-LEAD-7 | RR-A13, RR-A14 |
| RR-OPS-7, RR-OPS-8, RR-OPS-9 | RR-A15, RR-A16, RR-A17 |
| RR-FE-4 … RR-FE-8 | RR-A18 … RR-A22 |

**Differences from the working papers.** The lead reviewer overrode the domain reviewers in these places:
- **IR-14** is RESOLVED, not PARTIALLY RESOLVED. The lead reviewer obtained CI run evidence through the GitHub API, which the database/ops reviewer could not (RR-OPS-7 statements about "no CI execution" are superseded).
- **RR-02 and RR-03** are scoped to **merge**, not staging, consistent with the original IR-04 treatment of Founder-governance invariants.
- **RR-04** is scoped to merge as well as production, because DEV-007 is an unapproved deviation requiring implementation change.

### Appendix A — Commands (lead reviewer)

```
git fetch origin --prune
git rev-parse origin/implementation/p0-foundation          # 2f6b59a…
git log --format='%H %P %s' 9236aa3..origin/implementation/p0-foundation
git diff --diff-filter=MDR 778aa8f 2f6b59a -- docs/architecture   # empty
git diff --stat 6fd249c 2f6b59a                            # api/deploy/Dockerfile only
python3.13 -m venv venv2 && venv2/bin/pip install --require-hashes -r api/requirements-dev.txt
VEDA_TEST_ENGINES=sqlite python -m pytest -q -rs                                   # 435 passed
VEDA_TEST_DATABASE_URL_PG=postgresql+psycopg://postgres@127.0.0.1:55432/postgres \
  VEDA_TEST_ENGINES=postgresql python -m pytest -q -rs                            # PG 16.4: 427 passed, 8 skipped
VEDA_PG_DATA=<scratch>/pgdata18b VEDA_TEST_ENGINES=postgresql python -m pytest -q -rs  # PG 18.4: 427 passed, 8 skipped
curl https://api.github.com/repos/slaggala/veda-spaces/actions/runs?branch=implementation/p0-foundation
curl https://api.github.com/repos/slaggala/veda-spaces/actions/runs/36559966718/jobs   # 5 × success
detect-secrets scan <223 changed files>                    # fixtures/baseline only
```

### Appendix B — Auth/MFA and IR-01 working paper

#### B.1 The 20 required IR-01 items

Every item was REPRODUCED on SQLite and on embedded PostgreSQL with identical results; `head_ir01_{sqlite,pg}.txt` hold the raw lines. For each item: what was tried, the result, and whether it conforms.

1. **Victim token plus attacker transaction.**
   - Tried: the victim's pwd-only bearer used to confirm the attacker's transaction on paths C, B, A (the attacker's own session) and D.
   - Result: all four return `401 MFA_CHALLENGE_INVALID`. The victim session stays `pwd` with `mfa_verified_on=None`, and the victim has no factor.
   - Conforms: yes.
2. **Attacker token plus victim transaction.**
   - Tried: the attacker's ADMIN bearer with the victim's path A transaction, and with the victim's path C transaction.
   - Result: both return 401. The victim's factor stays PENDING. The attacker's session is unchanged.
   - Conforms: yes.
3. **Same user, other session.**
   - Tried: a path A transaction started in S1 and confirmed from S2, then confirmed anonymously.
   - Result: 401 and 401. S1 itself then confirms with 200.
   - Conforms: yes. 05 §11.3 path A requires "an existing FULL session plus fresh re-entry"; binding to the initiating session is the stricter reading, and no certified flow needs cross-session confirmation.
4. **Paths B and C with a bearer token.**
   - Tried: path C confirmed with the owner's **own** older bearer; path C start with a foreign bearer; path B confirm with a bearer; a garbage bearer.
   - Result: 401 `MFA_CHALLENGE_INVALID`, 401 `ENROLLMENT_PROOF_INVALID`, 401 `MFA_CHALLENGE_INVALID`, and 401 `AUTH_REQUIRED` for the garbage bearer. An anonymous confirm afterwards returns 200.
   - Conforms: yes. **Any** bearer is refused, including the owner's own. The SPA sends these calls anonymously (`app/src/modules/auth/mfa-pages.ts:241,282`).
5. **Path D reused as normal enrollment.**
   - Tried: the D transaction with the same user's FULL session, anonymously, as `invite_context`, and as `enrollment_token`; a recovery session with a `reauth` proof; the recovery session confirming an older path A transaction.
   - Result: all return 401.
   - Conforms: yes.
6. **Stale token.**
   - Tried: password changed in S2, which revokes S1; authz_version bump; sensitive grant between start and confirm; access token expired.
   - Result:
     - password changed: 401 `SESSION_INVALID`
     - authz_version bump: 200
     - sensitive grant: 401 `ENROLLMENT_PROOF_INVALID` (N-A1 re-checked)
     - expired token: 401 `TOKEN_EXPIRED`
   - Conforms: yes. The authz bump succeeding is by design: authorization is resolved from the database on every request (05 §5), and the binding is to the session, not to the token's `jti`.
7. **Revoked session.**
   - Tried: `DELETE /auth/sessions/{S1}`, and separately `/auth/logout`, before confirm.
   - Result: 401 `SESSION_INVALID` in both cases; the factor stays PENDING.
   - Conforms: yes.
8. **Expired transaction.**
   - Tried: confirm 15 min 5 s after start.
   - Result: 401. The PENDING factor remains until the next start (see RR-AUTH-9).
   - Conforms: yes, with the RR-AUTH-9 advisory.
9. **Consumed transaction replay.**
   - Result: 200, then 401 `MFA_CHALLENGE_INVALID`; one `MFA_CHALLENGE_REPLAY_BLOCKED` event; one session.
   - Conforms: yes.
10. **Mismatched pending factor.**
    - Tried: start twice, then confirm the first challenge with the second factor's code; the second challenge with the first factor's code; the factor revoked mid-transaction; `factor_id` tampered in the database to point at another user's PENDING factor.
    - Result: 401 `MFA_CHALLENGE_INVALID` (the first transaction was superseded), 401 `MFA_CODE_INVALID`, 401, and 401. No factor becomes ACTIVE for either user.
    - Conforms: yes.
11. **Changed purpose.**
    - Tried: a LOGIN token or STEP_UP token at confirm; an ENROLLMENT token at `/mfa/verify`, `/mfa/step-up` and `/mfa/recovery`; an INVITE_CONTEXT (fresh or consumed) at confirm; PATH_B, PATH_C or LOGIN tokens used as `invite_context`.
    - Result: every case returns 401. A fresh invite context still starts after being refused at confirm.
    - Conforms: yes.
12. **Parallel confirmations.**
    - Tried: 6 threads on path C, then 6 threads on path A.
    - Result: exactly one 200 and five 401 each time; 1 ACTIVE factor, 1 session and 1 recovery-code batch.
    - Engines: same on SQLite (`BEGIN IMMEDIATE`) and PostgreSQL (`FOR UPDATE`).
    - Conforms: yes.
13. **Partial failure.**
    - Tried: `_issue_recovery_codes` patched to raise during a path A replacement; `complete_login` patched to raise during path D.
    - Result:
      - path A: 500; the old ACTIVE factor is unchanged, the new factor stays PENDING, the session's methods and `mfa_verified_on` are unchanged, and there is no Set-Cookie.
      - path D: 500; the recovery session is not revoked, no cooling-off is set, and the old factor stays ACTIVE.
    - Conforms: yes (05 §11.5 commit rule).
14. **A failed attempt never upgrades.**
    - Tried: 6 wrong codes on path A; a wrong code on B; a wrong code on D.
    - Result:
      - path A: `attempts_remaining` counts 4, 3, 2, 1, 0, then `MFA_CHALLENGE_INVALID`. The session stays `pwd`, and the factor becomes REVOKED (abandoned).
      - path B: the user stays INVITED.
      - path D: the recovery session stays live and no FULL session exists.
    - Conforms: yes.
15. **Only the initiating session is upgraded.**
    - Result: S1 becomes `pwd+totp` with `mfa_verified_on` set, and the new access token has `sid=S1` and `amr=['pwd','otp']`. S2 stays `pwd`.
    - Conforms: yes.
16. **Other sessions.**
    - Path A: S2 is neither revoked nor elevated. 05 §11.3 requires no revocation on path A.
    - Path D: other sessions were already revoked at recovery (05 §11.5), and confirm revokes the recovery session (`mfa.py:540`).
    - Conforms: yes.
17. **Refresh-token rotation.**
    - Result: path A rotates S1's refresh token, and the new cookie refreshes to `amr=['pwd','otp']`.
    - **But** presenting the pre-confirm cookie within 20 s is treated as theft: S1 is revoked (`TOKEN_REUSE`) and a CRITICAL `REFRESH_REUSE_DETECTED` event is written.
    - Conforms: **no, see RR-AUTH-2.** Rotation is not documented in 05 §11.3, and the certified 05 §6.1 grace window is defeated.
18. **Open enrollment transactions end.**
    - Tried: path A confirm while two emailed path C links and other challenges were open.
    - Result: both links return 401 afterwards; 0 open challenges and 0 PENDING factors remain (`mfa.py:503-504`).
    - Conforms: yes.
19. **Audit and security events.**
    - Refusal event: `MFA_CHALLENGE` FAILURE with `subject` = the transaction owner, `created_by` = the caller, and `session_id` = the caller's session. `detail={stage:enrollment, reason:BINDING_MISMATCH, scope:principal, method:bearer}`.
    - Completion event: `created_by` = the owner.
    - No raw challenge token, code, access token, recovery code or base32 secret appears in any `security_event_log` or `audit_log` value. Factor audit rows carry `secret_ciphertext` and `wrapped_data_key` redacted (`kernel/audit_registry.py:81`).
    - Conforms: yes.
20. **Failures don't reveal ownership.**
    - Tried 8 cases: unknown token (anonymous or bearer), a foreign path A token (bearer or anonymous), path C plus bearer, consumed (anonymous or bearer), and expired.
    - Result: all identical — `(401, MFA_CHALLENGE_INVALID, same keys {code, detail, status, title, type})`. Start with a bearer on B or C refuses before evaluating the proof.
    - Conforms: yes.

**Head's own suites, SQLite:**
| Suite | Result |
|---|---|
| `test_auth.py` | 23 passed |
| `test_mfa.py` | 15 passed |
| `test_mfa_binding.py` | 19 passed |
| `test_auth_remediation.py` | 18 passed |
| `test_audit_security.py` | 17 passed |
| `tests/unit/test_config_environments.py` | 59 passed |
| `tests/unit/test_totp_passwords.py` | 17 passed in the combined run; **2 fail when run alone** without `VEDA_ENV` (RR-AUTH-6) |
| All of the above combined | 168 passed |
| Full head suite (with `VEDA_ENV=test`) | 435 passed |

**Head's own suites, embedded PostgreSQL:** the five integration files pass 92 of 92. `test_schema.py` on both engines: 52 passed, 2 skipped.

**My probes:** 49 of 49 pass on SQLite and 49 of 49 on PostgreSQL. The assertions encode the secure outcome, except RR-AUTH-1 and RR-AUTH-2, which print the insecure behaviour.

#### B.2 Adjacent flows

Every row was REPRODUCED on SQLite. The race rows were also run on PostgreSQL.

| Flow | Attack | Result | Verdict |
|---|---|---|---|
| Initial enrollment (A and C) | Cross-user, cross-session and cross-path, with a stolen bearer | All refused (items 1–4) | OK |
| Invitation enrollment (B) | Bearer; replayed or old `invite_context`; resend | Bearer refused. After a replay the earlier B transaction returns 401. After a resend the replayed context returns 401 and the old link returns 400. | OK. Residual: the link can be replayed until activation and each replay overwrites the password, by design (see AM-2 note). |
| Authenticator replacement (A with `replace`) | Foreign transaction with the admin bearer; wrong code; partial failure | Refused; the old factor stays ACTIVE and assurance is unchanged | OK |
| Recovery re-enrollment (D) | D with a FULL session or anonymously; recovery session plus an old path A transaction | 401 | OK |
| Restricted recovery session (Founder) | logout-all, reauth, step-up, email change, codes, users | All return 403 `RECOVERY_SESSION_RESTRICTED`; no refresh cookie is issued | OK |
| Step-up | Own token from another session; foreign token with own or foreign code; LOGIN token; replay | All return 401 `MFA_CHALLENGE_INVALID`; the legitimate call returns 204; S2 is not elevated | OK |
| Reauth | Reauth in S2, then path A start in S1 | 403 `STEP_UP_REQUIRED` (per-session) | OK |
| MFA verify at login | A's `mfa_token` with B's code | 401 `MFA_CODE_INVALID` | OK |
| Recovery | A's token with B's code; A's token with B's password and B's code | 401 `MFA_RECOVERY_INVALID`; the code lookup is scoped to `user_id` | OK |
| Recovery, parallel use of one code (4 threads) | Race | SQLite: 1×200, 3×401. PostgreSQL: 1×200, 3×409 `VERSION_CONFLICT`. One RECOVERY session either way. | OK (no double use). The PostgreSQL response code differs (RR-AUTH-5). |
| Password reset | Open enrollment during reset | Challenges and transactions ended. The **MFA_ENROLLMENT link is not invalidated**; it still starts with the *new* password (200). | Partial (IR-A04); no practical impact |
| Email change verify and cancel | Cancel token at verify, verify token at cancel, replay | 400 `EMAIL_TOKEN_INVALID` each time | OK |
| Invitation accept, bad token | — | 400, plus an `INVITE_ACCEPTED` FAILURE event with `TOKEN_INVALID` | OK |
| Logout-all racing a confirm (6×) | Race | SQLite: confirm 401, logout 204. PostgreSQL: confirm 409, logout 204. No elevation either way. | OK |
| Password change racing a confirm (6×) | Race | Same pattern, no 500 and no deadlock | OK |
| Confirm racing a restart (6×) | Race | Exactly one wins; ACTIVE plus PENDING is never more than one of each; no 500 or deadlock | OK |
| Refresh rotation, 6 parallel with the same cookie | Race | SQLite: 1 rotate, 1 grace, 4 theft (revoke, as certified in §6.1). PostgreSQL: 1×200 and 5×409; one successor. | No fork (RR-AUTH-5 for the 409) |
| Refresh after a path A confirm | Old cookie within 20 s | Session revoked as theft | **RR-AUTH-2** |
| Mass assignment | `user_id` on start, `session_id` on confirm, `user_id` on step-up | 422 `VALIDATION_FAILED` (closed schemas) | OK |
| Enumeration | `DELETE /auth/sessions/{other user's sid}` versus an unknown id | 404 and 404, identical; the other session is untouched. Tokens are 256-bit opaque and no transaction ids are exposed. | OK |
| Parallel start with the same path C link, or the same `invite_context` | Race | SQLite: 1×200, 3×401. PostgreSQL: 1×200, 3×409. One confirmable transaction. | OK |
| LOGIN challenge, 9 parallel wrong codes | Race | SQLite: 5 evaluated. **PostgreSQL: 9 evaluated** against a limit of 5; `failed_attempts` capped at 5. | IR-A01 residual (PostgreSQL gate) |

#### B.3 How the fix works

- **Start binds the transaction.** `veda/platform/auth/mfa.py:218-248` (`_start_factor`):
  - Every start first ends all of the user's open enrollment transactions: it expires open ENROLLMENT challenges and revokes PENDING factors (`service.invalidate_enrollment`, `service.py:322-339`).
  - It then creates one PENDING factor and a challenge carrying `factor_id`, `enrollment_path` and, for paths A and D, `session_id`.
- **Paths B and C refuse a bearer token.** `mfa.py:287-290` refuses any bearer on start for B and C. `mfa.py:294-301` requires an `INVITE_CONTEXT` challenge, a live invitation and no session.
- **Confirm derives everything from server state.** `mfa.py:397-423` (`_bound_transaction`):
  - The path comes from the challenge.
  - The challenge row is re-read `FOR UPDATE`, and `completed_on` is re-checked after the lock.
  - Paths A and D require `ctx.user.id == ch.user_id`, `ctx.session.id == ch.session_id`, and the session type to match the path.
  - Paths B and C require no bearer and no session.
  - The factor must be the challenge's own PENDING factor of the same user.
  - A mismatch returns the same answer as an unknown token (`_refuse_binding`, `mfa.py:377-394`).
- **Confirm re-checks eligibility.** `mfa.py:426-444` (`_require_eligible`) re-checks account state, a live invitation for path B, N-A1 and cooling-off.
- **Only the initiating session is elevated.** `mfa.py:516-533`: path A elevates only `ctx.session`, which is the bound session.
- **Schema.** The new columns and CHECKs are at `platform/auth/models.py:192-202` and in `migrations/versions/0009_mfa_challenge_binding.py`.

### Appendix C — Governance/RBAC working paper

#### C.1 Route recount

| Item | 9236aa3 | head 2f6b59a | Evidence |
|---|---|---|---|
| `app.url_map` rules | 107 | 107 | `route_inventory.py` → `out/routes.json` |
| Excluding `static` and `openapi` | 105 | 105 | same |
| (method, path) pairs | 105 | 105 | same |
| `http.ROUTES` specs / unique endpoints / orphan specs | 105 / 105 / 0 | 105 / 105 / 0 | same |
| Diff of (method, path, auth, permission, any_of, rbx, recovery, pwd, if_match) | — | **no difference** | REPRODUCED (set diff) |
| Diff against the 08 §1 index | +cancel-link (not in 08); −`POST /leads/exports` (P1) | unchanged; 08 unchanged (`git diff 9236aa3..HEAD -- docs/architecture` adds only `amendments/`) | SOURCE-INSPECTED |
| OpenAPI snapshot | — | 87 paths / 105 operations; cancel-link present with `x-rbac-exception: RBX-003` | SOURCE-INSPECTED |

Detail on OpenAPI: the snapshot documents `200` for cancel-link, but the handler returns `204` (`rbac/routes.py:488-490` has no `status=204`). This is ADVISORY RR-RBAC-A3.

**Startup declaration check (IR-A05).** `app.py:53-102` now has an RBX register keyed by (method, path) and refuses public routes that declare a permission. Probe results, run in the probe copy (`out/startup_probe.txt`):

| Injected route | Result |
|---|---|
| RBX-003 on an unregistered path | `RuntimeError … not in the RBX-003 register` ✔ |
| Unknown id RBX-999 | RuntimeError ✔ |
| Public with no declaration | RuntimeError ✔ |
| Public + permission, no rbx | `RuntimeError … declares a permission that cannot be enforced` ✔ |
| Bearer + unregistered RBX-004 | RuntimeError ✔ |
| Registered path family, other method | RuntimeError ✔ |
| **`auth="optional"` + `permission="user.read"`** | **create_app OK; an anonymous POST runs the handler → 204 with no permission check** ✘ |

The `optional` case happens because `http.py:577-589` skips `enforce_gates` when there is no ctx, and `app.py:101` only tests `auth == "public"`. No current route is affected: the only two `optional` routes are RBX-004 with no permission. IR-A05 is therefore **PARTIALLY RESOLVED**, and the gap stays at ADVISORY severity.

#### C.2 Probe table

Rows are REPRODUCED on SQLite unless marked. "PG" means also REPRODUCED on embedded PostgreSQL with the same outcome unless stated.

| # | Attempt | Actor | Outcome at head | Verdict |
|---|---|---|---|---|
| P01 | ADMIN account-control on a Founder (status, email, MFA reset/requirement, sessions, pwd-reset, unlock, DELETE, roles, DENY, protection_level, founder-actions) | ADMIN | 403 FOUNDER_PROTECTED / PERMISSION_DENIED / FOUNDER_GOVERNANCE_REQUIRED; PATCH protection_level 422; display_name 200 | blocked (unchanged) |
| P02 | F1 → F2 generic APIs; grant `user.founder.manage`; PUT roles [FOUNDER]; invite with FOUNDER | Founder | all 403; 5 `FOUNDER_GOVERNANCE_BYPASS_BLOCKED` | blocked |
| P03 | FOUNDER role PATCH/DELETE/PUT perms; copy_from FOUNDER; custom role + `user.founder.manage`; permission metadata PATCH | Founder | 403 FOUNDER_GOVERNANCE_REQUIRED / 422 IMMUTABLE_FIELD; I3 holds | blocked (role copy cannot manufacture Founder power) |
| P04 | ADMIN role escalation | ADMIN | self-held role 403; ungranted perms 403 ESCALATION_DENIED; **PATCH own ADMIN role `mfa_required=false` → 200** | IR-A06 unchanged |
| P05 | Mass assignment (roles, protection_level, is_founder, authz_version, …) on `/users/{id}` and `/auth/me` | any | 422 | blocked |
| P06 | IDOR: grants, approvals, sessions | various | 404 / 403 as before; ADMIN approve/deny of a Founder-class request → **403** while GET → 404 | see IR-A07 decision |
| P07 | SALES cross-owner lead / note / activity | SALES | 404 each; list count 0 | blocked (no lead enumeration) |
| P08 | Demotion, DENY, disable, MFA suspension, step-up expiry with the same token | — | 403 / 403 / 401 / 403 / 403 STEP_UP_REQUIRED | correct (authz_version and session invalidation) |
| P09 | One-open-per-target, target/dup approver, stale ex-Founder token, last-Founder self REVOKE/DISABLE | Founders | 409 / 403 / 409 / 403 / 409 LAST_FOUNDER | correct |
| **P10** (IR-04) | STANDARD email change → target promoted → Founder approves stale request | ADMIN + Founders | **409 INVALID_STATE; row CANCELLED/TARGET_BECAME_FOUNDER; proposed_email none** (PG) | **fixed** |
| **P11** (IR-08) | DELETE Founder via workflow, then F1 alone `/restore` | Founders | DELETE → **EXECUTED** (PG); **restore → 200, F3 back as a DISABLED Founder** (PG) | IR-08 fixed; **RR-RBAC-1** |
| P12 | cancel-link: invalid / extra field / valid / replay | anon | 400 / 422 / 204 / 400; link URL `…/approvals/cancel` | secure |
| **P13** (IR-05) | Custodian request while 2 eligible Founders exist (asserted mode) | CLI | **rc 3 INVALID_STATE (FOUNDER_AVAILABLE)** (PG) | **fixed** |
| P14 | Ineligible sole Founder cancels custodian GRANT_FOUNDER twice | Founder | [204, 204] | by design; AM-9 residual |
| P15 | Two Founders approve the same request concurrently | Founders | [200, 409], one FOUNDER row (PG) | correct |
| **P16** (IR-08) | FOUNDER_STATUS_CHANGE DISABLED / MFA_RESET / EMAIL / **DELETE** | Founders | all EXECUTED (PG); deleted row = (deleted, DISABLED, FOUNDER) | fixed |
| P17 | Pre-auth ordering, HEAD, foreign preflight, openapi.json | anon | 422 / 401 / 401 / 204 without ACAO / 200 (non-prod) | unchanged (A-7) |
| N01 | IR-04 MFA_RESET variant: audit, events, follow-ups | ADMIN + Founders | row CANCELLED/TARGET_BECAME_FOUNDER; `APPROVAL_CANCELLED` {reason}; audit CREATE + UPDATE(status, status_reason, decided_on); later approve → 409; requester cancel → 409; new STANDARD request on the Founder → 403 FOUNDER_PROTECTED (PG) | correct |
| N02 | IR-04 without cancellation (out-of-band promotion) | ADMIN | approve → 403 APPROVER_NOT_ELIGIBLE (approver G9 against the target, which now holds `user.founder.manage`); nothing applied | correct (defence in depth) |
| N03 | IR-04 via break-glass promotion (custodian GRANT_FOUNDER executed) | CLI | STANDARD row CANCELLED/TARGET_BECAME_FOUNDER (PG) | correct |
| N04 | IR-05 modes: one eligible Founder, other target / sole eligible Founder is the target / both Founders in cooling-off, then approve after cooling-off ended | CLI | refused + `BREAK_GLASS_REQUESTED` FAILURE {FOUNDER_AVAILABLE} / accepted / accepted, then **approve refused** | conformant to 06 §7.2.4 |
| N05 | Single-Founder mode: custodian mapped to requester F1; other custodian; execute before not_before; F1 in-app approve | CLI / F1 | 403 "different humans" / APPROVED / 409 / 409 | correct (12 TD-G G2, G12) |
| **N06** (IR-06) | STS mode with no AWS credentials | CLI | **uncaught `botocore NoCredentialsError`**; no request; no FAILURE event | fails closed, unclean (RR-RBAC-A1) |
| N06 | STS = K1, `--principal-arn K2` | CLI | rc 3 "supplied principal is not the caller's identity" (+ PRINCIPAL_MISMATCH event) | fixed |
| N06 | STS returns instance-profile role (default container/SSM credentials) | CLI | rc 3 "not a registered custodian" | fails closed → RR-RBAC-3 |
| N07 | `asserted` identity per environment | config | local/test allowed; staging/production: `validate_environment` error **and** `resolve()` 403; `VEDA_ENV=prod` → ConfigError | dev bypass not enableable in deployed envs |
| N08 | Cancel-link lifecycle on an APPROVED custodian request | Founders / target | links issued to f1, f2, target; disabled f2's link → 400; f1 cancels APPROVED → 204 CANCELLED_BY_NOTIFIED_PARTY; sibling link → 400; execute → 409; link after EXECUTED → 400; `BREAK_GLASS_CANCELLED` SUCCESS + FAILURE(TOKEN_INVALID) events; audit UPDATE by f1 (PG) | correct |
| N09 | In-app cancel / deny of a custodian request by an eligible Founder | Founder | GET 200; cancel 403 (requester only); **deny 200 DENIED** | acceptable, undocumented (A-5 carry-over) |
| N10 | Race: cancel-link vs `break_glass_execute` | — | SQLite: execute wins, link 400. **PG: link 204, execute raises `StaleDataError`**; final CANCELLED, target STANDARD | safe; unclean error (RR-RBAC-A2) |
| N11 | ADMIN restore of a deleted Founder; bootstrap with Founders present | ADMIN / CLI | 403 (no `user.restore`); bootstrap rc 2 refused | correct |
| N12 | Concurrent cross step-downs, F1 and F2 (only 2 Founders) | Founders | one EXECUTED, other 403; active Founders = 1 (SQLite and PG) | last Founder protected |
| N13 | Concurrent founder-actions on the same target | Founders | [202, 409], 1 row (SQLite and PG) | correct |
| N14 | Race: GRANT_FOUNDER approval vs STANDARD email-change approval | Founder + ADMIN | both EXECUTED; email change sequenced **before** the promotion (chain_seq 15 < 18) (SQLite and PG); **proposed_email = evil@evil.test on the new Founder** | serialised correctly, but see RR-RBAC-2 |
| N15 | Stale approver (factor revoked) / requester in cooling-off | Founders | 403 **PERMISSION_DENIED** (12 TD-G G7 says APPROVER_NOT_ELIGIBLE) / CANCELLED REQUESTER_INELIGIBLE | correct; code drift (A4) |
| N16 | IR-A07 oracle matrix | ADMIN / SALES | see §4 | — |
| **N17** | STANDARD email change approved (target ADMIN) → GRANT_FOUNDER → attacker verifies | ADMINs + Founders + anon | proposed_email survives promotion; `POST /auth/email/verify` → 204; **Founder email = attacker@evil.test** (PG) | **RR-RBAC-2** |

**Head's own tests (SQLite)**

| Suite | Result |
|---|---|
| `test_rbac.py` | 33 passed |
| `test_founder_governance.py` | 16 passed |
| `test_governance_remediation.py` | 11 passed |
| `unit/test_lint.py` | 9 passed |
| `unit/test_config_environments.py` | 59 passed |
| The three integration files on embedded PostgreSQL | 60 passed |

Coverage gaps in those suites:
- No test covers Founder restore (RR-RBAC-1) or a pending email change across promotion (RR-RBAC-2).
- The G7 test accepts either 403 code.

#### C.3 IR-A07 decision

**What the architecture says**
- 08 §5.11 (approve/deny rows) specifies `403 APPROVER_NOT_ELIGIBLE` for "is the requester, is the target, fails G9, or, for FOUNDER class, is not a Founder".
- 12 TD-G G1, G7 and G9 expect 403 for those cases.
- 08 §13 (404 = "missing, soft-deleted or out of scope") and GET `_visible` give 404.
- The head follows 08 §5.11. See `rbac/routes.py:436-458`, whose comment names the choice.

**Probe N16 (REPRODUCED)**

| Caller | Existing approval | Nonexistent approval |
|---|---|---|
| ADMIN (holds `user.mfa.reset`), approve or deny a Founder-class request | 403 | 404 (valid UUIDv7) |
| ADMIN, cancel | 404 | 404 |
| ADMIN, GET | 404 | 404 |
| SALES (fails the any-of route gate), approve | 403 PERMISSION_DENIED | 403 PERMISSION_DENIED (no oracle) |

For decided requests the ADMIN gets 409 INVALID_STATE, so the response also reveals the status.

**Security reasoning**
- Only authenticated holders of an approvals permission (ADMIN-class) can distinguish existing from missing ids.
- Ids are UUIDv7: 48-bit millisecond time prefix plus 74 random bits (`08 §2` regex; N16 shows version nibble 7). The time prefix is guessable, but the 74 random bits make enumeration infeasible. The oracle only confirms an id the caller already has.
- Those same ADMINs hold `security_event.read` and `audit.read`. Through them they already read `FOUNDER_ACTION_REQUESTED` events and `admin_approval_request` audit rows that contain the approval id, action, target and later status: N16 "approval id visible=True" for both endpoints.
- The oracle therefore discloses nothing beyond what the caller is already entitled to read.
- Normalizing to 404 would diverge from the certified 08 §5.11 and 12 TD-G, and would need an amendment. It would also degrade the SPA's error messaging for real approvers.

**Architecture impact**
- None required.
- Optional clarification in 08 §5.11: "for approvals the caller cannot see, approve/deny may return 403; the caller already sees ids via audit/security-event read".

#### C.4 DEV-005 decision

| Criterion | Result |
|---|---|
| Endpoint exists | `POST /api/v1/approvals/cancel-link` (`rbac/routes.py:479-490`), public, closed DTO `{token}` |
| Page/link exists and works | Link built at `handlers.py:447` → `{app_origin}/approvals/cancel#token=…` (P12). SPA route `routes.ts:34` (public, so it is not redirected for signed-in users; see `guard.ts:32`). The page reads the fragment, scrubs it with `history.replaceState`, needs an explicit click (mail-scanner safe), and POSTs anonymously to the endpoint (`approval-cancel-page.ts:25-47`). A router unit test asserts the title. The author's Playwright e2e evidence says PASS; I did not re-run it (no `node_modules`) |
| Authorization | 256-bit HMAC token, hash-only storage, purpose `APPROVAL_CANCEL`, bound to the request through the outbox payload. Only notified parties hold tokens: all ACTIVE Founders plus the target (`governance.py:276-295`). A disabled Founder's token dies (N08) |
| Cancellation rules | BREAK_GLASS channel and status PENDING or APPROVED only (`governance.py:552-565`). After EXECUTED or CANCELLED → uniform 400 (N08) |
| Replay prevention | Single use plus sibling invalidation (P12, N08). Race with execute is safe on both engines (N10) |
| Audit / security events | `BREAK_GLASS_CANCELLED` SUCCESS, and FAILURE(TOKEN_INVALID) for bad links. Audit UPDATE with `performed_by` = the token holder (N08). No SENSITIVE_ACTION, which is appropriate because this is not a permission use |
| RBX registration | In the startup register (`app.py:60-68`) and OpenAPI (`x-rbac-exception: RBX-003`). Not yet in the certified 06 §11 or 08 §1 until AM-5 is approved |
| Residuals | IR-A10 (outbox-retention binding), no rate limit (A-8), OpenAPI 200 vs 204 (A3) |

Not a security blocker. Implementation change is not required.

### Appendix D — Leads/audit-chain working paper

#### D.1 Chain probe table

Tampering was done with the immutability triggers dropped, the way a DB or host attacker would do it. S = SQLite, PG = embedded PostgreSQL.

| # | Scenario | S | PG | Expected | Verdict |
|---|---|---|---|---|---|
| C01 | Modify a middle row after the anchor | `row_hash mismatch` | same | detect | OK |
| C02 | Delete the anchored prefix (≤ anchor seq) | `prefix removed` | same | detect | OK (was ok=True at 9236aa3) |
| C03 | Delete a middle row | `gap` | same | detect | OK |
| C04a | Truncate the tail **below** the anchor | `truncated below anchor` | same | detect | OK (was ok=True) |
| C04b | Truncate the tail **above** the latest anchor (rows written after it) | **ok=True** | ok=True | inherent window | Residual accepted by 05 §9.6 / 11 §4 A2 (bounded by the daily anchor). RR-LEAD-7 |
| C05 | Renumber the head (sequence gap) | `gap` | same | detect | OK |
| C06 | Event recorded, then the transaction rolls back | contiguous, ok | same | no gap | OK |
| C07 | 6 threads × 15 deferred writes | 90/90, ok | 90/90, ok | no fork | OK |
| C08 | 4 **processes** × 20 writes | 80/80, ok | 80/80, ok | no fork | OK. Note: `_write_now` swallows writer failures (`security_events.py:393-397`), so a lost event shows only as a CRITICAL log or metric (see RR-LEAD-3). |
| C09 | Legitimate archive with the anchor inside the archived range, then a second archive | ok, ok | ok, ok | no false positive | OK |
| C10 | IR-26 Q3 boundary (event time and chain order disagree) | X and Y both kept online, nothing lost | same | no unexported deletion | OK (IR-26 fixed) |
| **C11** | **Forged archive manifest** (a new write-once object, `first_seq=1,last_seq=anchor+1`, a dummy sha256, a nonexistent file), then delete rows 1..anchor+1 | **ok=True** | **ok=True** | detect | **FAIL: RR-LEAD-1** |
| **C12** | Archive writes the manifest, then the DB transaction fails (simulated) | manifest (1,2) stored, rows still online; verify: **`prefix removed` (false positive)**; re-archive **refused forever** | same | atomic | **FAIL: RR-LEAD-2** |
| C13 | Anchor store unavailable during verify, archive and intake | verify **raises** ConnectionError: no report, **no CHAIN_BROKEN event, no CRITICAL log, no metric**. Archive raises, rows kept. Public intake returns 201 (the app keeps running). | same | fail closed and alert | Fails closed, but silently. See RR-LEAD-3 |
| C14 | Anchor stored, but recording the DB event fails; re-anchor at the same head | LocalAnchorStore raises "already exists". This self-heals once the head moves (the deferred FAILURE event does that). | same | — | Advisory (RR-LEAD-6) |
| C15 | `security_events.verify_chain(from_seq=first)` (used by `backups.py:146` restore-verify) after a prefix delete | ok=True | ok=True | — | Advisory: the restore check trusts the first row (RR-LEAD-7) |
| CLI | `veda.cli maintenance verify-chain` / `anchor-chain` as a subprocess against a tampered DB or an unwritable store | stdout: JSON report only. stderr: one plain line (`security_log_chain_broken ...`). **No EMF metric line.** | n/a | metric plus alarm | **FAIL: RR-LEAD-3** |

**SQLite vs PostgreSQL:** the chain behaviour is identical on both engines. The one audit-store difference is that the PostgreSQL GUC bypass (`SET LOCAL veda.maintenance='on'`) still lets any session update `audit_log` (original probe Q2 updated 209 rows; my D03 updated 6). This is unchanged since 9236aa3, and SQLite (the P0 production engine) is unaffected.

**External anchoring (S3 Object Lock):** the code is not stubbed. `S3AnchorStore` (`anchor_store.py:57-99`) uses `put_object` with `ObjectLockMode=COMPLIANCE` and a 3650-day retention, plus paginated list and get. The following are gaps:

- It is tested only with an in-memory `FakeS3` (`tests/integration/test_chain_integrity.py:160-202`). The fake does not enforce write-once, versioning, Object Lock or IAM.
- The real client builder is `# pragma: no cover` (`anchor_store.py:62-65`).
- Production requires `VEDA_ANCHOR_BUCKET` (`config.py:347-349`). Staging does not, so staging falls back to `LocalAnchorStore` on the same host (`anchor_store.py:116`).
- Without S3, verification uses the local directory. If the store errors, verification raises, so it fails closed, but with no alert (RR-LEAD-3).
- Role separation (a write-only writer role and a read-only verifier role, 05 §9.6) is **not implemented**. Both paths use the default boto3 credential chain, and the archive writer also needs List and Get (`maintenance.py:453`).

**Classification:**

| Aspect | Status |
|---|---|
| Repository behaviour | Resolved for the Q4 cases; C11 and C12 are defects |
| Staging | Staging evidence required: a bucket with Object Lock COMPLIANCE and versioning, PutObject checksum or MD5 accepted (botocore 1.43.104 defaults to flexible checksums), IAM writer/reader separation, and the list permission for the verifier |
| Production | Production gate required: SEVT-007 must not be claimed until then |
| AWS behaviour | **Not executed** |

#### D.2 DEV-004

| Check | Result (SQLite and PG identical) | Evidence |
|---|---|---|
| Re-consent when never withdrawn and the policy version is unchanged | **409 INVALID_STATE**, original evidence untouched | D01; `service.py:835-839` |
| Repeat after a valid re-consent | 409 | D01 |
| Re-consent after withdrawal | 200. Row: channel=PHONE_VERBAL, **ip=None, source_page=None**, withdrawal cleared | D01; `service.py:870-873` |
| Staff WEBSITE_FORM | 422 on PATCH and on staff create | D01; `schemas.py:52-63`. The DB CHECK still allows it (needed for public intake), so the restriction is app-level only. |
| Note or evidence required | Missing → 422. Whitespace only → 422. | D01; `schemas.py:63` |
| Policy version | Unknown → 422 UNKNOWN_POLICY_VERSION. A **different** published version is accepted without withdrawal, and alternating v2→v1→v2→v1 gave **200 ×4** (overwrites each time; history kept). | D02: RR-LEAD-4 |
| Historical evidence retention | A read-only SYSTEM activity with `metadata.previous` (channel, version, captured_on, source_page, `ip_address_recorded` flag, withdrawal). The full prior row, **including the web IP**, stays only in `audit_log` UPDATE `old_value` (immutable; D01 shows the old IP kept). | `service.py:841-869`, `activities.py:98-101` |
| Is the history append-only? | Over the API, PATCH or DELETE gives 422 SYSTEM_ACTIVITY_READ_ONLY. **Raw SQL UPDATE and DELETE on `lead_activity` are ALLOWED on both engines.** An ORM update of `metadata` is ALLOWED (it writes an audit UPDATE row). An ORM hard delete is blocked (ImmutableRowError). No new table; no DB guard. The original evidence survives in `audit_log` (the CREATE row of the activity plus the lead UPDATE). | D03: RR-LEAD-4 |
| Consent history cannot be overwritten | Row fields are overwritten by design. The history lives in the activity (mutable at DB level) and in `audit_log` (immutable on SQLite; bypassable on PG with the GUC). | D03 |
| Withdrawal persistent | Withdrawal clears nothing until a valid re-consent. It is 409 if already withdrawn. Withdrawal blocks planned contact activities. | `service.py:808-821` |
| Staff capture claims no web source or IP | Yes | D01 |
| System activity | Yes ("Consent to contact recorded again") | D01 |
| Audit | Lead UPDATE row (reason=None) plus activity CREATE | D01 |
| Security event | **None** for re-consent (none for withdrawal either). No catalog event is required by 05 §9 or 04 §5.4. | D01 |
| SALES scope | OWN: own lead → 200. Another user's lead → 404. `/history` → 403, but the evidence is visible in the timeline. | D04 |
| Erased lead | 409 (IR-28 guard) | P4 |
| Staff create-time consent | Accepted with **no note and no consent activity** (only "Lead created") | D05: RR-LEAD-4 |
| Migration of existing rows | No schema or data migration. The 0100 diff is reformatting only. There are no legacy rows while P0 is undeployed. The migrations were edited in place, which is safe only if no environment has applied 9236aa3's revisions. | `migrations/versions/0100_crm_leads.py` |
| Documentation | AM-4 correctly says there is no UI control in P0. The earlier F-18 claim was withdrawn. | AM-4 |

**Decision: DEV-004 is ACCEPTABLE WITH ARCHITECTURE AMENDMENT (AM-4).**

- All four required changes from the original review are implemented and reproduced.
- The residuals (version flip-flop, history mutable at DB level, create-time consent without a note) are MINOR and belong in AM-4's decision ("in-row + timeline" vs a dedicated append-only `lead_consent_event`).
- It is not a security blocker: it requires an authenticated user holding `lead.update` in scope plus If-Match.

#### D.3 IR-02 re-probe

| Probe | SQLite | PG |
|---|---|---|
| Q5 intake, verify delay 3 s | Concurrent staff write 201 in **0.04 s** (was 2.77 s) | n/a |
| Q5 intake, verify delay 6 s | Staff write 201 in **0.01 s** (was 503 after 5.19 s) | n/a |
| Q5 CAPTCHA-gated login, verify delay 6 s | Staff write 201 in **0.02 s**, login 200 | n/a |
| Q7 same key, both requests pass the pre-check (barrier in the verifier) | 201 + 201 with the same reference, **1 lead** (re-check in the write transaction, `routes.py:106-109`) | 201 + **409 DUPLICATE**, 1 lead (IR-A16, unchanged) |
| Replay with a spent token | 201, same body, 0 Turnstile calls | same |

**Mechanism:** `http.py:546-575` runs `prepare` in `unit_of_work(write=False)` and then opens `new_session(write=True)`. `routes.py:75-90` rolls back the read transaction before `turnstile.verify`. The login path is the same (`auth/routes.py:44-46`, `service.py:359-365`).

**Status: RESOLVED.**

#### D.4 Lead workflow regression sweep

| # | Step | Result at head |
|---|---|---|
| 1–2 | Form render, client validation | Unchanged (FE reviewer) |
| 3 | CAPTCHA | Fails closed (`CAPTCHA_FAILED`, PUBLIC_INTAKE_BLOCKED event persisted). Now outside the write lock. |
| 4 | Size, closed schema, limiter | Unchanged |
| 5 | Client IP | Unchanged (trusted-proxy CIDRs now validated) |
| 6 | Idempotency | Spent-token replay: 201, same body, 0 calls. Different body: 422 `IDEMPOTENCY_KEY_REUSED`. Same-key race: correct on SQLite; 409 on PG (IR-A16). |
| 7 | Server validation | Unchanged |
| 8 | Honeypot | 201 `{message, reference}`, stored `SUSPECTED`, QUARANTINED event, no `lead.created` outbox |
| 9 | Duplicates | Flagged `SUSPECTED`, never rejected |
| 10 | Consent evidence | WEBSITE_FORM, version, time, IP and page captured at intake |
| 11 | Atomicity | Outbox failure: 500 with nothing persisted (leads 4/4, audit 210/210). The site falls back to WhatsApp, so nothing is silently lost. |
| 12 | Audit actor | WEB_INTAKE / PUBLIC_FORM on the public transaction; staff actor and session correct; worker SYSTEM |
| 13 | Outbox / notify | In-app rows survive an email failure; DEAD after 8 attempts; retry does not re-send (IR-30) |
| 14 | Public response | Random reference, no internal fields |
| 15–16 | List / SALES scope | Another user's lead: 404; list scoped (1 visible) |
| 17 | Assign | 200 |
| 18 | Transitions | Forward skip (NEW→SITE_VISIT) 200; WON from an early stage without a comment 422; with a comment 200; reopen WON→NEGOTIATION with a comment 200; stale If-Match 409 |
| 19 | Notes / activities | Erased lead: 409 (IR-28); withdrawal blocks planned contact |
| 20 | WON/LOST effects | Unchanged |
| 21 | Erasure / withdrawal / hold | Refusal event persisted (IR-25); erased-lead writes blocked; consent flows as in §2 |

- **No regression** was found in steps 1–21.
- **Tamper-chain false confidence:** RR-LEAD-1 (verify reports ok after a forged manifest) and RR-LEAD-3 (detected breaks never reach an alarm).
- **Author test gap:** the author's `FakeS3` and in-process tests cannot reveal either defect. Tests call `create_app`, which configures logging, and the CLI never does.

### Appendix E — Database/ops/CI working paper

#### E.1 Migration recount

| Item | 9236aa3 SQLite | 9236aa3 PG16 | **head SQLite** | **head PG16** | **head PG18** | Delta |
|---|---|---|---|---|---|---|
| Tables (excluding alembic_version) | 24 | 24 | **24** | **24** | **24** | 0 |
| Columns | 502 | 502 | **504** | **504** | **504** | +2 (`mfa_challenge.factor_id`, `enrollment_path`) |
| PKs | 24 | 24 | 24 | 24 (+alembic = 25 in catalog) | 24 | 0 |
| FKs | 107 | 107 | **108** | **108** | **108** | +1 `fk_mfa_challenge__factor_id` (RESTRICT) |
| CHECKs (inspector) | 493 | 161 | **498** | **164** | **164** | SQLite +5 (`enrollment_path`, `_len`, `factor_id_format`, `path_purpose`, `factor_path`); PG +3 |
| Non-PK indexes | 72 | 72 | 72 | 72 | 72 | 0 (no index on `factor_id`) |
| Unique / partial indexes | 24 / 46 | 24 / 46 | 24 / 46 | 24 / 46 | 24 / 46 | 0 |
| Triggers | 4 | 4 | 4 | 4 | 4 | 0 |
| Unique constraints | 0 | 0 | 0 | 0 | 0 | 0 |

- **Contract columns.** All 24 tables carry the nine contract columns in order (`id, created_on, updated_on, created_by, updated_by, is_deleted, deleted_on, deleted_by, version`). Every table has `ck_<t>__version_positive` and `ck_<t>__soft_delete_consistent`, on all three engines.
- **Seeds, identical on every engine and across two fresh databases per engine:**
  - 3 roles, 45 permissions (16 sensitive), 101 role_permission rows, 6 lookup categories, 47 lookup values;
  - app_user: 3 rows, all SYSTEM, with **0 HUMAN**; user_credential 0; password hashes 0;
  - audit_log 206; security_event_log 0.
- **UUIDv7.**
  - SQLite enforces it with CHECK: a raw v4 insert is rejected by `ck_lookup_category__id_format`.
  - PostgreSQL enforces format only (native `uuid`): a raw v4 insert SUCCEEDED. This is unchanged from the original and documented in 03 §12.

#### E.1 Upgrade with data

Procedure:
1. `seed_old.py`, run in the **old** checkout with the old venv, migrates to `0100_crm_leads` and populates data through the old API. The data covers Founder, Admin and two Sales users with logins (sessions, refresh tokens, LOGIN challenges, security events), 3 leads, 1 public lead, and an **in-flight path-A ENROLLMENT challenge**.
2. The **head** `alembic upgrade head` is applied.
3. `post_new.py` runs the head app against the upgraded database.
4. `cmp_schema.py` compares the result with a fresh head database.

| Check | SQLite | PG 16.4 |
|---|---|---|
| Upgrade `0100_crm_leads -> 0009_mfa_challenge_binding` | rc 0 | rc 0 |
| Founder login + TOTP with a pre-upgrade factor (decrypt compatible) | 200 AUTHENTICATED | 200 AUTHENTICATED (the first try returned 401 from the replay guard because the old process had advanced the clock; it passed with a later step) |
| List leads, list audit logs | 200 / 200 | 200 / 200 |
| In-flight ENROLLMENT confirm after upgrade | **401 MFA_CHALLENGE_INVALID** (fails closed, as the migration docstring states) | same |
| `verify_chain` / `check_invariants` | ok, 11 rows / all true | ok, 9 rows / all true |
| Schema: upgraded vs fresh head | **identical** (tables, columns, FKs, CHECKs, indexes, triggers) | **identical** |
| Seed business data | identical (only `number_sequence` differs because leads were consumed) | identical (same) |
| `veda conformance` on the upgraded SQLite DB | `conformance: OK` | n/a |

`alembic check` on SQLite reports only reflection artefacts:
- DESC/expression indexes;
- unnamed column-level FKs added by `ALTER TABLE ADD COLUMN`, including `fk_mfa_challenge__factor_id`.

`test_schema.py:83` pairs these up. They are not real drift.

#### E.1 Readiness, rollback and N-1

`api/veda/platform/health.py:50-58` (`schema_state`), `:60-66` (`_detail_allowed`) and `:85` (`ok &= state in ("head","ahead")`) match AM-6 and DEV-008.

`ready_probe.py` runs a Flask test client with `REMOTE_ADDR` set, against the SQLite database at head:

| Image | Declaration | Loopback caller | Bridge peer 172.18.0.1 | Via edge (`CF-Connecting-IP`) |
|---|---|---|---|---|
| Head, DB at head | — | 200 `{"status":"ok","checks":{…"migrations":"head"…}}` | 200 `{"status":"ok"}` | 200 `{"status":"ok"}` |
| Head code with 0009 removed from its script dir (simulated AM-6-aware N-1) | none | **503** `migrations: ahead_undeclared` | 503 `{"status":"degraded"}` | 503 status only |
| Same | `VEDA_SCHEMA_AHEAD_ACCEPTED=0009_mfa_challenge_binding` | **200** `migrations: ahead` | 200 status only | 200 status only |
| Same | a wrong revision declared | 503 `ahead_undeclared` | 503 | 503 |
| **Actual N-1 image 9236aa3** | n/a (old code) | **503 `migrations: behind`**, with details shown to every caller | 503 with details | 503 with details |

Real gunicorn run (no-pip venv): `live` 200; `ready` from loopback returns the full checks; `ready` with a CF header returns `{"status":"ok"}`.

Conclusions:
- **IR-10.** The mechanism works for any future N-1 that contains AM-6. **The rollback target for this release (9236aa3) cannot become ready on the migrated schema.** It predates AM-6, and it also carries the IR-01 BLOCKER. Neither the runbook, AM-6 nor AM-11 says so. AM-11 says "Normal rollback: N-1 image on the migrated schema (columns ignored)". See RR-OPS-5.
- **IR-A17 is RESOLVED.** Only `{status}` reaches the edge and non-loopback callers. The details contain no secrets: they are the DB, migrations, FK, guards and outbox counters.
  - Under the committed compose topology (`ports: 127.0.0.1:8000:8000`), a host-side caller such as `deploy.sh`'s `curl` reaches the container from the Docker bridge gateway, which is not loopback. The host therefore never sees `checks`, so runbook §2 step 3 ("must pass /health/ready with `migrations: ahead`") cannot be observed from the host. This is operability only (RR-OPS-5).
- `deploy.sh --rollback` (`api/deploy/deploy.sh:38`) only greps that a `VEDA_SCHEMA_AHEAD_ACCEPTED=` line exists. It does not check that the line names the current DB revision; the readiness gate still catches a wrong value.
- **Stale declaration:** `VEDA_SCHEMA_AHEAD_ACCEPTED` left set in production is accepted silently (probe_config). It is harmless unless a future unknown revision matches it. Runbook §2 step 4 covers removal.

#### E.2 CI jobs

| Job | What runs | Mandatory? | Notes |
|---|---|---|---|
| api (sqlite) | hash-locked install; ruff check; ruff format --check; mypy ratchet; full pytest (`VEDA_TEST_ENGINES=sqlite`); openapi_check; deploy-check | Yes. No `continue-on-error`, `\|\| true` or soft exits; `fail-fast: false` still fails the workflow | Ratchet fail-open (RR-OPS-4) |
| api (postgresql) | same, with `VEDA_TEST_ENGINES=postgresql` against the `postgres:16` service; prints the server version | Yes | **The `postgres:16` tag floats** (16.x latest, not 16.4, no digest) |
| security | secret scan; `pip-audit --require-hashes --disable-pip --strict`; `bandit -ll -ii`; `npm ci --ignore-scripts`, `npm audit --omit=dev` (any severity), `npm audit --audit-level=high`; `docker build`; Trivy CRITICAL,HIGH `ignore-unfixed: true` `exit-code: 1` | Yes | No `.trivyignore` anywhere. `ignore-unfixed` silently accepts HIGH/CRITICAL with no upstream fix, with no recorded risk acceptance |
| app | `npm ci`; Playwright chromium; lint, typecheck, token lint, contrast, unit tests, build | Yes | — |
| e2e | runtime lock install; `app/e2e/run-all.sh` (workspace, access, site, axe) | Yes. `run-all.sh` uses `set -uo pipefail` plus an explicit `status=1` per failing journey and `exit $status`; bootstrap or wait failures `exit 1` | Browser tests do run in CI. The API runs as a **Flask dev server with `VEDA_ENV=local`**, not gunicorn or the image |

Other observations:
- **Actions are pinned by 40-hex SHA:**
  - checkout `3d3c42e5…` (v7.0.1)
  - setup-python `5fda3b95…`
  - setup-node `82076278…`
  - upload-artifact `043fb46d…`
  - trivy-action `ed142fd0…` (v0.36.0)
  
  Permissions are `contents: read`.
- Recommendation: confirm that the trivy-action SHA is the genuine v0.36.0 release commit. I could not verify it offline.
- **CI execution evidence: none available.** `gh` is not installed (`command not found`), so I could not verify any run. The author's report §7 and OI-RM-1 state that the first CI run is still outstanding.
- No CI job runs the built image (`docker run veda-api:ci …`). This means the pip-less image, the `on_starting` hook and the instance lock are never exercised in CI (RR-OPS-7).

#### E.2 Removing pip

I simulated the image with `python3.13 -m venv --without-pip $S/probes2/db/nopip`, then `pip --python nopip/bin/python install --require-hashes --no-deps -r requirements.txt`. `nopip/bin/python -m pip` reports "No module named pip".

| Operation (`python -m veda.cli …`, VEDA_ENV=local, SQLite) | Result |
|---|---|
| `migrate` | rc 0 (0001 → 0009) |
| `deploy-check` | `deploy-check: OK` |
| `bootstrap-founder --email … --name …` | rc 0, invite link JSON |
| `maintenance snapshot` / `restore-verify` / `disk-usage` / `verify-chain` / `anchor-chain` / `invariants` | all rc 0 (`invariants` printed its failures and still returned rc 0; see RR-OPS-1 note) |
| `worker --once`, `conformance`, `sync-permissions` | rc 0 |
| `gunicorn -c deploy/gunicorn.conf.py wsgi:app` | starts; `/health/live` 200; `/health/ready` 200 |

Other checks:
- Runtime imports of `pip`, `setuptools` or `pkg_resources`: only `sentry_sdk/utils.py:1817`, a guarded fallback, and `werkzeug/testapp.py`. Neither matters.
- Runbook and deploy steps using pip: none. The only matches are the Dockerfile build line, the README dev setup and CI installs.
- There is no Docker `HEALTHCHECK` and no compose healthcheck. This is unchanged, and the runbook relies on an external check.

**Removing pip does not break operability (REPRODUCED by simulation, not in the real image).**

**Trivy:** removing pip removes pip's vendored packages, which had fixable advisories. That is legitimate attack-surface reduction, not suppression. There is no ignore file. I could not run Trivy myself.

#### E.2 mypy ratchet

- **New violations fail.** A new file with errors fails because its baseline is 0. An extra error in a baselined file fails; I reproduced this: roles.py went 1 → 2, giving `FAIL rc 1`.
- **The baseline cannot grow for an existing file through `--update`**, which uses `min(n, baseline)`. It can grow only by editing the JSON by hand, and that is visible in review.
- **Renamed or moved files do not evade.** The new path has baseline 0, so it fails. However, `--update` computes `baseline.get(f, n)`, which **adds a new file with all its current errors**. Running `--update` after a rename silently re-admits the errors. Treat `--update` diffs as review items.
- **Baseline reductions** happen only when someone runs `--update`. Nothing forces the baseline down, and nothing reports it in CI, so fixed errors leave slack that later regressions can reuse.
- **Per-file totals, not per error code.** An error can be swapped within a file (fix an `union-attr`, add an `arg-type`) without detection.
- **Fail-open (REPRODUCED).** `current()` parses stdout only. It ignores the return code and stderr, and it never checks that mypy actually ran.
  - With mypy absent: `nopip/bin/python tools/mypy_ratchet.py` → `mypy: 0 errors (baseline 157); OK` rc 0.
  - With a broken config (`plugins = ["nonexistent_plugin"]`): `0 errors … OK` rc 0.
  - See RR-OPS-4.
- **Configuration** (`pyproject.toml [tool.mypy]`):
  - `files=["veda"]` only, so tests, tools and migrations are not type-checked;
  - `check_untyped_defs`, `no_implicit_optional` and `warn_unused_ignores` are on;
  - `disallow_any_generics=false`;
  - `ignore_missing_imports` is per-module only (boto3, sentry, phonenumbers, argon2, flask_limiter, gunicorn, psycopg), with no global ignore;
  - only 2 `type: ignore` comments exist in `veda`.
- **The baseline's 157 errors**:
  - 98 `union-attr`, 24 `arg-type`, 16 `assignment`, 8 `var-annotated`, 6 `attr-defined`, 3 `index`, 2 `return-value`;
  - concentrated in `auth/service.py` (62) and `notifications/handlers.py` (18).
  - The matrix calls them "157 pre-existing Optional-narrowing findings". Only about 98 are. The rest are sequence/list, SQLAlchemy typing and JWT key-type unions (`jwt_tokens.py:64`), plus `app.py:134` `JSONProvider.ensure_ascii`.
  - My sample showed nothing severe. The worst outcome is AttributeError → 500 on `None` session, user or credential, not an auth bypass.

#### E.3 Staging-only items

| Item | Code ready for staging? | Acceptance criteria | Evidence required | Owner | Failure behaviour (code) | Re-review |
|---|---|---|---|---|---|---|
| IR-03 S3 anchor (`api/veda/platform/anchor_store.py:57-99`; `maintenance.py` `anchor_chain`, `verify_chain`) | **Code ready; design residual.** COMPLIANCE put with 3650-day retention. boto3 1.43 sends default CRC32 checksums, which satisfies Object Lock's checksum requirement (to be confirmed in staging). `verify_chain` checks **only the latest anchor**. All containers share one instance role, so the "write-only writer / read-only verifier" split in the docstring is not realisable as deployed. A host attacker holding the chain key and `s3:PutObject` could re-chain history and write a newer anchor version | Anchor written daily; bucket has Object Lock COMPLIANCE plus versioning; delete or overwrite of a locked version denied; tampering with a DB row → `ChainVerificationFailed`; verification checks every anchor, or roles are separated | CLI outputs; S3 object-lock headers; IAM policies; a tamper drill; CloudWatch metric (blocked by RR-OPS-1) | Engineering (security) + Ops | Put failure → `log.critical`, `ChainAnchorFailed` metric (currently dropped, RR-OPS-1), deferred FAILURE event, non-zero exit | Targeted |
| IR-06 STS custodian (`api/veda/platform/rbac/custodians.py:22-59`) | **Not ready as documented.** The CLI runs inside the api container (`docker compose run`), where boto3 gets **instance-role credentials over IMDS**, not the custodian's SSM-session identity. Both custodians therefore resolve to `assumed-role/<instance-role>/i-…`. The effect is fail-closed (two different humans are required), but break-glass is unusable unless a credential-propagation procedure is defined (e.g. custodian `assume-role` with MFA, passed as `-e AWS_*`). Runbook §7 does not define one | Two distinct custodian ARNs derived from STS in one staging drill; a mismatched `--principal-arn` is refused with a FAILURE event | Drill transcript; STS ARNs stored on the request; security events | Ops + Engineering (security) | STS error → exception (CLI non-zero); mismatch → 403 plus a FAILURE event | Targeted (auth reviewer) |
| IR-11 replication / restore / rollback | **Partially ready.** `litestream.yml` is env-parameterised, but runbook §3 is broken (RR-OPS-3), the snapshot dir is not enforced (RR-OPS-2), and restore-verify never restores from S3 | Litestream lag within the owner-approved RPO; a restore from S3 to a new host passes restore-verify; the N-1 rollback rehearsal passes readiness with `ahead` (needs an AM-6-aware N-1, not 9236aa3); timed RTO | RG-1, RG-2 and RG-7 evidence; OWNER-INPUT-001 | Ops | restore-verify raises → `RestoreVerified=0` (dropped, RR-OPS-1); a missing manifest raises **outside** the try, so no metric at all | Operational readiness review |
| IR-12 alarms | **Not ready.** CLI, worker and scheduler metrics are never emitted (RR-OPS-1). Alarms and SNS exist only as runbook text | Each alarm in runbook §9 test-fired end-to-end to SNS email/SMS | RG-5 evidence (alarm history) | Ops + Engineering | — | Operational readiness review |
| SES (`notifications/email.py:97-120`, sesv2) | Code ready | Verified domain, DKIM/SPF/DMARC; production access out of sandbox; configuration set with bounce/complaint events; a send from staging | SES console / CLI evidence; a delivered test mail | Ops | Send exceptions → outbox retry → dead-letter (the OutboxDead metric is dropped, RR-OPS-1) | Targeted |
| KMS (`auth/crypto.py:86-96,124-133`) | Code ready (GenerateDataKey AES_256 / Decrypt with KeyId). The AAD constant is IR-A20 | Enrollment with a real CMK; decrypt after a key rotation; key policy limited to the instance role | Key policy; CloudTrail GenerateDataKey/Decrypt | Ops + Engineering | KMS error → request 500 (enrollment/verify unavailable; fails closed) | Targeted |
| S3 snapshots (`backups.py:73-85`) | Code ready, but `VEDA_SNAPSHOT_DIR` is not enforced (RR-OPS-2) | Object Lock COMPLIANCE upload plus 35-day retention; the local dir sits on the volume | S3 object retention headers | Ops | Upload error → exception, no `SnapshotCompleted` (dropped anyway) | Targeted |
| Readiness | Code ready (§1.7). From the host only `{status}` is visible (RR-OPS-5) | External check alarms on 2 failures; the deploy gate uses status only | Deploy logs | Ops | 503 → `deploy.sh` stops with the worker and scheduler paused | — |
| Cross-cutting | — | **IMDSv2 hop limit ≥ 2** so containers on the bridge network can reach instance-role credentials (KMS, SES, S3, STS, Litestream); `/var/lib/veda` owned by uid 10001, since the image runs as `veda` | Instance metadata options; `ls -ln` | Ops | Without them, every AWS adapter fails | — |

#### E.4 Registry completeness

- **Items: 106** (`.md` rows: 106).
- **Original findings IR-01 … IR-39: all 39 present.** Severities match: 1 BLOCKER (IR-01), 18 MAJOR, 20 MINOR.
- **Advisories: 16 of 25 present.**
  - Present: A01, A02, A06, A07, A08, A10, A11, A12, A14, A15, A16, A18, A20, A22, A23, A24.
  - **Missing: IR-A03, A04, A05, A09, A13, A17, A19, A21, A25.** These are the ones the matrix marks RESOLVED.
  - This contradicts the registry's own note ("RESOLVED findings are kept … until the targeted re-review confirms them") (RR-OPS-8).
- **Deviations: 8** (DEV-001 … DEV-008). **Amendments: 11** (AM-1 … AM-11), all PROPOSED, NOT APPROVED.
- **Gates: 27.** They are OWNER-INPUT-001…004, TG-01…08, RG-1…9, PG-DAST, PG-RET, PG-BG, PG-EMAIL, PG-PRIV and PGM-1.
  - The list matches `docs/architecture/gate-registry.json` exactly (27 `gate_id`s), with no status mismatches.
  - `gate-registry.json` and `.md` are **unchanged** since 9236aa3 and since 778aa8f. The only architecture changes are the new `amendments/` files.
- **TG-01** is "Pending — no verifiable owner approval exists" and **TG-08** is "Pending — not authorized". Both "Block merge". **No production gate is incorrectly closed:** all RG-* and PG-* are Pending or Blocked.
- **Remediation items OI-RM-1 … OI-RM-5 are present.** OI-RM-1 (first CI run) is OPEN and blocks merge.
- **Fields present on every item:** owner category, severity, affected scope, merge / staging / production impact, acceptance criteria, evidence required, failure behaviour, target phase, status, residual.
- **Current re-review findings:** not yet present (they are expected to be added from this re-review).
- **Inconsistencies:**
  - IR-14 is "RESOLVED" with merge impact "Cleared by the fix", while OI-RM-1 is OPEN (RR-OPS-8).
  - The IR-39 remediation text calls all 157 mypy errors "Optional-narrowing"; about 98 are.
  - Registry staging impact for IR-03 and IR-06 is "None", but staging verification is where their acceptance happens (report §7). This is consistent with the "production: Blocks" entry.

### Appendix F — Frontend/site/browser working paper

#### F.1 Toolchain

| # | Command (cwd `probes2/fe/app`) | Exit | Result |
|---|---|---|---|
| 1 | `npm ci` (clean, no node_modules) | 0 | added 426 packages, audited 427; "found 0 vulnerabilities" |
| 2 | Prettier / format check | n/a | **Not configured.** No prettier dependency, config or script. The IR-39 remediation text did not require it; advisory only. |
| 3 | `npm run lint` (eslint .) | 0 | 0 problems |
| 3b | `npx eslint src/zz-probe.ts` (temporary sink probe, then deleted) | 1 | Caught: `lit/directives/unsafe-html.js` (named and namespace imports), `.innerHTML=`, `['outerHTML']`, `insertAdjacentHTML`, `document.write`. **Missed:** `lit-html/directives/unsafe-html.js`, `lit/directives/unsafe-mathml.js`, a Lit `.innerHTML=${}` property binding, `createContextualFragment`, `setHTMLUnsafe`, `Reflect.set(el,'innerHTML')`, and computed `el[x]`. See RR-FE-4. |
| 4 | `npm run lint:tokens` | 0 | passed |
| 5 | `npm run typecheck` | 0 | clean |
| 6 | `npm test` (wtr, Chromium) | 0 | **6 files, 52 passed, 0 failed** |
| 7 | `npm run test:contrast` | 0 | 58 pairs pass (light and dark) |
| 8 | `npm run build` | 0 | built. No `.map` files and no `sourceMappingURL` in `dist/assets` (IR-A21). |
| 9 | `npm audit` | 0 | 0 vulnerabilities (info 0 / low 0 / moderate 0 / high 0 / critical 0; 476 deps: 15 prod, 462 dev) |
| 10 | `npm audit --omit=dev` | 0 | 0 vulnerabilities |
| 11 | `npm config get registry` | 0 | `https://registry.npmjs.org/`, from `app/.npmrc` (also sets `engine-strict=true`) |
| 12 | Lockfile `resolved` hosts | — | **476/476 `https://registry.npmjs.org`**, all with `integrity`. At 9236aa3 the lockfile had 460/460 on `https://npm.devsnc.com` (internal feed). Fixed. |

Node constraint: `.nvmrc` = `22.23.3`; `package.json engines.node` = `^22.13.0` with `engine-strict`. Node 22 is a supported LTS line (Maintenance LTS, EOL 2027-04-30). It satisfies Vite 7 (≥20.19/22.12) and removes the old Node-18 blocker. **Caveat:** `^22` combined with engine-strict refuses Node 24, the current Active LTS. Plan the move before April 2027 (RR-FE-8, advisory). CI uses `node-version-file: app/.nvmrc` and runs `npm audit --omit=dev` and `npm audit --audit-level=high` (ci.yml:78-83).

#### F.2 Browser E2E

`run-all.sh` resets a throwaway SQLite database and bootstraps a Founder. It then starts Flask on :5000, Vite on :5173, the site with intake on (:8000) and the site with the flag off (:8001), and runs four scripts.

| Script | Result | Covers |
|---|---|---|
| workspace.e2e.mjs | **7/7** | invitation with forced MFA enrollment (path B), recovery codes, dashboard, website lead appears in the list, lead detail and status change, audit, sign-out then sign-in with TOTP, 360 px lead list |
| access.e2e.mjs | **16/16** | Sales invitation; denial checks (no admin nav; API 403 with a real Sales bearer, 401 without); IR-19 title/focus; admin revoke (reload and in-app); logout proven by refused refresh (401); intake idempotency, duplicate and invalid cases; **IR-15 TD-F step 4**; **break-glass cancel link from the captured email → CANCELLED**; **IR-36 sign out everywhere** |
| site.e2e.mjs | **14/14** | error summary; honeypot; server 422 → Turnstile reset → 201 (stubbed Turnstile); form hidden after success and fallback (IR-17); UNKNOWN_POLICY_VERSION fallback; network-error WhatsApp; flag off (0 API calls, consent/privacy link hidden); 360 px; CSP (**index.html only**) |
| axe.e2e.mjs | **10/10** screens, 0 serious/critical | login, MFA, dashboard, leads, users, roles, audit, lead detail, website idle and error. 18 site nodes outside the form are tracked (OI-11). The site scan runs with `bypassCSP: true`. |

Total **47/47**, matching the author's `evidence/remediation/e2e.txt`.

Items not covered by the author's E2E, and my probes for them (`probe-app-rr.mjs`, `probe-app-rr2.mjs`, against the **production build under `app/public/_headers` CSP**, served by `csp-server.mjs` on :5174):
- Route titles and focus on every nav route plus browser Back: all eight routes (Leads, Follow-ups, Users, Roles, Permissions, Approvals, Audit log, Dashboard) set `"<Page> · Veda Workspace"` and focus the page `<h1>`. Back re-titles and refocuses. The first load keeps focus on `body`, as designed. **REPRODUCED.**
- Side effect: after "Sign in", `/mfa` focuses the `h1` "Two-step verification" rather than the code input. Keyboard users need one extra Tab (RR-FE-7, advisory).
- MFA timeout (AX-07), tested with a fake clock: at t+3:50 there is no warning; at **t+4:10 "expires in 1 minute" appears in a polite status region**; at t+5:10 the page shows "expired", the Verify button is gone and a "Sign in again" link appears. **REPRODUCED.** The step-up dialog has no pre-expiry warning (`step-up-dialog.ts:71` only reacts after `MFA_CHALLENGE_INVALID`).
- `/approvals/cancel`: the page exists, has its own title, scrubs the fragment and makes **no cancel call on load** (only the session `auth/refresh`). An explicit click sends `POST /api/v1/approvals/cancel-link`. A bogus token shows "Link not valid … expired or was already used"; no token shows "This link is invalid." and no button. The happy path is covered by the author's E2E (202 → CANCELLED). **REPRODUCED.**
- Account menu: opening leaves focus on the button (disclosure pattern); Tab reaches the first link; Escape closes and returns focus to the button. **An outside click leaves the menu open.**
- Stepper at 360 px: `role=region tabindex=0 aria-label="Pipeline status"`, scrollWidth 799 > clientWidth 328, so it is keyboard-scrollable. The toaster has persistent `status/polite` and `alert/assertive` regions created at start-up.
- App CSP (IR-A21): dashboard bar width 246 px rendered through the CSSOM `.style` binding. **0 violations** from the app itself. The single recorded `script-src-elem inline` came from the probe's own axe `addScriptTag`, which the CSP correctly blocked.
- Re-consent UI (DEV-004): no SPA control, consistent with the corrected deviation text. The timeline renders the system activity's subject and note but **not** the `consent_evidence` fields the register says are "visible in the lead timeline" (`lead-detail-page.ts:309-326`; RR-FE-6).
- Not covered by anyone: Firefox/WebKit legs, 200 % zoom, manual NVDA/VoiceOver (author-declared production gates), the forgot/reset and email-change journeys, and Founder governance approve/deny in the browser (API tests only).

#### F.3 Hostname-dependent fixtures

`git diff --name-only 9236aa3 HEAD` plus `git log --all --diff-filter=A` list only these JS/MJS files: `app/e2e/{access,axe,site,workspace}.e2e.mjs`, `app/e2e/static-server.mjs`, `app/eslint.config.js`, `app/scripts/*.mjs`, `app/web-test-runner.config.mjs` and `dist/assets/app.js`. **No committed file has a hostname in its name**, and there are no JS fixtures under `app/test/` or `docs/implementation/evidence/`. The hostname coupling is inside content:

| File | Coupling | Assessment |
|---|---|---|
| `app/e2e/static-server.mjs:43-51` | String-replaces `https://api.vedaspaces.com` in the CSP and the exact `<meta name="veda-api-base" content="">` / `veda-turnstile-sitekey` tags with the local API and Cloudflare's **public** Turnstile test key `1x00000000000000000000AA` | Intentional and documented in the header comment. It fails loudly: if `_headers` or the meta formatting changes, intake stays off or the CSP blocks the API, and site checks 3–5 fail. Cleaner options: read the origin with a regex from `connect-src`, or inject values through a test-only query/config instead of string patches. The server listens on all interfaces (`listen(port)`); for CI and dev prefer `127.0.0.1` (RR-FE-5). |
| `access.e2e.mjs:52` `mailLink` | Regex hard-codes `http://localhost:5173` in captured email links | Deterministic. It must match `VEDA_APP_ORIGIN`'s default, and does. |
| `*.e2e.mjs` | `founder@vedaspaces.test` and `priya.sales@vedaspaces.test` (reserved `.test` TLD); fixed passwords; `Origin: http://localhost:8000` | No personal or secret data. The only real contact data is the business phone and email already public on the site. |
| `workspace.e2e.mjs:73` | Writes `e2e-artifacts/founder.json` (email, password, **TOTP secret**) for the next script | Throwaway local database, and the directory is gitignored. **But CI uploads `app/e2e-artifacts` as a build artifact when the job fails** (ci.yml:127-129), so anyone with repo read access sees a TOTP secret. It is valueless outside the ephemeral runner. Hygiene advisory: exclude `founder.json` from the upload. |

Determinism: TOTP helpers wait for a fresh 30 s step (no reuse), and Turnstile is stubbed by route interception. The only external fetch is Google Fonts, which is optional.

What a person with only the public history would need to execute them: Node 22.23.x; `npm ci` against the public registry (now possible); `npx playwright install chromium`; Python 3.13 with the hash-locked `api/requirements*.txt`; free ports 5000, 5173, 8000 and 8001 (on macOS the AirPlay receiver on :5000 answers 403, which the `curl -f` port check does not detect); and no secrets. They cannot be executed without the API venv: `run-all.sh` depends on `API_PYTHON` and `tools/e2e_reset.sh`. This is documented at `run-all.sh:3-4`.

#### F.4 Public form stays disabled

- `dist/index.html:11-12`: `<meta name="veda-api-base" content="">` and `<meta name="veda-turnstile-sitekey" content="">` are both empty. Policy meta `2026-09-v1`.
- `dist/assets/app.js:58`: `apiBase = meta(api) && meta(sitekey) ? meta(api) : ''`. Both are required; with only the API base set, a console warning is logged and intake stays off (`:59`).
- With `apiBase` empty: no Turnstile script is added (`:152`), and `[data-intake-only]` blocks stay `hidden`. Submit does `preventDefault` → `window.open(wa.me…)` → `return` (`:166-169`). `fetch` is never reached.
- **Browser proof** (`probe-site-csp.mjs`, head `dist/` under its exact `_headers`, `logs/probe-site-csp.txt`):
  - consent `hidden=true`, not visible
  - Turnstile container not visible
  - no turnstile script
  - `/privacy` link present in the DOM but inside the hidden consent label: 0 visible links
  - form-note shows the original WhatsApp text
  - filled submit: **0 requests from the page (0 `/api/` calls)**; popup `https://api.whatsapp.com/send/?phone=919515125153&text=…Name: Asha Test…` (wa.me redirect)
  - 0 CSP events after submit
  - portfolio modal works
  - author E2E check "flag off keeps the WhatsApp hand-off" (apiCalls 0) also passes
- Difference from 778aa8f (baseline run side by side):
  - The WhatsApp text now includes a `Budget:` line, and property/service values are the new option labels. Intended.
  - **Regression (RR-FE-2):** the form now has `novalidate`, and property/service are no longer `required`. At head, an **empty** submit opens WhatsApp with `Name: \nPhone: …`. At 778aa8f, native validation blocked it ("no popup").
  - Otherwise identical: fonts, layout, 360 px no overflow, no CSP on the baseline.
- Required before enabling intake:
  1. Privacy Notice v2026-09-v1 published at `/privacy`, matching `veda-policy-version` (PG-PRIV, OI-5)
  2. Production Turnstile site key in the meta and the secret on the API
  3. `veda-api-base` set to the real API origin, with **that same origin in site CSP `connect-src`** (currently `https://api.vedaspaces.com` only). Turnstile needs `script-src` and `frame-src` `challenges.cloudflare.com`, which are present and verified with the test key.
  4. API CORS: `VEDA_PUBLIC_SITE_ORIGINS` set to exactly the site origins
  5. Rate limits and trusted-proxy CIDRs (IR-35) configured on the real host
  6. A staging run of site.e2e with the **real** Turnstile test keys (422→reset→201) and the RR-FE-1 fix deployed
  7. A decision on RR-FE-2 validation parity
  8. Privacy-owner gate sign-off and production approval

#### F.5 Site CSP

Method: `site-server.mjs` serves `dist/` with `_headers` applied verbatim (Cloudflare Pages matching; unknown paths get `404.html` with status 404). The only change is removing `upgrade-insecure-requests`, which would rewrite http://127.0.0.1. Head ran on :8100 and 778aa8f (no CSP) on :8101. Chromium 153, with `securitypolicyviolation` listener plus console capture.

| Page | Head (CSP) | 778aa8f |
|---|---|---|
| `/` (1280 and 360) | **0 violations**; fonts Cormorant/Manrope loaded; images ok; no overflow | same, 0 |
| `/` with simulated Cloudflare injections (Web Analytics beacon, email-decode script) | beacon script and `POST cloudflareinsights.com/cdn-cgi/rum` **allowed**; email-decode is `'self'` (my stub 404s → MIME error, not CSP) | same |
| `/404.html` (200) | **`style-src-elem` blocked inline `<style>` at 404.html:15.** Page renders **unstyled**: body bg transparent, font Times, h1 32 px, main `block` instead of `grid`, no web fonts applied (screenshot `out/site-head-404.png`) | styled: bg #fbf7ef, Manrope, h1 89.6 px, grid |
| `/no-such-page` (404) | same breakage | styled |
| `/privacy` (404) | same breakage | styled |
| `/` + form flag off, modal, submit | 0 violations | — |
| Flag on (scratch copy: metas filled, `connect-src` → local API) | real `challenges.cloudflare.com/turnstile/v0/api.js` plus challenge-platform and blob fetches, token issued, **0 violations** | n/a |

Also checked with no issues: no inline `<script>`, no `style=` attributes, no JSON-LD, no iframes or maps in `index.html`/`404.html`; `.avif`/`.jpg`/`.png` are `'self'`; tel:, mailto:, wa.me and Instagram are plain links (not CSP-governed); `form-action 'self'` is fine because the form never navigates; `frame-ancestors 'none'` and `X-Frame-Options: DENY` are consistent.
