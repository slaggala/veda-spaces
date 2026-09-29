# Veda Spaces P0 — Independent Implementation Review

**Review ID:** VEDA-SPACES-P0-INDEPENDENT-IMPLEMENTATION-REVIEW-01
**Date:** 2026-09-29
**Final verdict:** **NOT CERTIFIED** (1 BLOCKER, 18 MAJOR)

> This review covers the technical artifacts only. It does not modify implementation or architecture, fixes nothing, and authorizes no merge or deployment. The implementation remains unauthorized for merge or deployment until the owner explicitly authorizes the next step.

| Item | Value |
|---|---|
| Repository | `git@github.com:slaggala/veda-spaces.git` |
| Certified architecture SHA | `778aa8fdd918da48340319696ada3ff673e9fb8e` |
| Implementation branch | `implementation/p0-foundation` |
| Implementation SHA reviewed | `9236aa3ade38c33d03a57cf7a064ece29937b109` |
| Review branch | `review/p0-independent-implementation-review` (contains only `docs/reviews/p0-independent-implementation-review.{md,json}`) |
| Machine-readable twin | [p0-independent-implementation-review.json](p0-independent-implementation-review.json) |

## Contents

1. [Method and independence](#1-method-and-independence)
2. [Scope and diff verification](#2-scope-and-diff-verification-phase-1)
3. [Claims ledger](#3-claims-ledger)
4. [Architecture conformity summary](#4-architecture-conformity-summary-phase-2)
5. [Deviation decisions](#5-deviation-decisions-phase-3)
6. [Break-glass cancel endpoint](#6-break-glass-cancel-endpoint-phase-4)
7. [Database and migrations](#7-database-and-migrations-phase-5)
8. [Authentication, MFA and Founder governance](#8-authentication-mfa-and-founder-governance-phases-6-7)
9. [Authorization and RBAC](#9-authorization-and-rbac-phase-8)
10. [Lead workflow](#10-lead-workflow-phase-9)
11. [Audit, security events and notifications](#11-audit-security-events-and-notifications-phases-10-11)
12. [Frontend and browser](#12-frontend-and-browser-phase-12)
13. [Static analysis and dependencies](#13-static-analysis-and-dependencies-phase-13)
14. [Test reproduction and quality](#14-test-reproduction-and-quality-phase-14)
15. [Open issues OI-1 to OI-11](#15-open-issues-oi-1-to-oi-11-phase-15)
16. [Production readiness](#16-production-readiness-phase-16)
17. [Findings](#17-findings-phase-17)
18. [Blockers by stage](#18-blockers-by-stage)
19. [Architecture amendments required](#19-architecture-amendments-required)
20. [Final report A–AA](#20-final-report-aaa)
- [Appendices](#appendices)

---

## 1. Method and independence

- **Isolated checkout.** The review ran against a detached git worktree of `9236aa3`. `git status` was clean before and after every probe.
- **Probes ran on copies.** Every probe test ran against a copy of `api/` or `app/` in a scratch area. No tracked file of the implementation was modified.
- **Six review streams.** The lead reviewer covered scope, test reproduction and static analysis, then consolidated the results. Five independent domain reviewers covered:
  - authentication and MFA;
  - RBAC and Founder governance;
  - leads, audit and notifications;
  - database, migrations and operations;
  - frontend and browser.
- **Nothing trusted by default.** No conclusion was taken from comments, trace annotations, the implementation report or the deviation register.
- **Headline findings re-checked.** The lead reviewer re-verified every BLOCKER finding and every MAJOR finding that drives a decision directly against the source: IR-01, IR-02, IR-04, IR-09, IR-10, IR-15 and IR-17.
- **Evidence labels.** Each finding is marked **REPRODUCED** (executed, with output) or **SOURCE-INSPECTED** (read only).
- **Environment:**
  - macOS arm64, Python 3.13.7 in a fresh venv from `api/requirements-dev.txt`, SQLite 3.50.4.
  - Embedded PostgreSQL **18.4** (`pixeltable-pgserver` 0.6.0), matching the author.
  - Standalone PostgreSQL **16.4** (the binary bundled in `pixeltable-pgserver` 0.2.9), which is the architecture's target major version.
  - Node 20.9.0 and npm 10.1.0.
  - Playwright Chromium.
- **What was not done.** No production gates were executed. No AWS, Cloudflare, DNS or production system was contacted or modified. No credentials were used or exposed.

## 2. Scope and diff verification (Phase 1)

| Check | Result | Evidence |
|---|---|---|
| Commit exists on `origin/implementation/p0-foundation` | **Yes** | `git branch -a --contains 9236aa3` → local and `remotes/origin/implementation/p0-foundation`; `git rev-parse origin/implementation/p0-foundation` = `9236aa3…` |
| Certified SHA is the merge base | **Yes** | `git merge-base 778aa8f 9236aa3` = `778aa8fdd918…`; `git cat-file -p 9236aa3` parent = `778aa8f…` |
| No later implementation commits | **Yes** | `git log 778aa8f..origin/implementation/p0-foundation` = exactly one commit (`9236aa3 Implement Veda Spaces P0 platform`) |
| Working tree clean | **Yes** | `git status --short` empty |
| Architecture documents unchanged | **Yes** | `git diff --quiet 778aa8f 9236aa3 -- docs/architecture` exit 0 |
| Review artifacts not in the implementation branch | **Yes** | no `docs/reviews/` paths in the diff |
| Diff size | 255 files (250 added, 5 modified, 0 removed), +35 839 / −23 | `git diff --stat` |
| Modified files | `.gitignore`, `README.md`, `dist/index.html`, `dist/assets/app.js`, `dist/assets/enhancements.css` | `git diff --name-status` |
| Generated DB files, `node_modules`, venvs, caches, screenshots, reports | **None** | pattern scan of changed paths for `.db/.sqlite/.pem/.key/.env/.eml/.p12`, `node_modules`, `.venv`, `__pycache__`, `playwright-report`, `test-results`, `.png` |
| Binary files | 1: `app/public/img/warm-hero.jpg` (SPA login artwork) | `git diff --numstat` |
| Credentials / tokens / private keys / OTP secrets / recovery codes | **None real** | regex scan (AWS keys, private-key headers, GitHub/Slack/Stripe/Google tokens, Turnstile keys, `otpauth://`) plus `detect-secrets` over all 254 text files. All hits triaged: test-fixture passwords (`tests/support/factory.py:22`, `app/e2e/*.mjs`), error-title strings (`kernel/errors.py`), encoding alphabets (`leads/service.py:29`, `auth/crypto.py:26`), fixed test UUIDs, and the ephemeral CI Postgres service credential (`ci.yml:17,31`). `otpauth://` hits are code that builds URIs, not secrets |
| Production customer data | **None** | only synthetic fixtures |
| Unsafe example credentials | None usable against a real system; e2e passwords are local-stack fixtures | — |
| `dist/` changes limited to the public enquiry form | **Yes** | `dist/index.html`: 3 meta tags (`veda-api-base` empty = feature off) plus the contact form and success/fallback panels. `dist/assets/app.js`: only the contact-form submit handler replaced. `dist/assets/enhancements.css`: form-state styles appended. `dist/_headers` unchanged. With `veda-api-base` empty the original WhatsApp hand-off is preserved (reproduced by the frontend reviewer) |
| Unapproved architecture changes | **None in documents.** Behavioural departures are covered in §5 and §6 | — |

## 3. Claims ledger

| # | Author claim | Independent result | Status |
|---|---|---|---|
| 1 | 24 database tables | 24 on SQLite and PG16.4 (plus `alembic_version`) | **Confirmed** |
| 2 | 9 Alembic revisions | 9, linear | **Confirmed** |
| 3 | Exactly one Alembic head | `0100_crm_leads (head)` only, on both engines | **Confirmed** |
| 4 | 105 API routes | 105 declared routes. `url_map` has 107 rules: 105 plus Flask `static` plus non-production `openapi.json`. HEAD and OPTIONS are auto-methods | **Confirmed** |
| 5 | Every API protected by a permission or registered exception | Startup check fails closed on a missing declaration, but only checks that a declaration is *present* (IR-A05). The route gates held under about 120 bypass attempts. **However, IR-01 bypasses MFA/step-up gating at the service layer** | **Confirmed with qualification** |
| 6 | SQLite 273 passed | 273 passed, 0 failed, 0 skipped (18.3 s) | **Confirmed** |
| 7 | PostgreSQL 271 passed, 2 skipped | PG 18.4: 271 passed, 2 skipped. **PG 16.4: 271 passed, 2 skipped** (new evidence) | **Confirmed and extended** |
| 8 | Frontend 47 tests passed | 47 passed | **Confirmed** |
| 9 | 7 admin browser journeys passed | 7/7 (workspace), 12/12 (access). Two access checks prove less than claimed (IR-38) | **Confirmed with qualification** |
| 10 | 7 public-website journeys passed | 7/7. The success check does not assert the form is hidden, which masks IR-17 | **Confirmed with qualification** |
| 11 | Zero dependency vulnerabilities | Runtime: pip-audit 0; `npm audit --omit=dev` 0 (Nexus and GHSA feeds). Dev tooling: 195 advisories on the configured Nexus feed (JSON: 19 critical; text line: 17), 7 on the GHSA feed. No lockfile for Python (IR-13) | **Confirmed for runtime only** |
| 12 | Clean secret scan | No real secrets (§2) | **Confirmed** |
| 13 | Architecture documents unchanged | Byte-identical | **Confirmed** |
| 14 | No production credentials committed | None found | **Confirmed** |
| 15 | Four implementation deviations recorded | Four recorded. A fifth departure (break-glass `cancel-link`) is disclosed as OI-2 but not registered. DEV-004 register text claims a UI control that does not exist | **Confirmed with correction** |
| 16 | Eleven open issues recorded | 11 recorded. 39 numbered findings and 25 advisories in this review, most not in the register | **Register incomplete** |
| 17 | Deployment not performed | No deployment artifacts executed; CI never ran | **Confirmed** |
| 18 | Bandit: 1 High, 2 Medium, 18 Low, all false positives | Counts reproduced. B608 and B310 are false positives. B701 is a false positive for HTML/XSS and header injection, but plain-text content spoofing remains (IR-29) | **Confirmed with residual** |
| 19 | ruff format: 82 files | 83 files under ruff 0.16.9 (unpinned) | **Minor discrepancy** |

## 4. Architecture conformity summary (Phase 2)

Full requirement-by-requirement tables are in Appendices B–F. Runtime behaviour, not annotations, was the basis for each classification.

| Domain | Conformant | Partially conformant | Non-conformant | Intentional documented deviation | Untested / N/A |
|---|---|---|---|---|---|
| Authentication (AUTH-*) | 001, 002, 004–009, 012, 014, 016–018 | 003 (small blocklist), 010 (IR-22, IR-23), 013 (IR-25), 015 (IR-01) | — | 011 (DEV-002) | — |
| MFA (MFA-*) | 001–005, 008–010, 013 | 006 (IR-25), 014 (IR-01, IR-20) | **011, 012 (IR-01)** | DEV-001 index | 007/015 RBAC-side conformant |
| Security (SEC-*) | 001–004 | 005 (IR-09), 011 | — | DEV-003 | 006 (deployment), 007 frontend not met (IR-14) |
| RBAC / users | RBAC-001–016, 018–020; USER-004 | RBAC-017, **RBAC-021** (IR-04–IR-08); USER-001, USER-007 | — | — | RBAC-007 N/A (P1); USER-002/003/005/006 untested |
| Leads / notes / activities | LEAD-001–011, 013–016, 020, 023–026, 028, 030; NOTE-002/004; ACT-002–004 | LEAD-012, 018, 019, 027, 029; NOTE-001; ACT-001 | — | LEAD-024 (DEV-004: **rejected**, see §5) | LEAD-017/021/022, NOTE-003, ACT-005 N/A (P1/P2) |
| Audit / security events | AUDIT-001–003, 005, 006, 008, 010, 012; SEVT-001, 003, 011 | AUDIT-004 (PG, IR-33), 011; SEVT-004, 006 | **SEVT-007 (IR-03)** | — | SEVT-002, 005, 008–010 untested |
| Notifications | NOTIF-001–003, 008 | NOTIF-004 (IR-30), 005 (IR-29), 009 (SES untested) | — | — | NOTIF-006/007 N/A |
| Data / platform | DATA-001–010, 012, 014–017; PLAT-004, 005, 007, 009, 010, 013 | DATA-011 (CI unexecuted), PLAT-008 (IR-09) | — | DATA-007 (DEV-001) | DATA-013 untested |
| Logging / operations | LOG-002; OPS-008, 011 | LOG-001, 004, 005; OPS-003, 004, 006, 007, 010 | **LOG-003 (IR-27), LOG-006 (IR-12), OPS-002, OPS-009 (IR-11)** | — | OPS-001 untested (CI), OPS-005 owner input |
| UI / accessibility | UI-001–004, 006–010, 012–015, 017 | UI-011, UI-016 (IR-19, IR-37) | — | — | **UI-005 deviates (IR-15)**. Website intake: not ready to enable (IR-17, IR-18, IR-32) |

**Schema conformance is exact.**
- 24 of 24 tables.
- 502 columns, with zero missing, extra, mistyped or wrong-nullability columns against 03/04.
- All 72 specified indexes present, with matching predicates.
- 107 FKs, all ON DELETE RESTRICT.
- The nine audit-contract columns on every table, in order.
- The only index difference is DEV-001.

## 5. Deviation decisions (Phase 3)

| ID | Decision | Conditions / reasoning |
|---|---|---|
| **DEV-001** MFA factor uniqueness | **ACCEPTABLE WITH ARCHITECTURE AMENDMENT** | See below |
| **DEV-002** Invitation acceptance returns MFA-enrollment step | **ACCEPTABLE WITH ARCHITECTURE AMENDMENT** | Conditional on IR-01, IR-21 and IR-25. See below |
| **DEV-003** Optional login CAPTCHA token | **ACCEPTABLE WITH ARCHITECTURE AMENDMENT** | Conditional on IR-22 (IPv6 grouping), IR-09 (staging fail-open) and IR-02 (lock contention). See below |
| **DEV-004** Staff lead re-consent | **REQUIRES IMPLEMENTATION CHANGE** (plus architecture reconciliation) | See below and IR-16 |

**DEV-001: MFA factor uniqueness.**
- **Why the amendment is needed.** The certified two-column key really does contradict 05 §11.5 and TD-E. A second `enroll/start` by an enrolled user would hit a unique violation.
- **What the implementation guarantees (verified on SQLite and PG):**
  - The index `(user_id, factor_type, status)` is the same in the model, the migration and on both engines.
  - A second ACTIVE factor is rejected (`IntegrityError`).
  - A PENDING factor never authenticates at login, step-up or recovery. `active_factor` filters on `status == 'ACTIVE'`.
  - The old factor keeps working while a replacement is pending.
  - Confirm revokes the old factor, flushes, then promotes the new one.
  - Concurrent confirms cannot create two ACTIVE factors.
- **Condition.** Coexistence is also what lets path C replace an ACTIVE factor without it (IR-20). IR-20 must be fixed with the amendment.
- **Residual gap.** No event is written when a PENDING factor is abandoned (advisory).

**DEV-002: Invitation acceptance with MFA required.**
- **What the implementation guarantees:**
  - `invite_context` is a 256-bit token, stored hashed, single use, and expires in 15 minutes.
  - An INVITED user with a password set cannot sign in; the response is a uniform 401.
  - No session exists before enrollment is confirmed.
  - The invite link cannot be replayed after activation; the response is a uniform 400.
  - Disabling or deleting the invitee kills open contexts.
  - An abandoned acceptance can be restarted until the invite link expires.
  - Errors reveal nothing about whether an account exists.
- **Problems in the flow that must be fixed:**
  - IR-01: cross-user confirm.
  - IR-21: a resent invitation leaves old contexts live.
  - IR-25: no security event when the invite sets a password.
- **Architecture note.** Path B's second proof, the new password, is chosen by whoever holds the link. The 08 §4.5 amendment should acknowledge this.

**DEV-003: Optional login CAPTCHA token.**
- **What the implementation guarantees:**
  - The token is verified server-side.
  - A provider error or the 5 s timeout blocks the login.
  - Production refuses the dev verifier.
  - The `captcha_required` signal is identical for known and unknown emails, because unknown emails use an HMAC key.
  - A valid CAPTCHA does not lift the escalating delay.
  - Nothing about the token is logged.
- **Why the amendment is needed.** The optional field is required to implement 05 §4 under the closed 08 §4.1 schema.
- **Weaknesses in the underlying control:**
  - IR-22: IPv6 grouping lets a /64 escape per-network throttling.
  - IR-09: staging and any mistyped `VEDA_ENV` get the accept-anything verifier.
  - IR-02: CAPTCHA verification runs while the write lock is held.

**DEV-004: Staff lead re-consent.**
- **What the implementation gets right:**
  - The request schema is closed.
  - The policy version is validated against published versions.
  - The public endpoint rejects a re-consent object.
  - Authorization is `lead.update` within the caller's scope, with If-Match.
- **Why it requires an implementation change:**
  - Staff can re-consent a lead whose consent was never withdrawn, silently replacing valid original web-form evidence.
  - The original web form's IP and page are kept, so a phone consent carries website provenance.
  - Staff may select `WEBSITE_FORM` as the channel.
  - No reason is required and no timeline activity is written.
  - Sales users cannot see the prior evidence, because `/history` returns 403 for them.
  - The deviation register describes a UI control that does not exist.
- **Architecture.** 04 §5.4 and 08 §8.5 still need reconciling. This is not a security blocker, because it requires an authenticated user with `lead.update` in scope.

## 6. Break-glass cancel endpoint (Phase 4)

**The brief's premise is incorrect, and the report's OI-2 describes the direction correctly.** The certified API index (08 §1) contains **no** break-glass cancel endpoint. Its only approvals-cancel row, #47 `POST /api/v1/approvals/{approval_id}/cancel` (requester only), **is implemented** (`api/veda/platform/rbac/routes.py:363-368`). Probes confirmed the behaviour: target → 404, non-requester → 403, requester → 200.

**What the architecture requires.** The capability is required, but no endpoint is named for it:
- 06 §7.5 step 5: "Any of them can cancel through the signed link".
- 02 §10 `break_glass.requested`: the notification carries a cancel link.
- 03 `user_action_token.purpose` includes `APPROVAL_CANCEL`.
- 12 TD-G G12: "Cancel link by a notified party → CANCELLED".
- 06 §11 RBX-003 does not list the endpoint.

**What is implemented.** `POST /api/v1/approvals/cancel-link` (RBX-003, public), `governance.cancel_by_link` and `_issue_cancel_links`.

**Security assessment.** The endpoint is safe:
- 256-bit HMAC-derived token, with only a hash stored.
- Single use, with every sibling link for the request invalidated.
- Bound to one request; expires with the request.
- Uniform 400 response, so no enumeration.
- No ambient authority; the token is in a JSON body and CORS blocks foreign origins.
- Disabled Founders lose their links.

**Defect.** The emailed link points to SPA path `/approvals/cancel`, **which does not exist** (`app/src/core/router/routes.ts:20-50`), and no SPA code calls the endpoint. The veto is therefore unusable end-to-end. Combined with IR-05 and IR-06, Founders have no practical veto once a custodian approves.

| Question | Answer |
|---|---|
| Genuinely required by the certified architecture? | The **capability** is required (06 §7.5, TD-G G12). The **endpoint** is not named in 08 or 06 §11 |
| Equivalent behaviour elsewhere? | Partially. Founders can `deny` a PENDING break-glass request in-app. Once it is APPROVED, only the requester or the unreachable link can stop it |
| Availability risk | None to recovery. Execution proceeds after `not_before` |
| Recovery risk | None |
| Security risk | The endpoint has none. Governance risk comes from the missing veto (IR-07, aggravated by IR-05 and IR-06) |
| Governance inconsistency | Yes: 06 §11 register and 08 index omit a public endpoint |
| Is adding or keeping it safe? | Yes, with the SPA page, an 08 index row and an RBX-003 entry |
| Classification | **Documentation mismatch** (endpoint) plus **implementation defect** (SPA page missing). **Architecture amendment required** |
| Fifth deviation decision | **REQUIRES IMPLEMENTATION CHANGE** (add the SPA page and an E2E test), together with the amendment of 08 §1, 06 §11 and 09. **Not a SECURITY BLOCKER.** Register it as DEV-005 |

## 7. Database and migrations (Phase 5)

| Check | SQLite 3.50.4 | PostgreSQL 16.4 | PostgreSQL 18.4 |
|---|---|---|---|
| Empty → head | `0100_crm_leads` (9 steps) | `0100_crm_leads` | via full test suite |
| `alembic current` | `0100_crm_leads (head)` | same | — |
| `alembic heads` | exactly one | exactly one | — |
| Tables / columns / indexes / FKs | 24 / 502 / 72 / 107 | 24 / 502 / 72 / 107 | — |
| CHECK constraints | 493 (incl. type CHECKs) | 161 | — |
| Immutability triggers | 4 | 4 plus `veda_immutable_guard()` | — |
| Seeds (roles, permissions, matrix, lookups, system users, sequences) | 3, 45, 101, 47, 3, 1 | same | — |
| Human users / password hashes | 0 / 0 | 0 / 0 | — |
| Determinism (two fresh DBs) | identical fingerprint | identical | — |
| `downgrade -1` | refused (`NotImplementedError`), DB unchanged | same | — |
| Revision atomicity (induced failure) | rolled back to `0008` | rolled back to `0008` | — |
| Full test suite | 273 passed | **271 passed / 2 skipped** | 271 passed / 2 skipped |

**Properties confirmed**
- **UUIDv7.** Generated from a CSPRNG and monotonic within a process; 200 000 ids were canonical and strictly increasing.
- **Id storage.** Ids are `CHAR(32)` on SQLite and native `uuid` on PG. PG accepts non-v7 UUIDs from raw SQL; this is documented.
- **Timestamps.** Timezone-aware and normalised to UTC. The SQLite text format sorts lexicographically but has no DB CHECK (IR-A18).
- **Actor attribution.** One transaction time per unit of work; SYSTEM, WEB_INTAKE and ANONYMOUS seeded; migration rows marked `performed_via=MIGRATION`.
- **Optimistic concurrency.** A concurrent stale write on PG16 is rejected with 409.
- **Soft delete.** Deleted rows are filtered by default, and their unique keys can be reused.
- **Secrets at rest.** Only token hashes are stored. Recovery codes are HMAC'd. TOTP secrets are AES-GCM under a KMS-wrapped key.
- **Immutable logs.** SQLite triggers reject UPDATE and DELETE.

**Defects:**
- IR-33: on PG the immutability guard is bypassable through a GUC or TRUNCATE.
- IR-34: historical migrations import live application code.

**Expand-only / downgrade refusal.** This is **conformant** with 02 §12.4 and documented, and the DDL is genuinely N-1-compatible. Only `0008` alters an existing table, adding nullable columns and one NOT NULL column with a constant default. **However, the rollback strategy is non-functional as built.** The readiness probe rejects the N-1 image (IR-10), and the snapshot path is not implemented (IR-11). The downgrade refusal is therefore not yet backed by an effective rollback.

**PostgreSQL 16 vs 18.4.**
- No PG15+ or PG18-only constructs were found. There is no `NULLS NOT DISTINCT`, `MERGE`, SQL/JSON constructor or `uuidv7()`.
- This review ran the **full suite on PostgreSQL 16.4: 271 passed, 2 skipped**, matching 18.4.
- A PG16 run before merge is therefore **satisfied locally** by this review.
- A green CI run on the `postgres:16` service remains a merge condition (IR-14), because DATA-011 and OPS-001 require the dual-engine gate to be automated.

## 8. Authentication, MFA and Founder governance (Phases 6–7)

**Verified correct:**
- **Passwords.** Argon2id with m=64 MiB, t=3, p=1, a production floor, rehash on login, and a dummy hash for unknown users. The policy is 12–128 characters with NFKC normalisation and a small blocklist; the breached-password check is P1.
- **Access tokens.** ES256 JWT with pinned algorithm, `typ`, `kid` allow-list, iss/aud and expiry against the platform clock. `none`, HS256 and tampering attempts all return 401.
- **Session check.** The session is re-checked on every request without caching.
- **Refresh tokens:**
  - 256-bit tokens, SHA-256 hashed, rotated on use.
  - 20 s grace window with no Set-Cookie.
  - Reuse revokes the session and emails the user.
  - Cookie is HttpOnly, SameSite=Strict, Path=/api/v1/auth; production enforces Secure.
  - CSRF header required.
- **Password reset.** Single-use tokens, 30-minute expiry, all sessions revoked.
- **Recovery sessions.** 15-minute RECOVERY session with an allow-list; challenge replay and code replay both rejected.
- **TOTP.** ±1 window, replay protection via `last_used_step`, 5 attempts per challenge and 10 per account.
- **Recovery codes.** 50-bit codes, HMAC'd, single use.
- **Founder rules.** Self-approval, target approval and duplicate approvers are all prevented. LAST_FOUNDER protection holds. Concurrent approvals serialise on both engines.
- **Bootstrap.** The bootstrap-founder CLI refuses when any Founder or a prior bootstrap event exists.
- **FOUNDER_WORKFLOW_ONLY.** This permission cannot be granted, copied, denied or edited through generic APIs.

**Bypass attempts that succeeded:**
- **IR-01 (BLOCKER):** MFA and step-up bypass through cross-user enrollment confirmation.
- **IR-04 (MAJOR):** Founder email change or MFA reset through a stale STANDARD request.
- **IR-05 and IR-06 (MAJOR):** break-glass in steady state, and a single operator acting as both custodians.
- **IR-09 (MAJOR):** JWT forgery in any environment other than `production`.

**Attempts that failed**, per the Appendix C bypass table:
- user, role and permission APIs;
- direct grants;
- role copying;
- invitation with the FOUNDER role;
- ADMIN MFA reset or email change of a Founder;
- stale tokens after demotion, DENY or disable;
- stale authorization caches.

**Not implemented.** The "enrollment from an unseen network" alert (OI-7).

## 9. Authorization and RBAC (Phase 8)

- **Route count.** 105 routes. The full inventory, with method, path, public/private designation, authentication, permission or RBX exception, sensitivity, MFA/step-up, scope, audit and security events, rate limit and requirement IDs, is in **Appendix C.1**.
- **Core rules hold at runtime:**
  - default deny;
  - DENY over GRANT;
  - direct, role and scoped permissions;
  - OWN scope returns 404 for other records;
  - MFA-gated sensitive permissions;
  - `authz_version` propagation to the next request;
  - per-request session invalidation;
  - closed DTOs (mass assignment and over-posting rejected with 422).
- **IDOR probes.** All were blocked: SALES accessing another user's leads, notes, activities, sessions and notifications; grant-id/user-id mismatch; approval visibility.
- **Weak points:**
  - The route-declaration check only verifies that a declaration exists (IR-A05).
  - `PATCH /roles` has no self-held-role check (IR-A06).
  - Approvals return 403 where GET returns 404, revealing that the approval exists (IR-A07).
  - The 08 §12 per-user limit is not implemented (IR-A08).

## 10. Lead workflow (Phase 9)

The full 21-step table is in **Appendix D.2**.

**Verified correct:**
- **No enquiry is silently lost.** Busy → 503 → WhatsApp fallback.
- **Retries are safe.** The idempotency key is persisted in the database, checked before CAPTCHA, fingerprinted, and survives restart.
- **Duplicates.** Flagged and stored, not dropped; the public response does not reveal them.
- **Honeypot.** Hits get an identical 201 response and are stored as SUSPECTED.
- **CAPTCHA.** Fails closed. The site's `'no-widget'` token passes only in dev mode.
- **Failure isolation.** A notification failure never removes the lead or the in-app notification.
- **Public response.** Exactly `{reference, message}`. The reference is 8 random Crockford characters (40 bits), so it is not sequential and does not reveal volume. There is no public read endpoint, so leads cannot be enumerated.
- **Staff access.** Sales scope is enforced. Status transitions match 04 §3. Follow-ups are cancelled and recomputed on WON/LOST.

**Defects:**
- IR-02: CAPTCHA verification holds the write lock.
- IR-16: DEV-004 re-consent.
- IR-27: raw PII in exception logs.
- IR-28: writes still accepted on an erased lead.
- IR-25: erasure-refusal event rolled back.
- IR-17, IR-18, IR-31, IR-32: site integration.

**WhatsApp fallback.** The link carries PII by design; it is pre-existing and user-initiated (IR-A23).

**Legal hold.** No data model yet; it is an environment variable (OI-4).

## 11. Audit, security events and notifications (Phases 10–11)

**Previously reported defects: all three fixed, each confirmed by a probe:**
1. **Wrong audit actor.** Public intake rows are WEB_INTAKE via PUBLIC_FORM, staff rows are the request user with request and session ids, worker rows are SYSTEM, and CAPTCHA-blocked events are ANONYMOUS.
2. **Archive chain break.** A SECURITY_LOG_ARCHIVED event is appended before the delete, and verification after archival returns `ok=True` on both engines. A *different* boundary defect exists (IR-26).
3. **Failed notification deleting the in-app notification.** In-app rows commit in their own transaction. With a failing provider the in-app rows survive, and retries do not duplicate them. Retries do re-send email (IR-30).

**Verified correct:**
- Audit rows are written in the same transaction as the business change; a forced failure leaves no audit row and no lead.
- Old and new values are correct.
- Secrets are redacted.
- The HMAC chain is correctly constructed, using JCS (RFC 8785).
- Concurrent writers cannot fork the chain (BEGIN IMMEDIATE on SQLite, advisory lock on PG, unique chain_seq).
- Deferred failure events survive rollback.
- The outbox row is written in the business transaction, with backoff and dead-lettering.
- HTML emails autoescape, and subject lines have line breaks collapsed.

**Defects:**
- IR-03: verification ignores the external anchor.
- IR-26: archival loses rows at the cutoff boundary.
- IR-33: the PG guard can be bypassed.
- IR-A14: dead-letter alerting is a log line only.

**Bandit B701** (`notifications/templates.py:17`), inspected in the source.
- `_text_env` (autoescape off) renders only the `subject` and `text` blocks.
- HTML is always rendered through the separate `_html_env` (autoescape on). No code path renders HTML with the unescaped environment.
- A `<script>` probe was escaped in the HTML part, and CRLF in the subject was collapsed.
- **Classification:** false positive for XSS and header injection. **Residual:** plain-text content spoofing (IR-29, MINOR).

**AWS adapters.** The SES adapter, the KMS provider and S3 anchoring are untested (`# pragma: no cover`), so they are production-gated (OI-6).

## 12. Frontend and browser (Phase 12)

- **Build and type checks.** TypeScript `strict: true` (without `noUncheckedIndexedAccess`), typecheck clean, build 39.48 KB gzip, 47 unit tests passed.
- **Token storage.** The access token is held only in memory; local and session storage are empty. The refresh cookie is HttpOnly. The `?next=` parameter cannot redirect off-site. There are no `unsafeHTML`, `innerHTML`, `eval` or `javascript:` sinks in `app/src`.
- **Permissions in the UI.** Navigation and routes are filtered by permission; this is cosmetic, and the server stays authoritative.
- **CSP.** The app CSP works on the production build, with one advisory violation (IR-A21).
- **Automated accessibility.** axe reports 0 violations in light and dark themes on 10 screens.
- **Sign-out fix confirmed.** Signing out from the account menu or the forced-password screen now lands on `/login`, after which refresh returns 401 and the cookie is cleared. **The third sign-out entry point ("Sign out everywhere") is not fixed** (IR-36).

**Defects:**
- IR-15: lost update on "Re-apply mine".
- IR-19: route-change title and focus.
- IR-17, IR-18: public form.
- IR-37: accessibility gaps.
- IR-38: E2E evidence gaps.

**The 19 pre-existing public-site contrast nodes.** The full table is in Appendix F.2. All 19 were confirmed at `778aa8f` with identical colours; none is a false positive.

| Classification | Nodes |
|---|---|
| Production blocker | 0 |
| Required before enabling the form | 1: `#form-note`, the only node inside `<form>`, 4.06:1 (IR-32) |
| Tracked non-blocker | 18. Marketing content outside the form. `.portfolio-head > p` at 2.40:1 is the highest priority |
| False positive | 0 |

## 13. Static analysis and dependencies (Phase 13)

| Check | Command | Result | Severity / stage |
|---|---|---|---|
| Python lint | `ruff check veda tests migrations tools` | All checks passed | — |
| Python format | `ruff format --check …` | 83 files would be reformatted (no formatter configured) | MINOR (IR-39): staging CI |
| Python typing | mypy | Not configured | MINOR (IR-39) |
| Python SAST | `bandit -q -r veda` | High 1 (B701), Medium 2 (B608, B310), Low 18. Triaged in §11 | ADVISORY (residual in IR-29) |
| Python deps | `pip-audit -r api/requirements.txt` | No known vulnerabilities (as resolved today). No lockfile | MAJOR (IR-13) |
| Secret scan | regex plus detect-secrets | Clean (§2) | — |
| Import boundaries / raw SQL / role literals | `tests/unit/test_lint.py` (8 tests) | Pass | — |
| Frontend typecheck | `npm run typecheck` | Clean | — |
| Frontend lint | ESLint / Prettier | **Absent**. Only `lint:tokens` exists | MINOR (IR-39) |
| Frontend unit tests | `npm test` | 47 passed | — |
| Frontend build | `npm run build` | Success, 39.48 KB gzip | — |
| Contrast tokens | `npm run test:contrast` | 58 pairs pass, light and dark | — |
| Frontend deps (runtime) | `npm audit --omit=dev` | 0 | — |
| Frontend deps (dev) | `npm audit` | Nexus: 195 (19 critical / 5 high / 171 low per JSON). GHSA: 7 (6 high, 1 moderate): esbuild dev-server cross-origin read via vite 5.4.21; extract-zip path traversal via @web/test-runner | MINOR (IR-39). **Not dismissed:** exposure is developer workstations running `npm run dev` and CI/supply chain. Stage: before staging CI |
| Node constraint | — | Fix requires Node ≥ 20.19 (Vite ≥ 6.4.3) | MINOR (IR-39) |
| Browser tests in CI | — | Absent; CI never executed | MAJOR (IR-14): merge |

## 14. Test reproduction and quality (Phase 14)

| Suite | Author | This review | Command |
|---|---|---|---|
| Backend, SQLite | 273 passed | **273 passed** (18.3 s) | `VEDA_TEST_ENGINES=sqlite python -m pytest -q -rs` |
| Backend, PostgreSQL 18.4 | 271 / 2 skipped | **271 / 2 skipped** (56.7 s) | `VEDA_TEST_ENGINES=postgresql …` (embedded) |
| Backend, PostgreSQL 16.4 | not run | **271 / 2 skipped** (52.6 s) | `VEDA_TEST_DATABASE_URL_PG=…:55432 VEDA_TEST_ENGINES=postgresql …` |
| Frontend unit | 47 | **47** | `npm test` |
| Typecheck / build / contrast | pass | **pass** | `npm run typecheck && npm run build && npm run test:contrast` |
| Browser: workspace | 7/7 | **7/7** | `node e2e/workspace.e2e.mjs` |
| Browser: access | 12/12 | **12/12** (two checks overstated, IR-38) | `node e2e/access.e2e.mjs` |
| Browser: site | 7/7 | **7/7** (misses IR-17) | `node e2e/site.e2e.mjs` |
| Browser: axe | workspace 0; site 19 pre-existing | **same** | `node e2e/axe.e2e.mjs` |

**Skipped tests.** The same 2 are skipped on both PG versions: `test_schema.py:80` (SQLite pragma) and `test_schema.py:305` (SQLite-only format CHECKs). Both skips are legitimate.

**Coverage** (SQLite, branch):
- 85% total.
- Lowest security-relevant modules: `rbac/governance.py` 73%, `kernel/ratelimit.py` 57%, `identity/service.py` 74%, `rbac/roles.py` 74%.
- 12 `pragma: no cover` exclusions, covering the AWS adapters, Turnstile network calls and process loops.

**Quality assessment.**
- **Strengths.** Tests are isolated: each test gets a fresh migrated DB cloned from a template. They are deterministic, and fixtures are safe. There are concurrency tests (TD-F two-writer, G10 concurrent Founder, sequence allocation), a migration upgrade-with-data test on both engines, and negative fixtures for the schema conformance checks (TD-H).
- **Blind spots.** No test covers the defect classes found here:
  - IR-01: cross-principal enroll/confirm;
  - IR-04: a STANDARD request against a newly promoted Founder;
  - IR-08: Founder DELETE;
  - IR-05: break-glass operating mode;
  - IR-28: writes on an erased lead;
  - IR-26: the archival boundary;
  - IR-15: UI re-apply.
- **Tests that pass without proving the point.** Several tests assert the implementation's chosen behaviour rather than the architecture's intent. For example, the DEV-004 tests assert the overwrite behaviour, and the site E2E does not assert that the form is hidden. The IR-38 access checks (no bearer token sent, hard-coded result) also pass trivially.
- **Test tooling.** A fixed `veda_template` DB name prevents concurrent runs on a shared server (advisory).

**PostgreSQL 16 compatibility.** Established by this review's full-suite run. It still needs to be automated in CI (IR-14).

## 15. Open issues OI-1 to OI-11 (Phase 15)

| OI | Title | Actual evidence | Severity | Affected requirements | Module | Merge impact | Deployment impact | Required remediation | Required tests | Re-review |
|---|---|---|---|---|---|---|---|---|---|---|
| OI-1 | Deviations DEV-001…DEV-004 need an architecture decision | §5 of this review; register entries all PENDING | MAJOR | AUTH-011, MFA-005/013/014, AUTH-010, SEC-011, LEAD-012/024/027 | Platform auth; CRM leads | Blocks merge until decisions recorded and DEV-004 fixed/removed | n/a | Record AM-1..AM-4; fix DEV-004 (IR-16); register DEV-005 | Tests named in the register plus IR-16 validation | Yes (DEV-004) |
| OI-2 | Break-glass cancel-link not in 08 index | IR-07; 08 §1 has no such row; SPA page missing | MAJOR | RBAC-021, 06 §7.5 | Platform RBAC / SPA | Does not block merge by itself once registered as DEV-005 | Blocks production (PG-BG) | SPA /approvals/cancel page; AM-5 | Browser E2E via emailed link | Yes |
| OI-3 | HMAC-derived single-use action tokens | auth/crypto.py:37-39, service.py:170-194; used/expired rows rejected | ADVISORY | AUTH-008, AUTH-011, USER-007 | Platform auth | None | None | Document trade-off (AM-8) | Existing token tests | No |
| OI-4 | No legal-hold data model; erasure blocking via env var | VEDA_ERASURE_BLOCKED_STATUSES empty | MINOR | LEAD-029, AUDIT-011 | CRM leads | None | Production only if counsel requires legal hold at launch | Owner/legal decision; model if required | Erasure-blocked tests | If implemented |
| OI-5 | Privacy Notice missing; Turnstile site key and site CSP not configured | IR-32; dist/index.html:179; dist/_headers has no CSP at all (broader than stated) | MINOR (feature-gated) | LEAD-001, SEC-003, SEC-009 | Public site | None (flag off) | Blocks intake enablement | Publish notice; site key; full site CSP | site E2E with real Turnstile test key | Yes (intake enablement) |
| OI-6 | AWS adapters (SES, KMS, S3 Object Lock anchor) untested | `# pragma: no cover` on SesEmailProvider, AwsKmsProvider, anchor upload; archival anchors local only (IR-03) | MAJOR (production) | NOTIF-009, MFA-010, SEVT-007 | Platform notifications / auth / audit | None | Blocks production; staging verification required | Staging adapter verification; IR-03 fix | Stubbed-client unit tests + staging evidence | Yes (ops) |
| OI-7 | Alerts are log lines; unseen-network enrollment alert missing | IR-12; maintenance.py/worker.py log.critical/error | MAJOR (production) | LOG-006, SEVT-009, 05 §11.3 | Platform | None | Blocks production | Metrics + alert routing + test-fire; implement missing alert | RG-5 | Yes (ops) |
| OI-8 | No formatter/type checker; no ESLint | IR-39; 83 files unformatted | MINOR | 12 §5 | Tooling | None | Before staging CI | Adopt ruff format, mypy (or waiver), ESLint | CI jobs | No |
| OI-9 | Browser E2E not in CI; CI never executed | IR-14; ci.yml; 12 §5 gates missing | MAJOR | OPS-001, DATA-011, SEC-007 | CI | **Blocks merge** | — | Green CI incl. postgres:16; add missing gates | CI run evidence | Yes (evidence) |
| OI-10 | Dev toolchain advisories; upgrade needs Node ≥ 20.19 | IR-39; Nexus 195 (19 critical JSON), GHSA 7 (6 high) | MINOR | SEC-007 | Frontend tooling | None | Before staging CI (supply-chain exposure) | Node ≥ 20.19, Vite ≥ 6.4.3, WTR 1.x | npm audit in CI | No |
| OI-11 | Pre-existing public-site contrast (19 nodes) | Appendix F.2; 18 outside form, #form-note inside | ADVISORY (18) / MINOR (#form-note) | UI-011, AX-05, AX-08 | Public site | None | #form-note before intake enablement | Token fixes | axe on site | No |

**Additional issues not in the register.** Every finding in §17 not mapped above is newly discovered. That includes the BLOCKER IR-01 and the MAJOR findings IR-02 through IR-06, IR-08 through IR-10, IR-13 and IR-15 through IR-19. IR-07, IR-11, IR-12 and IR-14 extend open issues already in the register (OI-2, OI-6, OI-7, OI-9).

## 16. Production readiness (Phase 16)

Production gates were **not executed** by this review. The full gate table is in Appendix E.3.

| Area | State | Gate |
|---|---|---|
| Config separation / prod validation | Fail-open outside `production`; incomplete inside (IR-09) | **Blocks staging** |
| Secrets management | Env vars; SSM wiring absent (report §14) | Blocks production |
| Debug mode | No `debug=True` or `app.run`. OpenAPI is served whenever the env is not `production` | OK (see IR-09) |
| CORS | Exact allowlist; credentials only for the app origin | OK |
| Proxy handling / trusted IP | `CF-Connecting-IP` trusted unconditionally; no ProxyFix (IR-35) | Blocks production |
| Trusted hosts | Not validated | Post-production follow-up |
| Secure cookies / CSRF | HttpOnly, Secure (prod), SameSite=Strict, Path-scoped; CSRF header plus origin check | OK (IR-A03) |
| Health / readiness | Present; strict head equality breaks N-1 rollback (IR-10); publicly verbose (IR-A17) | Blocks production |
| Structured logs | structlog JSON with masking; stdlib and exception paths bypass it (IR-27) | Blocks production |
| Metrics / alerts | None / log lines (IR-12) | Blocks production |
| Backups / recovery / restore testing | Litestream config, snapshot job and restore verification absent (IR-11) | Blocks production |
| Database path persistence | Dockerfile absolute path; settings default relative and unvalidated (IR-09) | Blocks production |
| Encryption at rest | Delegated to EBS/KMS; not in repo | Blocks production |
| Single-writer SQLite | 1 gthread worker; `deploy-check` is a text match (IR-35) | Blocks production |
| PostgreSQL deployment | Target only; guard bypass (IR-33); concurrency advisories (IR-A01) | PostgreSQL release gate |
| SES / S3 archive / KMS | Untested adapters (OI-6) | Blocks staging verification / production |
| CSP | App: strict and working. Site: absent (IR-32) | Blocks intake enablement |
| Privacy notice | `/privacy` missing (IR-32) | Blocks intake enablement |
| Retention | Values unset → jobs refuse (safe default; OWNER-INPUT-002) | Blocks production |
| Erasure | Implemented; post-erasure writes allowed (IR-28) | Blocks production |
| Legal hold | No model; env-var status list (OI-4) | Post-production follow-up (production if required by counsel) |
| Incident diagnostics | request_id throughout; unstructured exceptions (IR-27); no runbook | Blocks production |
| Deployment rollback | Normal path broken (IR-10); disaster path absent (IR-11) | Blocks production |
| Runbooks | None for the API (IR-11) | Blocks production |
| Owner gates | TG-01 and TG-08 recorded as Pending in the frozen `gate-registry.md`. The report cites owner briefs as authorization | Record before merge |
| Unexecuted gates (report §16) | OWNER-INPUT-001..004, PG-DAST, RG-1..7, PostgreSQL release gate, browser/device matrix, staging, SES production access | Blocks production |

## 17. Findings (Phase 17)

Severity counts: **BLOCKER 1 · MAJOR 18 · MINOR 20 · ADVISORY 25**.

### 17.1 Summary

| ID | Severity | Domain | Title | Verification | Blocking scope |
|---|---|---|---|---|---|
| IR-01 | **BLOCKER** | Authentication / MFA | MFA enrollment confirmation is not bound to the caller: a bearer token plus any unbound enrollment challenge grants MFA verification and step-up to the token's session | REPRODUCED (SQLite and PostgreSQL) | merge |
| IR-02 | **MAJOR** | Leads / Authentication / Availability | Cloudflare Turnstile siteverify (up to 5 s network I/O) runs while the database-wide SQLite write lock is held (public intake and CAPTCHA-gated login) | REPRODUCED (public intake) | production; feature:public-intake enablement |
| IR-03 | **MAJOR** | Audit / Security events | Security-event chain verification never consults the external anchor and accepts deletion of the anchored prefix and tail truncation | REPRODUCED locally on SQLite and PostgreSQL | production (tamper-evidence claim) |
| IR-04 | **MAJOR** | Founder governance | A STANDARD dual-control request survives the target's promotion to Founder and then executes against the Founder (G11 time-of-check/time-of-use bypass) | REPRODUCED (SQLite and PostgreSQL) | merge (governance bypass) |
| IR-05 | **MAJOR** | Founder governance / break-glass | Custodians can initiate full break-glass while eligible Founders exist (no operating-mode check) | REPRODUCED (SQLite and PostgreSQL) | production (PG-BG); break-glass unusable until OWNER-INPUT-004 anyway |
| IR-06 | **MAJOR** | Founder governance / break-glass | Break-glass CLI trusts a caller-supplied --principal-arn (two-person control is self-asserted) | REPRODUCED | production (PG-BG) |
| IR-07 | **MAJOR** | Founder governance / break-glass (Phase 4) | Break-glass cancel link targets a non-existent SPA route; the 06 §7.5 notified-party veto is unusable end-to-end | SOURCE-INSPECTED | production (PG-BG) |
| IR-08 | **MAJOR** | Founder governance | FOUNDER_STATUS_CHANGE with DELETED always fails (I3 evaluation drops soft-deleted users but keeps their live FOUNDER role row) | REPRODUCED (SQLite and PostgreSQL) | merge (P0 functional acceptance of RBAC-021) |
| IR-09 | **MAJOR** | Configuration / Production readiness | Production-safety validation is fail-open: any VEDA_ENV other than exactly 'production' (including staging, unset, 'prod') runs with publicly derivable dev keys, local KMS, capture email and the accept-anything CAPTCHA verifier; production validation is also incomplete | REPRODUCED | staging; production |
| IR-10 | **MAJOR** | Operations / Migrations | Readiness gate requires DB revision == image head exactly, so the architecture's normal rollback (redeploy N-1 on the migrated schema) always reports not-ready | REPRODUCED | production (and RG-7 rehearsal) |
| IR-11 | **MAJOR** | Operations | Backup (Litestream config, nightly snapshot), restore verification and API deploy/migrate runbooks are absent from the deliverable | SOURCE-INSPECTED | production |
| IR-12 | **MAJOR** | Operations / Observability | No metrics, no alert routing, error tracker optional (LOG-006 is mandatory in P0) | SOURCE-INSPECTED | production |
| IR-13 | **MAJOR** | Supply chain / Build reproducibility | Runtime Python dependencies are open ranges with no lockfile or hashes; container base image floats | SOURCE-INSPECTED | merge (recommended) ; staging; production |
| IR-14 | **MAJOR** | CI / Quality gates | CI workflow has never executed and omits PR gates required by 12 §5 (types, N-1 test, OpenAPI diff, dependency/image/secret scan, E2E smoke + axe) | SOURCE-INSPECTED | merge |
| IR-15 | **MAJOR** | Frontend / Data integrity | Lead edit 'Re-apply mine' after a version conflict silently reverts the other writer's committed changes | REPRODUCED (browser probe + audit log) | production |
| IR-16 | **MAJOR** | Leads / Privacy (DEV-004) | DEV-004 staff re-consent overwrites consent evidence, mixes provenance and is accepted without prior withdrawal | REPRODUCED | feature:staff re-consent (remove the consent field from LeadPatchIn or fix before merge) |
| IR-17 | **MAJOR** | Public website intake | Enquiry form remains visible after success/fallback ([hidden] overridden by .contact-form{display:grid}); resubmission reports a false failure | REPRODUCED | feature:public-intake enablement (veda-api-base) |
| IR-18 | **MAJOR** | Public website intake | Turnstile token is never reset; after any server-side 422 the corrected resubmission reuses a spent token and fails CAPTCHA | SOURCE-INSPECTED (precondition REPRODUCED: server-side field 422 after client validation passes) | feature:public-intake enablement |
| IR-19 | **MAJOR** | Frontend / Accessibility | SPA route changes never update the document title nor move focus/announce navigation (WCAG 2.4.2 Level A) | REPRODUCED | production |
| IR-20 | **MINOR** | Authentication / MFA | Path C (emailed enrollment link + password) replaces an existing ACTIVE factor without step-up by that factor; open enrollment links survive enrollment by another path | REPRODUCED | production |
| IR-21 | **MINOR** | Authentication / Invitation (DEV-002) | Resending an invitation does not revoke earlier invite_context challenges; link replay mints parallel contexts and overwrites the password | REPRODUCED | production |
| IR-22 | **MINOR** | Authentication / Throttling | IPv6 /64 network grouping is string-based and breaks on compressed addresses, defeating per-network throttle and CAPTCHA and causing false global lockouts | REPRODUCED | production |
| IR-23 | **MINOR** | Authentication / Rate limits | Certified 5/min per-email login limit lets anyone lock a known account out from every network | REPRODUCED | production |
| IR-24 | **MINOR** | Authentication | Password re-entry (reauth) and change-password are not throttled; password guessing with a stolen bearer then satisfies password-based step-up | SOURCE-INSPECTED | production |
| IR-25 | **MINOR** | Security events | Security-event gaps: no event on MFA-path invite password set, invalid action tokens, CSRF-rejected refresh, MFA throttle and per-network throttle activation; erasure refusal event rolled back | SOURCE-INSPECTED | production |
| IR-26 | **MINOR** | Audit / Security events | Security-log archival deletes events it never exported when event time and chain order disagree near the cutoff | REPRODUCED | production (before archival is enabled; currently refuses without OWNER-INPUT-002) |
| IR-27 | **MINOR** | Logging / Privacy | Unhandled exceptions and DB errors log raw PII (stdlib loggers bypass structlog masking; engine lacks hide_parameters) | REPRODUCED | production |
| IR-28 | **MINOR** | Leads / Erasure | An erased (anonymised) lead still accepts notes, activities and status changes, re-introducing PII after erasure is reported complete | REPRODUCED | production |
| IR-29 | **MINOR** | Notifications | Plain-text staff notification emails can be content-spoofed via newlines in public form fields | REPRODUCED | production |
| IR-30 | **MINOR** | Notifications | Outbox retry resends email to recipients who already received it | REPRODUCED | production |
| IR-31 | **MINOR** | Public website intake | UNKNOWN_POLICY_VERSION is shown as an inline field error with no WhatsApp route | SOURCE-INSPECTED | feature:public-intake (before any policy-version rotation) |
| IR-32 | **MINOR** | Public website intake | Enquiry-form prerequisites absent: /privacy page missing, no site CSP, Turnstile site key unset, showErrors() uses innerHTML with server strings, #form-note contrast 4.06:1 | REPRODUCED | feature:public-intake enablement |
| IR-33 | **MINOR** | PostgreSQL | PostgreSQL immutability guard is bypassable (user-settable GUC veda.maintenance, no TRUNCATE trigger) and app/retention roles are never provisioned | REPRODUCED | pg-release-gate (MAJOR for PGM-1) |
| IR-34 | **MINOR** | Migrations | Historical migrations import the live permission registry and role matrix, so freshly built environments drift from upgraded ones | SOURCE-INSPECTED | post-production follow-up (required before first registry change) |
| IR-35 | **MINOR** | Operations | Single-process/instance constraint is enforced only by a text match on gunicorn.conf.py; client IP trusted from CF-Connecting-IP without a trusted-proxy check | REPRODUCED | production |
| IR-36 | **MINOR** | Frontend | 'Sign out everywhere' leaves the user on /profile with stale personal data displayed | REPRODUCED | production |
| IR-37 | **MINOR** | Frontend / Accessibility | Accessibility gaps: 360 px status stepper not keyboard-scrollable (axe serious), unreliable toast announcements, no MFA-timeout warning, window.prompt for sensitive reason, incomplete listbox/menu/tab semantics | REPRODUCED | production |
| IR-38 | **MINOR** | Test evidence quality | Browser E2E evidence overstates coverage and security-critical modules have the lowest coverage | REPRODUCED | production |
| IR-39 | **MINOR** | Tooling | No Python formatter or type checker enforced, no ESLint/Prettier; frontend dev toolchain carries dev-only advisories (upgrade needs Node ≥ 20.19) | REPRODUCED | staging (CI/supply-chain exposure) ; production |

### 17.2 Detail

#### IR-01 · BLOCKER · MFA enrollment confirmation is not bound to the caller: a bearer token plus any unbound enrollment challenge grants MFA verification and step-up to the token's session

- **Domain:** Authentication / MFA
- **Verification:** REPRODUCED (SQLite and PostgreSQL); source confirmed by lead reviewer
- **Evidence:**
  - api/veda/platform/auth/mfa.py:259 — challenge/session binding is enforced only when ch.session_id is not None; ctx.user.id is never compared with ch.user_id
  - api/veda/platform/auth/mfa.py:280 — enrollment path is chosen from the presence of a bearer context (path A) rather than from the challenge
  - api/veda/platform/auth/mfa.py:297-301 — path A sets auth_methods='pwd+totp' and mfa_verified_on on the CALLER's session while the factor promoted belongs to ch.user_id
  - api/veda/platform/auth/routes.py:289 — POST /auth/mfa/enroll/confirm declared auth='optional'
  - Contrast: api/veda/platform/auth/mfa.py:328 (step-up) correctly requires ch.user_id == ctx.user.id and ch.session_id == ctx.session.id
  - Probe P1b output: 'admin regenerate codes w/o fresh step-up: 403 STEP_UP_REQUIRED' → 'cross confirm using admin bearer: 200 AUTHENTICATED' → 'admin regenerate codes after cross confirm: 200 [codes]'
  - Probe P1: a password-only session of a user holding an MFA-gated sensitive grant went from 403 MFA_REQUIRED to 200 on GET /api/v1/audit-logs
- **Affected requirements:** MFA-011, MFA-012, MFA-014, AUTH-015, 05 §11.3, 05 §11.6, 06 §3.2 (G10)
- **Risk:** Complete bypass of step-up (G10) and of MFA-gated sensitive permissions for anyone who holds a victim's access token — exactly the threat step-up exists to contain.
- **Exploit / failure scenario:** Attacker obtains victim X's bearer access token (XSS elsewhere, shared device, log leak). Attacker also controls an unbound ENROLLMENT challenge and its TOTP secret — trivially obtained as any invitee whose role requires MFA (path B) or as any MFA-required user without a factor (path C). Attacker calls POST /auth/mfa/enroll/confirm with their own challenge_token + code and 'Authorization: Bearer <X token>'. X's session is marked MFA-verified and freshly stepped-up; attacker can then regenerate X's recovery codes, change roles, reset MFA, read security events, etc., without X's authenticator.
- **Required remediation:** Derive the path from the challenge, never from the presence of ctx. If ch.session_id is None (paths B/C) reject any request carrying a bearer token. If ch.session_id is set, require ctx.session.id == ch.session_id AND ctx.user.id == ch.user_id. Always require ctx.user.id == ch.user_id when ctx is present. Store the PENDING factor id on the challenge so confirm promotes exactly that factor.
- **Required validation:** Regression tests reproducing P1 and P1b (and a path-D variant: recovery session + foreign unbound challenge) must fail closed on SQLite and PostgreSQL; full MFA suite green.
- **Architecture amendment required:** No
- **Re-review required:** Yes — security re-review of the enrollment/step-up state machine
- **Blocking scope:** merge

#### IR-02 · MAJOR · Cloudflare Turnstile siteverify (up to 5 s network I/O) runs while the database-wide SQLite write lock is held (public intake and CAPTCHA-gated login)

- **Domain:** Leads / Authentication / Availability
- **Verification:** REPRODUCED (public intake); login path SOURCE-INSPECTED
- **Evidence:**
  - api/veda/kernel/http.py:425,464 — every non-GET route opens db.new_session(write=True) before the handler runs
  - api/veda/kernel/db.py:46-51 — write sessions issue BEGIN IMMEDIATE (global SQLite write lock); busy_timeout 5000 ms
  - api/veda/modules/crm/leads/routes.py:69 — turnstile.verify() inside the write unit of work
  - api/veda/platform/auth/service.py:229 — login calls turnstile.verify() inside the write unit of work when captcha_required
  - api/veda/kernel/turnstile.py:41 — urlopen(..., timeout=5)
  - Probe Q5: 3 s verify delay → concurrent staff POST /leads waited 2.77 s; 6 s delay → staff write returned 503 after 5.19 s
- **Affected requirements:** LEAD-018, AUTH-010, NFR-003, ADR-008, 04 §5.1 (transaction covers steps 6–11 only)
- **Risk:** Anonymous traffic serialises every platform write (staff edits, logins, token refresh, outbox) behind a third-party round-trip; a slow or degraded siteverify produces 503s for all staff writes.
- **Exploit / failure scenario:** Bots submit enquiries with junk tokens from many IPs (20/min/IP allowed); each request holds the write lock for the siteverify RTT. During a Cloudflare slowdown staff writes and refresh-token rotation fail with 503.
- **Required remediation:** Perform idempotency lookup and Turnstile verification in a read-only session (or before opening the write unit of work); open the write transaction only for steps 6–11 and re-check the idempotency key inside it. Apply the same pattern to login.
- **Required validation:** Re-run Q5: staff write latency independent of verify delay; add an integration test with a slow verifier stub for both intake and login.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production; feature:public-intake enablement

#### IR-03 · MAJOR · Security-event chain verification never consults the external anchor and accepts deletion of the anchored prefix and tail truncation

- **Domain:** Audit / Security events
- **Verification:** REPRODUCED locally on SQLite and PostgreSQL; S3 path SOURCE-INSPECTED
- **Evidence:**
  - api/veda/platform/maintenance.py:240-245 — latest_anchor() reads only local anchors.jsonl
  - api/veda/platform/maintenance.py:277-283 — production anchor_chain() writes only to S3, never the local file
  - api/veda/platform/maintenance.py:316-320 — archival anchors are written only locally
  - api/veda/platform/maintenance.py:253-259 — a missing anchored row is assumed archived; no manifest/hash check
  - Probe Q4: deleting rows ≤ anchor seq → verify ok=True; deleting the head row → verify ok=True (both engines)
- **Affected requirements:** SEVT-006, SEVT-007, 05 §9.6, 11 §4 A2
- **Risk:** The 'daily external anchor bounds undetected rewrite to one day' property does not hold; an attacker with the chain key or DB-level access can delete or truncate security evidence without the nightly verification detecting it.
- **Exploit / failure scenario:** Host-level attacker drops SQLite triggers (accepted residual) and deletes the most recent security events after a compromise; nightly verification reports OK.
- **Required remediation:** Verification must fetch the latest S3 anchor via a read role, require the anchored (seq,row_hash) to be present or covered by a verified archive manifest, require DB head seq ≥ anchored seq, and write archival anchors to S3.
- **Required validation:** Q4 cases must return ok=False; unit test with stubbed S3 client.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production (tamper-evidence claim)

#### IR-04 · MAJOR · A STANDARD dual-control request survives the target's promotion to Founder and then executes against the Founder (G11 time-of-check/time-of-use bypass)

- **Domain:** Founder governance
- **Verification:** REPRODUCED (SQLite and PostgreSQL)
- **Evidence:**
  - api/veda/platform/rbac/governance.py:70-75 — _open_request_guard is scoped per class, so STANDARD and FOUNDER requests coexist on one target
  - api/veda/platform/rbac/governance.py:100-108 — _execute_standard runs start_email_change / admin_reset without re-checking protection_level/G11
  - Probe P10: ADMIN raises EMAIL_CHANGE on ADMIN a2 → a2 promoted to Founder → a Founder approves the stale STANDARD request → 200 EXECUTED, Founder's proposed_email = attacker-controlled address
- **Affected requirements:** RBAC-020, RBAC-021, USER-007, MFA-007, 06 §7.1 G11, 06 §7.4 (eligibility re-checked at execution)
- **Risk:** Founder account-control actions (email change, MFA reset) can be initiated by an ADMIN and completed with one approval, bypassing the Founder-level dual-Founder workflow. Email change leads to password-reset capability for the new mailbox.
- **Exploit / failure scenario:** Malicious ADMIN files an email-change request against a colleague who is about to be promoted to Founder; after promotion, the stale request is approved (social engineering or confusion) and executes against a Founder.
- **Required remediation:** Re-apply G11 and requester G9 at approval and execution time (FAILED FOUNDER_PROTECTED); additionally cancel open STANDARD requests on GRANT_FOUNDER execution.
- **Required validation:** P10 must end FAILED/FOUNDER_PROTECTED on both engines; add TD-G case.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** merge (governance bypass)

#### IR-05 · MAJOR · Custodians can initiate full break-glass while eligible Founders exist (no operating-mode check)

- **Domain:** Founder governance / break-glass
- **Verification:** REPRODUCED (SQLite and PostgreSQL)
- **Evidence:**
  - api/veda/platform/rbac/governance.py:387-408 — break_glass_request validates action, target and open-request guard but never checks that no eligible Founder exists
  - Probe P13: with two eligible Founders present, custodians K1+K2 granted FOUNDER to a SALES user after the 24 h delay
- **Affected requirements:** RBAC-021, 06 §7.2.2, 06 §7.2.4
- **Risk:** Break-glass becomes a parallel, steady-state path to grant/revoke/disable/MFA-reset any Founder; combined with IR-06 and IR-07, Founders have no usable veto once a custodian approves.
- **Exploit / failure scenario:** Two custodians (or one via IR-06) grant Founder status to an arbitrary user while the real Founders are available.
- **Required remediation:** Refuse break_glass_request (409, BREAK_GLASS_REQUESTED FAILURE event) unless no eligible Founder other than the target exists; consider letting any eligible Founder cancel APPROVED break-glass requests in-app.
- **Required validation:** P13 → refusal in steady state; TD-G case.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production (PG-BG); break-glass unusable until OWNER-INPUT-004 anyway

#### IR-06 · MAJOR · Break-glass CLI trusts a caller-supplied --principal-arn (two-person control is self-asserted)

- **Domain:** Founder governance / break-glass
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/cli/main.py:253 — --principal-arn argument passed straight through (main.py:189-197)
  - api/veda/platform/rbac/governance.py:380-384 — custodian_human only looks the ARN up in configuration; no STS/SSM identity check anywhere
  - Probe P13: one shell ran 'request --principal-arn K1' and 'approve --principal-arn K2'; approval accepted and recorded
- **Affected requirements:** RBAC-021, 06 §7.5 items 2 and 4 (ARNs verified from SSM session identity / CloudTrail)
- **Risk:** One operator with host access satisfies 'two distinct humans' and produces legitimate-looking, hash-chained BREAK_GLASS_APPROVED evidence with a false principal.
- **Exploit / failure scenario:** A single custodian with SSM access requests and approves a break-glass Founder grant alone.
- **Required remediation:** Derive the principal from sts:GetCallerIdentity or the SSM session environment; refuse mismatches; record session id and ARN.
- **Required validation:** CLI approve fails when caller identity ≠ supplied ARN (mocked STS); TD-G case.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production (PG-BG)

#### IR-07 · MAJOR · Break-glass cancel link targets a non-existent SPA route; the 06 §7.5 notified-party veto is unusable end-to-end

- **Domain:** Founder governance / break-glass (Phase 4)
- **Verification:** SOURCE-INSPECTED; emailed URL REPRODUCED (P12); API endpoint REPRODUCED working
- **Evidence:**
  - api/veda/platform/notifications/handlers.py:309 — link built as {app_origin}/approvals/cancel#token=…
  - app/src/core/router/routes.ts:20-50 — no /approvals/cancel route (falls through to not-found); no SPA code calls /api/v1/approvals/cancel-link
  - api/veda/platform/rbac/routes.py:371-379 — POST /api/v1/approvals/cancel-link (RBX-003) works: 256-bit HMAC token, hash-only storage, single use with sibling invalidation (P12: invalid 400 / extra field 422 / valid 204 / replay 400)
  - docs/architecture/08-api-design.md §1 — no break-glass cancel row; #47 POST /approvals/{id}/cancel is implemented (rbac/routes.py:363-368)
  - docs/architecture/06-rbac.md §11 — RBX-003 register does not list cancel-link
- **Affected requirements:** RBAC-021, 06 §7.5 step 5, 12 TD-G G12, PG-BG
- **Risk:** Governance: the cooling-off veto the architecture relies on to contain break-glass cannot be exercised by its intended users. Security of the endpoint itself: no defect found.
- **Exploit / failure scenario:** Founders receive the break-glass notification, click the cancel link, and land on a not-found page while the custodian action proceeds.
- **Required remediation:** Add a public SPA page /approvals/cancel that POSTs the fragment token; add browser E2E; amend 08 §1, 06 §11 RBX-003 and 09 (page spec).
- **Required validation:** Browser E2E cancels a pending break-glass request from the emailed link.
- **Architecture amendment required:** Yes — 08 §1 index row, 06 §11 RBX-003 register entry, 09 page
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production (PG-BG)

#### IR-08 · MAJOR · FOUNDER_STATUS_CHANGE with DELETED always fails (I3 evaluation drops soft-deleted users but keeps their live FOUNDER role row)

- **Domain:** Founder governance
- **Verification:** REPRODUCED (SQLite and PostgreSQL)
- **Evidence:**
  - api/veda/platform/rbac/guards.py:148-152 — holders = live FOUNDER user_role rows; protected = users via soft-delete-filtered query
  - api/veda/platform/rbac/users.py:144-150 — DELETE sets is_deleted but leaves FOUNDER user_role live
  - api/veda/platform/rbac/governance.py:241-248 — request marked FAILED FOUNDER_STATE_INCONSISTENT
  - Probe P11/P16: approved DELETE → FAILED; workaround REVOKE_FOUNDER then DELETE → 204
- **Affected requirements:** RBAC-021, USER-001, 06 §7.2.2
- **Risk:** A documented P0 governance action is unusable (fails closed; no security exposure).
- **Exploit / failure scenario:** Departed Founder cannot be deleted through the canonical workflow.
- **Required remediation:** Evaluate I3 consistently (include_deleted on both sides, or exclude deleted on both), or soft-delete the FOUNDER user_role on DELETE per an explicit decision; add a TD-G case.
- **Required validation:** P16 DELETE → EXECUTED with invariants I1–I3 holding and nightly invariant job agreeing.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** merge (P0 functional acceptance of RBAC-021)

#### IR-09 · MAJOR · Production-safety validation is fail-open: any VEDA_ENV other than exactly 'production' (including staging, unset, 'prod') runs with publicly derivable dev keys, local KMS, capture email and the accept-anything CAPTCHA verifier; production validation is also incomplete

- **Domain:** Configuration / Production readiness
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/config.py:132-143 — keys fall back to values derived from the public constant 'local-development-only'
  - api/veda/config.py:207-210 — validate_production returns [] unless settings.is_production
  - api/veda/platform/auth/jwt_tokens.py:54-60 — non-production JWT key derived from sha256('veda-dev-jwt::' + env)
  - api/veda/kernel/turnstile.py:37-38 — non-cloudflare mode accepts any token not starting with 'fail'
  - Probe P6b: env='staging' → validate_production [] and a JWT forged with the derivable key verifies
  - DB/ops probe: env 'production' still accepts rate limits disabled, 1-byte HMAC keys, placeholder KMS ARN, localhost origins, relative SQLite path, jwt_kid=dev-1, no Sentry/anchor bucket; cmd_migrate skips validation (cli/main.py:42-52)
- **Affected requirements:** SEC-005, PLAT-008, OPS-003, LOG-004, AUTH-004, 02 §11.4
- **Risk:** An internet-facing staging environment (or a production host with a mistyped VEDA_ENV) accepts forged access tokens, mintable reset/invite links, forgeable security-event chains and decryptable TOTP seeds.
- **Exploit / failure scenario:** Staging deployed at api-staging.vedaspaces.com without every secret set; an attacker derives the dev JWT key and signs an admin token.
- **Required remediation:** Fail closed: VEDA_ENV must be one of {local,test,staging,production}; only local/test may derive dev keys and only with an explicit opt-in; apply secret checks to staging; add key-length, KMS ARN, https/non-localhost origin, absolute DB path, rate-limit, Sentry, anchor-bucket and non-dev kid checks; validate in migrate.
- **Required validation:** Parameterised unit tests over env values and each missing/weak setting; create_app must refuse.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** staging; production

#### IR-10 · MAJOR · Readiness gate requires DB revision == image head exactly, so the architecture's normal rollback (redeploy N-1 on the migrated schema) always reports not-ready

- **Domain:** Operations / Migrations
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/platform/health.py:43-45 — checks['migrations'] = 'head' if current == head else 'behind'; ok &= current == head
  - Probe: DB at 0100_crm_leads with N-1 image head 0008_account_security → 503 {"migrations":"behind"} (label also wrong: DB is ahead)
- **Affected requirements:** OPS-004, LOG-005, 02 §12.4, 11 §2 B3
- **Risk:** The only rollback strategy that justifies the expand-only / no-downgrade policy is non-functional; the running N-1 API also flips to not-ready immediately after migration.
- **Exploit / failure scenario:** A release migrates, the new image misbehaves, ops redeploys N-1: /health/ready stays 503 and the deploy gate fails; only snapshot restore remains (see IR-11).
- **Required remediation:** Accept the image head or a declared N-1-compatible descendant (e.g., migrations record lineage/compat metadata that readiness checks); fix the 'behind' label.
- **Required validation:** Test that loads an app whose script directory lacks the latest revision against a head DB and expects 200; 503 when genuinely behind or divergent.
- **Architecture amendment required:** Yes — clarify LOG-005 / 08 §3 readiness semantics ('at or compatibly ahead of the image head')
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production (and RG-7 rehearsal)

#### IR-11 · MAJOR · Backup (Litestream config, nightly snapshot), restore verification and API deploy/migrate runbooks are absent from the deliverable

- **Domain:** Operations
- **Verification:** SOURCE-INSPECTED
- **Evidence:**
  - api/deploy/docker-compose.yml references /etc/veda/litestream.yml which is not in the repository
  - No VACUUM INTO / snapshot job and no restore-verification job anywhere in api/ (grep)
  - deployment.md covers only the marketing site; no API runbooks (11 §8)
  - Implementation report §16/§17 acknowledge these gates were not executed
- **Affected requirements:** OPS-002, OPS-004, OPS-005, OPS-007, OPS-009, RG-1, RG-2, RG-7
- **Risk:** Volume loss or a bad migration without a restorable, verified copy; RPO/RTO unproven.
- **Exploit / failure scenario:** EBS volume failure in production with no replicated copy.
- **Required remediation:** Commit litestream.yml, nightly VACUUM INTO + Object Lock job, restore-verification job with metrics/alerts, a deploy/migrate script implementing 02 §12.4, and 11 §8 runbooks.
- **Required validation:** RG-1, RG-2, RG-7 evidence.
- **Architecture amendment required:** No
- **Re-review required:** Operational readiness review
- **Blocking scope:** production

#### IR-12 · MAJOR · No metrics, no alert routing, error tracker optional (LOG-006 is mandatory in P0)

- **Domain:** Operations / Observability
- **Verification:** SOURCE-INSPECTED
- **Evidence:**
  - No metrics emission anywhere in api/veda (grep)
  - Alerts are stdlib log lines: maintenance.py:265,343,345,406; security_events.py:311; worker.py:97
  - Sentry DSN not required in production (config.py validate_production)
  - Implementation report OI-7
- **Affected requirements:** LOG-004, LOG-006, OPS-009, SEVT-009, RG-5
- **Risk:** Chain breaks, invariant failures, dead-lettered notifications, replication lag or disk exhaustion go unnoticed.
- **Exploit / failure scenario:** Outbox dead-letters every lead notification for days; nobody is paged.
- **Required remediation:** Emit the 02 §9 metric set, route CRITICAL/ERROR to paging, require Sentry in production, test-fire each alert.
- **Required validation:** RG-5 evidence.
- **Architecture amendment required:** No
- **Re-review required:** Operational readiness review
- **Blocking scope:** production

#### IR-13 · MAJOR · Runtime Python dependencies are open ranges with no lockfile or hashes; container base image floats

- **Domain:** Supply chain / Build reproducibility
- **Verification:** SOURCE-INSPECTED; drift REPRODUCED (ruff format count 83 vs reported 82 under ruff 0.16.9; resolved SQLAlchemy 2.1.1, Flask-Limiter 4.1.1)
- **Evidence:**
  - api/requirements.txt — 10 of 14 packages have no upper bound; no lock/constraints file; no hashes
  - api/deploy/Dockerfile — floating python:3.13-slim and pip install -r requirements.txt at build time
  - .github/workflows/ci.yml:26 — CI installs a different set from requirements-dev.txt
  - Implementation report records no resolved package versions
- **Affected requirements:** SEC-007, OPS-001, PLAT-008, 11 §5 X11
- **Risk:** The shipped image is not the tested set; a transitive major upgrade can alter auth, JWT or rate-limit behaviour in production; no hash verification.
- **Exploit / failure scenario:** A new Flask-Limiter or PyJWT major resolves at image build and silently changes limiter keys or token validation.
- **Required remediation:** Generate a hashed lock (pip-compile --generate-hashes / uv), install with --require-hashes in CI and the image, pin the base image by digest, run pip-audit against the lock, record resolved versions in evidence.
- **Required validation:** CI job fails on lock drift; reproducible image digest.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** merge (recommended) ; staging; production

#### IR-14 · MAJOR · CI workflow has never executed and omits PR gates required by 12 §5 (types, N-1 test, OpenAPI diff, dependency/image/secret scan, E2E smoke + axe)

- **Domain:** CI / Quality gates
- **Verification:** SOURCE-INSPECTED
- **Evidence:**
  - .github/workflows/ci.yml:1-49 — api job: ruff check, pytest, deploy-check; app job: typecheck, lint:tokens, contrast, unit tests, build
  - docs/architecture/12-test-strategy.md:342-348 — PR gates list types, migration N-1 test, OpenAPI diff, dependency + image scan, secret scan, E2E smoke + axe
  - Implementation report OI-9: 'CI workflow was written but not executed'
  - api/veda/cli/main.py:226-231 — deploy-check is a substring match on the gunicorn config (probe: GUNICORN_CMD_ARGS=--workers=4 still reports OK)
- **Affected requirements:** OPS-001, DATA-011, SEC-007, 12 §5
- **Risk:** MINOR items cannot be tracked through enforceable gates when the gates themselves are not automated; dual-engine and PostgreSQL 16 conformance depends on a pipeline that has never run.
- **Exploit / failure scenario:** A regression that breaks PostgreSQL or introduces a vulnerable dependency merges unnoticed.
- **Required remediation:** Execute CI green on the PR (including the postgres:16 matrix leg); add mypy (or document the waiver), OpenAPI diff, pip-audit/npm audit, secret scan, container scan and an E2E smoke + axe job.
- **Required validation:** Green CI run URL attached to the re-review evidence.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** merge

#### IR-15 · MAJOR · Lead edit 'Re-apply mine' after a version conflict silently reverts the other writer's committed changes

- **Domain:** Frontend / Data integrity
- **Verification:** REPRODUCED (browser probe + audit log); source confirmed by lead reviewer
- **Evidence:**
  - app/src/modules/leads/lead-form.ts:153-181 — on reapply, saveEdit(values, {...original, ...fresh}, fresh.version) diffs the entire stale form against fresh, so every field the other user changed is sent with its old value
  - Probe: other client PATCHes city/priority; UI user edits only message and re-applies → server city/priority reverted; audit changed_fields [city, message, priority]
- **Affected requirements:** UI-005, DATA-006, 12 §4.12 TD-F step 4 ('no data loss'), 09 §3.2
- **Risk:** Client defeats server-side optimistic concurrency; silent lost updates to lead contact data and priority.
- **Exploit / failure scenario:** Two staff edit one lead concurrently; the second user's re-apply undoes the first user's work.
- **Required remediation:** Compute the user's own edits once (diff against the originally loaded record) and on re-apply send only those against fresh.version; surface true field-level conflicts.
- **Required validation:** Unit test for saveEdit diffing; browser TD-F step-4 journey showing only 'message' changed.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production

#### IR-16 · MAJOR · DEV-004 staff re-consent overwrites consent evidence, mixes provenance and is accepted without prior withdrawal

- **Domain:** Leads / Privacy (DEV-004)
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/modules/crm/leads/service.py:462-468 — re-consent overwrites consent_* in the row and clears withdrawal fields
  - api/veda/modules/crm/leads/schemas.py:48-50,95 — staff may choose channel WEBSITE_FORM
  - Probe P3: after re-consent row shows channel=PHONE_VERBAL with original website ip and source_page retained
  - Probe: three consecutive re-consent PATCHes without withdrawal all 200; original survives only in audit_log UPDATE old_value; SALES /history → 403
  - Probe P3b: SALES with OWN scope re-consents a withdrawn lead (200); no system activity/timeline entry, reason=None
  - Deviation register claims a lead-drawer UI control; app/src contains none
- **Affected requirements:** LEAD-012, LEAD-024, LEAD-027, 04 §5.4, 08 §8.5, ADR-005
- **Risk:** Consent evidence (DPDP-relevant) misstates its origin and can be replaced without trace in the lead timeline; the 'original consent evidence' depends on audit rows subject to archival and erasure rewriting.
- **Exploit / failure scenario:** A salesperson re-consents a customer who withdrew, choosing WEBSITE_FORM; the row now asserts a website consent with the original web IP and the Do-not-contact banner disappears.
- **Required remediation:** Clear/replace consent_ip_address and consent_source_page with the new capture context (NULL for staff channels); forbid WEBSITE_FORM from staff; accept only when withdrawn, never captured, or the policy version changes; require a note/evidence reference and write a system activity; consider an append-only consent-event child table; correct the deviation register.
- **Required validation:** Probe P3/P3b variants: provenance cleared, activity written, re-consent without withdrawal rejected, WEBSITE_FORM rejected.
- **Architecture amendment required:** Yes — reconcile 04 §5.4 with 08 §8.5 and decide in-row vs audit-only retention of prior consent
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** feature:staff re-consent (remove the consent field from LeadPatchIn or fix before merge)

#### IR-17 · MAJOR · Enquiry form remains visible after success/fallback ([hidden] overridden by .contact-form{display:grid}); resubmission reports a false failure

- **Domain:** Public website intake
- **Verification:** REPRODUCED; CSS source confirmed by lead reviewer
- **Evidence:**
  - dist/assets/app.js:122-123 — contactForm.hidden = true
  - dist/assets/styles.css (pre-existing) — .contact-form{display:grid} with no [hidden] override
  - Probe: after 201 the form computes display:grid (737 px) beside the success panel; resubmitting → 422 IDEMPOTENCY_KEY_REUSED → 'Something went wrong on our side' while the lead is stored
  - app/e2e/site.e2e.mjs:38-41 — success check does not assert the form is hidden
- **Affected requirements:** LEAD-001, LEAD-019, 09 §4.11, AX-08
- **Risk:** Customers are told a stored enquiry failed; duplicate WhatsApp hand-offs.
- **Exploit / failure scenario:** Visitor submits, edits a field in the still-visible form, resubmits and sees a failure panel.
- **Required remediation:** Add .contact-form[hidden], .form-panel[hidden]{display:none}; assert hidden state in E2E.
- **Required validation:** site.e2e asserts form hidden for success and fallback.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** feature:public-intake enablement (veda-api-base)

#### IR-18 · MAJOR · Turnstile token is never reset; after any server-side 422 the corrected resubmission reuses a spent token and fails CAPTCHA

- **Domain:** Public website intake
- **Verification:** SOURCE-INSPECTED (precondition REPRODUCED: server-side field 422 after client validation passes)
- **Evidence:**
  - api/veda/modules/crm/leads/routes.py:69,72-74 — CAPTCHA verified before validation, consuming the single-use token
  - dist/assets/app.js:135,175 — client re-reads the same widget response; no turnstile.reset() anywhere; 'no-widget' sent when absent
- **Affected requirements:** LEAD-001, LEAD-019, 04 §5.1, 02 §2 intake step 3
- **Risk:** Any correctable server validation error converts into a CAPTCHA failure and WhatsApp fallback; enquiries degrade to the manual channel.
- **Exploit / failure scenario:** Name '12' passes client validation, server returns a field error, user corrects and resubmits → CAPTCHA_FAILED.
- **Required remediation:** Call turnstile.reset(widgetId) after every non-201; gate submit on a token; treat 'api-base set but no site key' as a deploy-check error.
- **Required validation:** E2E with a real Turnstile test key covering 422 → correct → 201.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** feature:public-intake enablement

#### IR-19 · MAJOR · SPA route changes never update the document title nor move focus/announce navigation (WCAG 2.4.2 Level A)

- **Domain:** Frontend / Accessibility
- **Verification:** REPRODUCED
- **Evidence:**
  - app/index.html:8 — static <title>; no document.title assignment in app/src
  - app/src/shell/app.ts:91-94 — location change only updates pathname; <main id=outlet tabindex=-1> (app.ts:185) is never focused
- **Affected requirements:** UI-011, UI-016 (AX-01), 09 §5
- **Risk:** Screen-reader users receive no indication of navigation; all history entries share one title.
- **Exploit / failure scenario:** Keyboard/screen-reader user activates 'Leads'; focus stays on the sidebar and nothing is announced.
- **Required remediation:** Per-route titles, focus the page heading or #outlet on vaadin-router-location-changed, announce via a polite live region.
- **Required validation:** Browser test asserting title and focus after navigation; manual NVDA/VoiceOver check.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production

#### IR-20 · MINOR · Path C (emailed enrollment link + password) replaces an existing ACTIVE factor without step-up by that factor; open enrollment links survive enrollment by another path

- **Domain:** Authentication / MFA
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/platform/auth/mfa.py:222-239 — path C never checks for an ACTIVE factor
  - mfa.py enroll_confirm does not invalidate open MFA_ENROLLMENT tokens
  - Probe P2/P2b: factor REPLACED while ACTIVE; old link valid after path-A enrollment (200)
- **Affected requirements:** MFA-014, 05 §11.3, DEV-001
- **Risk:** Path C (emailed enrollment link + password) replaces an existing ACTIVE factor without step-up by that factor; open enrollment links survive enrollment by another path
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Refuse path C start with 409 when an ACTIVE factor exists; invalidate open MFA_ENROLLMENT tokens on any confirm. Fix together with DEV-001 amendment.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production

#### IR-21 · MINOR · Resending an invitation does not revoke earlier invite_context challenges; link replay mints parallel contexts and overwrites the password

- **Domain:** Authentication / Invitation (DEV-002)
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/platform/rbac/users.py:95-109 — resend invalidates INVITE tokens only
  - api/veda/platform/auth/service.py:511-516 — each MFA-path accept creates a new ENROLLMENT challenge
  - Probe P3: old invite_context after resend → start 200 → confirm 200 AUTHENTICATED ACTIVE
- **Affected requirements:** AUTH-011, MFA-014, DEV-002
- **Risk:** Resending an invitation does not revoke earlier invite_context challenges; link replay mints parallel contexts and overwrites the password
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** On resend and each MFA-path accept, expire open ENROLLMENT challenges and revoke PENDING factors, or bind the challenge to the INVITE token and re-check liveness.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production

#### IR-22 · MINOR · IPv6 /64 network grouping is string-based and breaks on compressed addresses, defeating per-network throttle and CAPTCHA and causing false global lockouts

- **Domain:** Authentication / Throttling
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/kernel/http.py:152-158 and kernel/logging.py:57-63 — ':'.join(ip.split(':')[:4])
  - Probe P4: 12 failures from one /64 never set captcha_required; account globally throttled instead
- **Affected requirements:** AUTH-010, SEC-011, DEV-003
- **Risk:** IPv6 /64 network grouping is string-based and breaks on compressed addresses, defeating per-network throttle and CAPTCHA and causing false global lockouts
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Use ipaddress.ip_network(f'{ip}/64', strict=False) (and /24 for IPv4, handling IPv4-mapped); consider /64 keying for the per-IP limiter.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production

#### IR-23 · MINOR · Certified 5/min per-email login limit lets anyone lock a known account out from every network

- **Domain:** Authentication / Rate limits
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/platform/auth/routes.py:43-44; kernel/ratelimit.py:20-26 — key is email only
  - Probe P5: five requests from another network → victim's own login 429
- **Affected requirements:** AUTH-010, SEC-011, 05 §4 A-01, 08 §12
- **Risk:** Certified 5/min per-email login limit lets anyone lock a known account out from every network
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Key per-email limits on (email, network) or count failures only with an exemption for the last successful network; amend 08 §12.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** Yes — 08 §12
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production

#### IR-24 · MINOR · Password re-entry (reauth) and change-password are not throttled; password guessing with a stolen bearer then satisfies password-based step-up

- **Domain:** Authentication
- **Verification:** SOURCE-INSPECTED
- **Evidence:**
  - api/veda/platform/auth/service.py:462-470, 489-495 — no throttle.record_password_failure / account counter
- **Affected requirements:** AUTH-010, MFA-011
- **Risk:** Password re-entry (reauth) and change-password are not throttled; password guessing with a stolen bearer then satisfies password-based step-up
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Count reauth/change failures in the account throttle (10 per 15 min) and emit throttle events.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production

#### IR-25 · MINOR · Security-event gaps: no event on MFA-path invite password set, invalid action tokens, CSRF-rejected refresh, MFA throttle and per-network throttle activation; erasure refusal event rolled back

- **Domain:** Security events
- **Verification:** SOURCE-INSPECTED; erasure part REPRODUCED
- **Evidence:**
  - api/veda/platform/auth/service.py:511-516, 186-194
  - api/veda/platform/auth/routes.py:49-51
  - api/veda/platform/auth/throttle.py:70-77,111-121 (return value ignored at mfa.py:110,140,273,338)
  - api/veda/modules/crm/leads/service.py:665-668 — record() then raise; probe P6: 0 ERASURE_BLOCKED events persisted
- **Affected requirements:** AUTH-013, MFA-006, SEVT-002, SEVT-011, LEAD-029
- **Risk:** Security-event gaps: no event on MFA-path invite password set, invalid action tokens, CSRF-rejected refresh, MFA throttle and per-network throttle activation; erasure refusal event rolled back
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Record INVITE_ACCEPTED/TOKEN_INVALID, TOKEN_REFRESH FAILURE on CSRF rejection, ACCOUNT_THROTTLED scope=mfa|network; use security_events.defer for ERASURE_BLOCKED.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production

#### IR-26 · MINOR · Security-log archival deletes events it never exported when event time and chain order disagree near the cutoff

- **Domain:** Audit / Security events
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/platform/maintenance.py:303-304 selects occurred_on < cutoff; :327 deletes chain_seq <= last.chain_seq
  - Probe Q3 (both engines): row exported? False; still in DB? False; verify ok=True
- **Affected requirements:** SEVT-004, AUDIT-009
- **Risk:** Security-log archival deletes events it never exported when event time and chain order disagree near the cutoff
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Select by chain_seq range, export exactly the range deleted, assert counts in the same transaction.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production (before archival is enabled; currently refuses without OWNER-INPUT-002)

#### IR-27 · MINOR · Unhandled exceptions and DB errors log raw PII (stdlib loggers bypass structlog masking; engine lacks hide_parameters)

- **Domain:** Logging / Privacy
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/kernel/logging.py:30-43 — scrub applies only to structlog events
  - api/veda/app.py:134-137 — log.exception on stdlib logger
  - api/veda/kernel/db.py:56-64 — create_engine without hide_parameters=True
  - Probe Q6: forced NOT NULL violation on public intake logs enquirer name, email and message
  - api/veda/app.py:58-62 — Sentry initialised without before_send scrubbing
- **Affected requirements:** LOG-001, LOG-003, SEC-009
- **Risk:** Unhandled exceptions and DB errors log raw PII (stdlib loggers bypass structlog masking; engine lacks hide_parameters)
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Route stdlib logging through structlog ProcessorFormatter with masking, set hide_parameters=True, add Sentry scrubbing and include_local_variables=False.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production

#### IR-28 · MINOR · An erased (anonymised) lead still accepts notes, activities and status changes, re-introducing PII after erasure is reported complete

- **Domain:** Leads / Erasure
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/modules/crm/leads/activities.py:32-37,101-127; service.py:479-537 — no anonymized_on check
  - Probe P4: note with phone 201, activity with email 201, NEW→CONTACTED 200 while allowed_transitions=[]
- **Affected requirements:** LEAD-029, AUDIT-011, NOTE-001, ACT-001
- **Risk:** An erased (anonymised) lead still accepts notes, activities and status changes, re-introducing PII after erasure is reported complete
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Return 409 INVALID_STATE on every mutating lead/note/activity route when anonymized_on is set.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production

#### IR-29 · MINOR · Plain-text staff notification emails can be content-spoofed via newlines in public form fields

- **Domain:** Notifications
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/kernel/dto.py:31 — strip_controls keeps \n\r\t
  - api/veda/modules/crm/leads/events.py:35-57 — public name/city flow into text part
  - Probe: forged 'Open the lead:' line above the genuine link; HTML part escaped correctly
- **Affected requirements:** NOTIF-005
- **Risk:** Plain-text staff notification emails can be content-spoofed via newlines in public form fields
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Collapse whitespace in single-line fields at intake; render untrusted values on labelled lines.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production

#### IR-30 · MINOR · Outbox retry resends email to recipients who already received it

- **Domain:** Notifications
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/platform/notifications/worker.py:78-79
  - Probe P5: sends [u1, u2, u1, u2]
- **Affected requirements:** NOTIF-004, 02 §10.1
- **Risk:** Outbox retry resends email to recipients who already received it
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Track per-(event, recipient, template) delivery state or fan out per recipient.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production

#### IR-31 · MINOR · UNKNOWN_POLICY_VERSION is shown as an inline field error with no WhatsApp route

- **Domain:** Public website intake
- **Verification:** SOURCE-INSPECTED
- **Evidence:**
  - dist/assets/app.js:198-201
- **Affected requirements:** LEAD-019, 04 §5.1
- **Risk:** UNKNOWN_POLICY_VERSION is shown as an inline field error with no WhatsApp route
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Treat UNKNOWN_POLICY_VERSION as non-field: show fallback with reload prompt.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** feature:public-intake (before any policy-version rotation)

#### IR-32 · MINOR · Enquiry-form prerequisites absent: /privacy page missing, no site CSP, Turnstile site key unset, showErrors() uses innerHTML with server strings, #form-note contrast 4.06:1

- **Domain:** Public website intake
- **Verification:** REPRODUCED
- **Evidence:**
  - dist/index.html:179 links /privacy (not present)
  - dist/_headers has no Content-Security-Policy (pre-existing)
  - dist/assets/app.js:94-105 innerHTML sink (not exploitable today: messages are static server literals)
  - #form-note #746e66 on #f1e5d7 = 4.06:1 (needs 4.5:1)
- **Affected requirements:** LEAD-001, SEC-003, SEC-009, AX-05, AX-08, OI-5
- **Risk:** Enquiry-form prerequisites absent: /privacy page missing, no site CSP, Turnstile site key unset, showErrors() uses innerHTML with server strings, #form-note contrast 4.06:1
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Publish the Privacy Notice (v2026-09-v1), add a site CSP incl. Turnstile/API origins, provision the site key, build the summary with textContent, fix #form-note colour.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** feature:public-intake enablement

#### IR-33 · MINOR · PostgreSQL immutability guard is bypassable (user-settable GUC veda.maintenance, no TRUNCATE trigger) and app/retention roles are never provisioned

- **Domain:** PostgreSQL
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/kernel/migration_support.py:327-351, 387-403
  - PG16.4 probe: TRUNCATE succeeded; SET LOCAL veda.maintenance='on' + DELETE removed 206 audit rows; non-owner role with GUC succeeded
- **Affected requirements:** 07 §6.2, AUDIT-004, SEVT-006, DATA-014
- **Risk:** PostgreSQL immutability guard is bypassable (user-settable GUC veda.maintenance, no TRUNCATE trigger) and app/retention roles are never provisioned
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** BEFORE TRUNCATE trigger; role-based bypass (SECURITY DEFINER maintenance function) instead of GUC; provision veda_app/veda_retention; assert grants in readiness.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** pg-release-gate (MAJOR for PGM-1)

#### IR-34 · MINOR · Historical migrations import the live permission registry and role matrix, so freshly built environments drift from upgraded ones

- **Domain:** Migrations
- **Verification:** SOURCE-INSPECTED
- **Evidence:**
  - api/veda/kernel/migration_support.py:165-167, 204-206
  - api/veda/cli/main.py:101-107 — sync-permissions does not sync role_permission
- **Affected requirements:** PLAT-005, RBAC-018, OPS-004
- **Risk:** Historical migrations import the live permission registry and role matrix, so freshly built environments drift from upgraded ones
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Freeze seed literals per revision; make catalog/matrix changes via new data migrations.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** post-production follow-up (required before first registry change)

#### IR-35 · MINOR · Single-process/instance constraint is enforced only by a text match on gunicorn.conf.py; client IP trusted from CF-Connecting-IP without a trusted-proxy check

- **Domain:** Operations
- **Verification:** REPRODUCED
- **Evidence:**
  - api/veda/cli/main.py:226-231 — probe: GUNICORN_CMD_ARGS=--workers=4 → 'deploy-check: OK'
  - api/veda/kernel/http.py:146-149; kernel/ratelimit.py:17 — CF-Connecting-IP trusted unconditionally
- **Affected requirements:** OPS-006, OPS-010, RG-3, RG-6, SEC-006, AUTH-010
- **Risk:** Single-process/instance constraint is enforced only by a text match on gunicorn.conf.py; client IP trusted from CF-Connecting-IP without a trusted-proxy check
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Runtime single-instance lock and worker assertion; accept CF-Connecting-IP only from configured proxy CIDRs; commit proxy/tunnel config.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production

#### IR-36 · MINOR · 'Sign out everywhere' leaves the user on /profile with stale personal data displayed

- **Domain:** Frontend
- **Verification:** REPRODUCED
- **Evidence:**
  - app/src/modules/auth/profile-page.ts:198 — session.logout(true) without navigate('/login')
- **Affected requirements:** UI-015, AUTH-007
- **Risk:** 'Sign out everywhere' leaves the user on /profile with stale personal data displayed
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Navigate to /login after logout-all; cover all three sign-out entry points in E2E.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production

#### IR-37 · MINOR · Accessibility gaps: 360 px status stepper not keyboard-scrollable (axe serious), unreliable toast announcements, no MFA-timeout warning, window.prompt for sensitive reason, incomplete listbox/menu/tab semantics

- **Domain:** Frontend / Accessibility
- **Verification:** REPRODUCED
- **Evidence:**
  - app/src/design-system/components.ts:36,147
  - app/src/modules/admin/user-drawer.ts:264
  - app/src/shell/app.ts:171-181
- **Affected requirements:** UI-011, UI-016 (AX-03, AX-06, AX-07, AX-09)
- **Risk:** Accessibility gaps: 360 px status stepper not keyboard-scrollable (axe serious), unreliable toast announcements, no MFA-timeout warning, window.prompt for sensitive reason, incomplete listbox/menu/tab semantics
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Fix per item; add manual screen-reader script.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production

#### IR-38 · MINOR · Browser E2E evidence overstates coverage and security-critical modules have the lowest coverage

- **Domain:** Test evidence quality
- **Verification:** REPRODUCED
- **Evidence:**
  - app/e2e/access.e2e.mjs:90-91 — 'API 401/403' check sends no bearer (proves 401 only); :102-103 hard-codes reloadSignedOut = true
  - Chromium-only; no forgot/reset, approvals, email-change, role-edit or TD-F step-4 journeys
  - Coverage (SQLite, branch): total 85%; rbac/governance.py 73%, kernel/ratelimit.py 57%, identity/service.py 74%
  - No existing test exercised cross-user enroll/confirm (IR-01), Founder DELETE (IR-08) or STANDARD→Founder TOCTOU (IR-04)
- **Affected requirements:** 12 §4.8, 12 §6, OPS-001
- **Risk:** Browser E2E evidence overstates coverage and security-critical modules have the lowest coverage
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Fix the two assertions; add negative security tests for the IR-01/IR-04/IR-08 classes; add Firefox/WebKit legs per 12 §4.8.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** production

#### IR-39 · MINOR · No Python formatter or type checker enforced, no ESLint/Prettier; frontend dev toolchain carries dev-only advisories (upgrade needs Node ≥ 20.19)

- **Domain:** Tooling
- **Verification:** REPRODUCED
- **Evidence:**
  - ruff format --check: 83 files would be reformatted (report says 82; unpinned ruff)
  - No mypy configuration; no ESLint/Prettier binaries or config
  - npm audit (configured Nexus feed): 195 advisories (JSON metadata 19 critical / 5 high / 171 low; text summary says 17 critical); public GHSA feed: 7 (6 high, 1 moderate: esbuild via vite 5.4.21, extract-zip via @web/test-runner); --omit=dev: 0 in both feeds
- **Affected requirements:** SEC-007, 12 §5, OI-8, OI-10
- **Risk:** No Python formatter or type checker enforced, no ESLint/Prettier; frontend dev toolchain carries dev-only advisories (upgrade needs Node ≥ 20.19)
- **Exploit / failure scenario:** See evidence.
- **Required remediation:** Adopt ruff format + mypy (or documented waiver), ESLint with lit plugin banning unsafe directives; upgrade Node to ≥ 20.19 and Vite ≥ 6.4.3 / WTR 1.x; add dependency audit to CI.
- **Required validation:** Regression test reproducing the evidence must pass.
- **Architecture amendment required:** No
- **Re-review required:** Targeted re-review of the fix
- **Blocking scope:** staging (CI/supply-chain exposure) ; production


### 17.3 Advisories

- **IR-A01** PostgreSQL concurrency: refresh rotation, recovery-code consumption and challenge attempt counting are read-then-write without row locks/conditional updates (safe on SQLite via BEGIN IMMEDIATE) — auth/service.py:358-374, mfa.py:70-88,133-147. Fix before PGM-1.
- **IR-A02** Login timing delta ≈1.2–1.6 ms known vs unknown account (extra post-request write) — auth/service.py:266-283.
- **IR-A03** Refresh/logout CSRF origin allow-list includes public-site origins (auth/service.py:334); mitigated by CORS preflight; tighten to app_origin.
- **IR-A04** Password reset does not invalidate open MFA challenges / enrollment links (auth/service.py:443-459).
- **IR-A05** Startup route-declaration check is presence-only; RBX ids/paths not validated against the 06 §11 register; public route with a permission would be silently unenforced (app.py:41-49, http.py:69-70,465-474). No current route affected.
- **IR-A06** PATCH /roles/{id} lacks a self-held-role check and accepts mfa_required (not in 08 §6.1) — rbac/roles.py:70-89.
- **IR-A07** Approval deny/cancel emit no SENSITIVE_ACTION; invite with sensitive role sends no rbac.sensitive_grant email; approve/deny return 403 where GET returns 404 (existence oracle).
- **IR-A08** 08 §12 per-user 600 req/5 min limit not implemented; token endpoints unthrottled (entropy makes brute force infeasible).
- **IR-A09** HMAC/action/chain keys have no minimum-length check in production (config.py:212-219). Folded into IR-09 remediation.
- **IR-A10** Cancel-link binding depends on outbox_event rows surviving retention purge (<3 days breaks live links, fail closed).
- **IR-A11** A hostile sole Founder can repeatedly cancel custodian break-glass (architecture residual of 06 §7.5; needs owner decision).
- **IR-A12** Client-supplied X-Request-ID / CF-Ray adopted as request_id; fine for correlation, not trustworthy as evidence (http.py:133-143).
- **IR-A13** Turnstile siteverify hostname/action not checked (turnstile.py:42).
- **IR-A14** DEAD outbox rows alert only via log.error; /health ignores DEAD; erasure-audit job lacks per-event failure handling (worker.py:97,122-126; maintenance.py:161-207).
- **IR-A15** IP/user-agent retained in audit_log/security_event_log after lead erasure; several free-text fields not in pii_fields (07 §2 gap).
- **IR-A16** PostgreSQL concurrent duplicate Idempotency-Key returns 409 instead of the original 201 (lead stored once).
- **IR-A17** /health/ready publicly exposes migration/guard/outbox state (health.py:36-62).
- **IR-A18** No SQLite format CHECK on UTCDATETIME columns; three CODE(n) columns lack enum CHECKs (event_type, failure_reason, status_reason).
- **IR-A19** sync-permissions CLI labels audit rows performed_via=MIGRATION (migration_support.py:117).
- **IR-A20** TOTP AES-GCM AAD is constant (crypto.py:120,128); bind to user_id‖factor_id.
- **IR-A21** App CSP: styleMap first render raises one style-src-attr violation (components.ts:291); production sourcemaps published (vite.config.ts:8); e2e scripts import undeclared playwright/axe-core.
- **IR-A22** HMAC-derived action tokens (OI-3): acceptable; residual — K_action compromise plus row ids yields every live link; document in 05/03.
- **IR-A23** WhatsApp fallback URL carries enquirer PII to wa.me (pre-existing, user-initiated); mention in Privacy Notice.
- **IR-A24** 18 pre-existing public-site contrast nodes outside the form (OI-11); highest priority .portfolio-head > p at 2.40:1.
- **IR-A25** Implementation report/register accuracy: DEV-004 claims a UI control that does not exist; ruff format count 82 vs 83; npm critical count 17 (text) vs 19 (JSON); PostgreSQL 16 not executed by the author (now reproduced by this review).

## 18. Blockers by stage

**Merge blockers** (all must be resolved or explicitly accepted by the owner before any merge):
- **IR-01** (BLOCKER) MFA enrollment confirmation is not bound to the caller: a bearer token plus any unbound enrollment challenge grants MFA verification and step-up to the token's session
- **IR-04** (MAJOR) A STANDARD dual-control request survives the target's promotion to Founder and then executes against the Founder (G11 time-of-check/time-of-use bypass)
- **IR-08** (MAJOR) FOUNDER_STATUS_CHANGE with DELETED always fails (I3 evaluation drops soft-deleted users but keeps their live FOUNDER role row)
- **IR-13** (MAJOR) Runtime Python dependencies are open ranges with no lockfile or hashes; container base image floats
- **IR-14** (MAJOR) CI workflow has never executed and omits PR gates required by 12 §5 (types, N-1 test, OpenAPI diff, dependency/image/secret scan, E2E smoke + axe)
- **IR-16** (MAJOR) DEV-004 staff re-consent overwrites consent evidence, mixes provenance and is accepted without prior withdrawal
- Deviation decisions recorded by the Architecture Owner (DEV-001..003 amendments; DEV-004 fix or removal; DEV-005 registered).
- Owner gates TG-01 and TG-08 recorded (currently Pending in `gate-registry.md`).

**Staging blockers:**
- All merge blockers above, plus:
- **IR-09** (MAJOR) Production-safety validation is fail-open: any VEDA_ENV other than exactly 'production' (including staging, unset, 'prod') runs with publicly derivable dev keys, local KMS, capture email and the accept-anything CAPTCHA verifier; production validation is also incomplete
- **IR-39** (MINOR) No Python formatter or type checker enforced, no ESLint/Prettier; frontend dev toolchain carries dev-only advisories (upgrade needs Node ≥ 20.19)

**Production blockers:**
- All merge and staging blockers above, plus:
- **IR-02** (MAJOR) Cloudflare Turnstile siteverify (up to 5 s network I/O) runs while the database-wide SQLite write lock is held (public intake and CAPTCHA-gated login)
- **IR-03** (MAJOR) Security-event chain verification never consults the external anchor and accepts deletion of the anchored prefix and tail truncation
- **IR-05** (MAJOR) Custodians can initiate full break-glass while eligible Founders exist (no operating-mode check)
- **IR-06** (MAJOR) Break-glass CLI trusts a caller-supplied --principal-arn (two-person control is self-asserted)
- **IR-07** (MAJOR) Break-glass cancel link targets a non-existent SPA route; the 06 §7.5 notified-party veto is unusable end-to-end
- **IR-10** (MAJOR) Readiness gate requires DB revision == image head exactly, so the architecture's normal rollback (redeploy N-1 on the migrated schema) always reports not-ready
- **IR-11** (MAJOR) Backup (Litestream config, nightly snapshot), restore verification and API deploy/migrate runbooks are absent from the deliverable
- **IR-12** (MAJOR) No metrics, no alert routing, error tracker optional (LOG-006 is mandatory in P0)
- **IR-15** (MAJOR) Lead edit 'Re-apply mine' after a version conflict silently reverts the other writer's committed changes
- **IR-19** (MAJOR) SPA route changes never update the document title nor move focus/announce navigation (WCAG 2.4.2 Level A)
- **IR-20** (MINOR) Path C (emailed enrollment link + password) replaces an existing ACTIVE factor without step-up by that factor; open enrollment links survive enrollment by another path
- **IR-21** (MINOR) Resending an invitation does not revoke earlier invite_context challenges; link replay mints parallel contexts and overwrites the password
- **IR-22** (MINOR) IPv6 /64 network grouping is string-based and breaks on compressed addresses, defeating per-network throttle and CAPTCHA and causing false global lockouts
- **IR-23** (MINOR) Certified 5/min per-email login limit lets anyone lock a known account out from every network
- **IR-24** (MINOR) Password re-entry (reauth) and change-password are not throttled; password guessing with a stolen bearer then satisfies password-based step-up
- **IR-25** (MINOR) Security-event gaps: no event on MFA-path invite password set, invalid action tokens, CSRF-rejected refresh, MFA throttle and per-network throttle activation; erasure refusal event rolled back
- **IR-26** (MINOR) Security-log archival deletes events it never exported when event time and chain order disagree near the cutoff
- **IR-27** (MINOR) Unhandled exceptions and DB errors log raw PII (stdlib loggers bypass structlog masking; engine lacks hide_parameters)
- **IR-28** (MINOR) An erased (anonymised) lead still accepts notes, activities and status changes, re-introducing PII after erasure is reported complete
- **IR-29** (MINOR) Plain-text staff notification emails can be content-spoofed via newlines in public form fields
- **IR-30** (MINOR) Outbox retry resends email to recipients who already received it
- **IR-35** (MINOR) Single-process/instance constraint is enforced only by a text match on gunicorn.conf.py; client IP trusted from CF-Connecting-IP without a trusted-proxy check
- **IR-36** (MINOR) 'Sign out everywhere' leaves the user on /profile with stale personal data displayed
- **IR-37** (MINOR) Accessibility gaps: 360 px status stepper not keyboard-scrollable (axe serious), unreliable toast announcements, no MFA-timeout warning, window.prompt for sensitive reason, incomplete listbox/menu/tab semantics
- **IR-38** (MINOR) Browser E2E evidence overstates coverage and security-critical modules have the lowest coverage
- All unexecuted production gates in implementation report §16 (OWNER-INPUT-001..004, PG-DAST, RG-1..RG-7, browser/device matrix, SES production access).

**Feature-gated (public intake: must hold before `veda-api-base` is set):**
- **IR-02** (MAJOR) Cloudflare Turnstile siteverify (up to 5 s network I/O) runs while the database-wide SQLite write lock is held (public intake and CAPTCHA-gated login)
- **IR-17** (MAJOR) Enquiry form remains visible after success/fallback ([hidden] overridden by .contact-form{display:grid}); resubmission reports a false failure
- **IR-18** (MAJOR) Turnstile token is never reset; after any server-side 422 the corrected resubmission reuses a spent token and fails CAPTCHA
- **IR-31** (MINOR) UNKNOWN_POLICY_VERSION is shown as an inline field error with no WhatsApp route
- **IR-32** (MINOR) Enquiry-form prerequisites absent: /privacy page missing, no site CSP, Turnstile site key unset, showErrors() uses innerHTML with server strings, #form-note contrast 4.06:1

**PostgreSQL release gate (PGM-1):** IR-33, IR-A01, IR-A16, plus the SQLite→PostgreSQL data-migration rehearsal (11 §3.4).

## 19. Architecture amendments required

| # | Document / section | Amendment | Trigger |
|---|---|---|---|
| AM-1 | 03 §5.5 | Key `ux_user_mfa_factor__user_live` on `(user_id, factor_type, status)` | DEV-001 |
| AM-2 | 08 §4.5, 05 §11.3 | Document 200 `MFA_ENROLLMENT_REQUIRED` + `invite_context`; acknowledge that path B's second proof is link possession | DEV-002 |
| AM-3 | 08 §4.1, §4.7 | Optional `turnstile_token`; `captcha_required` and `attempts_remaining` response fields | DEV-003 |
| AM-4 | 04 §5.4 vs 08 §8.5; LEAD-027 | Reconcile the re-consent mechanism; decide in-row or append-only retention of prior consent | DEV-004 |
| AM-5 | 08 §1, 06 §11 (RBX-003), 09 | Add `POST /api/v1/approvals/cancel-link` and the `/approvals/cancel` page | DEV-005 / IR-07 |
| AM-6 | LOG-005, 08 §3, 02 §12.4 | Readiness semantics "at or compatibly ahead of image head" | IR-10 |
| AM-7 | 08 §12 | Per-email login/forgot limits keyed with network, or failure-only | IR-23 |
| AM-8 | 05 / 03 (OI-3) | Document HMAC-derived action-token trade-off and key-rotation effect | IR-A22 |
| AM-9 | 06 §7.5 | Owner decision on repeated sole-Founder cancellation of custodian break-glass | IR-A11 |
| AM-10 | 07 §2 | Extend `pii_fields` to free-text consent/loss/activity fields; IP retention after erasure | IR-A15 |

## 20. Final report (A–AA)

| Key | Item | Result |
|---|---|---|
| A | Architecture SHA | `778aa8fdd918da48340319696ada3ff673e9fb8e` |
| B | Implementation SHA | `9236aa3ade38c33d03a57cf7a064ece29937b109` |
| C | Review branch | `review/p0-independent-implementation-review` |
| D | Review commit SHA | Recorded in the commit that adds this file (see `git log` on the review branch) |
| E | Push status | Pushed normally (no force) |
| F | Scope and diff verification | Passed. One commit on top of the certified SHA; architecture byte-identical; `dist/` limited to the enquiry form; no secrets or generated artefacts (§2) |
| G | Architecture conformity | Schema exact. Most requirements conformant. Non-conformant: MFA-011, MFA-012, SEVT-007, LOG-003, LOG-006, OPS-002, OPS-009. UI-005 deviates (§4) |
| H | Tables / migrations | 24 tables, 502 columns, 72 indexes, 107 FKs, 9 revisions, one head, on SQLite and PG16.4 (§7) |
| I | API recount | 105 routes confirmed; 08 diff: `leads/exports` (P1) absent, `approvals/cancel-link` extra (§9, App. C) |
| J | Backend tests | SQLite 273/0/0 reproduced |
| K | PostgreSQL tests | 18.4: 271/0/2 reproduced. **16.4: 271/0/2** (new) |
| L | Frontend tests | 47 passed; typecheck, build, contrast pass; runtime audit 0; dev audit 195 (Nexus) / 7 (GHSA) |
| M | Browser tests | workspace 7/7, access 12/12, site 7/7, axe as reported. Evidence gaps IR-38 |
| N | Security review | 1 BLOCKER (IR-01 MFA/step-up bypass); MAJOR IR-02, IR-03, IR-09, IR-13 |
| O | RBAC / authorization | Core RBAC sound under about 120 bypass attempts; governance defects IR-04 to IR-08 |
| P | Lead workflow | Sound intake core; DEV-004 rejected; intake not ready to enable (IR-02, IR-17, IR-18, IR-31, IR-32) |
| Q | Audit / security events | Three prior defects fixed; chain anchoring ineffective (IR-03); archival boundary loss (IR-26) |
| R | Deviation decisions | DEV-001, DEV-002, DEV-003: ACCEPTABLE WITH ARCHITECTURE AMENDMENT. DEV-004: REQUIRES IMPLEMENTATION CHANGE |
| S | Break-glass endpoint | Premise incorrect: 08 has no such endpoint; the implemented `cancel-link` is secure but unregistered and its SPA page is missing. REQUIRES IMPLEMENTATION CHANGE plus architecture amendment; register as DEV-005 |
| T | Open issues | 11 assessed (§15); the register is materially incomplete |
| U | Findings by severity | BLOCKER 1 · MAJOR 18 · MINOR 20 · ADVISORY 25 |
| V | Merge blockers | §18 |
| W | Staging blockers | §18 |
| X | Production blockers | §18 |
| Y | Architecture amendments | AM-1 … AM-10 (§19) |
| Z | Exact next authorized action | **Owner decision only.** No merge, no deployment. The next step is the owner's decision whether to authorize a remediation workstream on `implementation/p0-foundation` as new commits (no history rewrite) addressing IR-01 first, then the merge-scoped MAJOR findings, plus Architecture-Owner decisions on AM-1 to AM-5. A targeted independent re-review then follows against the new frozen SHA |
| AA | Final verdict | **NOT CERTIFIED** |

### Verdict rationale

**NOT CERTIFIED.**

- **A BLOCKER exists.** IR-01 is a reproduced bypass of MFA step-up and of MFA-gated sensitive permissions on both engines.
- **Material MAJOR findings remain in merge scope:**
  - IR-04: Founder-governance bypass.
  - IR-08: Founder deletion broken.
  - IR-14: CI never executed and missing gates.
  - IR-16: DEV-004.
  - IR-13: no dependency lock (recommended).
- **Further MAJOR findings block staging or production:** IR-09, IR-02, IR-03, IR-05, IR-06, IR-07, IR-10, IR-11, IR-12, IR-15, IR-19.

The implementation is otherwise well-structured, and its core controls held under adversarial probing:
- schema exactness;
- migration discipline;
- default-deny RBAC with DENY-over-GRANT;
- refresh-token rotation;
- idempotent intake;
- a correctly constructed audit and security-event hash chain.

A certification with conditions is not available while a BLOCKER stands.

---

## Appendices

Appendices B to F are the domain reviewers' working tables, included verbatim as evidence. Their local finding identifiers (F-xx / A-xx) map to the consolidated IR identifiers as follows.

| Working paper | Local ID → consolidated ID |
|---|---|
| Auth/MFA (App. B) | F-01→IR-01 · F-02→IR-20 · F-03→IR-21 · F-04→IR-22 · F-05→IR-23 · F-06→IR-09 · F-07→IR-24 · F-08→IR-A04 · F-09, F-10→IR-25 · F-11→IR-A01 · F-12→IR-A02 · F-13→IR-A03 · F-14→IR-27 |
| RBAC/governance (App. C) | F-1→IR-08 · F-2→IR-06 · F-3→IR-05 · F-4→IR-07 · F-5→IR-04 (**raised MINOR→MAJOR by lead reviewer**) · A-1→IR-A05 · A-3→IR-A06 · A-4, A-5→IR-A07 · A-8→IR-A08 · A-9→IR-A09 · A-10→IR-A10 · A-11→IR-A11 |
| Leads/audit/notifications (App. D) | F-01→IR-02 · F-02→IR-03 · F-03→IR-26 · F-04→IR-16 (**raised MINOR→MAJOR**: deviation classified REQUIRES IMPLEMENTATION CHANGE) · F-05→IR-27 · F-06→IR-28 · F-07→IR-25 · F-08→IR-29 · F-09→IR-30 · F-10→IR-31 · F-11→IR-32 · F-12→IR-33 · F-13→IR-A12 · F-14→IR-A13 · F-15→IR-A14 · F-16→IR-A15 · F-17→IR-A16 · F-18→IR-A25 · F-19→IR-A23 |
| DB/ops (App. E) | F-01→IR-10 · F-02→IR-09 · F-03→IR-11 · F-04→IR-12 · F-05→IR-13 · F-06→IR-33 · F-07→IR-27 · F-08→IR-34 · F-09, F-10→IR-35 · F-11→IR-A17 · F-12, F-13→IR-A18 · F-15→IR-A19 · F-16→IR-14 (**raised ADVISORY→MAJOR**) · F-19→IR-A20. Note: E §7 states the full PG16 suite was not run by that reviewer; the lead reviewer ran it (271/0/2) |
| Frontend (App. F) | F-1→IR-15 · F-2→IR-17 · F-3→IR-18 · F-4→IR-19 · F-5→IR-36 · F-6, F-7→IR-32 · F-8→IR-A21 · F-9→IR-38 · F-10→IR-14, IR-39 · F-11→IR-37 · F-12→IR-A21, IR-A23 |

### Appendix A — Probe and command index

| Area | Probes |
|---|---|
| Lead reviewer | test runs (SQLite, PG18.4, PG16.4), coverage, ruff, bandit, pip-audit, detect-secrets and regex secret scan, `deploy-check`, source verification of IR-01, IR-02, IR-04, IR-09, IR-10, IR-15, IR-17 |
| Auth/MFA | P1, P1b, P2, P2b, P3, P3b, P4–P11 (15 probe tests; P1, P1b, P8, P10, P11 also on PostgreSQL) |
| RBAC/governance | P01–P17 (22 probe tests; P10, P11, P13, P15 also on PostgreSQL); runtime `url_map` inventory |
| Leads/audit/notifications | P1–P6, Q1–Q6 (SQLite and PostgreSQL where stated) |
| DB/ops | `probe_migrations.py`, `probe_immutability.py`, `probe_occ.py`, `probe_ops.py`, `diff_spec.py` (SQLite 3.50.4 and PG16.4) |
| Frontend | npm ci/audit/typecheck/lint/test/build; four e2e scripts against a local stack; `probe-app*.mjs`, `probe-site*.mjs`, `csp-server.mjs`; axe on baseline `778aa8f` and `9236aa3` |

### Appendix B — Authentication and MFA working paper

#### B.1 Requirement conformance

| ID | Classification | Evidence |
|---|---|---|
| AUTH-001 | Conformant | `veda/platform/auth/service.py:222-305` login flow; `routes.py:43-46`. |
| AUTH-002 | Conformant | `passwords.py:39` uses Argon2id (argon2-cffi default type ID) with 16-byte salt, 32-byte hash; `config.py:68-71` defaults m=64 MiB, t=3, p=1; `config.py:229-230` rejects values below the OWASP floor in production; rehash on login at `service.py:291-292`; semaphore at `passwords.py:41,52`. |
| AUTH-003 | Partially conformant | `passwords.py:78-98` covers length 12–128, NFKC, a small bundled blocklist, email local-part, name and veda/vedaspaces. The blocklist has about 50 entries, which is far short of a "common/breached list". The HIBP check is P1. The same-password check exists only against the current password (`service.py:452,472`), as specified. |
| AUTH-004 | Conformant (P0 scope) | `jwt_tokens.py`: ES256 only, `typ`=at+jwt, `kid` lookup, iss/aud/required claims, 15 min. Probe P6: `none`, HS256 and payload tampering all return 401. JWKS is served at `routes.py:83-87`. In non-production environments the key is derived from a public constant (F-06). |
| AUTH-005 | Conformant | `service.py:338-393`: SHA-256-hashed 256-bit tokens, rotation, 20 s grace that returns an access token only (no Set-Cookie), reuse → session revoked plus `REFRESH_REUSE_DETECTED`. Cookie flags at `service.py:117-122`. Probe P7: HttpOnly, SameSite=Strict, Path=/api/v1/auth. Grace returns 200 without Set-Cookie; second reuse returns 401; successor returns 401 after theft detection; missing CSRF headers return 403. Secure=False appears only because test settings turn it off; production forces it (`config.py:227`). |
| AUTH-006 | Conformant | `request_auth.py:131-181`: uncached join of `user_session` and `app_user`; checks revoked, idle, absolute, status and deleted. |
| AUTH-007 | Conformant | `routes.py:62-80`. |
| AUTH-008 | Conformant | `service.py:428-459`: invalidates earlier tokens, 30 min, hash stored, single use, sent only to the verified email, revokes all sessions, MFA untouched. The token is HMAC-derived rather than random (see §2 OI-3). |
| AUTH-009 | Conformant (minor residual) | Uniform 401 across unknown, invited, disabled and throttled (P3b, P10). The captcha signal is identical for known and unknown accounts (P10). There is a residual timing delta of about 1.2–1.6 ms on about 95 ms (F-12). |
| AUTH-010 | Partially conformant | Per-pair, global and MFA throttles are implemented (`throttle.py`). IPv6 network grouping is wrong for compressed addresses (F-04). The certified per-email rate limit lets an attacker lock a victim out (F-05). |
| AUTH-011 | Conformant with DEV-002 | `service.py:500-535`; see §2 and F-03. |
| AUTH-012 | Conformant | `service.py:462-486`: needs the current password, blocked during cooling-off, revokes other sessions, rotates the refresh token. Password guessing through this endpoint is not throttled (F-07). |
| AUTH-013 | Partially conformant | Refresh success and failure events are written, but a CSRF-rejected refresh writes no `TOKEN_REFRESH` (`routes.py:49-51`: `check_csrf` runs before the service). Setting an invite password writes no event (F-09). |
| AUTH-014 | Conformant | `cli/main.py:69-99`. |
| AUTH-015 | Partially conformant | Policy enforcement exists, but F-01 lets MFA verification be attached to the wrong principal. |
| AUTH-016 | Conformant | `routes.py:216-237`; admin revoke in `rbac/users.py:228-235`. |
| AUTH-017 | Conformant | `rbac/users.py:124-135,144-156`: revokes sessions and invalidates tokens and challenges. |
| AUTH-018 | Conformant | Personas are data-driven (resolver). |
| MFA-001 | Conformant | `totp.py`: RFC 6238, SHA-1, 6 digits, ±1 step. |
| MFA-002/003/004 | Conformant | Resolver-based; no role-name checks found in the auth code. |
| MFA-005 | Conformant | `crypto.py:42-53`: 10 codes, 50 bits, HMAC under K_recovery, single use (P9 reuse → 401), rotated at every enrollment (`mfa.py:242-254`), regeneration needs step-up. |
| MFA-006 | Partially conformant | MFA throttle activation writes no `ACCOUNT_THROTTLED` event (F-10). |
| MFA-007/015 | Out of scope (RBAC reviewer). The `admin_reset` effect (`mfa.py:401-422`) is conformant. |
| MFA-008 | Conformant | No SMS, email-OTP or remember-device paths exist. |
| MFA-009 | Conformant | Replay rejection `totp.py:41-51` with `last_used_step`; 5 attempts per challenge; 10 per account in 15 min (`throttle.py:111-121`). Per-challenge counting can be raced on PostgreSQL (advisory). |
| MFA-010 | Conformant | AES-256-GCM with a KMS-wrapped data key (`crypto.py:116-127`); AWS KMS is forced in production; the secret is shown once. |
| MFA-011 | **Non-conformant** | Step-up is bypassable through F-01 (reproduced, P1b). |
| MFA-012 | **Non-conformant** | Sensitive permission is activated in another user's pwd-only session through F-01 (reproduced, P1). |
| MFA-013 | Conformant | `mfa.py:126-161`; P9 shows the recovery-session allow-list, challenge replay → 401, and consumed code → 401. |
| MFA-014 | **Partially conformant** | Paths A–D exist, but path C can replace an ACTIVE factor without that factor (F-02), and confirm is not bound to the principal (F-01). |
| SEC-001/003 | Conformant (code) | HSTS, CSP and nosniff at `app.py:102-113`. |
| SEC-002 | Conformant | `app.py:142-151`: credentials only for `app_origin`. The CSRF allow-list is wider than needed (F-13). |
| SEC-004 | Conformant | Closed pydantic schemas with lengths (`routes.py`). |
| SEC-005 | Partially conformant | Production guard at `config.py:207-233`. Every other `VEDA_ENV` value, including `staging` or a typo, silently falls back to public dev keys (F-06). |
| SEC-006 | Untested / deployment | The code trusts `CF-Connecting-IP` unconditionally (`kernel/http.py:146-149`, `kernel/ratelimit.py:16-17`). This is safe only if the origin really accepts Cloudflare traffic alone. |
| SEC-007..010 | N/A for this scope | |
| SEC-011 | Partially conformant | Limits exist (`routes.py`), but see F-05 (victim lockout) and F-04. |

#### B.2 Probes

All probes are in `scratchpad/probes/auth/api_copy/tests/integration/test_probe_auth.py`. Output is in `scratchpad/probes/auth/probe_run_sqlite.txt`. Engines: SQLite for all; PostgreSQL additionally for P1, P1b, P8, P10 and P11.

| Probe | Purpose | Result |
|---|---|---|
| Baseline | `test_auth.py` and `test_mfa.py` | 38 passed |
| P1 | Cross-user confirm upgrades a foreign pwd-only session | Reproduced (F-01) |
| P1b | Step-up bypass on an Admin session through the attacker's own path C challenge | Reproduced (F-01) |
| P2 / P2b | Path C replaces an ACTIVE factor; link survives path A enrollment | Reproduced (F-02) |
| P3 | Old invite_context survives resend; parallel contexts | Reproduced (F-03) |
| P3b | INVITED login, context single use, invite replay after activation | Correct |
| P4 | IPv6 /64 grouping and CAPTCHA trigger | Reproduced (F-04) |
| P5 | Per-email limit locks out a victim from another network | Reproduced (F-05) |
| P6 | JWT `none`, HS256 and payload tampering | All 401 (correct) |
| P6b | Staging config: dev JWT, action key and turnstile | Reproduced (F-06) |
| P7 | Refresh cookie flags, CSRF, rotation, grace, reuse | Correct |
| P8 | DEV-001: second ACTIVE rejected, PENDING never authenticates, old factor works | Correct (both engines) |
| P9 | Recovery-session allow-list, bad password, challenge and code replay | Correct |
| P10 | DEV-003: CAPTCHA signal uniform for known and unknown accounts; valid CAPTCHA does not lift the delay | Correct |
| P11 | Login timing, unknown vs known | Delta of about 1.2–1.6 ms (F-12) |

### Appendix C — RBAC and Founder-governance working paper

#### C.1 Route inventory: counting and fail-closed verification

| Item | Result | Evidence |
|---|---|---|
| `app.url_map` rules | 107 | `route_inventory.py` output |
| Excluding `static` and `openapi` | 105 rules, each with exactly one non-HEAD/OPTIONS method → **105 routes** | same |
| `http.ROUTES` specs | 105, 105 unique endpoints, all present in url_map (no orphan spec) | same |
| HEAD | Auto-added for GETs. It goes through the same `dispatch(spec)`, so auth is enforced (HEAD /api/v1/users unauth → 401) | P17 REPRODUCED |
| OPTIONS | Answered in `before_request` (`app.py:94-100`) with 204 and no data. ACAO is only for the configured origin (foreign origin → no ACAO) | P17 REPRODUCED |
| `static` | Flask default `/static/<path:filename>`. No static folder ships, so it serves nothing. Excluded from the check by name (`app.py:45`) | SOURCE-INSPECTED |
| `openapi.json` | Registered **after** the check (`app.py:87-92`), only when `not settings.is_production`. Unauthenticated (P17 → 200), matching 08 §2.1 ("served at staging") | REPRODUCED |
| Startup check | `check_route_declarations` (`app.py:41-49`) raises `RuntimeError` if any url_map endpoint lacks a `RouteSpec` or `spec.declared` is false (`http.py:69-70`: permission or any_of or rbx). It runs after all blueprints register and before the app is returned, so it fails closed for routes registered through `Api.route` or raw `add_url_rule`. Test `test_startup_fails_for_undeclared_route` covers it | SOURCE-INSPECTED |
| Bypass potential | (a) Routes added **after** `create_app` returns (only `openapi`, by design) are not checked. (b) The check is **presence-only**: it does not verify that an `rbx` id exists in the 06 §11 register, that the path is listed under that id, or that `auth="public"` ⇒ rbx. The last point is covered by lint test `test_lint.py:50`, not at startup. (c) For `auth="public"` routes any declared `permission` would be silently unenforced, because `enforce_gates` only runs when a ctx exists (`http.py:473-474`). No current route is affected. See ADVISORY A-1 | SOURCE-INSPECTED |
| Error handlers | `HTTPException`/`Exception` handlers only format problem responses. They create no routes and bypass no gates | SOURCE-INSPECTED |
| Pre-auth ordering | Path-id validation and body parsing run before authentication (`http.py:457-466`): unauth `POST /users/not-an-id/status` → 422 `INVALID_ID`, with a valid id → 401. This leaks only syntax validity (ADVISORY A-7) | P17 REPRODUCED |

#### C.1 Route inventory: full table (runtime url_map)

Columns: the sensitivity class is that of the declared code(s). "Step-up/guards" is source-inspected per handler; "MFA" means sensitive codes are effective only in an MFA-verified FULL session outside cooling-off (`resolver.py:157-179`). The audit column is uniform: every write goes through the kernel `before_flush` hook (`kernel/audit_hook.py:154`), which writes `audit_log` rows for FULL-policy entities in the same transaction, so it is not repeated per row. The rate-limit column is **"none"** except for the listed auth/public routes. The 08 §12 "authenticated user, all endpoints 600 req / 5 min" limit is not implemented (the `Limiter` has no `default_limits`; ADVISORY A-8).

| # | Method | Path | Pub/Priv | AuthN | Permission / RBX | Sensitive class | MFA / step-up / guards | Resource scope | Security event(s) | Rate limit | Req |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/v1/activities` | private | Bearer JWT + live session row | lead_activity.read | — | — | lead.read scope OWN/ALL (404 outside) | PERMISSION_DENIED on 403 | none | LEAD-015 |
| 2 | GET | `/api/v1/approvals` | private | Bearer JWT + live session row | user.mfa.reset / user.email.change / user.founder.manage (any) | ACCOUNT_CONTROL | MFA-verified session | visibility filter (`_visible`) | PERMISSION_DENIED on 403 | none | RBAC-021 |
| 3 | GET | `/api/v1/approvals/{approval_id}` | private | Bearer | same any-of | ACCOUNT_CONTROL | MFA-verified session | visibility filter → 404 | PERMISSION_DENIED on 403 | none | RBAC-021 |
| 4 | POST | `/api/v1/approvals/{approval_id}/approve` | private | Bearer | same any-of | ACCOUNT_CONTROL | step-up; eligibility 06 §7.2.3/§7.4; G9 approver | `session.get` (no visibility filter; ineligible → 403, see A-5) | FOUNDER_ACTION_APPROVED / APPROVAL_APPROVED, *_EXECUTED/FAILED, SENSITIVE_ACTION | none | RBAC-021 |
| 5 | POST | `/api/v1/approvals/{approval_id}/cancel` | private | Bearer | same any-of | ACCOUNT_CONTROL | requester only (no step-up) | requester only (others → 404) | FOUNDER_ACTION_CANCELLED / APPROVAL_CANCELLED | none | RBAC-021 |
| 6 | POST | `/api/v1/approvals/{approval_id}/deny` | private | Bearer | same any-of | ACCOUNT_CONTROL | step-up; eligibility | `session.get` (no visibility filter) | FOUNDER_ACTION_DENIED / APPROVAL_DENIED (no SENSITIVE_ACTION, A-4) | none | RBAC-021 |
| 7 | POST | `/api/v1/approvals/cancel-link` | **public** | none | RBX-003 (not in 06 §11 list) | — | single-use HMAC token | token → request binding | BREAK_GLASS_CANCELLED | **none** | RBAC-021 |
| 8 | GET | `/api/v1/audit-logs` | private | Bearer | audit.read | SECURITY_DATA | MFA-verified session | n/a (PII masking per 06 §8) | SENSITIVE_READ (15-min dedupe) | none | AUDIT-008 |
| 9 | GET | `/api/v1/audit-logs/{audit_id}` | private | Bearer | audit.read | SECURITY_DATA | MFA | n/a | SENSITIVE_READ | none | AUDIT-008 |
| 10 | GET | `/api/v1/auth/.well-known/jwks.json` | public | none | RBX-006 | — | — | n/a | — | none | AUTH-004 |
| 11 | POST | `/api/v1/auth/email/cancel` | public | none | RBX-003 | — | single-use token | token | flow-specific | none | USER-007 |
| 12 | POST | `/api/v1/auth/email/verify` | public | none | RBX-003 | — | single-use token | token | flow-specific | none | USER-007 |
| 13 | POST | `/api/v1/auth/invite/accept` | public | none | RBX-003 | — | single-use token | token | flow-specific | 10/min | AUTH-011 |
| 14 | POST | `/api/v1/auth/login` | public | none | RBX-001 | — | — | n/a | flow-specific | 10/min IP + 5/min email | AUTH-001 |
| 15 | POST | `/api/v1/auth/logout` | private | Bearer | RBX-002 | — | RECOVERY + pwd-change allowed | own session | flow-specific | none | AUTH-007 |
| 16 | POST | `/api/v1/auth/logout-all` | private | Bearer | RBX-002 | — | — | own sessions | flow-specific | none | AUTH-007 |
| 17 | GET | `/api/v1/auth/me` | private | Bearer | profile.read | — | RECOVERY + pwd-change allowed | self | — | none | USER-004 |
| 18 | PATCH | `/api/v1/auth/me` | private | Bearer | profile.update | — | closed DTO | self | — | none | USER-004 |
| 19 | PUT | `/api/v1/auth/me/email` | private | Bearer | RBX-004 | — | step-up (MFA or password) | self | flow-specific | none | USER-007 |
| 20 | GET | `/api/v1/auth/mfa` | private | Bearer | profile.read | — | — | self | — | none | MFA-001 |
| 21 | POST | `/api/v1/auth/mfa/enroll/confirm` | private/optional | optional bearer / enrollment token | RBX-004 | — | RECOVERY-allowed | self | flow-specific | 10/min | MFA-014 |
| 22 | POST | `/api/v1/auth/mfa/enroll/start` | private/optional | optional bearer / enrollment token | RBX-004 | — | RECOVERY-allowed | self | flow-specific | 10/min | MFA-014 |
| 23 | DELETE | `/api/v1/auth/mfa/factor` | private | Bearer | RBX-004 | — | step-up | self | flow-specific | none | MFA-003 |
| 24 | POST | `/api/v1/auth/mfa/recovery` | public | none | RBX-001 | — | challenge + password + code | n/a | flow-specific | 10/min | MFA-013 |
| 25 | POST | `/api/v1/auth/mfa/recovery-codes` | private | Bearer | RBX-004 | — | step-up | self | flow-specific | none | MFA-005 |
| 26 | POST | `/api/v1/auth/mfa/step-up` | private | Bearer | RBX-004 | — | — | self | flow-specific | 10/min | MFA-011 |
| 27 | POST | `/api/v1/auth/mfa/verify` | public | none | RBX-001 | — | challenge token | n/a | flow-specific | 10/min | MFA-001 |
| 28 | POST | `/api/v1/auth/password/change` | private | Bearer | RBX-004 | — | pwd-change allowed | self | flow-specific | none | AUTH-012 |
| 29 | POST | `/api/v1/auth/password/forgot` | public | none | RBX-003 | — | — | n/a | flow-specific | 5/min IP + 3/h email | AUTH-008 |
| 30 | POST | `/api/v1/auth/password/reset` | public | none | RBX-003 | — | single-use token | token | flow-specific | 5/min | AUTH-008 |
| 31 | POST | `/api/v1/auth/reauth` | private | Bearer | RBX-004 | — | — | self | flow-specific | none | MFA-011 |
| 32 | POST | `/api/v1/auth/refresh` | public | refresh cookie | RBX-002 | — | — | own session | flow-specific | none | AUTH-005 |
| 33 | GET | `/api/v1/auth/sessions` | private | Bearer | session.read | — | — | OWN (hard-coded) | — | none | AUTH-016 |
| 34 | DELETE | `/api/v1/auth/sessions/{session_id}` | private | Bearer | session.revoke | — | — | OWN (other user's → 404) | — | none | AUTH-016 |
| 35 | POST | `/api/v1/founder-actions` | private | Bearer | user.founder.manage | ACCOUNT_CONTROL | step-up; Founder eligibility 06 §7.2.3 | target by id | FOUNDER_ACTION_REQUESTED (+BREAK_GLASS_REQUESTED), SENSITIVE_ACTION | none | RBAC-021 |
| 36 | GET | `/api/v1/leads` | private | Bearer | lead.read | — | — | scope-filtered list | — | none | LEAD-013 |
| 37 | POST | `/api/v1/leads` | private | Bearer | lead.create | — | — | n/a (create) | — | none | LEAD-003 |
| 38 | DELETE | `/api/v1/leads/{lead_id}` | private | Bearer | lead.delete | DESTRUCTIVE | MFA (no step-up per G10) | OWN/ALL → 404 | SENSITIVE_ACTION | none | LEAD-016 |
| 39 | GET | `/api/v1/leads/{lead_id}` | private | Bearer | lead.read | — | — | OWN/ALL → 404 | — | none | LEAD-013 |
| 40 | PATCH | `/api/v1/leads/{lead_id}` | private | Bearer | lead.update | — | — | OWN/ALL → 404 | — | none | LEAD-024 |
| 41 | GET | `/api/v1/leads/{lead_id}/activities` | private | Bearer | lead_activity.read | — | — | parent lead scope → 404 | — | none | ACT-001 |
| 42 | POST | `/api/v1/leads/{lead_id}/activities` | private | Bearer | lead_activity.create | — | — | parent lead scope → 404 | — | none | ACT-001 |
| 43 | DELETE | `/api/v1/leads/{lead_id}/activities/{activity_id}` | private | Bearer | lead_activity.delete | — | — | parent scope + owner → 404 | — | none | ACT-002 |
| 44 | PATCH | `/api/v1/leads/{lead_id}/activities/{activity_id}` | private | Bearer | lead_activity.update | — | — | parent scope + owner → 404 | — | none | ACT-002 |
| 45 | POST | `/api/v1/leads/{lead_id}/activities/{activity_id}/cancel` | private | Bearer | lead_activity.update | — | — | same | — | none | ACT-003 |
| 46 | POST | `/api/v1/leads/{lead_id}/activities/{activity_id}/complete` | private | Bearer | lead_activity.update | — | — | same | — | none | ACT-003 |
| 47 | POST | `/api/v1/leads/{lead_id}/assign` | private | Bearer | lead.assign | — | — | lead scope | — | none | LEAD-007 |
| 48 | POST | `/api/v1/leads/{lead_id}/consent/withdraw` | private | Bearer | lead.update | — | — | lead scope | — | none | LEAD-027 |
| 49 | POST | `/api/v1/leads/{lead_id}/duplicate-resolution` | private | Bearer | lead.update | — | — | lead scope | — | none | LEAD-010 |
| 50 | POST | `/api/v1/leads/{lead_id}/erasure` | private | Bearer | lead.erase | DESTRUCTIVE | step-up | lead scope | SENSITIVE_ACTION | none | LEAD-029 |
| 51 | GET | `/api/v1/leads/{lead_id}/history` | private | Bearer | lead.read + audit.read | SECURITY_DATA | MFA | lead scope | SENSITIVE_READ | none | AUDIT-006 |
| 52 | GET | `/api/v1/leads/{lead_id}/notes` | private | Bearer | lead_note.read | — | — | parent lead scope → 404 | — | none | NOTE-001 |
| 53 | POST | `/api/v1/leads/{lead_id}/notes` | private | Bearer | lead_note.create | — | — | parent lead scope → 404 | — | none | NOTE-001 |
| 54 | DELETE | `/api/v1/leads/{lead_id}/notes/{note_id}` | private | Bearer | lead_note.delete | — | — | parent scope + author | — | none | NOTE-002 |
| 55 | PATCH | `/api/v1/leads/{lead_id}/notes/{note_id}` | private | Bearer | lead_note.update | — | — | parent scope + author | — | none | NOTE-002 |
| 56 | POST | `/api/v1/leads/{lead_id}/restore` | private | Bearer | lead.restore | — | — | lead scope | — | none | LEAD-016 |
| 57 | POST | `/api/v1/leads/{lead_id}/spam-resolution` | private | Bearer | lead.update | — | — | lead scope | — | none | LEAD-018 |
| 58 | POST | `/api/v1/leads/{lead_id}/status` | private | Bearer | lead.status.change / lead.reopen (any-of; transition-specific check in handler) | — | — | lead scope → 404 | — | none | LEAD-005 |
| 59 | GET | `/api/v1/leads/duplicates` | private | Bearer | lead.read | — | — | scope-filtered | — | none | LEAD-010 |
| 60 | GET | `/api/v1/leads/summary` | private | Bearer | lead.read | — | — | scope-filtered | — | none | LEAD-014 |
| 61 | GET | `/api/v1/lookups` | private | Bearer | lookup.read | — | — | n/a | — | none | PLAT-009 |
| 62 | GET | `/api/v1/lookups/{category_code}` | private | Bearer | lookup.read | — | — | n/a | — | none | PLAT-009 |
| 63 | POST | `/api/v1/lookups/{category_code}/values` | private | Bearer | lookup.manage | — | — | n/a | — | none | PLAT-009 |
| 64 | PATCH | `/api/v1/lookups/{category_code}/values/{value_id}` | private | Bearer | lookup.manage | — | — | n/a | — | none | PLAT-009 |
| 65 | GET | `/api/v1/notifications` | private | Bearer | notification.read | — | — | OWN (recipient) | — | none | NOTIF-001 |
| 66 | POST | `/api/v1/notifications/{notification_id}/read` | private | Bearer | notification.read | — | — | OWN (else 404) | — | none | NOTIF-001 |
| 67 | POST | `/api/v1/notifications/read-all` | private | Bearer | notification.read | — | — | OWN | — | none | NOTIF-001 |
| 68 | GET | `/api/v1/permissions` | private | Bearer | permission.read | — | — | n/a | — | none | RBAC-004 |
| 69 | GET | `/api/v1/permissions/{permission_id}` | private | Bearer | permission.read | — | — | n/a | — | none | RBAC-004 |
| 70 | PATCH | `/api/v1/permissions/{permission_id}` | private | Bearer | permission.manage | ACCESS_CONTROL | step-up; closed DTO (name/description) | n/a | SENSITIVE_ACTION | none | RBAC-004 |
| 71 | GET | `/api/v1/permissions/{permission_id}/holders` | private | Bearer | permission.read + user.read | — | — | n/a | — | none | RBAC-016 |
| 72 | POST | `/api/v1/public/leads` | public | none | RBX-005 | — | Turnstile + idempotency | n/a (create) | PUBLIC_INTAKE_* | 20/min + 120/h IP | LEAD-001 |
| 73 | GET | `/api/v1/roles` | private | Bearer | role.read | — | — | n/a | — | none | RBAC-008 |
| 74 | POST | `/api/v1/roles` | private | Bearer | role.manage | ACCESS_CONTROL | step-up; G2 on copy; G13 | n/a | SENSITIVE_ACTION | none | RBAC-008 |
| 75 | DELETE | `/api/v1/roles/{role_id}` | private | Bearer | role.manage | ACCESS_CONTROL | step-up; G5 / G13 / ROLE_IN_USE | n/a | SENSITIVE_ACTION | none | RBAC-008 |
| 76 | GET | `/api/v1/roles/{role_id}` | private | Bearer | role.read | — | — | n/a | — | none | RBAC-008 |
| 77 | PATCH | `/api/v1/roles/{role_id}` | private | Bearer | role.manage | ACCESS_CONTROL | step-up; G13 (no self-held/G2 check, A-3) | n/a | SENSITIVE_ACTION | none | RBAC-008 |
| 78 | GET | `/api/v1/roles/{role_id}/permissions` | private | Bearer | role.read | — | — | n/a | — | none | RBAC-008 |
| 79 | PUT | `/api/v1/roles/{role_id}/permissions` | private | Bearer | role.manage | ACCESS_CONTROL | step-up; G1 per code, self-held role → 403, G4, G8, G13 | n/a | SENSITIVE_ACTION | none | RBAC-009 |
| 80 | GET | `/api/v1/roles/{role_id}/users` | private | Bearer | role.read + user.read | — | — | n/a | — | none | RBAC-008 |
| 81 | GET | `/api/v1/security-events` | private | Bearer | security_event.read | SECURITY_DATA | MFA | n/a (ALL-only) | SENSITIVE_READ | none | SEVT-005 |
| 82 | GET | `/api/v1/security-events/{event_id}` | private | Bearer | security_event.read | SECURITY_DATA | MFA | n/a | SENSITIVE_READ | none | SEVT-005 |
| 83 | GET | `/api/v1/users` | private | Bearer | user.read (+user.restore for include_deleted) | — | — | n/a | — | none | USER-001 |
| 84 | POST | `/api/v1/users` | private | Bearer | user.create (+user.role.manage if role_ids) | — | step-up only if roles contain sensitive perms; G2/G13 on roles | n/a | INVITE_SENT (+SENSITIVE_ACTION per sensitive role) | none | USER-001 |
| 85 | DELETE | `/api/v1/users/{user_id}` | private | Bearer | user.delete | ACCOUNT_CONTROL | step-up; G3/G4/G9/G11 | target by id | SENSITIVE_ACTION | none | USER-001 |
| 86 | GET | `/api/v1/users/{user_id}` | private | Bearer | user.read | — | — | target by id | — | none | USER-001 |
| 87 | PATCH | `/api/v1/users/{user_id}` | private | Bearer | user.profile.update | — | closed DTO; self → 403 | target by id | — | none | RBAC-019 |
| 88 | GET | `/api/v1/users/{user_id}/effective-permissions` | private | Bearer | user.read + permission.read | — | — | target by id | — | none | RBAC-016 |
| 89 | POST | `/api/v1/users/{user_id}/email-change` | private | Bearer | user.email.change | ACCOUNT_CONTROL | step-up; G3/G9/G11; dual (G12) if privileged | target by id | SENSITIVE_ACTION (+APPROVAL_REQUESTED) | none | USER-007 |
| 90 | POST | `/api/v1/users/{user_id}/invite/resend` | private | Bearer | user.create | — | G9 | target by id | INVITE_SENT | none | AUTH-011 |
| 91 | PUT | `/api/v1/users/{user_id}/mfa-requirement` | private | Bearer | user.mfa.require | ACCOUNT_CONTROL | step-up; G3/G9/G11 | target by id | SENSITIVE_ACTION | none | MFA-003 |
| 92 | POST | `/api/v1/users/{user_id}/mfa/reset` | private | Bearer | user.mfa.reset | ACCOUNT_CONTROL | step-up; G3/G9/G11; dual if privileged | target by id | SENSITIVE_ACTION, ADMIN_MFA_RESET_* | none | MFA-007 |
| 93 | POST | `/api/v1/users/{user_id}/password-reset` | private | Bearer | user.password.reset | — | G3/G9/G11 (no step-up; non-sensitive) | target by id | PASSWORD_RESET_REQUESTED | none | AUTH-008 |
| 94 | GET | `/api/v1/users/{user_id}/permissions` | private | Bearer | user.read | — | — | target by id | — | none | RBAC-006 |
| 95 | POST | `/api/v1/users/{user_id}/permissions` | private | Bearer | user.permission.manage | ACCESS_CONTROL | step-up; G1/G3/G4/G8/G9/G11/G13 | target by id | SENSITIVE_ACTION (+PERMISSION_SUSPENDED); G13 → FOUNDER_GOVERNANCE_BYPASS_BLOCKED | none | RBAC-006 |
| 96 | DELETE | `/api/v1/users/{user_id}/permissions/{grant_id}` | private | Bearer | user.permission.manage | ACCESS_CONTROL | step-up; G1 on DENY removal, G3/G4/G9/G11/G13 | grant.user_id must equal path user (else 404) | SENSITIVE_ACTION | none | RBAC-006 |
| 97 | POST | `/api/v1/users/{user_id}/restore` | private | Bearer | user.restore | — | G9 | target by id (incl. deleted) | — | none | USER-001 |
| 98 | GET | `/api/v1/users/{user_id}/roles` | private | Bearer | user.read | — | — | target by id | — | none | RBAC-008 |
| 99 | PUT | `/api/v1/users/{user_id}/roles` | private | Bearer | user.role.manage | ACCESS_CONTROL | step-up; G2/G3/G4/G9/G13; Founder target → G13 block | target by id | SENSITIVE_ACTION (+PERMISSION_SUSPENDED); G13 → BYPASS_BLOCKED | none | RBAC-009 |
| 100 | POST | `/api/v1/users/{user_id}/sessions/revoke` | private | Bearer | user.session.revoke | ACCOUNT_CONTROL | step-up; G3/G9/G11 | target by id | SENSITIVE_ACTION | none | AUTH-016 |
| 101 | POST | `/api/v1/users/{user_id}/status` | private | Bearer | user.status.manage | ACCOUNT_CONTROL | step-up; G3/G4/G9/G11 | target by id | SENSITIVE_ACTION | none | RBAC-019 |
| 102 | POST | `/api/v1/users/{user_id}/unlock` | private | Bearer | user.status.manage | ACCOUNT_CONTROL | step-up; G3/G9/G11 | target by id | SENSITIVE_ACTION, ACCOUNT_UNTHROTTLED | none | AUTH-010 |
| 103 | GET | `/api/v1/users/assignable` | private | Bearer | lead.assign | — | — | n/a | — | none | LEAD-007 |
| 104 | GET | `/health/live` | public | none | RBX-006 | — | — | n/a | — | none | LOG-005 |
| 105 | GET | `/health/ready` | public | none | RBX-006 | — | — | n/a | — | none | LOG-005 |
| — | GET | `/api/v1/openapi.json` | public (non-prod only) | none | *undeclared; excluded by name* | — | — | — | — | none | API-008 |
| — | GET | `/static/<path>` | Flask default | none | excluded by name | — | — | — | — | — | — |

#### C.2 08 §1 index vs implementation

Row by row, all 87 index rows (≈105 physical endpoints) were matched against the runtime inventory.

| Direction | Endpoint | Classification |
|---|---|---|
| In 08, **missing** in implementation | #75 `POST /api/v1/leads/exports` | **Acceptable scope exclusion**: marked P1 in 08 and ADR-009 |
| In implementation, **not in 08** | `POST /api/v1/approvals/cancel-link` (RBX-003, public) | Realises 06 §7.5 step 5. **Documentation mismatch** → 08 §1 and the 06 §11 RBX register need a row (see §3) |
| In implementation, not in 08 index | `GET /api/v1/openapi.json` (non-production) | Conformant with 08 §2.1 prose. Not an index row by nature |
| Gate differences (not path differences) | #45–#47 approvals: 08 says "the permission of the request's action". Implementation gates at route level with **any-of** (`user.mfa.reset`, `user.email.change`, `user.founder.manage`) and enforces the specific action's permission in `_visible` / `governance.approve/deny/cancel` | Conformant in effect (probes P06/P09) |
| | #66 `/leads/{id}/status`: `lead.status.change` / `lead.reopen` | Implemented as `any_of` + handler check. Conformant (not re-probed) |
| | #50 `PATCH /roles/{id}`: 08 §6.1 body `{name, description, is_assignable}`. Implementation also accepts `mfa_required` | Extra writable field (see A-3). 06 §9 anticipates `role.mfa_required` changes, so this is minor doc drift |

All other rows (#1–#74, #76–#87) have a matching method, path and declared permission. Count check: 08 physical endpoints = 105 − 1 (cancel-link) + 1 (exports) = 105.

#### C.3 Requirement conformance

| Req | Status | Evidence |
|---|---|---|
| RBAC-001 | Conformant | Models and migrations present (SOURCE-INSPECTED) |
| RBAC-002 | Conformant | Guards use codes, `grant_path` and `protection_level` only (`guards.py`); lint `test_lint.py:23-45` |
| RBAC-003 | Conformant | Registry naming (`registry.py:17-48`) |
| RBAC-004 | Conformant | Sync upserts owned metadata and bumps `authz_version` (`migration_support.py:188-235`). PATCH permission accepts name/description only (P03: grant_path, sensitivity_class, is_sensitive → 422 `IMMUTABLE_FIELD`) |
| RBAC-005 | Conformant | TEAM → 422 (G8); OWN lead scoping → 404 (P07) |
| RBAC-006 | Conformant | DENY wins, from the next request (P08: GET /leads → 403 after DENY) |
| RBAC-007 | N/A (P1) | Non-null validity → 422 `TIME_BOUND_GRANTS_NOT_ENABLED` (`guards.py:91-93`) |
| RBAC-008 | Conformant | Seeded matrix plus registry validation (`registry.py:133-168`) |
| RBAC-009 | Conformant | P04: custom role +user.delete / +user.permission.manage → 403 `ESCALATION_DENIED`. Copy of FOUNDER → 403. G9 is applied on every account-control path |
| RBAC-010 | Conformant | P04: self PUT roles / self status → 403 `SELF_MODIFICATION_DENIED`. Self-held role grant edit → 403 |
| RBAC-011 | Conformant | `InvariantGuard` under BEGIN IMMEDIATE / advisory lock. LAST_FOUNDER (P09). Nightly job present |
| RBAC-012 | Conformant (A-1) | Route gate + service guards + scoped repositories; startup check presence-only |
| RBAC-013 | Conformant | Uncached session+user read per request; resolver cache keyed on `authz_version`. Demotion, DENY and disable all apply on the next request (P08) |
| RBAC-014 | Conformant | P07 (all child routes 404), P06 (sessions/grants/approvals 404) |
| RBAC-015 | Conformant | G5 system roles; immutable codes (P03) |
| RBAC-016 | Conformant | Effective permissions with sources (`users.py:408-433`) (SOURCE-INSPECTED) |
| RBAC-017 | Partially conformant | MFA gating and step-up verified (P08). Gaps: no `reason` on invite-with-sensitive-role, role copy, unlock or PATCH role (08 bodies omit it, so there is a 06 G6 vs 08 conflict); no `rbac.sensitive_grant` email for invite-with-sensitive-role (`users.py:88-91`); no SENSITIVE_ACTION on approval deny/cancel (A-4) |
| RBAC-018 | Conformant | Seed rule enforced. Runtime allows adding a sensitive permission to SALES (P04 → 200), which 06 §3.1 rule 4 permits (A-6) |
| RBAC-019 | Conformant | P05: `roles`, `protection_level` and `is_founder` → 422 `FIELD_NOT_UPDATABLE`; others → 422. Same for `/auth/me` |
| RBAC-020 | Conformant | P01 (all ADMIN→Founder paths → 403), P04, P09 |
| RBAC-021 | **Partially conformant** | Eligibility, self-approval, target, duplicate approver, one-open-per-target, last-Founder and concurrency are all correct (P09, P15 on both engines). Defects: F-1 (Founder DELETE never executes), F-2 (ARN not verified), F-3 (custodian break-glass in steady state), F-4 (cancel link unusable), F-5 (STANDARD→Founder TOCTOU) |
| USER-001 | Partially conformant | Generic invite/edit/deactivate/delete conformant; deleting a Founder via the canonical workflow is broken (F-1). Workaround: REVOKE_FOUNDER, then DELETE (P16) |
| USER-002 | Untested | Outside RBAC depth |
| USER-003 | Untested | — |
| USER-004 | Conformant | P05 (`/auth/me` closed DTO) |
| USER-005 | Untested | — |
| USER-006 | Untested | UI |
| USER-007 | Partially conformant | Admin email change of a Founder → 403 (P01/P02). A STANDARD request created before the target became a Founder executes against the Founder (F-5) |

#### C.4 Bypass and IDOR attempts

All REPRODUCED on SQLite. P10, P11, P13 and P15 were repeated on PostgreSQL with identical results.

| # | Attempt | Actor | Outcome | Verdict |
|---|---|---|---|---|
| P01 | POST /users/{F}/status DISABLED | ADMIN | 403 FOUNDER_PROTECTED | blocked |
| P01 | email-change / mfa/reset / mfa-requirement / sessions/revoke / password-reset / unlock on Founder | ADMIN | 403 FOUNDER_PROTECTED (each) | blocked |
| P01 | DELETE /users/{F} | ADMIN | 403 PERMISSION_DENIED (user.delete) | blocked |
| P01 | PUT /users/{F}/roles → [ADMIN] or [] | ADMIN | 403 FOUNDER_GOVERNANCE_REQUIRED | blocked |
| P01 | PATCH /users/{F} display_name | ADMIN | 200 | by design (profile fields are not account control) |
| P01 | PATCH /users/{F} protection_level | ADMIN | 422 FIELD_NOT_UPDATABLE | blocked |
| P01 | POST /founder-actions | ADMIN | 403 PERMISSION_DENIED | blocked |
| P02 | F1 → F2: /status, DELETE, DENY lead.read, mfa reset, email-change | Founder | 403 FOUNDER_PROTECTED | blocked |
| P02 | F1 PUT roles F2 → [ADMIN] | Founder | 403 FOUNDER_GOVERNANCE_REQUIRED | blocked |
| P02 | F1 DENY user.founder.manage on F2; GRANT user.founder.manage to SALES; PUT SALES → [FOUNDER]; invite with FOUNDER role | Founder | 403 FOUNDER_GOVERNANCE_REQUIRED; 5 `FOUNDER_GOVERNANCE_BYPASS_BLOCKED` events | blocked |
| P03 | PATCH FOUNDER role mfa_required / is_assignable | Founder | 403 FOUNDER_GOVERNANCE_REQUIRED | blocked |
| P03 | PATCH FOUNDER role grant_path | Founder | 422 IMMUTABLE_FIELD | blocked |
| P03 | DELETE FOUNDER role; PUT FOUNDER perms []; copy_from FOUNDER; custom role + user.founder.manage | Founder | 403 FOUNDER_GOVERNANCE_REQUIRED | blocked |
| P03 | PATCH permission grant_path / sensitivity_class / is_sensitive | Founder | 422 IMMUTABLE_FIELD; name → 200 | blocked |
| P04 | ADMIN PUT own ADMIN role perms | ADMIN | 403 SELF_MODIFICATION_DENIED | blocked |
| P04 | ADMIN custom role + user.delete / user.permission.manage | ADMIN | 403 ESCALATION_DENIED | blocked |
| P04 | ADMIN copy_from ADMIN | ADMIN | 201 | by design (G2 holds) |
| P04 | ADMIN PUT SALES role + user.role.manage | ADMIN | 200 | by design (06 §3.1 rule 4), A-6 |
| P04 | ADMIN PATCH own ADMIN role mfa_required=false / is_assignable=false | ADMIN | 200 / 200 | A-3 (no effective MFA weakening: sensitive codes still require MFA) |
| P04 | ADMIN disables peer ADMIN | ADMIN | 200 | by design (G9 equal) |
| P04 | self PUT roles / self status | ADMIN | 403 SELF_MODIFICATION_DENIED | blocked |
| P05 | PATCH /users/{id} and /auth/me with roles / protection_level / is_founder | any | 422 FIELD_NOT_UPDATABLE | blocked |
| P05 | … with authz_version / email_verified_on / security_cooling_off_until | any | 422 VALIDATION_FAILED (unknown field) | blocked |
| P06 | DELETE /users/{S1}/permissions/{grant of S2} | Founder | 404; grant untouched | blocked |
| P06 | SALES GET / approve an approval | SALES | 403 PERMISSION_DENIED | blocked |
| P06 | Target GET / cancel / approve own MFA-reset request | ADMIN target | 404 / 404 / 403 APPROVER_NOT_ELIGIBLE | blocked |
| P06 | Requester approves own | ADMIN | 403 APPROVER_NOT_ELIGIBLE | blocked |
| P06 | ADMIN GET Founder-class approval | ADMIN | 404 | blocked |
| P06 | ADMIN approve / deny Founder-class approval | ADMIN | **403** APPROVER_NOT_ELIGIBLE (GET gives 404) | blocked; existence oracle A-5 |
| P06 | S1 DELETE S2's session | SALES | 404 | blocked |
| P07 | S1 GET / PATCH / status on S2's lead; notes GET/POST/PATCH/DELETE; activities GET/PATCH/complete/DELETE | SALES | 404 each | blocked |
| P07 | S1 history / assign / users / security-events / audit-logs / assignable | SALES | 403 PERMISSION_DENIED | blocked |
| P08 | Demoted ADMIN reuses token | — | 403 on next request | correct |
| P08 | DENY lead.read → same token | — | 403 | correct |
| P08 | Disabled user reuses token | — | 401 SESSION_INVALID | correct |
| P08 | SALES without MFA granted audit.read | — | 403 (suspended) | correct |
| P08 | PUT roles 11 min after MFA | Founder | 403 STEP_UP_REQUIRED | correct |
| P09 | Second Founder-level request on the same target | Founder | 409 REQUEST_ALREADY_OPEN | correct |
| P09 | Target approves / denies / cancels | Founder target | 403 / 403 / 404 | correct |
| P09 | Third Founder approves → second approval; requester approves after execution | Founders | 200 EXECUTED; 409 INVALID_STATE; 409 | correct |
| P09 | Demoted Founder's stale token → founder-actions | ex-Founder | 403 | correct |
| P09 | Last Founder self REVOKE / self DISABLE | Founder | 409 LAST_FOUNDER | correct |
| P15 | Two Founders approve the same request concurrently (threads) | Founders | [200, 409]; exactly one FOUNDER role row (SQLite and PostgreSQL) | correct |
| **P10** | ADMIN requests EMAIL_CHANGE of privileged ADMIN a2 → a2 promoted to Founder → Founder approves the old STANDARD request | ADMIN + Founder | **200 EXECUTED; Founder's `proposed_email = attacker@evil.test`** (both engines) | **bypass of G11 / FOUNDER_EMAIL_CHANGE (F-5)** |
| **P11/P16** | FOUNDER_STATUS_CHANGE `DELETE` approved by a second Founder | Founders | **200 but FAILED `FOUNDER_STATE_INCONSISTENT`** (both engines). DISABLED, MFA_RESET and EMAIL_CHANGE execute. Workaround REVOKE + DELETE → 204 | **defect (F-1)** |
| P12 | cancel-link: invalid token / extra field / valid / replay | anonymous | 400 / 422 / 204 / 400 | secure |
| **P13** | Custodian `break-glass request` with 2 eligible Founders present; same shell `approve --principal-arn K2`; execute after 24 h | CLI | request PENDING → APPROVED → **EXECUTED**, victim becomes FOUNDER (both engines) | **F-2 + F-3** |
| P14 | Sole Founder cancels custodian GRANT_FOUNDER of a replacement, twice | Founder | 204, 204 | by design (06 §7.5); A-11 |
| P17 | Unauth bad-id path / HEAD / preflight from foreign origin | anonymous | 422 / 401 / 204 without ACAO | A-7 |

### Appendix D — Leads, audit and notifications working paper

#### D.1 Requirement conformance

Key: C = Conformant · P = Partially conformant · N = Non-conformant · D = Intentional documented deviation · U = Untested · N/A = not applicable.

###### LEAD-*

| Req | Class | Evidence / note |
|---|---|---|
| LEAD-001 | C | `routes.py:49-78`, probe P1/P2 |
| LEAD-002 | C | model plus `present()` |
| LEAD-003 | C | `service.py:367-412` |
| LEAD-004/005/006 | C | `service.py:479-537` matches 04 §3: forward skip, one step back with a comment, WON from an early stage needs a comment, LOST needs a reason, reopen only LOST→CONTACTED or WON→NEGOTIATION. Gap: transitions are allowed on an erased lead (F-06). |
| LEAD-007 | C | `service.py:547-561`. Eligible assignees are resolved by permission. |
| LEAD-008 | C | `lead_number` never appears in a public response (probe P2). |
| LEAD-009 | C | `parse_phone` |
| LEAD-010 | C | Duplicates are flagged and stored, never rejected (existing TD-B). There is a concurrency edge on PostgreSQL (F-17). |
| LEAD-011 | C | UTM fields captured, landing page stripped of PII (`service.py:252-261`). |
| LEAD-012 | P | Captured correctly at intake. Staff re-consent leaves mixed provenance (F-04 / DEV-004). |
| LEAD-013/014/015/016 | C | Not deep-probed beyond the existing tests. Scope predicate verified in `repository.py:26-56`. |
| LEAD-018 | P | Ordering is correct: limiter, then idempotency, then CAPTCHA (`routes.py:51,63-72`). CAPTCHA fails closed (`turnstile.py:34-44`). Honeypot hits are quarantined. The CAPTCHA network call holds the write lock (F-01). The siteverify hostname is not checked (F-14). |
| LEAD-019 | P | The site treats `UNKNOWN_POLICY_VERSION` as an inline error with no WhatsApp route (F-10). |
| LEAD-020 | C | `events.py:45-70`. Recipients are resolved by permission (probe P5). |
| LEAD-023 | C | `validate_public` |
| LEAD-024 | C | `_update` |
| LEAD-025 | C | Body is `{reference, message}` only. The reference is 8 Crockford characters from `secrets` (40 bits, `service.py:40-48`), so it is not sequential and does not leak volume. The honeypot response has the same shape (probe P2: `CHTP-9DKS`, `KY3H-QFPA`, …). |
| LEAD-026 | C | The error summary is focusable with `role=alert`. See F-11 (`innerHTML`). |
| LEAD-027 | P | Withdrawal is correct. Re-consent overwrites the row consent and relies on audit_log (F-04, DEV-004). |
| LEAD-028 | C | Ships disabled. The production guard is at `config.py:231`. |
| LEAD-029 | P | Anonymization and audit rewrite work (existing test). Refusal evidence is rolled back (F-07). Writes on an erased lead are still accepted (F-06). Legal hold is only a status env var (OI-4, documented). |
| LEAD-030 | C | `intake_unmapped` |
| LEAD-017/021/022 | N/A | P1/P2 |

###### NOTE-* and ACT-*

| Req | Class | Note |
|---|---|---|
| NOTE-001 | P | Scope rules are correct. Notes can be added to an erased lead (F-06). |
| NOTE-002 | C | OWN = author (`activities.py:19-21`) |
| NOTE-003 | N/A (P1) | Pin field exists. |
| NOTE-004 | C | `activities.py:31-32` |
| ACT-001 | P | Correct, but activities can be added on an erased lead (F-06). |
| ACT-002/003 | C | PLANNED → COMPLETED or CANCELLED only; system rows are read-only (`activities.py:135-140`). |
| ACT-004 | C | System STATUS_CHANGE and ASSIGNMENT rows. Re-consent writes no system activity (F-04). |
| ACT-005 | N/A (P1) | |

###### AUDIT-*

| Req | Class | Note |
|---|---|---|
| AUDIT-001 | C | Same transaction. Probe P1b: a forced failure leaves 0 audit rows and 0 leads. |
| AUDIT-002/003 | C | Actor, via, request_id, session_id, ip and user agent captured (probe P1). |
| AUDIT-004 | C (SQLite) / P (PostgreSQL) | Triggers block UPDATE and DELETE on both engines (probe Q1). On PostgreSQL any session can `SET veda.maintenance='on'` and bypass the trigger when role separation is not provisioned (F-12). |
| AUDIT-005 | C | Redaction in `audit_hook.py:62-95` |
| AUDIT-006 | C | Parent linkage |
| AUDIT-008 | C | Not re-probed |
| AUDIT-010 | C | `audit_hook.py:161-163` |
| AUDIT-011 | P | Runs from the maintenance process. Failure handling is weak (F-15). IP and user agent columns are not erased (F-16). |
| AUDIT-012 | C | |
| AUDIT-007/009/013 | N/A | P1/P2 |

###### SEVT-*

| Req | Class | Note |
|---|---|---|
| SEVT-001 | C | |
| SEVT-002 | U | Catalog breadth not in scope |
| SEVT-003 | C | Detail allow-list (`security_events.py:163-176`) |
| SEVT-004 | P | Archival anchors are written locally, not to S3 (OI-6). The boundary loses rows (F-03). |
| SEVT-005 | U | Not in scope |
| SEVT-006 | P | The keyed HMAC and JCS construction is correct. Verification accepts a deleted anchored prefix and a truncated tail (F-02). |
| SEVT-007 | N | Verification never reads the S3 anchor. Archival anchors never reach S3 (F-02). |
| SEVT-008/009/010 | U | |
| SEVT-011 | C | Deferred events survive rollback. Exception: F-07 uses `record` instead of `defer`. |

###### NOTIF-*

| Req | Class | Note |
|---|---|---|
| NOTIF-001 | C | |
| NOTIF-002 | C | Adapter design is correct. The SES adapter is untested (`# pragma: no cover`). |
| NOTIF-003 | C | Outbox is written in the business transaction. |
| NOTIF-004 | P | Retries and dead-lettering work (probe P5b: DEAD after 8 attempts). Alerting is a log line only, and `/health` ignores DEAD rows (F-15). Retries resend email to recipients who already received it (F-09). |
| NOTIF-005 | P | Templates are versioned with HTML and text parts, and HTML autoescapes. Plain-text content can be spoofed (F-08). |
| NOTIF-008 | C | Probe P5: the in-app rows survive an email failure and the lead is untouched. |
| NOTIF-009 | P | The SES adapter is untested (OI-6). |
| NOTIF-006/007 | N/A | |

#### D.2 Lead workflow (21 steps)

| # | Step | Verdict | Evidence |
|---|---|---|---|
| 1 | Form render | OK | `dist/index.html:168-185`. The honeypot is off-screen, not `display:none` (`enhancements.css .hp-field`), with `tabindex=-1`, `aria-hidden` and `autocomplete=off`. Intake stays off while `veda-api-base` is empty. |
| 2 | Client validation | OK | `app.js:110-120`. The server re-validates everything. |
| 3 | CAPTCHA | OK (fail closed). F-01, F-14 | If no widget is present the site sends `'no-widget'` (`app.js:175`). **Dev** mode accepts any token not starting with `fail` (`turnstile.py:37-38`), so it passes. **Production** is forced to `cloudflare` mode by `config.py:225-226`, so `'no-widget'` fails at siteverify and the site falls back to WhatsApp. A provider error or the 5 s timeout returns False (fail closed, `turnstile.py:41-44`). The call runs while the SQLite write lock is held (F-01). |
| 4 | API: size, closed schema, rate limit | OK | `PUBLIC_MAX_BODY` is 16 KB. `limits=[20/min, 120/h]` per IP runs before the handler. |
| 5 | Client IP | OK subject to deployment | `ratelimit.py:17` and `http.py:146-149` trust `CF-Connecting-IP`. This is spoofable only if the origin is reachable without going through Cloudflare. 02 §11 requires the SG plus Authenticated Origin Pulls, but the repo has no proxy config (compose binds `127.0.0.1:8000`). ADVISORY. |
| 6 | Idempotency | OK | The key is **persisted** in `lead.intake_idempotency_key` with a unique index (`0100:170`). It survives restart and ignores a spent token (probe P2: same reference, Turnstile calls = 0). A different fingerprint returns 422. On PostgreSQL, a concurrent duplicate returns 409 instead of a replay (F-17). |
| 7 | Server validation | OK | `service.py:264-306` |
| 8 | Honeypot | OK | The lead is **stored** with `SUSPECTED` and the same 201 shape. A `PUBLIC_INTAKE_QUARANTINED` event is written. No `lead.created` is emitted (`service.py:329-361`). Not dropped. |
| 9 | Duplicate detection | OK | Flagged and never rejected. Not disclosed. |
| 10 | Consent evidence | OK at intake | Policy version, server time, `WEBSITE_FORM`, source page and IP are captured. |
| 11 | Persistence and atomicity | OK | Single transaction (probe P1b). A busy database returns 503, then the WhatsApp fallback. Nothing is silently lost. |
| 12 | Audit | OK | CREATE rows are by WEB_INTAKE via PUBLIC_FORM (probe P1). |
| 13 | Outbox / notification | OK | The outbox row is in the same transaction. An email failure never touches the lead (probe P5). |
| 14 | Public-safe response | OK | `{reference, message}`. The reference is random, 40 bits. `Cache-Control: no-store`. |
| 15 | Admin list | OK | Spam is hidden by default. Results are scoped. |
| 16 | SALES scope | OK | OWN = assigned or created. Out of scope returns 404. Visible but outside the action scope returns 403. |
| 17 | Assign | OK | Eligible users are resolved by `lead.read`. ASSIGNMENT activity plus outbox. |
| 18 | Status transitions | OK against 04 §3, with one gap | The erased-lead gap is F-06. |
| 19 | Notes and activities | OK, with one gap | Consent withdrawal blocks planning contact activities. Writes on an erased lead are still allowed (F-06). |
| 20 | Follow-up and WON/LOST | OK | PLANNED activities are cancelled and `next_follow_up_on` is recomputed. |
| 21 | Retention, erasure, withdrawal, legal hold | Partial | See F-04, F-06, F-07, F-15, F-16. Legal hold is only `VEDA_ERASURE_BLOCKED_STATUSES` (OI-4, documented). |

**Other checks**

- **WhatsApp fallback URL contains PII** (`app.js:66-79`). This is the pre-existing, user-initiated hand-off, preserved as LEAD-019 requires. `Referrer-Policy: strict-origin-when-cross-origin` stops referrer leakage. The PII reaches wa.me or Meta and browser history by design. Acceptable (ADVISORY F-19).
- **Lead enumeration.** There is no public read endpoint. Staff-side IDs are authorized by scope, so none is possible.

#### D.3 Previously reported defects

| Defect | Status | Proof |
|---|---|---|
| (1) Wrong actor in audit log | **Fixed** | `context.py:93-104`: `acting()` flushes before restoring the context. Probe P1: every row in the public transaction (lead and lead_activity CREATE) has `performed_by = …0002` (WEB_INTAKE) via PUBLIC_FORM. The quarantine event actor is WEB_INTAKE. The CAPTCHA-blocked event actor is ANONYMOUS (…0003), which is appropriate. The staff UPDATE actor is the request user with request_id and session_id. Worker rows are SYSTEM (…0001). |
| (2) Archive chain break | **Fixed** | `maintenance.py:321-328` appends SECURITY_LOG_ARCHIVED before the delete and anchors the last archived seq. Probe Q3: `verify after archive: ok=True` on both engines. A **new** boundary defect exists (F-03), and verification is weak (F-02). |
| (3) Failed notification deleting in-app notification | **Fixed** | `worker.py:69-84`: the handler's in-app rows commit in their own transaction, and emails are sent afterwards. Probe P5 with a failing provider: event FAILED with attempts 1, in-app rows 2. On retry: DONE with in-app rows still 2 (no duplicates, thanks to `ux_notification__event_recipient` plus the exists check). The retry resends email (F-09). |

### Appendix E — Database, migrations and operations working paper

#### E.1 Migration commands and outputs

| Command | SQLite (fresh file) | PostgreSQL 16.4 (fresh DB) |
|---|---|---|
| `python -m alembic heads` | `0100_crm_leads (head)`, exactly one head | `0100_crm_leads (head)`, exactly one head |
| `python -m alembic upgrade head` | rc 0. 9 steps, `0001_kernel` → … → `0100_crm_leads` | rc 0. Same 9 steps ("Will assume transactional DDL") |
| `python -m alembic current` | `0100_crm_leads (head)` | `0100_crm_leads (head)` |
| `python -m alembic history` | linear chain `<base> → 0001_kernel → 0002_identity → 0003_rbac → 0004_auth → 0005_audit → 0006_reference → 0007_notifications → 0008_account_security → 0100_crm_leads (head)` | identical |
| `python -m alembic downgrade -1` | rc 1, `NotImplementedError: down-migrations are not supported` (0100_crm_leads.py:287) | rc 1, same |
| `alembic current` after the refused downgrade | `0100_crm_leads (head)`, no partial change | `0100_crm_leads (head)` |
| `alembic upgrade head` again | rc 0, no-op | rc 0, no-op |
| `alembic downgrade 0100_crm_leads:0008_account_security --sql` (offline) | rc 1, same NotImplementedError | rc 1 (`BEGIN;` emitted, then the error) |

**Atomicity (REPRODUCED).** I upgraded to `0008`, pre-created a conflicting `lead_activity` table, then ran `upgrade head`:

| | SQLite | PG16 |
|---|---|---|
| rc | 1 | 1 |
| `lead` table exists after the failure | **No** (rolled back) | **No** (rolled back) |
| `alembic_version` | `0008_account_security` | `0008_account_security` |

`transaction_per_migration=True` together with the kernel `BEGIN` hook makes each revision atomic on SQLite as well as on PG.

#### E.1 Recount against claims

| Metric | Claimed | SQLite (mine) | PG16.4 (mine) | Verdict |
|---|---|---|---|---|
| Revisions | 9 | 9 (single linear head) | 9 | ✓ |
| Tables (excl. `alembic_version`) | 24 | 24 | 24 | ✓ |
| Columns | — | 502 | 502 | equal across engines |
| Primary keys | — | 24 (all `id`, `pk_<t>`) | 24 | ✓ |
| Indexes (non-PK) | 72 | 72 (24 unique, 46 partial) | 72 (24 unique, 46 partial) | ✓ |
| Foreign keys | 107 | 107 (`PRAGMA foreign_key_list`: all `ON DELETE RESTRICT`) | 107 (`pg_constraint.confdeltype='r'` for all 107) | ✓ |
| UNIQUE constraints | — | 0 (uniqueness is partial unique indexes only) | 0 | by design |
| CHECK constraints | 493 / 161 | 493 | 161 (catalog count 161) | ✓ |
| Triggers | "guards present" | 4 (`trg_{audit_log,security_event_log}__no_{update,delete}`) | 4 + function `veda_immutable_guard()` | ✓ present (see §5 for bypasses) |
| Native ENUM types | none | n/a | 0 (`pg_type.typtype='e'`) | ✓ |
| Seeds: roles, permissions, matrix, lookups, system users, sequences | 3, 45, 101, 47, 3, 1 | 3, 45, 101, 47 (+6 categories), 3, 1 | same | ✓ |
| Role flags | — | FOUNDER (assignable=0, FOUNDER_WORKFLOW_ONLY, mfa=1), ADMIN (1, STANDARD, mfa=1), SALES (1, STANDARD, mfa=0), all is_system | same | ✓ matches 03 §10 |
| Sensitive permissions | — | 16 of 45 | 16 | — |
| Matrix split | — | FOUNDER 42 ALL + 3 OWN; ADMIN 35 + 3; SALES 8 + 10 | same | — |
| Human users / credential rows / password hashes | 0 / — / 0 | 0 / 0 / 0 | 0 / 0 / 0 | ✓ AUTH-014 |
| System users | 3 | `…0001` SYSTEM (self-created), `…0002` WEB_INTAKE, `…0003` ANONYMOUS, all `created_by=SYSTEM`, STANDARD | same (rendered with hyphens by PG) | ✓ |
| `number_sequence` | LEAD | `LEAD, VS-L-, YEAR, NULL, 1, 6` | same | ✓ |
| Migration audit rows | — | 206 CREATE rows, `performed_via=MIGRATION` (3 app_user, 3 role, 45 permission, 101 role_permission, 6 + 47 lookups, 1 sequence) | 206 | ✓ backfill works |
| `security_event_log` rows | — | 0 | 0 | — |

**Determinism (REPRODUCED).** I migrated two fresh databases per engine and compared a full schema fingerprint (tables, columns, types,
nullability, defaults, FKs, checks, index SQL, triggers). The fingerprints matched on both engines. Business seed content (permission codes, matrix `role|perm|scope`, lookup `cat|code|label|order`, role flags, sequence) is identical across the two DBs of each engine and across engines (compared as sets, because PG collation orders `ORDER BY code` differently). Ids and timestamps differ run to run, which is expected: seeds use `new_id()` and `clock.now()`.

#### E.2 Audit-contract columns

All **24/24** tables carry all nine contract columns as the **first nine columns in order** (`id, created_on, updated_on, created_by, updated_by, is_deleted, deleted_on, deleted_by, version`), with the correct nullability (`deleted_on` and `deleted_by` nullable, the rest NOT NULL) and defaults (`is_deleted false`, `version 1`). All 24 have the three actor FKs (`created_by`, `updated_by`, `deleted_by` → `app_user.id` ON DELETE RESTRICT), which accounts for 72 of the 107 FKs.

| Table | 9 cols | order | 3 actor FKs | Behavioural exception (enforced how) |
|---|---|---|---|---|
| app_user | ✓ | ✓ | ✓ (self-ref) | EXC-008 (service) |
| user_credential, role, permission, user_role, role_permission, user_permission, user_mfa_factor, lookup_category, lookup_value, number_sequence, lead, lead_note, lead_activity, notification | ✓ | ✓ | ✓ | — / EXC-005, EXC-010 |
| user_session, refresh_token, user_action_token, user_mfa_recovery_code, mfa_challenge, outbox_event, admin_approval_request | ✓ | ✓ | ✓ | EXC-003/004/006: `ck_<t>__never_deleted` (`is_deleted = false`) CHECK |
| audit_log, security_event_log | ✓ | ✓ | ✓ | EXC-001: `ck_<t>__immutable_contract` (`is_deleted=false AND version=1`), triggers; audit_log also `performed_by=created_by AND performed_on=created_on` |

**Exceptions: none.** No table omits a column, and 03 §2.1 authorises none. **DATA-001 conformant.**

FK-less GUID columns (excluding `id`) number exactly **10**, matching 03 §2.11:
`audit_log.{entity_id,parent_entity_id,session_id,transaction_id}`, `security_event_log.{session_id,target_entity_id}`,
`refresh_token.replaced_by_id`, `outbox_event.aggregate_id`, `notification.entity_id`, `user_mfa_recovery_code.batch_id`.
The only non-GUID `_id/_by/_to` columns are the three R-01 strings (`audit_log.request_id`, `security_event_log.request_id`,
`outbox_event.locked_by`, all VARCHAR(64)). Both match §2.11.1 exactly.

#### E.2 Schema vs architecture

Method: `diff_spec.py` parses every column row of 03 §4–§8 and 04 §2/§9/§10 and compares name, logical→PG type (including varchar/char length), nullability and index names with the migrated PG16 and SQLite schemas. I then compared every index definition and predicate and every table-specific CHECK by hand.

| Result | Detail |
|---|---|
| Missing / extra tables | **None** (24 = 03 §11 inventory; no `user` table) |
| Missing / extra columns | **None** in any of the 24 tables |
| Type differences (incl. lengths) | **None** (CODE(n)→varchar(n), CHAR(n)→bpchar(n), GUID→uuid, UTCDATETIME→timestamptz, JSON→jsonb, MONEY_MINOR→int8, DATE→date, SMALLINT→int2) |
| Nullability differences | **None** |
| Index names | All 72 specified indexes exist and no unspecified index exists |
| Index columns / predicates | Match 03/04 on both engines (`is_deleted = 0` on SQLite, `is_deleted = false` on PG), except DEV-001 below |
| FK ON DELETE | RESTRICT on all 107 (SQLite `RESTRICT`; PG `confdeltype='r'`). No cascades. ✓ 03 §1 |
| Unique-without-`is_deleted` indexes | Exactly the EXC-007 allow-list: refresh/action/challenge token hashes, recovery code hash, chain_seq, two admin_approval_request open indexes, `lead.public_reference`, `lead.intake_idempotency_key` (`IS NOT NULL`), `notification (source_event_id, recipient_user_id)` (`IS NOT NULL`). ✓ |

| # | Difference | Engines | Documented? |
|---|---|---|---|
| D-1 | `ux_user_mfa_factor__user_live` is keyed `(user_id, factor_type, status)` instead of `(user_id, factor_type)`; predicate unchanged: SQLite `status IN ('PENDING','ACTIVE') AND is_deleted = 0`, PG `status = ANY(ARRAY['PENDING','ACTIVE']) AND is_deleted = false` | Identical on both | **Yes, DEV-001.** Sound from the DB side: at most one ACTIVE and at most one PENDING per user/type, REVOKED unconstrained. The index is the same on both engines and needs no engine-specific feature. Needs a 03 §5.5 amendment. |
| D-2 | `security_event_log.event_type` CODE(50), `.failure_reason` CODE(40) and `admin_approval_request.status_reason` CODE(30) have **no `IN (…)` CHECK**, although 03 §1 says CODE(n) = string + CHECK | Both | **No.** Kernel-enforced for event_type and failure_reason (`security_events.py:216-223`, `CATALOG`/`FAILURE_REASONS`). status_reason is free text. ADVISORY (F-13). |
| D-3 | Extra CHECKs that tighten the spec: `ck_app_user__authz_version_positive`, `ck_number_sequence__{next_value_positive,padding_range}`, `ck_mfa_challenge__failed_attempts` (0–5), `ck_user_session__auth_methods`, `ck_user_mfa_factor__active_confirmed`, `ck_*__never_deleted` | Both | Implied by the spec notes. Benign. |
| D-4 | SQLite declares BOOL as `BOOLEAN` (NUMERIC affinity) rather than `INTEGER`. The `IN (0,1)` CHECK makes it equivalent. | SQLite | Immaterial |

All spec'd CHECKs are present on both engines: app_user (6), role/permission patterns, admin_approval_request (the 5 listed + enums), lead (10 + withdrawal channel), lead_activity (5 + enums), lead_note, audit/security pair checks.

#### E.2 Immutability probes

`audit_log` held 206 seeded rows. I inserted one `security_event_log` row raw, which is allowed.

| Attempt | SQLite | PostgreSQL 16.4 (owner `postgres`) |
|---|---|---|
| `UPDATE audit_log SET reason='tamper' …` | **REJECTED** `immutable` | **REJECTED** `RestrictViolation: immutable` |
| `DELETE FROM audit_log WHERE …` (1 row) | **REJECTED** | **REJECTED** |
| `DELETE FROM audit_log` (all) | **REJECTED** | **REJECTED** |
| `UPDATE security_event_log SET severity=…` (1 row present) | **REJECTED** | (same trigger; verified on audit_log) |
| `DELETE FROM security_event_log` | **REJECTED** | — |
| `TRUNCATE audit_log` / `TRUNCATE security_event_log` | n/a | **SUCCEEDED**: no TRUNCATE trigger, and no REVOKE because no `veda_app` role exists |
| `SET LOCAL veda.maintenance='on'; UPDATE audit_log …` | n/a | **SUCCEEDED** (1 row) |
| `SET LOCAL veda.maintenance='on'; DELETE FROM audit_log` | n/a | **SUCCEEDED** (206 rows) |
| Non-owner role with table DML grants, no GUC: `UPDATE audit_log` | n/a | **REJECTED** (trigger) |
| **Non-owner role** with DML grants + `SET LOCAL veda.maintenance='on'`: `UPDATE audit_log` | n/a | **SUCCEEDED**: any role can set a custom GUC |
| `DROP TRIGGER trg_audit_log__no_update` (any file-level writer) | **SUCCEEDED** (known, accepted residual 07 §6.2 / 11 §4 A2; readiness detects missing triggers) | — |
| `veda_app` / `veda_retention` roles present | n/a | none. The grant block in `migration_support.py:344-351` is a no-op unless the roles already exist, and nothing in the repo provisions them |

Conclusion: on SQLite, the P0 production engine, the guards behave as designed and the residual risk is the documented one. On PostgreSQL the guard does **not** meet 07 §6.2 ("application role INSERT, SELECT only; triggers block UPDATE") (F-06).

#### E.3 Production-readiness gate table

Classification: **M** = blocks merge · **S** = blocks staging · **P** = blocks production · **F** = post-production follow-up.

| Area | State at 9236aa3 | Evidence | Gate |
|---|---|---|---|
| Config separation / prod validation | `validate_production` runs only when `VEDA_ENV == "production"` exactly. Unset, `prod`, `Production` and `staging` all get **0 problems**, dev keys derived from the public constant `"local-development-only"`, local KMS and capture email. Even with `production`, it accepts rate limits disabled, 1-byte HMAC keys, the placeholder `…:key/local-dev` KMS ARN, localhost origins, the default relative `sqlite:///var/veda.db`, `jwt_kid=dev-1`, and no anchor bucket, Sentry or custodians. `cmd_migrate` skips validation. | REPRODUCED (`ops_probe.json`) | **S, P** (F-02) |
| Secrets management | Env vars, per SEC-005 design. No SSM wiring in the repo (report §14). | SOURCE | P |
| Debug mode | No `debug=True` or `app.run`. OpenAPI is exposed only when not production, so it is exposed in staging and under typo'd envs. | SOURCE | ✓ (F-02 caveat) |
| CORS | Exact allowlist. Credentials only for `app_origin`. Defaults are localhost and are not validated in prod. | SOURCE | ✓ / F-02 |
| Proxy handling / client IP | No ProxyFix and no trusted-proxy list. `CF-Connecting-IP` is trusted unconditionally (`http.py:148`, `ratelimit.py:17`, `logging.py:80`). Compose binds `127.0.0.1:8000`, so a host proxy or tunnel is assumed but not in the repo. | SOURCE | **P** (F-10) |
| Trusted hosts | No Host-header validation (`TRUSTED_HOSTS`/`SERVER_NAME` unset). Low impact because links use configured base URLs. | SOURCE | F |
| Secure cookies / CSRF | Refresh cookie `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth` plus an `X-Requested-With` and Origin check. `cookie_secure` is enforced in prod. (Observation for the security reviewer: the refresh Origin check uses `allowed_origins`, which includes the public marketing origin, `service.py:334`.) | SOURCE | ✓ |
| Health / readiness | `/health/live`. `/health/ready` checks DB, migrations == head, FK pragma and guards (LOG-005 ✓), but it breaks N-1 rollback (F-01) and publicly exposes migration, guard and outbox-lag state (F-11). | REPRODUCED | **P** (F-01), F (F-11) |
| Structured logs | structlog JSON with a masking processor for `veda.http`. **Stdlib loggers** (`app._unhandled`, worker, maintenance "alerts", security-event writer failure) emit **plain text, unmasked**. The engine lacks `hide_parameters=True`, so DB errors log bound parameters (PII). | REPRODUCED | **P** (F-07) |
| Metrics | None emitted (no CloudWatch, StatsD or Prometheus). LOG-006 says "mandatory in P0". | SOURCE | **P** (F-04) |
| Alerts | CRITICAL/ERROR stdlib log lines only (OI-7). No routing and no test-fires (RG-5). | SOURCE | **P** (F-04) |
| Error tracker | Sentry is optional (`sentry_dsn` not required in prod). LOG-004. | SOURCE | P (F-02/F-04) |
| Backups (Litestream) | Compose service pinned `litestream/litestream:0.3.13`, but `/etc/veda/litestream.yml` is absent. No nightly `VACUUM INTO` + Object Lock job (no `VACUUM` in code). No EBS snapshot automation. | SOURCE | **P** (F-03) |
| Restore testing | OPS-009 automated restore verification is **not implemented** (no job or code). RG-1/RG-2 not executed. | SOURCE | **P** (F-03) |
| SQLite path persistence | Dockerfile sets `sqlite:////var/lib/veda/veda.db`. Compose mounts `/var/lib/veda`. The settings default is relative `var/veda.db` (container layer) if the env is missing, and this is not validated. | SOURCE | P (F-02) |
| Encryption at rest | Delegated to EBS/KMS (OPS-007). Not in the repo. RG gate "Encrypted persistent volume" pending. | — | P |
| Single-writer / single process | 1 gthread worker × 8 threads, BEGIN IMMEDIATE, busy_timeout 5000, SQLITE_BUSY → 503. `deploy-check` is a **text match** on the conf file. `GUNICORN_CMD_ARGS=--workers=4` yields `workers = 4` while `deploy-check: OK`. It does not detect compose `--scale` or a second host, and there is no runtime single-instance lock. | REPRODUCED | **P** (F-09) |
| Migrations in deploy | Not wired into compose or the image. The runbook step is manual. No deploy script or runbook for the API in the repo (`deployment.md` covers only the marketing site). | SOURCE | **P** (F-03) |
| PostgreSQL deployment | Target only (PGM-1). The guard defects in F-06 apply to that gate. | REPRODUCED | PGM-1 |
| SES / S3 / KMS readiness | Adapters untested without AWS (OI-6, TG-02). Security-event archive is local JSONL. The anchor bucket is optional. | SOURCE | **P** |
| CSP | API `default-src 'none'`. The app `_headers` CSP is strict. The marketing site has **no CSP** (`dist/_headers`), and Turnstile and `connect-src` are not configured (OI-5). | SOURCE | P (before intake go-live) |
| Privacy notice | `/privacy` is linked from `dist/index.html:179` but does not exist (OI-5, PG-PRIV). Intake flag is off. | SOURCE | P (intake) |
| Retention | All retention values are `None`, so jobs refuse (OWNER-INPUT-002). Safe default. | SOURCE | P (PG-RET) |
| Erasure | Implemented per report. Not reviewed in depth by me. | — | — |
| Legal hold | No data model. `VEDA_ERASURE_BLOCKED_STATUSES` is empty (OI-4). | SOURCE | F (P if legal requires) |
| Incident diagnostics | request_id everywhere. Exception logs are unstructured (F-07). No runbook. | SOURCE | P |
| Deployment rollback | Normal rollback is broken by readiness (F-01). Disaster rollback depends on snapshots that are not implemented (F-03). | REPRODUCED | **P** |
| Runbooks | None in the repo (deploy/migrate, restore, key rotation, break-glass, incident: 11 §8). | SOURCE | **P** |
| Governance | `gate-registry` TG-01 and TG-08 ("explicit owner authorization of implementation") are **Pending — not authorized**, with blocking scope "All implementation". | SOURCE | M (outside DB scope, flagged) |

#### E.4 Requirement conformance

| Req | Classification | Basis |
|---|---|---|
| DATA-001 | Conformant | REPRODUCED 24/24 |
| DATA-002 | Conformant | REPRODUCED. PG raw-SQL acceptance of non-v7 is documented. |
| DATA-003 | Conformant | SOURCE (one `tx_time`) + REPRODUCED types. F-12 advisory. |
| DATA-004 | Conformant | REPRODUCED FKs and seeds. F-15 label advisory. |
| DATA-005 | Conformant | REPRODUCED CHECK on both engines |
| DATA-006 | Conformant | REPRODUCED (PG16 ORM race) + SOURCE If-Match |
| DATA-007 | Conformant; DEV-001 intentional documented deviation (index key) | REPRODUCED |
| DATA-008 | Conformant | REPRODUCED |
| DATA-009 | Conformant (source-inspected: hook blocks hard delete without exception) | SOURCE |
| DATA-010 | Conformant for app connections | REPRODUCED. F-14a for tooling. |
| DATA-011 | Partially: schema passes on SQLite and PG16 locally, but CI is unexecuted (F-16) | REPRODUCED / SOURCE |
| DATA-012 | Conformant | REPRODUCED |
| DATA-013 | Untested by me (API layer; tests exist) | — |
| DATA-014 | Conformant (allow-list exact); F-13 minor undocumented CHECK gaps | REPRODUCED |
| DATA-015 | Conformant | SOURCE + REPRODUCED atomic migration audit rows |
| DATA-016 | Conformant (`quoted_amount_minor` bigint, `currency` char(3)) | REPRODUCED |
| DATA-017 | Conformant by design (non-FK correlation ids exact). Purge not run by me. | REPRODUCED schema |
| PLAT-004 | Conformant (engine branches limited to advisory locks, A-13) | SOURCE |
| PLAT-005 | Conformant, with the F-08 caveat | REPRODUCED |
| PLAT-007 | Conformant (F-12 advisory) | REPRODUCED |
| PLAT-008 | **Partially** (no secrets in the repo, but fail-open dev keys, F-02) | REPRODUCED |
| PLAT-009 / 010 / 013 | Conformant | REPRODUCED |
| PLAT-001/002/003/006/011/012 | N/A to this review | — |
| LOG-001 | **Partially** (F-07) | REPRODUCED |
| LOG-002 | Conformant (columns and header; client-supplied ids accepted by pattern) | SOURCE |
| LOG-003 | **Non-conformant** in the stdlib and exception path (F-07) | REPRODUCED |
| LOG-004 | **Partially** (Sentry optional, F-02/F-04) | SOURCE |
| LOG-005 | **Partially** (content conformant; strict equality breaks OPS-004, F-01) | REPRODUCED |
| LOG-006 | **Non-conformant** (no metrics or alert routing, F-04) | SOURCE |
| OPS-001 | **Untested** (CI never run, F-16) | SOURCE |
| OPS-002 | **Non-conformant / not delivered** (F-03) | SOURCE |
| OPS-003 | **Partially** (staging unvalidated, F-02) | REPRODUCED |
| OPS-004 | Migrations conformant (expand-only, refused downgrade); **rollback non-functional** (F-01); runbook absent (F-03) | REPRODUCED |
| OPS-005 | Untested (owner input) | — |
| OPS-006 / OPS-010 | **Partially** (config OK; enforcement weak, F-09) | REPRODUCED |
| OPS-007 | Partially (Dockerfile and compose correct; unvalidated default path; EBS encryption not in the repo) | SOURCE |
| OPS-008 | Conformant (documented gate) | SOURCE |
| OPS-009 | **Non-conformant / not delivered** (F-03) | SOURCE |
| OPS-011 | Conformant (region is config) | SOURCE |

**Blocking summary:** Merge conditions are F-16 (execute CI green, including `postgres:16`) and, recommended, F-05 (lockfile), plus the owner-authorization gate TG-08, which is outside DB scope. Staging is blocked by F-02 and F-05. Production is blocked by F-01, F-02, F-03, F-04, F-05, F-07, F-09 and F-10. The PostgreSQL gate is blocked by F-06. Post-production follow-ups are F-08 and F-11 through F-15 and F-19.

#### E.5 Full table / column / constraint inventory

Legend: SQLite type as declared; PG type from information_schema (udt_name(len)); N = nullable; default is the server default (PG rendering). The nine contract columns are listed for every table. Contract CHECKs on every table: `ck_<t>__soft_delete_consistent`, `ck_<t>__version_positive`, `ck_<t>__updated_after_created`. SQLite-only type CHECKs (`_format`, `_json`, `_bool`, `_len`) are counted per table.

###### `admin_approval_request` — 27 columns, PK pk_admin_approval_request(id), 6 FKs, 4 indexes, 13 portable CHECKs + 19 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `action_class` | VARCHAR(10) | varchar(10) |  |  |
| 11 | `action_type` | VARCHAR(30) | varchar(30) |  |  |
| 12 | `channel` | VARCHAR(12) | varchar(12) |  | 'IN_APP' |
| 13 | `target_user_id` | CHAR(32) | uuid |  |  |
| 14 | `requested_by` | CHAR(32) | uuid |  |  |
| 15 | `request_payload` | JSON | jsonb |  |  |
| 16 | `reason` | VARCHAR(1000) | varchar(1000) |  |  |
| 17 | `status` | VARCHAR(12) | varchar(12) |  | 'PENDING' |
| 18 | `status_reason` | VARCHAR(30) | varchar(30) | Y |  |
| 19 | `approver_user_id` | CHAR(32) | uuid | Y |  |
| 20 | `external_requester_ref` | VARCHAR(2048) | varchar(2048) | Y |  |
| 21 | `external_approver_ref` | VARCHAR(2048) | varchar(2048) | Y |  |
| 22 | `external_approver_human` | VARCHAR(200) | varchar(200) | Y |  |
| 23 | `decided_on` | VARCHAR(27) | timestamptz | Y |  |
| 24 | `decision_reason` | VARCHAR(1000) | varchar(1000) | Y |  |
| 25 | `not_before` | VARCHAR(27) | timestamptz | Y |  |
| 26 | `expires_on` | VARCHAR(27) | timestamptz |  |  |
| 27 | `executed_on` | VARCHAR(27) | timestamptz | Y |  |

**FKs:** `fk_admin_approval_request__approver_user_id` (approver_user_id) → app_user.id ON DELETE RESTRICT; `fk_admin_approval_request__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_admin_approval_request__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_admin_approval_request__requested_by` (requested_by) → app_user.id ON DELETE RESTRICT; `fk_admin_approval_request__target_user_id` (target_user_id) → app_user.id ON DELETE RESTRICT; `fk_admin_approval_request__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_admin_approval_request__pending` (status, expires_on) WHERE ((status) = 'PENDING')
- `ix_admin_approval_request__target` (target_user_id, created_on DESC)
- `ux_admin_approval_request__open_founder_target` UNIQUE (target_user_id) WHERE (((action_class) = 'FOUNDER') AND ((status) = ANY ((ARRAY['PENDING', 'APPROVED'])[])))
- `ux_admin_approval_request__open_per_target_action` UNIQUE (target_user_id, action_type) WHERE ((status) = ANY ((ARRAY['PENDING', 'APPROVED'])[]))

**Table-specific CHECKs:** `ck_admin_approval_request__action_class`; `ck_admin_approval_request__action_type`; `ck_admin_approval_request__approver_distinct`; `ck_admin_approval_request__channel`; `ck_admin_approval_request__class_matches_type`; `ck_admin_approval_request__external_distinct`; `ck_admin_approval_request__never_deleted`; `ck_admin_approval_request__no_self_approval`; `ck_admin_approval_request__no_self_target`; `ck_admin_approval_request__status`

###### `app_user` — 29 columns, PK pk_app_user(id), 4 FKs, 4 indexes, 10 portable CHECKs + 19 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `email` | VARCHAR(254) | varchar(254) |  |  |
| 11 | `email_normalized` | VARCHAR(254) | varchar(254) |  |  |
| 12 | `full_name` | VARCHAR(150) | varchar(150) |  |  |
| 13 | `display_name` | VARCHAR(80) | varchar(80) | Y |  |
| 14 | `phone_e164` | VARCHAR(16) | varchar(16) | Y |  |
| 15 | `user_type` | VARCHAR(20) | varchar(20) |  | 'HUMAN' |
| 16 | `status` | VARCHAR(20) | varchar(20) |  | 'INVITED' |
| 17 | `status_changed_on` | VARCHAR(27) | timestamptz |  |  |
| 18 | `timezone` | VARCHAR(40) | varchar(40) |  | 'Asia/Kolkata' |
| 19 | `locale` | VARCHAR(10) | varchar(10) |  | 'en-IN' |
| 20 | `email_verified_on` | VARCHAR(27) | timestamptz | Y |  |
| 21 | `mfa_required` | BOOLEAN | bool |  | false |
| 22 | `authz_version` | INTEGER | int4 |  | 1 |
| 23 | `last_login_on` | VARCHAR(27) | timestamptz | Y |  |
| 24 | `proposed_email` | VARCHAR(254) | varchar(254) | Y |  |
| 25 | `proposed_email_normalized` | VARCHAR(254) | varchar(254) | Y |  |
| 26 | `proposed_email_requested_on` | VARCHAR(27) | timestamptz | Y |  |
| 27 | `proposed_email_requested_by` | CHAR(32) | uuid | Y |  |
| 28 | `protection_level` | VARCHAR(10) | varchar(10) |  | 'STANDARD' |
| 29 | `security_cooling_off_until` | VARCHAR(27) | timestamptz | Y |  |

**FKs:** `fk_app_user__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_app_user__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_app_user__proposed_email_requested_by` (proposed_email_requested_by) → app_user.id ON DELETE RESTRICT; `fk_app_user__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_app_user__full_name` (full_name)
- `ix_app_user__status` (status) WHERE (is_deleted = false)
- `ux_app_user__email_normalized` UNIQUE (email_normalized) WHERE (is_deleted = false)
- `ux_app_user__proposed_email` UNIQUE (proposed_email_normalized) WHERE ((proposed_email_normalized IS NOT NULL) AND (is_deleted = false))

**Table-specific CHECKs:** `ck_app_user__authz_version_positive`; `ck_app_user__email_normalized_lower`; `ck_app_user__proposed_email_differs`; `ck_app_user__proposed_email_pair`; `ck_app_user__protection_level`; `ck_app_user__status`; `ck_app_user__user_type`

###### `audit_log` — 27 columns, PK pk_audit_log(id), 4 FKs, 5 indexes, 9 portable CHECKs + 21 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `entity_type` | VARCHAR(60) | varchar(60) |  |  |
| 11 | `entity_id` | CHAR(32) | uuid |  |  |
| 12 | `action` | VARCHAR(20) | varchar(20) |  |  |
| 13 | `old_value` | JSON | jsonb | Y |  |
| 14 | `new_value` | JSON | jsonb | Y |  |
| 15 | `changed_fields` | JSON | jsonb | Y |  |
| 16 | `performed_by` | CHAR(32) | uuid |  |  |
| 17 | `performed_on` | VARCHAR(27) | timestamptz |  |  |
| 18 | `performed_via` | VARCHAR(20) | varchar(20) |  |  |
| 19 | `parent_entity_type` | VARCHAR(60) | varchar(60) | Y |  |
| 20 | `parent_entity_id` | CHAR(32) | uuid | Y |  |
| 21 | `transaction_id` | CHAR(32) | uuid |  |  |
| 22 | `request_id` | VARCHAR(64) | varchar(64) | Y |  |
| 23 | `session_id` | CHAR(32) | uuid | Y |  |
| 24 | `ip_address` | VARCHAR(45) | varchar(45) | Y |  |
| 25 | `user_agent` | VARCHAR(500) | varchar(500) | Y |  |
| 26 | `reason` | VARCHAR(500) | varchar(500) | Y |  |
| 27 | `payload_schema` | SMALLINT | int2 |  | 1 |

**FKs:** `fk_audit_log__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_audit_log__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_audit_log__performed_by` (performed_by) → app_user.id ON DELETE RESTRICT; `fk_audit_log__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_audit_log__entity` (entity_type, entity_id, performed_on DESC)
- `ix_audit_log__parent` (parent_entity_type, parent_entity_id, performed_on DESC) WHERE (parent_entity_id IS NOT NULL)
- `ix_audit_log__performed_by` (performed_by, performed_on DESC)
- `ix_audit_log__performed_on` (performed_on DESC)
- `ix_audit_log__transaction_id` (transaction_id)

**Table-specific CHECKs:** `ck_audit_log__action`; `ck_audit_log__entity_type_pattern`; `ck_audit_log__immutable_contract`; `ck_audit_log__parent_pair`; `ck_audit_log__performed_matches_contract`; `ck_audit_log__performed_via`

**Triggers (both engines):** trg_audit_log__no_update, trg_audit_log__no_delete

###### `lead` — 62 columns, PK pk_lead(id), 10 FKs, 13 indexes, 17 portable CHECKs + 45 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `lead_number` | VARCHAR(20) | varchar(20) |  |  |
| 11 | `public_reference` | CHAR(9) | bpchar(9) |  |  |
| 12 | `name` | VARCHAR(150) | varchar(150) |  |  |
| 13 | `phone` | VARCHAR(16) | varchar(16) |  |  |
| 14 | `phone_raw` | VARCHAR(30) | varchar(30) |  |  |
| 15 | `email` | VARCHAR(254) | varchar(254) | Y |  |
| 16 | `email_normalized` | VARCHAR(254) | varchar(254) | Y |  |
| 17 | `city` | VARCHAR(100) | varchar(100) | Y |  |
| 18 | `locality` | VARCHAR(150) | varchar(150) | Y |  |
| 19 | `project_type_id` | CHAR(32) | uuid | Y |  |
| 20 | `property_type_id` | CHAR(32) | uuid | Y |  |
| 21 | `budget_range_id` | CHAR(32) | uuid | Y |  |
| 22 | `message` | TEXT | text | Y |  |
| 23 | `status` | VARCHAR(20) | varchar(20) |  | 'NEW' |
| 24 | `status_changed_on` | VARCHAR(27) | timestamptz |  |  |
| 25 | `priority` | VARCHAR(10) | varchar(10) |  | 'MEDIUM' |
| 26 | `source_id` | CHAR(32) | uuid |  |  |
| 27 | `source_detail` | VARCHAR(200) | varchar(200) | Y |  |
| 28 | `utm_source` | VARCHAR(100) | varchar(100) | Y |  |
| 29 | `utm_medium` | VARCHAR(100) | varchar(100) | Y |  |
| 30 | `utm_campaign` | VARCHAR(100) | varchar(100) | Y |  |
| 31 | `utm_term` | VARCHAR(100) | varchar(100) | Y |  |
| 32 | `utm_content` | VARCHAR(100) | varchar(100) | Y |  |
| 33 | `landing_page` | VARCHAR(500) | varchar(500) | Y |  |
| 34 | `referrer_url` | VARCHAR(500) | varchar(500) | Y |  |
| 35 | `assigned_to` | CHAR(32) | uuid | Y |  |
| 36 | `assigned_on` | VARCHAR(27) | timestamptz | Y |  |
| 37 | `next_follow_up_on` | VARCHAR(27) | timestamptz | Y |  |
| 38 | `last_activity_on` | VARCHAR(27) | timestamptz | Y |  |
| 39 | `expected_close_on` | DATE | date | Y |  |
| 40 | `quoted_amount_minor` | BIGINT | int8 | Y |  |
| 41 | `currency` | CHAR(3) | bpchar(3) |  | 'INR'::bpchar |
| 42 | `won_on` | VARCHAR(27) | timestamptz | Y |  |
| 43 | `lost_on` | VARCHAR(27) | timestamptz | Y |  |
| 44 | `lost_reason_id` | CHAR(32) | uuid | Y |  |
| 45 | `lost_reason_note` | VARCHAR(1000) | varchar(1000) | Y |  |
| 46 | `duplicate_status` | VARCHAR(15) | varchar(15) |  | 'NONE' |
| 47 | `duplicate_of_lead_id` | CHAR(32) | uuid | Y |  |
| 48 | `consent_contact` | BOOLEAN | bool |  | false |
| 49 | `consent_policy_version` | VARCHAR(20) | varchar(20) | Y |  |
| 50 | `consent_captured_on` | VARCHAR(27) | timestamptz | Y |  |
| 51 | `consent_channel` | VARCHAR(20) | varchar(20) | Y |  |
| 52 | `consent_source_page` | VARCHAR(500) | varchar(500) | Y |  |
| 53 | `consent_ip_address` | VARCHAR(45) | varchar(45) | Y |  |
| 54 | `intake_idempotency_key` | VARCHAR(64) | varchar(64) | Y |  |
| 55 | `intake_request_fingerprint` | CHAR(64) | bpchar(64) | Y |  |
| 56 | `intake_unmapped` | JSON | jsonb | Y |  |
| 57 | `spam_status` | VARCHAR(15) | varchar(15) |  | 'NONE' |
| 58 | `consent_withdrawn_on` | VARCHAR(27) | timestamptz | Y |  |
| 59 | `consent_withdrawal_channel` | VARCHAR(20) | varchar(20) | Y |  |
| 60 | `consent_withdrawal_note` | VARCHAR(500) | varchar(500) | Y |  |
| 61 | `search_text` | TEXT | text |  | ''::text |
| 62 | `anonymized_on` | VARCHAR(27) | timestamptz | Y |  |

**FKs:** `fk_lead__assigned_to` (assigned_to) → app_user.id ON DELETE RESTRICT; `fk_lead__budget_range_id` (budget_range_id) → lookup_value.id ON DELETE RESTRICT; `fk_lead__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_lead__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_lead__duplicate_of_lead_id` (duplicate_of_lead_id) → lead.id ON DELETE RESTRICT; `fk_lead__lost_reason_id` (lost_reason_id) → lookup_value.id ON DELETE RESTRICT; `fk_lead__project_type_id` (project_type_id) → lookup_value.id ON DELETE RESTRICT; `fk_lead__property_type_id` (property_type_id) → lookup_value.id ON DELETE RESTRICT; `fk_lead__source_id` (source_id) → lookup_value.id ON DELETE RESTRICT; `fk_lead__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_lead__assigned_status` (assigned_to, status, created_on DESC) WHERE (is_deleted = false)
- `ix_lead__created_by` (created_by) WHERE (is_deleted = false)
- `ix_lead__created_on` (created_on DESC)
- `ix_lead__email_normalized` (email_normalized) WHERE ((email_normalized IS NOT NULL) AND (is_deleted = false))
- `ix_lead__next_follow_up` (next_follow_up_on) WHERE (((status) <> ALL ((ARRAY['WON', 'LOST'])[])) AND (is_deleted = false))
- `ix_lead__phone` (phone) WHERE (is_deleted = false)
- `ix_lead__retention` (status, status_changed_on) WHERE (((status) = ANY ((ARRAY['WON', 'LOST'])[])) AND (anonymized_on IS NULL))
- `ix_lead__source` (source_id, created_on DESC) WHERE (is_deleted = false)
- `ix_lead__spam_queue` (spam_status, created_on DESC) WHERE (((spam_status) = 'SUSPECTED') AND (is_deleted = false))
- `ix_lead__status_created` (status, created_on DESC) WHERE (is_deleted = false)
- `ux_lead__intake_idempotency_key` UNIQUE (intake_idempotency_key) WHERE (intake_idempotency_key IS NOT NULL)
- `ux_lead__lead_number` UNIQUE (lead_number) WHERE (is_deleted = false)
- `ux_lead__public_reference` UNIQUE (public_reference)

**Table-specific CHECKs:** `ck_lead__assigned_consistency`; `ck_lead__consent_channel`; `ck_lead__consent_complete`; `ck_lead__consent_withdrawal_channel`; `ck_lead__duplicate_status`; `ck_lead__lost_consistency`; `ck_lead__message_len`; `ck_lead__not_self_duplicate`; `ck_lead__priority`; `ck_lead__quoted_amount`; `ck_lead__spam_status`; `ck_lead__status`; `ck_lead__withdrawal_consistency`; `ck_lead__won_consistency`

###### `lead_activity` — 26 columns, PK pk_lead_activity(id), 6 FKs, 3 indexes, 13 portable CHECKs + 18 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `lead_id` | CHAR(32) | uuid |  |  |
| 11 | `activity_type` | VARCHAR(20) | varchar(20) |  |  |
| 12 | `is_system_generated` | BOOLEAN | bool |  | false |
| 13 | `activity_status` | VARCHAR(12) | varchar(12) |  | 'COMPLETED' |
| 14 | `subject` | VARCHAR(200) | varchar(200) |  |  |
| 15 | `description` | TEXT | text | Y |  |
| 16 | `direction` | VARCHAR(10) | varchar(10) | Y |  |
| 17 | `scheduled_on` | VARCHAR(27) | timestamptz | Y |  |
| 18 | `completed_on` | VARCHAR(27) | timestamptz | Y |  |
| 19 | `duration_minutes` | INTEGER | int4 | Y |  |
| 20 | `outcome_id` | CHAR(32) | uuid | Y |  |
| 21 | `owner_user_id` | CHAR(32) | uuid |  |  |
| 22 | `location` | VARCHAR(300) | varchar(300) | Y |  |
| 23 | `from_status` | VARCHAR(20) | varchar(20) | Y |  |
| 24 | `to_status` | VARCHAR(20) | varchar(20) | Y |  |
| 25 | `cancelled_reason` | VARCHAR(300) | varchar(300) | Y |  |
| 26 | `metadata` | JSON | jsonb | Y |  |

**FKs:** `fk_lead_activity__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_lead_activity__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_lead_activity__lead_id` (lead_id) → lead.id ON DELETE RESTRICT; `fk_lead_activity__outcome_id` (outcome_id) → lookup_value.id ON DELETE RESTRICT; `fk_lead_activity__owner_user_id` (owner_user_id) → app_user.id ON DELETE RESTRICT; `fk_lead_activity__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_lead_activity__lead_planned` (lead_id, scheduled_on) WHERE (((activity_status) = 'PLANNED') AND (is_deleted = false))
- `ix_lead_activity__lead_timeline` (lead_id, created_on DESC) WHERE (is_deleted = false)
- `ix_lead_activity__owner_planned` (owner_user_id, scheduled_on) WHERE (((activity_status) = 'PLANNED') AND (is_deleted = false))

**Table-specific CHECKs:** `ck_lead_activity__completed_has_time`; `ck_lead_activity__description_len`; `ck_lead_activity__direction`; `ck_lead_activity__duration`; `ck_lead_activity__from_status`; `ck_lead_activity__planned_has_schedule`; `ck_lead_activity__status`; `ck_lead_activity__status_change_fields`; `ck_lead_activity__to_status`; `ck_lead_activity__type`

###### `lead_note` — 13 columns, PK pk_lead_note(id), 4 FKs, 2 indexes, 5 portable CHECKs + 8 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `lead_id` | CHAR(32) | uuid |  |  |
| 11 | `body` | TEXT | text |  |  |
| 12 | `is_pinned` | BOOLEAN | bool |  | false |
| 13 | `visibility` | VARCHAR(20) | varchar(20) |  | 'INTERNAL' |

**FKs:** `fk_lead_note__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_lead_note__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_lead_note__lead_id` (lead_id) → lead.id ON DELETE RESTRICT; `fk_lead_note__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_lead_note__created_by` (created_by) WHERE (is_deleted = false)
- `ix_lead_note__lead_created` (lead_id, is_pinned DESC, created_on DESC) WHERE (is_deleted = false)

**Table-specific CHECKs:** `ck_lead_note__body_len`; `ck_lead_note__visibility`

###### `lookup_category` — 14 columns, PK pk_lookup_category(id), 3 FKs, 1 indexes, 3 portable CHECKs + 10 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `code` | VARCHAR(50) | varchar(50) |  |  |
| 11 | `name` | VARCHAR(100) | varchar(100) |  |  |
| 12 | `description` | VARCHAR(500) | varchar(500) | Y |  |
| 13 | `module` | VARCHAR(50) | varchar(50) |  |  |
| 14 | `is_system` | BOOLEAN | bool |  | true |

**FKs:** `fk_lookup_category__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_lookup_category__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_lookup_category__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ux_lookup_category__code` UNIQUE (code) WHERE (is_deleted = false)

###### `lookup_value` — 16 columns, PK pk_lookup_value(id), 4 FKs, 2 indexes, 3 portable CHECKs + 11 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `category_id` | CHAR(32) | uuid |  |  |
| 11 | `code` | VARCHAR(50) | varchar(50) |  |  |
| 12 | `label` | VARCHAR(120) | varchar(120) |  |  |
| 13 | `description` | VARCHAR(500) | varchar(500) | Y |  |
| 14 | `sort_order` | INTEGER | int4 |  | 100 |
| 15 | `is_active` | BOOLEAN | bool |  | true |
| 16 | `attributes` | JSON | jsonb | Y |  |

**FKs:** `fk_lookup_value__category_id` (category_id) → lookup_category.id ON DELETE RESTRICT; `fk_lookup_value__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_lookup_value__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_lookup_value__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_lookup_value__category_active` (category_id, is_active, sort_order)
- `ux_lookup_value__category_code` UNIQUE (category_id, code) WHERE (is_deleted = false)

###### `mfa_challenge` — 17 columns, PK pk_mfa_challenge(id), 5 FKs, 2 indexes, 6 portable CHECKs + 10 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `user_id` | CHAR(32) | uuid |  |  |
| 11 | `purpose` | VARCHAR(20) | varchar(20) |  |  |
| 12 | `token_hash` | CHAR(64) | bpchar(64) |  |  |
| 13 | `session_id` | CHAR(32) | uuid | Y |  |
| 14 | `expires_on` | VARCHAR(27) | timestamptz |  |  |
| 15 | `failed_attempts` | INTEGER | int4 |  | 0 |
| 16 | `completed_on` | VARCHAR(27) | timestamptz | Y |  |
| 17 | `ip_address` | VARCHAR(45) | varchar(45) | Y |  |

**FKs:** `fk_mfa_challenge__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_mfa_challenge__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_mfa_challenge__session_id` (session_id) → user_session.id ON DELETE RESTRICT; `fk_mfa_challenge__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT; `fk_mfa_challenge__user_id` (user_id) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_mfa_challenge__expires_on` (expires_on)
- `ux_mfa_challenge__token_hash` UNIQUE (token_hash)

**Table-specific CHECKs:** `ck_mfa_challenge__failed_attempts`; `ck_mfa_challenge__never_deleted`; `ck_mfa_challenge__purpose`

###### `notification` — 18 columns, PK pk_notification(id), 5 FKs, 4 indexes, 4 portable CHECKs + 13 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `recipient_user_id` | CHAR(32) | uuid |  |  |
| 11 | `notification_type` | VARCHAR(60) | varchar(60) |  |  |
| 12 | `title` | VARCHAR(200) | varchar(200) |  |  |
| 13 | `body` | VARCHAR(1000) | varchar(1000) | Y |  |
| 14 | `entity_type` | VARCHAR(60) | varchar(60) | Y |  |
| 15 | `entity_id` | CHAR(32) | uuid | Y |  |
| 16 | `link_path` | VARCHAR(300) | varchar(300) | Y |  |
| 17 | `read_on` | VARCHAR(27) | timestamptz | Y |  |
| 18 | `source_event_id` | CHAR(32) | uuid | Y |  |

**FKs:** `fk_notification__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_notification__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_notification__recipient_user_id` (recipient_user_id) → app_user.id ON DELETE RESTRICT; `fk_notification__source_event_id` (source_event_id) → outbox_event.id ON DELETE RESTRICT; `fk_notification__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_notification__entity` (entity_type, entity_id) WHERE (entity_id IS NOT NULL)
- `ix_notification__recipient_all` (recipient_user_id, created_on DESC)
- `ix_notification__recipient_unread` (recipient_user_id, created_on DESC) WHERE ((read_on IS NULL) AND (is_deleted = false))
- `ux_notification__event_recipient` UNIQUE (source_event_id, recipient_user_id) WHERE (source_event_id IS NOT NULL)

**Table-specific CHECKs:** `ck_notification__entity_pair`

###### `number_sequence` — 15 columns, PK pk_number_sequence(id), 3 FKs, 1 indexes, 6 portable CHECKs + 9 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `sequence_key` | VARCHAR(50) | varchar(50) |  |  |
| 11 | `prefix` | VARCHAR(20) | varchar(20) |  |  |
| 12 | `reset_period` | VARCHAR(10) | varchar(10) |  | 'YEAR' |
| 13 | `current_period` | VARCHAR(10) | varchar(10) | Y |  |
| 14 | `next_value` | BIGINT | int8 |  | 1 |
| 15 | `padding` | INTEGER | int4 |  | 6 |

**FKs:** `fk_number_sequence__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_number_sequence__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_number_sequence__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ux_number_sequence__key` UNIQUE (sequence_key) WHERE (is_deleted = false)

**Table-specific CHECKs:** `ck_number_sequence__next_value_positive`; `ck_number_sequence__padding_range`; `ck_number_sequence__reset_period`

###### `outbox_event` — 20 columns, PK pk_outbox_event(id), 3 FKs, 2 indexes, 6 portable CHECKs + 12 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `event_type` | VARCHAR(80) | varchar(80) |  |  |
| 11 | `aggregate_type` | VARCHAR(60) | varchar(60) |  |  |
| 12 | `aggregate_id` | CHAR(32) | uuid |  |  |
| 13 | `payload` | JSON | jsonb |  |  |
| 14 | `status` | VARCHAR(12) | varchar(12) |  | 'PENDING' |
| 15 | `attempts` | INTEGER | int4 |  | 0 |
| 16 | `next_attempt_on` | VARCHAR(27) | timestamptz |  |  |
| 17 | `locked_by` | VARCHAR(64) | varchar(64) | Y |  |
| 18 | `locked_on` | VARCHAR(27) | timestamptz | Y |  |
| 19 | `processed_on` | VARCHAR(27) | timestamptz | Y |  |
| 20 | `last_error` | VARCHAR(2000) | varchar(2000) | Y |  |

**FKs:** `fk_outbox_event__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_outbox_event__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_outbox_event__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_outbox_event__aggregate` (aggregate_type, aggregate_id)
- `ix_outbox_event__due` (status, next_attempt_on) WHERE ((status) = ANY ((ARRAY['PENDING', 'FAILED'])[]))

**Table-specific CHECKs:** `ck_outbox_event__attempts`; `ck_outbox_event__never_deleted`; `ck_outbox_event__status`

###### `permission` — 21 columns, PK pk_permission(id), 3 FKs, 2 indexes, 7 portable CHECKs + 17 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `code` | VARCHAR(100) | varchar(100) |  |  |
| 11 | `module` | VARCHAR(50) | varchar(50) |  |  |
| 12 | `resource` | VARCHAR(50) | varchar(50) |  |  |
| 13 | `action` | VARCHAR(50) | varchar(50) |  |  |
| 14 | `name` | VARCHAR(120) | varchar(120) |  |  |
| 15 | `description` | VARCHAR(500) | varchar(500) | Y |  |
| 16 | `supports_scope` | BOOLEAN | bool |  | false |
| 17 | `is_sensitive` | BOOLEAN | bool |  | false |
| 18 | `sensitivity_class` | VARCHAR(20) | varchar(20) | Y |  |
| 19 | `grant_path` | VARCHAR(25) | varchar(25) |  | 'STANDARD' |
| 20 | `is_system` | BOOLEAN | bool |  | true |
| 21 | `requirement_ref` | VARCHAR(50) | varchar(50) | Y |  |

**FKs:** `fk_permission__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_permission__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_permission__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_permission__module_resource` (module, resource)
- `ux_permission__code` UNIQUE (code) WHERE (is_deleted = false)

**Table-specific CHECKs:** `ck_permission__code_pattern`; `ck_permission__grant_path`; `ck_permission__sensitivity`; `ck_permission__sensitivity_class`

###### `refresh_token` — 16 columns, PK pk_refresh_token(id), 4 FKs, 3 indexes, 4 portable CHECKs + 8 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `session_id` | CHAR(32) | uuid |  |  |
| 11 | `token_hash` | CHAR(64) | bpchar(64) |  |  |
| 12 | `issued_on` | VARCHAR(27) | timestamptz |  |  |
| 13 | `expires_on` | VARCHAR(27) | timestamptz |  |  |
| 14 | `used_on` | VARCHAR(27) | timestamptz | Y |  |
| 15 | `replaced_by_id` | CHAR(32) | uuid | Y |  |
| 16 | `grace_used_on` | VARCHAR(27) | timestamptz | Y |  |

**FKs:** `fk_refresh_token__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_refresh_token__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_refresh_token__session_id` (session_id) → user_session.id ON DELETE RESTRICT; `fk_refresh_token__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_refresh_token__expires_on` (expires_on)
- `ix_refresh_token__session_id` (session_id)
- `ux_refresh_token__token_hash` UNIQUE (token_hash)

**Table-specific CHECKs:** `ck_refresh_token__never_deleted`

###### `role` — 18 columns, PK pk_role(id), 3 FKs, 2 indexes, 5 portable CHECKs + 13 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `code` | VARCHAR(50) | varchar(50) |  |  |
| 11 | `name` | VARCHAR(100) | varchar(100) |  |  |
| 12 | `name_normalized` | VARCHAR(100) | varchar(100) |  |  |
| 13 | `description` | VARCHAR(500) | varchar(500) | Y |  |
| 14 | `is_system` | BOOLEAN | bool |  | false |
| 15 | `is_assignable` | BOOLEAN | bool |  | true |
| 16 | `grant_path` | VARCHAR(25) | varchar(25) |  | 'STANDARD' |
| 17 | `mfa_required` | BOOLEAN | bool |  | false |
| 18 | `sort_order` | INTEGER | int4 |  | 100 |

**FKs:** `fk_role__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_role__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_role__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ux_role__code` UNIQUE (code) WHERE (is_deleted = false)
- `ux_role__name_normalized` UNIQUE (name_normalized) WHERE (is_deleted = false)

**Table-specific CHECKs:** `ck_role__code_pattern`; `ck_role__grant_path`

###### `role_permission` — 12 columns, PK pk_role_permission(id), 5 FKs, 2 indexes, 4 portable CHECKs + 8 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `role_id` | CHAR(32) | uuid |  |  |
| 11 | `permission_id` | CHAR(32) | uuid |  |  |
| 12 | `scope` | VARCHAR(10) | varchar(10) |  | 'ALL' |

**FKs:** `fk_role_permission__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_role_permission__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_role_permission__permission_id` (permission_id) → permission.id ON DELETE RESTRICT; `fk_role_permission__role_id` (role_id) → role.id ON DELETE RESTRICT; `fk_role_permission__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_role_permission__permission_id` (permission_id) WHERE (is_deleted = false)
- `ux_role_permission__role_perm` UNIQUE (role_id, permission_id) WHERE (is_deleted = false)

**Table-specific CHECKs:** `ck_role_permission__scope`

###### `security_event_log` — 29 columns, PK pk_security_event_log(id), 4 FKs, 7 indexes, 9 portable CHECKs + 23 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `event_type` | VARCHAR(50) | varchar(50) |  |  |
| 11 | `event_category` | VARCHAR(20) | varchar(20) |  |  |
| 12 | `outcome` | VARCHAR(10) | varchar(10) |  |  |
| 13 | `severity` | VARCHAR(10) | varchar(10) |  | 'INFO' |
| 14 | `subject_user_id` | CHAR(32) | uuid | Y |  |
| 15 | `session_id` | CHAR(32) | uuid | Y |  |
| 16 | `email_attempted_hash` | CHAR(64) | bpchar(64) | Y |  |
| 17 | `failure_reason` | VARCHAR(40) | varchar(40) | Y |  |
| 18 | `permission_code` | VARCHAR(100) | varchar(100) | Y |  |
| 19 | `target_entity_type` | VARCHAR(60) | varchar(60) | Y |  |
| 20 | `target_entity_id` | CHAR(32) | uuid | Y |  |
| 21 | `occurred_on` | VARCHAR(27) | timestamptz |  |  |
| 22 | `ip_address` | VARCHAR(45) | varchar(45) | Y |  |
| 23 | `user_agent` | VARCHAR(500) | varchar(500) | Y |  |
| 24 | `request_id` | VARCHAR(64) | varchar(64) | Y |  |
| 25 | `detail` | JSON | jsonb | Y |  |
| 26 | `chain_seq` | BIGINT | int8 |  |  |
| 27 | `prev_hash` | CHAR(64) | bpchar(64) | Y |  |
| 28 | `chain_key_label` | VARCHAR(40) | varchar(40) |  |  |
| 29 | `row_hash` | CHAR(64) | bpchar(64) |  |  |

**FKs:** `fk_security_event_log__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_security_event_log__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_security_event_log__subject_user_id` (subject_user_id) → app_user.id ON DELETE RESTRICT; `fk_security_event_log__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_security_event_log__ip` (ip_address, occurred_on DESC)
- `ix_security_event_log__occurred` (occurred_on DESC, id DESC)
- `ix_security_event_log__outcome` (outcome, occurred_on DESC) WHERE ((outcome) <> 'SUCCESS')
- `ix_security_event_log__subject` (subject_user_id, occurred_on DESC)
- `ix_security_event_log__target` (target_entity_type, target_entity_id, occurred_on DESC) WHERE (target_entity_id IS NOT NULL)
- `ix_security_event_log__type` (event_type, occurred_on DESC)
- `ux_security_event_log__chain_seq` UNIQUE (chain_seq)

**Table-specific CHECKs:** `ck_security_event_log__chain_seq_positive`; `ck_security_event_log__event_category`; `ck_security_event_log__immutable_contract`; `ck_security_event_log__outcome`; `ck_security_event_log__severity`; `ck_security_event_log__target_pair`

**Triggers (both engines):** trg_security_event_log__no_update, trg_security_event_log__no_delete

###### `user_action_token` — 17 columns, PK pk_user_action_token(id), 4 FKs, 2 indexes, 5 portable CHECKs + 10 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `user_id` | CHAR(32) | uuid |  |  |
| 11 | `purpose` | VARCHAR(25) | varchar(25) |  |  |
| 12 | `token_hash` | CHAR(64) | bpchar(64) |  |  |
| 13 | `expires_on` | VARCHAR(27) | timestamptz |  |  |
| 14 | `sent_to_email_normalized` | VARCHAR(254) | varchar(254) |  |  |
| 15 | `used_on` | VARCHAR(27) | timestamptz | Y |  |
| 16 | `invalidated_on` | VARCHAR(27) | timestamptz | Y |  |
| 17 | `requested_ip` | VARCHAR(45) | varchar(45) | Y |  |

**FKs:** `fk_user_action_token__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_user_action_token__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_user_action_token__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT; `fk_user_action_token__user_id` (user_id) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_user_action_token__user_open` (user_id, purpose) WHERE ((used_on IS NULL) AND (invalidated_on IS NULL))
- `ux_user_action_token__token_hash` UNIQUE (token_hash)

**Table-specific CHECKs:** `ck_user_action_token__never_deleted`; `ck_user_action_token__purpose`

###### `user_credential` — 16 columns, PK pk_user_credential(id), 4 FKs, 1 indexes, 4 portable CHECKs + 8 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `user_id` | CHAR(32) | uuid |  |  |
| 11 | `password_hash` | VARCHAR(255) | varchar(255) | Y |  |
| 12 | `password_changed_on` | VARCHAR(27) | timestamptz | Y |  |
| 13 | `must_change_password` | BOOLEAN | bool |  | false |
| 14 | `failed_login_count` | INTEGER | int4 |  | 0 |
| 15 | `failed_window_started_on` | VARCHAR(27) | timestamptz | Y |  |
| 16 | `locked_until` | VARCHAR(27) | timestamptz | Y |  |

**FKs:** `fk_user_credential__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_user_credential__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_user_credential__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT; `fk_user_credential__user_id` (user_id) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ux_user_credential__user_id` UNIQUE (user_id) WHERE (is_deleted = false)

**Table-specific CHECKs:** `ck_user_credential__failed_login_count`

###### `user_mfa_factor` — 21 columns, PK pk_user_mfa_factor(id), 4 FKs, 1 indexes, 7 portable CHECKs + 11 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `user_id` | CHAR(32) | uuid |  |  |
| 11 | `factor_type` | VARCHAR(10) | varchar(10) |  | 'TOTP' |
| 12 | `status` | VARCHAR(10) | varchar(10) |  | 'PENDING' |
| 13 | `secret_ciphertext` | TEXT | text |  |  |
| 14 | `wrapped_data_key` | TEXT | text |  |  |
| 15 | `kms_key_arn` | VARCHAR(2048) | varchar(2048) |  |  |
| 16 | `label` | VARCHAR(100) | varchar(100) | Y |  |
| 17 | `confirmed_on` | VARCHAR(27) | timestamptz | Y |  |
| 18 | `last_used_step` | BIGINT | int8 | Y |  |
| 19 | `last_used_on` | VARCHAR(27) | timestamptz | Y |  |
| 20 | `revoked_on` | VARCHAR(27) | timestamptz | Y |  |
| 21 | `revoke_reason` | VARCHAR(20) | varchar(20) | Y |  |

**FKs:** `fk_user_mfa_factor__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_user_mfa_factor__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_user_mfa_factor__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT; `fk_user_mfa_factor__user_id` (user_id) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ux_user_mfa_factor__user_live` UNIQUE (user_id, factor_type, status) WHERE (((status) = ANY ((ARRAY['PENDING', 'ACTIVE'])[])) AND (is_deleted = false))

**Table-specific CHECKs:** `ck_user_mfa_factor__active_confirmed`; `ck_user_mfa_factor__factor_type`; `ck_user_mfa_factor__revoke_reason`; `ck_user_mfa_factor__status`

###### `user_mfa_recovery_code` — 14 columns, PK pk_user_mfa_recovery_code(id), 4 FKs, 3 indexes, 4 portable CHECKs + 8 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `user_id` | CHAR(32) | uuid |  |  |
| 11 | `batch_id` | CHAR(32) | uuid |  |  |
| 12 | `code_hash` | CHAR(64) | bpchar(64) |  |  |
| 13 | `used_on` | VARCHAR(27) | timestamptz | Y |  |
| 14 | `invalidated_on` | VARCHAR(27) | timestamptz | Y |  |

**FKs:** `fk_user_mfa_recovery_code__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_user_mfa_recovery_code__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_user_mfa_recovery_code__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT; `fk_user_mfa_recovery_code__user_id` (user_id) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_user_mfa_recovery_code__batch` (user_id, batch_id)
- `ix_user_mfa_recovery_code__user_open` (user_id) WHERE ((used_on IS NULL) AND (invalidated_on IS NULL))
- `ux_user_mfa_recovery_code__hash` UNIQUE (code_hash)

**Table-specific CHECKs:** `ck_user_mfa_recovery_code__never_deleted`

###### `user_permission` — 16 columns, PK pk_user_permission(id), 5 FKs, 2 indexes, 6 portable CHECKs + 10 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `user_id` | CHAR(32) | uuid |  |  |
| 11 | `permission_id` | CHAR(32) | uuid |  |  |
| 12 | `effect` | VARCHAR(5) | varchar(5) |  | 'GRANT' |
| 13 | `scope` | VARCHAR(10) | varchar(10) |  | 'ALL' |
| 14 | `valid_from` | VARCHAR(27) | timestamptz | Y |  |
| 15 | `valid_until` | VARCHAR(27) | timestamptz | Y |  |
| 16 | `reason` | VARCHAR(500) | varchar(500) |  |  |

**FKs:** `fk_user_permission__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_user_permission__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_user_permission__permission_id` (permission_id) → permission.id ON DELETE RESTRICT; `fk_user_permission__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT; `fk_user_permission__user_id` (user_id) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_user_permission__permission_id` (permission_id) WHERE (is_deleted = false)
- `ux_user_permission__user_perm` UNIQUE (user_id, permission_id) WHERE (is_deleted = false)

**Table-specific CHECKs:** `ck_user_permission__effect`; `ck_user_permission__scope`; `ck_user_permission__validity_order`

###### `user_role` — 14 columns, PK pk_user_role(id), 5 FKs, 2 indexes, 4 portable CHECKs + 8 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `user_id` | CHAR(32) | uuid |  |  |
| 11 | `role_id` | CHAR(32) | uuid |  |  |
| 12 | `valid_from` | VARCHAR(27) | timestamptz | Y |  |
| 13 | `valid_until` | VARCHAR(27) | timestamptz | Y |  |
| 14 | `reason` | VARCHAR(500) | varchar(500) | Y |  |

**FKs:** `fk_user_role__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_user_role__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_user_role__role_id` (role_id) → role.id ON DELETE RESTRICT; `fk_user_role__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT; `fk_user_role__user_id` (user_id) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_user_role__role_id` (role_id) WHERE (is_deleted = false)
- `ux_user_role__user_role` UNIQUE (user_id, role_id) WHERE (is_deleted = false)

**Table-specific CHECKs:** `ck_user_role__validity_order`

###### `user_session` — 24 columns, PK pk_user_session(id), 5 FKs, 2 indexes, 7 portable CHECKs + 13 SQLite-only CHECKs

| # | Column | SQLite | PostgreSQL | N | Default |
|---|---|---|---|---|---|
| 1 | `id` | CHAR(32) | uuid |  |  |
| 2 | `created_on` | VARCHAR(27) | timestamptz |  |  |
| 3 | `updated_on` | VARCHAR(27) | timestamptz |  |  |
| 4 | `created_by` | CHAR(32) | uuid |  |  |
| 5 | `updated_by` | CHAR(32) | uuid |  |  |
| 6 | `is_deleted` | BOOLEAN | bool |  | false |
| 7 | `deleted_on` | VARCHAR(27) | timestamptz | Y |  |
| 8 | `deleted_by` | CHAR(32) | uuid | Y |  |
| 9 | `version` | INTEGER | int4 |  | 1 |
| 10 | `user_id` | CHAR(32) | uuid |  |  |
| 11 | `started_on` | VARCHAR(27) | timestamptz |  |  |
| 12 | `last_seen_on` | VARCHAR(27) | timestamptz |  |  |
| 13 | `idle_expires_on` | VARCHAR(27) | timestamptz |  |  |
| 14 | `absolute_expires_on` | VARCHAR(27) | timestamptz |  |  |
| 15 | `session_type` | VARCHAR(10) | varchar(10) |  | 'FULL' |
| 16 | `auth_methods` | VARCHAR(50) | varchar(50) |  |  |
| 17 | `reauth_on` | VARCHAR(27) | timestamptz | Y |  |
| 18 | `mfa_verified_on` | VARCHAR(27) | timestamptz | Y |  |
| 19 | `revoked_on` | VARCHAR(27) | timestamptz | Y |  |
| 20 | `revoked_by` | CHAR(32) | uuid | Y |  |
| 21 | `revoke_reason` | VARCHAR(30) | varchar(30) | Y |  |
| 22 | `ip_address` | VARCHAR(45) | varchar(45) | Y |  |
| 23 | `user_agent` | VARCHAR(500) | varchar(500) | Y |  |
| 24 | `device_label` | VARCHAR(100) | varchar(100) | Y |  |

**FKs:** `fk_user_session__created_by` (created_by) → app_user.id ON DELETE RESTRICT; `fk_user_session__deleted_by` (deleted_by) → app_user.id ON DELETE RESTRICT; `fk_user_session__revoked_by` (revoked_by) → app_user.id ON DELETE RESTRICT; `fk_user_session__updated_by` (updated_by) → app_user.id ON DELETE RESTRICT; `fk_user_session__user_id` (user_id) → app_user.id ON DELETE RESTRICT

**Indexes (PG definition; SQLite identical columns/predicate with `is_deleted = 0`):**

- `ix_user_session__absolute_expires_on` (absolute_expires_on)
- `ix_user_session__user_active` (user_id) WHERE (revoked_on IS NULL)

**Table-specific CHECKs:** `ck_user_session__auth_methods`; `ck_user_session__never_deleted`; `ck_user_session__revoke_reason`; `ck_user_session__session_type`

### Appendix F — Frontend working paper

#### F.1 Command results

| # | Command | Exit | Result | vs claim |
|---|---|---|---|---|
| 1 | `npm ci` | 0 | 378 packages added; "195 vulnerabilities (173 low, 5 high, 17 critical)"; EBADENGINE warning (`errorstacks@2.4.2` wants node ≥24) | matches #9 |
| 2 | `npm audit` (configured registry `npm.devsnc.com` → Nexus IQ policy feed) | 1 | 195 total: **19 critical, 5 high, 0 moderate, 171 low** (JSON metadata; the text summary line says 17 critical). 171 "low" are Nexus *policy* hits ("component older than 5 years", "license unknown"), not CVEs | #9 said "dev tooling"; confirmed |
| 3 | `npm audit --omit=dev` (Nexus) | 0 | **0 vulnerabilities** | matches #15 |
| 4 | `npm audit --registry=https://registry.npmjs.org` (GitHub advisory DB, for cross-check) | 1 | **7: 0 critical, 6 high, 1 moderate** | not reported by author |
| 5 | `npm audit --omit=dev --registry=https://registry.npmjs.org` | 0 | 0 vulnerabilities | — |
| 6 | `npm run typecheck` | 0 | clean | matches |
| 7 | `npm run lint:tokens` | 0 | "no raw colour values outside tokens.css" | matches |
| 8 | `npm run test:contrast` | 0 | 58 pairs pass, light + dark | matches |
| 9 | `npm test` (wtr, Playwright Chromium already cached) | 0 | **6 files, 47 passed, 0 failed** | matches #12 |
| 10 | `npm run build` | 0 | initial `index-*.js` 125.63 kB / **39.48 kB gzip**; lazy chunks auth/leads/admin/audit; `sourcemap: true` emits `.map` files | matches #13 |
| 11 | `node e2e/workspace.e2e.mjs` | 0 | **7/7**, console errors 0 | matches #16 |
| 12 | `node e2e/access.e2e.mjs` | 0 | **12/12** (see F-9 on what two checks really prove) | matches #17 |
| 13 | `node e2e/site.e2e.mjs` | 0 | **7/7** | matches #18 |
| 14 | `node e2e/axe.e2e.mjs` | 1 | workspace 8/8 screens 0 violations; website idle + error state: 1 rule, **19 serious color-contrast nodes** | matches #19 |

Dependency detail (task 1):
- **Critical (Nexus feed, IDs are internal/2026 CVE numbers I cannot verify against a public DB):** `vite` (direct devDep; CVE-2026-39365, CVE-2026-53632, sonatype-2026-001849 + via `postcss`→`source-map-js` CVE-2026-93749), `@web/test-runner` (direct; via `@web/dev-server`, `@web/dev-server-rollup`, `@rollup/plugin-node-resolve`, `deepmerge` CVE-2026-93753), `fast-glob`/`micromatch`/`braces` (CVE-2026-93687), `@puppeteer/browsers`/`extract-zip` (CVE-2026-19693, CVE-2026-56876), `pac-proxy-agent`/`get-uri`/`basic-ftp` (sonatype-2026-007301), `degenerator`/`escodegen`/`source-map`. High: `koa`, `zod`, `chromium-bidi`, `puppeteer-core`, `@web/dev-server-core`.
- **Public GHSA feed:** `esbuild ≤0.24.2 || 0.27.3–0.28.0` (moderate; GHSA-67mh-4wv8-2f99 "any website can send requests to the dev server and read the response", GHSA-g7r4-m6w7-qqqr Windows dev-server arbitrary file read) pulled in by **vite 5.4.21** (fix = vite ≥6.4.3/8.x → requires Node ≥20.19, OI-10); `extract-zip` symlink path traversal / arbitrary write (GHSA-jmr9-qjv8-65gv, GHSA-7pqw-9j4j-h8q3, high) via `@web/test-runner-chrome`→`puppeteer-core`→`@puppeteer/browsers` (only used when downloading browsers; this project uses the Playwright launcher).
- **Exposure:** none ship in the production bundle (`--omit=dev` = 0 in both feeds; runtime deps are only `lit`, `@lit/context`, `@vaadin/router`, `qrcode-generator`). Exposure is (a) developer workstations running `npm run dev` (esbuild/vite dev-server cross-origin read — Vite binds localhost by default, so exploitation needs the developer to visit a malicious page while the dev server runs) and (b) CI/supply-chain (test runner, archive extraction). Neither is an internet-facing production risk.
- **CI:** `.github/workflows/ci.yml` app job runs `npm ci`, playwright install, typecheck, lint:tokens, test:contrast, test, build — **no `npm audit`/dependency scan, no e2e, no axe** (12 §5 requires "dependency + image scan … E2E smoke + axe" on PR; SEC-007). See F-10.
- **Linters:** no ESLint, no Prettier (no binaries in `node_modules/.bin`, no config files) — OI-8 confirmed. 12 §5 PR lint "unsafeHTML, import boundaries" is therefore not automated; I verified manually that `src/**` contains no `unsafeHTML`/`unsafeSVG`/`innerHTML`/`eval`/`new Function`/`document.write`.
- **tsconfig** (`app/tsconfig.json`): `strict: true`, `noImplicitOverride`, `noUnusedLocals`, `noUnusedParameters`, `isolatedModules`, `skipLibCheck: true`. Not enabled: `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitReturns`, `noFallthroughCasesInSwitch`. API responses are cast (`body.data as T`, `client.ts:157`) without runtime validation — acceptable for P0 (ADVISORY).

#### F.2 Public-site contrast nodes

Baseline and current both report **19** nodes (18 at 360 px because `.section-label` is `display:none`), identical selectors/colours except `.form-note`→`#form-note` (same element, gained an `id`). Success and fallback states: same 19 (the "hidden" form is still rendered — F-2). **No node is in labels, inputs, consent text, required/optional markers, error text, error summary, success or fallback panels** — only `#form-note` is inside `<form>`.

| # | Node | Colours / ratio (need 4.5:1) | Location | Pre-exists @778aa8f | Classification | Reason |
|---|---|---|---|---|---|---|
| 1 | `.section-label` "About Veda Spaces" | #827b71 / #fbf7ef 3.91 (10.9 px) | About | yes | Tracked non-blocker | Decorative vertical label, marketing content |
| 2 | `.about-copy > .eyebrow` | #ad6d54 / #fbf7ef 3.85 (12 px) | About | yes | Tracked non-blocker | Eyebrow text |
| 3 | `.portfolio-head .eyebrow` | #ad6d54 / #fffaf3 3.97 | Portfolio | yes | Tracked non-blocker | Eyebrow |
| 4 | `.portfolio-head > p` | #aaa39a / #fffaf3 **2.40** (16 px) | Portfolio | yes | Tracked non-blocker — **highest priority** of the set | Body copy far below AA (colour intended for dark section reused on light) |
| 5–7 | `.case-number` ×3 "Project 0n / Design showcase" | #ad6d54 / #fffaf3 3.97 (11 px) | Case studies | yes | Tracked non-blocker | Meta labels |
| 8–14 | `.process-grid article p` ×7 | #e6d7d2 / #995f4a 3.67 (12.8 px) | Process | yes | Tracked non-blocker | Descriptive copy, `opacity:.75` on copper; fix by removing opacity |
| 15 | `.why-copy > .eyebrow` | #ad6d54 / #fbf7ef 3.85 | Why | yes | Tracked non-blocker | Eyebrow |
| 16 | `.contact-copy > .eyebrow` "Begin your home" | #ad6d54 / #f1e5d7 3.32 | Contact section, outside `<form>` | yes | Tracked non-blocker (fix together with #17) | Adjacent to form but not part of it |
| 17 | `#form-note` / `.form-note` | #746e66 / #f1e5d7 4.06 (11.2 px) | **Inside the enquiry form** | yes | **Required before enabling form** (F-6) | AX-08 applies AX-05 to the public form; text changes when intake is on |
| 18–19 | `.footer-bottom > span` ×2 | #777777 / #191310 4.10 (10.9 px) | Footer | yes | Tracked non-blocker | Copyright/footer meta |

None is a production blocker for the workspace (the site is an existing marketing page outside UI-011's workspace scope and the intake flag is off). None is a false positive (all measured on solid backgrounds with reduced motion; no opacity/animation artefacts). Recommend a follow-up site-wide token fix (OI-11) since WCAG AA is the stated standard.

#### F.3 Conformance

| Req | Status | Basis |
|---|---|---|
| UI-001 Login | **Conforms** | e2e + axe light/dark; autocomplete, uniform error, focus, `?next=` sanitised, captcha after server flag |
| UI-002 Forgot/reset | Conforms (source) — not browser-tested | fragment token + history scrub; journey missing from e2e (F-9) |
| UI-003 Dashboard | Conforms | e2e + axe light/dark; F-8 advisory |
| UI-004 Lead details | Conforms with gap | e2e + axe; mobile stepper keyboard scroll (F-11.1) |
| UI-005 Lead create/edit | **Deviates** | F-1 lost update on "Re-apply mine" (TD-F step 4) |
| UI-006 Users | Conforms (minor) | axe light/dark; `prompt()` for reason (F-11.4) |
| UI-007 Roles | Conforms | axe light/dark |
| UI-008 Permissions | Conforms (source only) | not scanned/e2e |
| UI-009 Audit + security events | Conforms | e2e + axe light/dark |
| UI-010 Brand tokens | Conforms | lint:tokens |
| UI-011 WCAG 2.2 AA light+dark | **Partial** | 0 axe violations light+dark on 10 screens (reviewer-extended), but F-4 (2.4.2 / route focus), F-11; no Firefox/WebKit/200% zoom/manual SR |
| UI-012 360 px lead screens | Conforms (minor) | scrollWidth 360; F-11.1 |
| UI-013 Cosmetic permission UI | Conforms | nav/route guard filtered; server authoritative (browser evidence weak, F-9) |
| UI-014 A11y tokens light+dark checked | Conforms | 58 pairs, runs in CI |
| UI-015 MFA/recovery/step-up screens | Conforms (partial AX-07) | e2e path B enrollment + challenge; no pre-expiry announcement; no manual SR |
| UI-016 AX-01…AX-10 | **Partial** | AX-02/04/05/10 met; AX-01/03/06/07/09 gaps (F-4, F-11); AX-08 public form gaps (F-2, F-3, F-6) |
| UI-017 Approvals + email change | Conforms (source + axe) | not e2e |
| Website intake (LEAD-001/019, 09 §4.11) — flag off | **Not ready to enable** | F-2, F-3, F-6, F-7, `/privacy` missing (OI-5); flag-off behaviour conforms |
| SEC-003 CSP | App: conforms (1 advisory, F-8). Site: **absent** (pre-existing; F-7) | |
| SEC-007 Dependency scanning in CI (frontend) | **Not met** | F-10 |
