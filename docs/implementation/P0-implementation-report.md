# Veda Spaces P0 — Implementation Report

> **Not certified, not merged, not deployed.** This report is the author's evidence for the targeted independent
> re-review that follows the remediation of the independent implementation review. It approves nothing.

| Item | Value |
|---|---|
| Certified architecture | `778aa8fdd918da48340319696ada3ff673e9fb8e` (certified documents unchanged; proposed amendments moved to `docs/proposals/amendments/`, RR-A23) |
| Implementation branch | `implementation/p0-foundation` |
| Reviewed implementation | `9236aa3ade38c33d03a57cf7a064ece29937b109` |
| Independent review | review/p0-independent-implementation-review @ 1aaf019b6c872a075d13e9b3a2a2e9c16489f6f4 — verdict **NOT CERTIFIED** ({'BLOCKER': 1, 'MAJOR': 18, 'MINOR': 20, 'ADVISORY': 25}) |
| Remediation workstream | VEDA-SPACES-P0-IMPLEMENTATION-REMEDIATION-01 (one commit on top of `9236aa3`) |
| Remediation matrix | [P0-review-remediation-matrix.md](P0-review-remediation-matrix.md) (+ `.json`) — all 39 findings, 25 advisories, 11 open issues |
| Open issues | [P0-open-issues.md](P0-open-issues.md) (+ `.json`) — 106 entries incl. every gate |
| Deviations | [P0-implementation-deviations.md](P0-implementation-deviations.md) — DEV-001…DEV-008, none approved |
| Amendments | [docs/proposals/amendments](../proposals/amendments/README.md) — AM-1…AM-13, all PROPOSED, NOT APPROVED |
| Runbooks | [docs/operations/api-runbooks.md](../operations/api-runbooks.md) |
| Evidence | [evidence/remediation/](evidence/remediation/) — raw output of the clean-environment run below |

## 0000. Consolidated owner decision (2026-09-30)

The owner's decisions are recorded in [P0-owner-decision-record.md](P0-owner-decision-record.md):

- **OD-2 and OD-3:** APPROVED.
- **Amendments:**
  - APPROVED: AM-1, AM-3, AM-8.
  - APPROVED WITH CONDITIONS: AM-2, AM-4, AM-5, AM-6, AM-7, AM-11, AM-12, AM-13. AM-4 was approved by the confirmation instruction VEDA-SPACES-P0-FINAL-GOVERNANCE-EVIDENCE-SYNC.
  - DEFERRED: AM-9, AM-10.
- **Gates:** TG-01 and TG-08 APPROVED. The owner waived their evidence entries in the certified-tree decision log for merge readiness; the certified registry is unchanged.
- **Merge safety:** option C APPROVED, not executed.

Reports:
- [P0-gate-status-report.md](P0-gate-status-report.md)
- [P0-amendment-disposition-report.md](P0-amendment-disposition-report.md)
- [P0-merge-readiness-report.md](P0-merge-readiness-report.md)
- [P0-staging-gate-report.md](P0-staging-gate-report.md)
- [P0-production-gate-report.md](P0-production-gate-report.md)

No implementation, architecture, merge, deployment or intake change was made.

## 000. Document-conditions closure (after the document-level check)

This section records the response to the document-level check, `review/p0-independent-implementation-review @ 093cfa6872c209deb9991910c457afcdb4ad2d04`. Its verdict was **READY WITH DOCUMENT CONDITIONS**, and it authorizes no merge or deployment. It reviewed tree `3f5920b17d21214b39414d080d34246746c8c40d`.

This change touches documents, one validation test and the CI checkout depth only. No implementation, schema, security control, authentication, RBAC, governance, API, frontend or `dist/` file changed.

| Condition | Result |
|---|---|
| DC-01 | Merge-safety option C is now an executable procedure. It covers the base commit, the exact `dist/` restore, and the CI treatment: a site-release fixture plus two reviewed test-harness lines. It also covers integrity checks, CI, the merge, verification, the later site release by reverting the keep-live commit, branch hygiene and rollback. The procedure was simulated end to end in a throwaway clone; nothing was pushed. |
| DC-02 | AM-4 now matches the code: 409 INVALID_STATE, 422 for an unknown version, "different version" semantics, and the exact superseded snapshot. It proposes an ordering rule, an erasure exemption for either immutability option, the withdrawal note, and the tracked-deviation consequence of approval. |
| DC-04 | The SHA check covers all governance documents, READMEs, `deployment.md` and `deploy.sh`, for both full and abbreviated SHAs. Every cited SHA must be a known commit with its recorded subject. Role-specific references are asserted, and planted invalid SHAs fail. CI checks out full history, and missing history fails in CI instead of skipping. |
| DC-07 | Reviewer classifications are quoted verbatim, from both reviews. Implementation provenance now separates `6ec2e76` from `3f5920b`. OD-2 and OD-3 are described everywhere as brief instructions approved by the owner on 2026-09-30. TG-01 and TG-08 are PENDING. A test enforces all of this. |
| Not in scope | DC-03 (before production), DC-05 (staging), DC-06 and DC-08 (PostgreSQL release gate). They are recorded in [P0-open-issues.md](P0-open-issues.md). |

## 00. Technical-conditions closure (after the final targeted check)

This section records workstream VEDA-SPACES-P0-TECHNICAL-CONDITIONS-CLOSURE-01.

- **Final targeted check:** `review/p0-independent-implementation-review @ 56c20ba992b519daa79aa3802a28343aab8c0b41`. Verdict: **CERTIFIED WITH TECHNICAL CONDITIONS**. It authorizes no merge or deployment.
- **Reviewed implementation:** `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`. The SHA quoted in the brief, `6ec2e76f156e963c7363c4ad9ce93d0bc0b11f41`, does not exist (FC-A01). No repository document cited it.
- **Owner decision package:** [P0-owner-decision-package.md](P0-owner-decision-package.md). It records no decision.
- **Merge-safety plan:** [P0-merge-safety-plan.md](P0-merge-safety-plan.md). It recommends option C and has not been executed.
- **Evidence:** [evidence/technical-conditions/](evidence/technical-conditions/).

| Condition | Result |
|---|---|
| Amendment text (AM-2, 4, 6, 7, 9, 10, 11, 12, 13) | Corrected per the final check (FC-05, FC-08, FC-12, FC-A05, FC-A06, FC-A08, FC-A09, FC-A10, FC-A11, FC-A12). Every amendment now carries the required fields. All remain PROPOSED, NOT APPROVED, and `test_governance_docs.py` checks this. |
| FC-02 | Approved EMF metric names with numeric values are exempt from key-based redaction. Everything else, including every recovery field, is still redacted. `NoEffectiveRecoveryAdmin` is emitted unredacted by the CLI, and a subprocess test checks it. |
| FC-06 | Auth modes are allow-listed (`bearer`, `public`, `optional`) at declaration, at startup and at dispatch. |
| FC-11 | The ratchet now refuses: inline `# mypy:` comments; `[tool.mypy]` keys or values outside the reviewed set; per-module overrides beyond third-party `ignore_missing_imports`; shadow `mypy.ini`, `.mypy.ini` or `setup.cfg`; and coded ignores with no justification. mypy runs isolated (`-I`) with an explicit config file, and a local `mypy` package cannot shadow the installed one. |
| FC-12 | `deploy.sh` enforces `RELEASE_FLOOR=3` (from `veda/release.py`) and the schema floor in every mode, with no override. `9236aa3`, `2f6b59a`, unversioned images and malformed output are all refused before any change. Tested with stubbed docker; no rehearsal is claimed. |
| FC-04 | The clock is read after the connection or write lock is acquired. An update is never stamped before the row's creation. Deterministic and concurrent tests run on SQLite and PostgreSQL. |
| Still open | FC-01, FC-03, FC-07, FC-09, FC-10, FC-13, FC-14, FC-15 and the advisories, as recorded in [P0-open-issues.md](P0-open-issues.md). FC-05 and FC-08 are disclosed and wait on owner decisions. |

## 0. Final merge-blocker remediation (targeted re-review)

Workstream VEDA-SPACES-P0-FINAL-MERGE-BLOCKER-REMEDIATION-01. It responds to the targeted re-review
`review/p0-independent-implementation-review @ 15d25a759cfc0342bdca45ba4a9c51550270f305`, whose verdict was
**NOT CERTIFIED**, with IR-01 RESOLVED and no BLOCKER.

- **Previous head:** `2f6b59a`.
- **Matrix:** [P0-final-merge-blocker-matrix.md](P0-final-merge-blocker-matrix.md) (+ `.json`). It covers:
  - RR-01…RR-18;
  - RR-A01…RR-A25;
  - the 34 reconciliation items the re-review did not resolve;
  - OD-1…OD-5.
- **Merge-safety plan:** [P0-merge-safety-plan.md](P0-merge-safety-plan.md). It is a plan only and has not been executed.
- **Evidence:** [evidence/final-merge-blockers/](evidence/final-merge-blockers/).

| Finding | Result at this commit |
|---|---|
| RR-01 (404 CSP) | Styles moved to `/assets/404.css`. CSP unchanged. The browser checks the page under the production headers: HTTP 404, 0 CSP violations, no inline code, responsive, and axe-clean after an AA contrast fix. |
| RR-02 (Founder restore) | Implements the OD-2 brief instruction (approved by the owner on 2026-09-30): `FOUNDER_STATUS_CHANGE` with status `RESTORE`, requested by one Founder and approved by a second. The generic restore returns 403 plus a bypass event. Both break-glass channels are refused. Proposed amendment AM-12. |
| RR-03 (email change survives promotion) | Implements the OD-3 brief instruction (approved by the owner on 2026-09-30) with governance classes: escalation withdraws weaker-class work, and verification fails closed. Proposed amendment AM-13. |
| RR-04 (DEV-007) | Layered limiter covering account, aggregate, wide-network, reset-email and endpoint tiers. It never locks anyone out, and the challenge closes the MFA_REQUIRED oracle. AM-7 rewritten; the earlier text was rejected as written. |
| RR-05, RR-06 (archive manifests) | Write-once exports. Verification requires finalised, contiguous, hash-checked, re-chained and announced manifests. Two-phase ordering with idempotent retry and repair. S3 Object Lock is **not** verified against real S3. |
| RR-07 (CLI logging, scheduler) | Every CLI process configures logging. `MaintenanceJobFailed` and `ScheduledJobFailed` record job exit codes. |
| RR-08 (refresh successor) | `rotate_session_refresh` links successors after path-A confirmation and after a password change. |
| RR-10, RR-14 | Staging and production refuse broad proxy CIDRs, weak, development, duplicate or invalid keys, and a snapshot directory outside the database volume. |
| RR-11 (flag-off form) | Validates before the WhatsApp hand-off. Errors are accessible, entered values are kept, and the message is built only from validated fields. |
| RR-16 (mypy ratchet) | Fails closed (exit 2) if mypy is absent, mis-configured, only partly run, or its baseline is malformed or has grown. Update mode is explicit and never admits new errors. |
| RR-17 (rollback) | Rollback floor `0009_mfa_challenge_binding` enforced by `deploy.sh`, which reads readiness inside the container. The runbook prohibits rollback to `9236aa3`. No rehearsal is claimed. |
| IR-A05 | Startup refuses an optional-auth or public route that declares a permission. |
| Still open | RR-09, RR-12, RR-13, RR-15 and RR-18 (production or staging blockers), plus the other re-review advisories; see the matrix. |

**Reviewer reproducers against the previous head (`2f6b59a`):** the new suites fail there.

- `test_final_merge_blockers`: 15 failed.
- `test_layered_limiter`: 12 failed.
- `test_archive_ordering`: 15 failed.
- `test_mypy_ratchet`: 17 failed.

These outputs are in `evidence/final-merge-blockers/prefix-2f6b59a-*.txt`.

**Clean-environment run at this tree:** 29 steps, every exit code 0. The first run found a PostgreSQL concurrency defect in the new OD-3 code, since fixed; `evidence/final-merge-blockers/README.md` has the details.

- **pytest, SQLite:** 535 passed in 32.04s.
- **pytest, PostgreSQL 16.4:** 525 passed, 10 skipped in 96.93s (0:01:36).
- **pytest, PostgreSQL 18.4:** 525 passed, 10 skipped in 89.73s (0:01:29).
- **Browser:** 7/7 workspace journeys, 16/16 access checks, 31/31 site checks, and 12/12 screens without serious or critical axe violations.

**Not covered in the browser:** Founder restore, the email-change privilege transition and MFA recovery. These are covered by API integration tests on both engines only.

**Unchanged:**

- The certified architecture.
- The review artifacts.
- The intake metas, which stay empty, so the public API remains disabled.
- TG-01 and TG-08, which stay **PENDING**.
- No amendment is approved.
- Nothing has been merged or deployed.

## 1. IR-01 (BLOCKER): MFA enrollment confirmation bound to its principal, session, factor and path

**Root cause.** `enroll_confirm` picked the enrollment path from whether a bearer token was present (path A)
instead of from the challenge. It never compared the caller with the challenge owner, and an unbound
(path B/C) challenge accepted any bearer. So a victim's access token plus the attacker's own enrollment
transaction marked the victim's session MFA-verified and freshly stepped-up (review probes P1, P1b).

**Fix.**
- Every ENROLLMENT challenge now records `enrollment_path` (INVITE_CONTEXT, PATH_A…PATH_D) and the `factor_id` it
  may promote (migration `0009_mfa_challenge_binding`, DEV-006/AM-11).
- Confirm derives everything from server state:
  - paths A/D require caller user = challenge user, caller session = initiating session, and the right session type;
  - paths B/C refuse any bearer;
  - the factor must still be PENDING and owned by the challenge user;
  - eligibility is re-checked (account state, live invitation, N-A1, no ACTIVE factor for path C).
- A binding failure counts against the transaction, records a redacted event and answers like an unknown challenge.
- Success elevates only the initiating session (with a fresh refresh token), and ends every other open enrollment
  transaction and link. Concurrent confirmations serialise.
- The step-up, login, recovery, password-reset, email-change, invitation, approval and break-glass flows were reviewed
  for the same confusion; step-up was already bound, and the token flows take the principal from the token, not a
  bearer.

**Exploit regression evidence.** `tests/integration/test_mfa_binding.py`, 19 tests covering P1, P1b, a path-D
variant, the attacker/victim bearer swap, another session of the same user, revoked or disabled sessions, stale
eligibility, expiry, replay, a wrong factor, wrong-purpose tokens, the invitation context, recovery transactions,
parallel confirms, failure half-way, a failed replacement, and refresh rotation.
- **Before the fix** (`9236aa3`): 14 failed on SQLite and 15 on PostgreSQL, each exploit case answering
  `200 AUTHENTICATED` ([ir01-prefix-sqlite.txt](evidence/remediation/ir01-prefix-sqlite.txt),
  [ir01-prefix-postgresql.txt](evidence/remediation/ir01-prefix-postgresql.txt)).
- **After the fix:** all pass on SQLite, PostgreSQL 16.4 and PostgreSQL 18.4
  ([security-regressions-sqlite.txt](evidence/remediation/security-regressions-sqlite.txt),
  [security-regressions-pg16.txt](evidence/remediation/security-regressions-pg16.txt)).
- **Reviewed code against the new suites:** the lead/consent/MFA/intake regression files fail 29 of 39 on
  `9236aa3` ([prefix-9236aa3-sqlite.txt](evidence/remediation/prefix-9236aa3-sqlite.txt)).

## 2. Findings after remediation

| Severity | Resolved | Resolved — amendment pending owner decision | Partially resolved | Open |
|---|---|---|---|---|
| BLOCKER | — | IR-01 | — | — |
| MAJOR | IR-02, IR-04, IR-05, IR-08, IR-09, IR-13, IR-14, IR-15, IR-17, IR-18, IR-19 | IR-07, IR-10, IR-16 | IR-03, IR-06, IR-11, IR-12 | — |
| MINOR | IR-20, IR-21, IR-22, IR-24, IR-25, IR-26, IR-27, IR-28, IR-29, IR-30, IR-31, IR-35, IR-36, IR-37, IR-39 | IR-23 | IR-32, IR-38 | IR-33, IR-34 |

*Partially resolved* means every repository deliverable is complete, but a staging or production execution gate
remains:
- IR-03 and IR-06: real S3 and STS in staging;
- IR-11: RG-1, RG-2 and RG-7 rehearsals;
- IR-12: alarm routing and the RG-5 test-fire;
- IR-32: Privacy Notice and Turnstile site key;
- IR-38: Firefox and WebKit legs.

The two *open* MINORs are gate-scoped exactly as the reviewer classified them:
- IR-33: the PostgreSQL release gate;
- IR-34: before the first registry change.

Per-finding detail is in the matrix.

## 3. What changed

**Schema.**
- One expand-only migration, `0009_mfa_challenge_binding`: two nullable columns on `mfa_challenge`, one FK and
  CHECKs.
- Totals: 24 tables, 10 revisions, one Alembic head.
- No other table changed.
- 105 API routes, the same count as `9236aa3`; the contract is frozen in `api/openapi.snapshot.json`.

**Backend** (`api/veda`):
- MFA transaction binding (IR-01, IR-20, IR-21).
- Founder-governance fixes:
  - execution-time G11/G9;
  - promotion cancels STANDARD requests;
  - approvals re-read after the governance lock;
  - break-glass operating mode;
  - STS custodian identity;
  - consistent I3.
- Fail-closed configuration for all four environments (IR-09).
- Turnstile outside the write lock (IR-02).
- Tamper evidence: external anchor store, archival boundary.
- Readiness schema semantics (IR-10, IR-A17).
- Snapshot and restore verification (IR-11).
- EMF metrics (IR-12).
- Logging:
  - masked JSON for every record;
  - exceptions without messages;
  - `hide_parameters`;
  - Sentry scrubbing (IR-27).
- Lead and notification fixes (IR-16, IR-28, IR-29, IR-30).
- Throttling and events:
  - parsed /24 and /64 networks, and per-(email, network) limits;
  - reauth throttle;
  - the missing security events;
  - trusted-proxy client IP;
  - single-instance enforcement (IR-22…IR-25, IR-35).
- Advisories: RBX register validation, Turnstile hostname check, CSRF origin, reset invalidation, CLI audit labels
  (IR-A03, A04, A05, A13, A19).

**Frontend** (`app/`):
- Conflict re-apply sends only the user's edits (IR-15).
- Route titles, focus and announcement (IR-19).
- Sign-out-everywhere (IR-36).
- Break-glass cancel page (IR-07).
- The five accessibility items of IR-37.
- CSSOM style binding, no production source maps (IR-A21).
- Tooling: ESLint; Node 22 LTS; Vite 7.3; Web Test Runner 1.0; public-registry lockfile (IR-39).

**Website** (`dist/`, intake still disabled):
- Hidden-state CSS (IR-17).
- Turnstile reset and token gate (IR-18).
- Policy-version fallback (IR-31).
- DOM-built error summary, `#form-note` contrast, site CSP (IR-32).
- The consent/verification block and the Privacy Notice link appear only when intake is enabled.

**Supply chain and CI:**
- Hash-locked Python requirements and a digest-pinned base image (IR-13).
- CI gates: dual engine including PostgreSQL 16, format, types, OpenAPI diff, secret scan, audits, image scan,
  browser E2E + axe (IR-14).

**Operations:** Litestream config, `deploy.sh`, runbooks (IR-11).

**Documentation:**
- remediation matrix;
- open-issue register;
- deviations DEV-001…DEV-008;
- amendments AM-1…AM-11 (PROPOSED).

## 4. Test and evidence reproduction (clean environment)

**Environment.** A fresh copy of exactly the files to be committed (`git ls-files -co --exclude-standard`),
byte-identical to the working tree ([clean-copy.txt](evidence/remediation/clean-copy.txt),
[source-manifest.sha256](evidence/remediation/source-manifest.sha256)).
- A new Python 3.13.7 venv installed with `pip install --require-hashes -r requirements-dev.txt`
  ([api-pip-freeze.txt](evidence/remediation/api-pip-freeze.txt)).
- Node BuildVersion:		25G83 with `npm ci` against registry.npmjs.org.
- Databases: SQLite 3.50.4; PostgreSQL 16.4 (TCP server from the
  `pixeltable-pgserver` 0.2.9 binaries); PostgreSQL 18.4 (embedded `pixeltable-pgserver` 0.6.0);
  Playwright Chromium.
- Host ([environment.txt](evidence/remediation/environment.txt)): Darwin <host> 25.6.0 Darwin Kernel Version 25.6.0: Fri Jul 31 19:16:36 PDT 2026; root:xnu-12377.161.14~5/RELEASE_ARM64_T

| Step | Command | Exit | Time | Output |
|---|---|---|---|---|
| `api-venv` | `python3.13 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements-dev.txt` | 0 | 48s | [api-venv.txt](evidence/remediation/api-venv.txt) |
| `api-pip-freeze` | `.venv/bin/pip freeze --all` | 0 | 1s | [api-pip-freeze.txt](evidence/remediation/api-pip-freeze.txt) |
| `api-ruff-check` | `.venv/bin/ruff check veda tests migrations tools` | 0 | 0s | [api-ruff-check.txt](evidence/remediation/api-ruff-check.txt) |
| `api-ruff-format` | `.venv/bin/ruff format --check veda tests migrations tools` | 0 | 1s | [api-ruff-format.txt](evidence/remediation/api-ruff-format.txt) |
| `api-mypy-ratchet` | `/private/tmp/claude-501/-Users-srinivasulu-laggala-Documents-veda-spaces-aws-source/a8fccb24-d8d1-42b6-801b-51ca021aba4a/scratchpad/clean2/api/.venv/b` | 0 | 9s | [api-mypy-ratchet.txt](evidence/remediation/api-mypy-ratchet.txt) |
| `api-openapi` | `/private/tmp/claude-501/-Users-srinivasulu-laggala-Documents-veda-spaces-aws-source/a8fccb24-d8d1-42b6-801b-51ca021aba4a/scratchpad/clean2/api/.venv/b` | 0 | 8s | [api-openapi.txt](evidence/remediation/api-openapi.txt) |
| `api-deploy-check` | `VEDA_ENV=test /private/tmp/claude-501/-Users-srinivasulu-laggala-Documents-veda-spaces-aws-source/a8fccb24-d8d1-42b6-801b-51ca021aba4a/scratchpad/clea` | 0 | 0s | [api-deploy-check.txt](evidence/remediation/api-deploy-check.txt) |
| `api-bandit` | `.venv/bin/bandit -q -r veda -ll -ii` | 0 | 2s | [api-bandit.txt](evidence/remediation/api-bandit.txt) |
| `api-bandit-all` | `.venv/bin/bandit -q -r veda -f txt; true` | 0 | 1s | [api-bandit-all.txt](evidence/remediation/api-bandit-all.txt) |
| `api-pip-audit` | `.venv/bin/pip-audit -r requirements.txt --require-hashes --disable-pip --strict --progress-spinner off` | 0 | 5s | [api-pip-audit.txt](evidence/remediation/api-pip-audit.txt) |
| `secret-scan` | `git init -q . 2>/dev/null; git add -A >/dev/null 2>&1; PATH=/private/tmp/claude-501/-Users-srinivasulu-laggala-Documents-veda-spaces-aws-source/a8fccb` | 0 | 11s | [secret-scan.txt](evidence/remediation/secret-scan.txt) |
| `pytest-sqlite` | `VEDA_TEST_ENGINES=sqlite /private/tmp/claude-501/-Users-srinivasulu-laggala-Documents-veda-spaces-aws-source/a8fccb24-d8d1-42b6-801b-51ca021aba4a/scra` | 0 | 28s | [pytest-sqlite.txt](evidence/remediation/pytest-sqlite.txt) |
| `pytest-pg16` | `VEDA_TEST_ENGINES=postgresql VEDA_TEST_DATABASE_URL_PG=postgresql+psycopg://postgres@127.0.0.1:55432/postgres /private/tmp/claude-501/-Users-srinivasu` | 0 | 82s | [pytest-pg16.txt](evidence/remediation/pytest-pg16.txt) |
| `pytest-pg18` | `VEDA_TEST_ENGINES=postgresql /private/tmp/claude-501/-Users-srinivasulu-laggala-Documents-veda-spaces-aws-source/a8fccb24-d8d1-42b6-801b-51ca021aba4a/` | 0 | 74s | [pytest-pg18.txt](evidence/remediation/pytest-pg18.txt) |
| `security-regressions-sqlite` | `VEDA_TEST_ENGINES=sqlite /private/tmp/claude-501/-Users-srinivasulu-laggala-Documents-veda-spaces-aws-source/a8fccb24-d8d1-42b6-801b-51ca021aba4a/scra` | 0 | 7s | [security-regressions-sqlite.txt](evidence/remediation/security-regressions-sqlite.txt) |
| `security-regressions-pg16` | `VEDA_TEST_ENGINES=postgresql VEDA_TEST_DATABASE_URL_PG=postgresql+psycopg://postgres@127.0.0.1:55432/postgres /private/tmp/claude-501/-Users-srinivasu` | 0 | 23s | [security-regressions-pg16.txt](evidence/remediation/security-regressions-pg16.txt) |
| `migrations-sqlite-pg18` | `ENGINES=sqlite,postgresql /private/tmp/claude-501/-Users-srinivasulu-laggala-Documents-veda-spaces-aws-source/a8fccb24-d8d1-42b6-801b-51ca021aba4a/scr` | 0 | 2s | [migrations-sqlite-pg18.txt](evidence/remediation/migrations-sqlite-pg18.txt) |
| `migrations-pg16` | `ENGINES=postgresql VEDA_TEST_DATABASE_URL_PG=postgresql+psycopg://postgres@127.0.0.1:55432/postgres /private/tmp/claude-501/-Users-srinivasulu-laggala` | 0 | 2s | [migrations-pg16.txt](evidence/remediation/migrations-pg16.txt) |
| `app-npm-ci` | `npm ci --no-fund` | 0 | 5s | [app-npm-ci.txt](evidence/remediation/app-npm-ci.txt) |
| `app-lint` | `npm run lint` | 0 | 2s | [app-lint.txt](evidence/remediation/app-lint.txt) |
| `app-typecheck` | `npm run typecheck` | 0 | 4s | [app-typecheck.txt](evidence/remediation/app-typecheck.txt) |
| `app-lint-tokens` | `npm run lint:tokens` | 0 | 0s | [app-lint-tokens.txt](evidence/remediation/app-lint-tokens.txt) |
| `app-contrast` | `npm run test:contrast` | 0 | 0s | [app-contrast.txt](evidence/remediation/app-contrast.txt) |
| `app-test` | `npm test` | 0 | 6s | [app-test.txt](evidence/remediation/app-test.txt) |
| `app-build` | `npm run build` | 0 | 3s | [app-build.txt](evidence/remediation/app-build.txt) |
| `app-audit-runtime` | `npm audit --omit=dev` | 0 | 2s | [app-audit-runtime.txt](evidence/remediation/app-audit-runtime.txt) |
| `app-audit-all` | `npm audit` | 0 | 4s | [app-audit-all.txt](evidence/remediation/app-audit-all.txt) |
| `e2e` | `API_PYTHON=/private/tmp/claude-501/-Users-srinivasulu-laggala-Documents-veda-spaces-aws-source/a8fccb24-d8d1-42b6-801b-51ca021aba4a/scratchpad/clean2/` | 0 | 160s | [e2e.txt](evidence/remediation/e2e.txt) |

**Backend test results**
- SQLite: 435 passed in 25.71s
- PostgreSQL 16.4: 427 passed, 8 skipped in 80.21s
- PostgreSQL 18.4: 427 passed, 8 skipped in 72.50s

On PostgreSQL the skips are the two SQLite-only schema checks and the six SQLite-only snapshot/restore tests. JUnit:
[pytest-sqlite.xml](evidence/remediation/pytest-sqlite.xml), [pytest-pg16.xml](evidence/remediation/pytest-pg16.xml),
[pytest-pg18.xml](evidence/remediation/pytest-pg18.xml).

**Security regressions** (IR/DEV suites, verbose):
- SQLite: 162 passed in 6.66s
- PostgreSQL 16.4: 156 passed, 6 skipped in 22.27s

Concurrency cases include parallel enrollment confirmations, a promotion racing a STANDARD approval, and the existing
TD-F and G10 suites. Audit-chain cases are in `test_chain_integrity.py` and `test_audit_security.py`.

**Migrations** ([migrations-sqlite-pg18.txt](evidence/remediation/migrations-sqlite-pg18.txt),
[migrations-pg16.txt](evidence/remediation/migrations-pg16.txt)):

| Check | SQLite 3.50.4 | PostgreSQL 16.4 | PostgreSQL 18.4 |
|---|---|---|---|
| Empty → head | 0009_mfa_challenge_binding | 0009_mfa_challenge_binding | 0009_mfa_challenge_binding |
| Heads / revisions | ['0009_mfa_challenge_binding'] / 10 | ['0009_mfa_challenge_binding'] / 10 | same |
| Tables / columns / indexes / FKs | 24 / 504 / 72 / 108 | 24 / 504 / 72 / 108 | 24 / 504 / 72 / 108 |
| CHECK constraints | 498 | 164 | 164 |
| Conformance (03 §2.7) / audit columns / guards | True / True / True | True / True / True | True / True / True |
| Human users / password hashes seeded | 0 / 0 | 0 / 0 | 0 / 0 |
| Seeds (roles, permissions, matrix, lookups, system users, sequence); deterministic | {'roles': 3, 'permissions': 45, 'matrix': 101, 'lookups': 47, 'system_users': 3, 'sequence': 1}; True | {'roles': 3, 'permissions': 45, 'matrix': 101, 'lookups': 47, 'system_users': 3, 'sequence': 1}; True | {'roles': 3, 'permissions': 45, 'matrix': 101, 'lookups': 47, 'system_users': 3, 'sequence': 1}; True |
| Raw UUIDv4 insert rejected by the database | True | n/a (native uuid; version nibble validated by the kernel GUID type on bind) | same |
| `downgrade -1` (0009 → 0100) | refused; schema stays at 0009_mfa_challenge_binding with ['enrollment_path', 'factor_id'] | refused; stays at 0009_mfa_challenge_binding | refused; stays at 0009_mfa_challenge_binding |

**Rollback boundary** (IR-10, AM-6). Down-migrations do not exist and are refused. That is not rollback support in
itself. The supported rollback is:
- **Normal:** the N-1 image on the migrated, expand-only schema. Readiness accepts it only after the operator declares
  the newer revision (`VEDA_SCHEMA_AHEAD_ACCEPTED`), and never when the database is behind.
- **Disaster:** restore the pre-deploy snapshot, verified by `veda maintenance restore-verify`, and accept the reported
  data-loss window (runbook §2–§3).

`test_ops_remediation.py` exercises the boundary; `test_schema.py::test_migration_upgrade_with_data` upgrades data
from N-1 to head on every engine. RG-7 (rehearsal on the host) is not executed.

**Frontend** (clean `npm ci`, Node 22): ESLint, typecheck, token lint, contrast (58 pairs), unit/component tests
(52 passed, 0 failed; the title test runs twice because `components.test` imports `router.test`), and the production build all
exit 0. `npm audit --omit=dev` and a full `npm audit` both report 0 vulnerabilities
on registry.npmjs.org.

**Browser** ([e2e.txt](evidence/remediation/e2e.txt)). A live stack from the clean copy: Flask on SQLite, Vite, and the site served
with its production `_headers` (intake on at :8000, flag off at :8001).
- Workspace, 7/7 journeys passed:
  - invitation with forced MFA enrollment;
  - TOTP sign-in;
  - lead from the website;
  - status change;
  - audit;
  - mobile.
- Access, 16/16 access checks passed:
  - permission denial proven with a Sales token;
  - route title and focus;
  - session revocation on reload and in-app;
  - logout with a refused refresh;
  - repeated, duplicate and invalid submissions;
  - TD-F step-4 re-apply;
  - break-glass cancel from the real email;
  - sign-out-everywhere.
- Website, 14/14 site checks passed:
  - server 422 → Turnstile reset → 201;
  - form hidden after success and fallback;
  - policy-version fallback;
  - network fallback;
  - flag off hides consent, verification and the link;
  - 360 px;
  - **0 CSP violations** under the production policy.
- Axe, 10/10 screens without serious/critical violations:
  - 8 workspace screens;
  - the website form scope;
  - 18 pre-existing marketing nodes tracked (OI-11).

Not covered in the browser:
- Chromium only (Firefox and WebKit are OI-RM-2);
- recovery with a recovery code, which is covered at API level (`test_mfa.py`, `test_mfa_binding.py`).

**Security**:
- Secret scan: no candidates beyond the reviewed baseline ([secret-scan.txt](evidence/remediation/secret-scan.txt)); `founder.json`
  and screenshots from the E2E run are not committed.
- `pip-audit` on the hash lock: no known vulnerabilities ([api-pip-audit.txt](evidence/remediation/api-pip-audit.txt)).
- Bandit: medium and above, 0 ([api-bandit.txt](evidence/remediation/api-bandit.txt)). The low findings are in
  [api-bandit-all.txt](evidence/remediation/api-bandit-all.txt): message strings and subprocess use in the scheduler.
- IR-01 exploit regressions: §1.
- Route authorization inventory: startup RBX-register validation, plus `test_rbac.py` role × endpoint matrix.
- IDOR, mass-assignment, token-replay, MFA-bypass and step-up-bypass probes: `test_rbac.py`, `test_api_contract.py`,
  `test_mfa.py`, `test_mfa_binding.py`, `test_auth.py`, `test_governance_remediation.py`.

Manual security review and DAST (PG-DAST) are still required. Automated checks are supporting evidence only.

## 5. CI

`.github/workflows/ci.yml` runs on this branch. Every job is mandatory, and the actions are pinned to commit SHAs:
- **api** (SQLite, and PostgreSQL 16 service): ruff check and format, mypy ratchet, full pytest, OpenAPI diff,
  deploy-check.
- **security:** secret scan, pip-audit, bandit, npm audit, image build + Trivy.
- **app:** ESLint, typecheck, tokens, contrast, tests, build.
- **e2e:** journeys + axe.

The first run is triggered by this push; its result is recorded in the final report of the remediation, not here.

## 6. Deviations and amendments

- DEV-001…DEV-003: acceptable with amendments per the reviewer. Their conditions are resolved: IR-20; IR-01, IR-21,
  IR-25; IR-22, IR-09, IR-02.
- DEV-004: corrected (IR-16).
- DEV-005: the cancel link (IR-07).
- DEV-006: binding columns (IR-01).
- DEV-007: per-(email, network) limits (IR-23).
- DEV-008: readiness semantics (IR-10, IR-A17).

All await the Architecture Owner through AM-1…AM-11, which are PROPOSED, NOT APPROVED. The certified documents are
byte-identical to `778aa8f`.

## 7. Blockers by stage (after remediation)

**Merge:**
- Targeted independent re-review of this commit.
- Architecture-Owner decisions on AM-1…AM-5, and on AM-6, AM-7 and AM-11, which back implemented behaviour.
- Owner gates TG-01 and TG-08 recorded.
- A green first CI run (OI-RM-1).

**Staging** — everything above, plus:
- developer machines and CI on Node ≥ 22.13;
- staging verification of SES, KMS, S3 anchors and STS custodians (IR-03, IR-06, OI-6).

**Production** — everything above, plus:
- RG-1…RG-9;
- PG-DAST, PG-BG, PG-RET and PG-EMAIL;
- OWNER-INPUT-001…004;
- alarm routing and the RG-5 test-fire (IR-12);
- rehearsals (IR-11);
- Firefox and WebKit legs (OI-RM-2);
- the manual screen-reader script (OI-RM-5);
- the open advisories the owner decides to require.

**Public intake enablement:**
- Privacy Notice v2026-09-v1 page;
- Turnstile site key;
- a run with the real Turnstile test keys (IR-32, IR-18 residual);
- PG-PRIV.

The API base stays empty in `dist/index.html`.

**PostgreSQL release (PGM-1):** IR-33, IR-A01, IR-A16, the data-migration rehearsal.

## 8. Corrections to earlier claims

- **DEV-004 lead-drawer control.** The register claimed a lead-drawer re-consent control; none exists, and 09
  specifies none (IR-A25). The register is corrected.
- **Earlier `ruff format` and npm audit figures.** Superseded: the tree is now formatted, and the audits report 0.
- **The eleven-item open-issue list.** Superseded by [P0-open-issues.md](P0-open-issues.md) (106 entries).
- **The first report's test counts.** 273 on SQLite and 271 + 2 skipped on PostgreSQL 18.4 described `9236aa3`.
  The counts above describe this commit.

## 9. Status

**The implementation is not certified, not merged and not deployed. The public lead API remains disabled.** No
production gate was executed. The remediation is committed on `implementation/p0-foundation` for a targeted
independent re-review.

## Appendix A — P0 implementation reference (from the freeze report of 9236aa3, updated where the remediation changed it)

### A.1 Directory structure

As at the freeze commit. The remediation adds `docs/architecture/amendments/`, `docs/operations/` and `docs/implementation/evidence/remediation/`; its file-level changes are `git diff --stat 9236aa3 HEAD`.

Directories added by the implementation (every directory containing a committed file):

```
.github/workflows
api
api/deploy
api/migrations
api/migrations/versions
api/tests
api/tests/integration
api/tests/support
api/tests/unit
api/tools
api/veda
api/veda/cli
api/veda/kernel
api/veda/modules
api/veda/modules/crm
api/veda/modules/crm/leads
api/veda/platform
api/veda/platform/audit
api/veda/platform/auth
api/veda/platform/identity
api/veda/platform/lookups
api/veda/platform/notifications
api/veda/platform/notifications/templates
api/veda/platform/rbac
app
app/e2e
app/public
app/public/img
app/scripts
app/src
app/src/core/api
app/src/core/auth
app/src/core/authz
app/src/core/format
app/src/core/i18n
app/src/core/router
app/src/core/telemetry
app/src/design-system
app/src/modules/admin
app/src/modules/audit
app/src/modules/auth
app/src/modules/leads
app/src/shell
app/test
docs/implementation
docs/implementation/evidence
```

Top-level roles: `api/` Flask backend (02 §3.2) · `app/` Lit + TypeScript workspace (02 §2.2) · `dist/` marketing
site (enquiry form only) · `.github/workflows/` CI definition (not run here) · `docs/implementation/` this report,
deviation register and evidence.

### A.2 Files added, modified and removed

As at the freeze commit (relative to the certified baseline).

| Change | Files |
|---|---|
| Added | 250 files: `api/` (143), `app/` (81), `docs/implementation/` (report, deviation register ×2, 23 evidence files), `.github/workflows/ci.yml` |
| Modified | `.gitignore` (generated/sensitive artifacts) · `README.md` (links to api/app/report) · `dist/index.html`, `dist/assets/app.js`, `dist/assets/enhancements.css` (enquiry form, §Q) |
| Removed | None |
| Unchanged | `docs/architecture/**` including review, remediation and validation documents (verified by `git diff --quiet 778aa8f -- docs/architecture`) |

#### dist/ changes (enquiry-form integration only, LEAD-001/019, 09 §4.11)

- `dist/index.html`: three meta tags (`veda-api-base` — **empty, feature off**; `veda-turnstile-sitekey` — empty;
  `veda-policy-version`); the contact form replaced by the ADR-005 form (required name/phone/consent; optional email,
  property type with the Decision 4 options, service, budget, location, brief; off-screen honeypot; error summary;
  success and WhatsApp-fallback panels).
- `dist/assets/app.js`: only the contact-form submit handler is replaced. With `veda-api-base` empty the behaviour is the
  original WhatsApp hand-off (verified by `e2e-site.txt` check 5). Navigation, modal and reveal code unchanged.
- `dist/assets/enhancements.css`: styles appended for the new form states only.

### A.3 Database tables and migrations

24 tables, 10 revisions (0009_mfa_challenge_binding added by the remediation), one Alembic head (`0009_mfa_challenge_binding`); counts at the freeze commit below, current counts in §4. Every table carries the nine audit-contract
columns (ADR-003) with actor FKs to `app_user.id`; UUIDv7 32-hex ids (ADR-002); no table named `user` (ADR-001).

| Revision | Tables | Audit policy |
|---|---|---|
| 0001_kernel | — (SQLite pragma assertion) | — |
| 0002_identity | app_user, user_credential (+ SYSTEM, WEB_INTAKE, ANONYMOUS) | FULL |
| 0003_rbac | role, permission, user_role, role_permission, user_permission (+ roles, 45 permissions, matrix) | FULL |
| 0004_auth | user_session, refresh_token, user_action_token, user_mfa_factor, user_mfa_recovery_code, mfa_challenge, security_event_log (+ immutability guards) | EVENT_ONLY · factor FULL · security_event_log IMMUTABLE_STORE |
| 0005_audit | audit_log (+ guards; CREATE backfill for 0002–0003 seeds) | IMMUTABLE_STORE |
| 0006_reference | lookup_category, lookup_value, number_sequence (+ 6 categories, 47 values, LEAD sequence) | FULL |
| 0007_notifications | outbox_event, notification | EVENT_ONLY |
| 0008_account_security | admin_approval_request (+ app_user proposed-email, protection_level, cooling-off columns) | FULL |
| 0100_crm_leads | lead, lead_note, lead_activity | FULL |
| 0009_mfa_challenge_binding | mfa_challenge: factor_id, enrollment_path (IR-01, DEV-006/AM-11) | EVENT_ONLY (unchanged) |

Migration evidence (`evidence/migration-evidence.json`, produced by `evidence/migration_evidence.py` on fresh databases):

| Check | SQLite | PostgreSQL 18.4 (embedded) |
|---|---|---|
| Empty database → head | 0100_crm_leads | 0100_crm_leads |
| Tables / indexes / FKs | 24 / 72 / 107 | 24 / 72 / 107 |
| Named CHECK constraints | 493 (incl. SQLite type CHECKs) | 161 |
| Schema conformance (03 §2.7 rules 1–9) | OK | OK |
| Nine audit columns on every table | True | True |
| Immutability guards present | True | True |
| Human users / password hashes after migration | 0 / 0 | 0 / 0 |
| Seed counts (roles, permissions, matrix, lookups, system users, sequences) | 3, 45, 101, 47, 3, 1 | 3, 45, 101, 47, 3, 1 |
| Seed deterministic across two fresh databases | True | True |
| Raw UUIDv4 insert rejected by the database | True | n/a — native `uuid` accepts any UUID; v7 enforced by the kernel GUID type on bind (03 §12) |
| `alembic downgrade -1` | refused (NotImplementedError) | refused (NotImplementedError) |
| Re-upgrade after refused downgrade | 0100_crm_leads | 0100_crm_leads |

**Rollback boundary.** Down-migrations are deliberately unsupported: 02 §12.4 makes every migration expand-only and
N-1-compatible, and rollback is (normal) redeploying the N-1 image on the migrated schema or (disaster) restoring
the pre-migration snapshot. Additional migration tests: upgrade-with-data from 0008 to head
(`test_migration_upgrade_with_data`, both engines), models-match-schema (`test_PLAT_005_…`), purge ordering with
`foreign_keys=ON` (`test_DATA_017_…`), TD-H negative fixtures (12 cases). No migration requires manual data editing.

### A.4 API catalog

105 routes. Each declares a permission code or an RBX exception; startup fails otherwise (06 §8). 08 index row 75
(`POST /leads/exports`, P1) is not built. `POST /api/v1/approvals/cancel-link` implements the 06 §7.5 signed
break-glass cancel link (see §13 OI-2).

| # | Method | Path | Gate | Req |
|---|---|---|---|---|
| 1 | GET | `/health/live` | RBX-006 | LOG-005 |
| 2 | GET | `/health/ready` | RBX-006 | LOG-005 |
| 3 | GET | `/api/v1/activities` | `lead_activity.read` | LEAD-015 |
| 4 | GET | `/api/v1/approvals` | `user.mfa.reset` / `user.email.change` / `user.founder.manage` (any) | RBAC-021 |
| 5 | GET | `/api/v1/approvals/{approval_id}` | `user.mfa.reset` / `user.email.change` / `user.founder.manage` (any) | RBAC-021 |
| 6 | POST | `/api/v1/approvals/{approval_id}/approve` | `user.mfa.reset` / `user.email.change` / `user.founder.manage` (any) | RBAC-021 |
| 7 | POST | `/api/v1/approvals/{approval_id}/cancel` | `user.mfa.reset` / `user.email.change` / `user.founder.manage` (any) | RBAC-021 |
| 8 | POST | `/api/v1/approvals/{approval_id}/deny` | `user.mfa.reset` / `user.email.change` / `user.founder.manage` (any) | RBAC-021 |
| 9 | POST | `/api/v1/approvals/cancel-link` | RBX-003 | RBAC-021 |
| 10 | GET | `/api/v1/audit-logs` | `audit.read` | AUDIT-008 |
| 11 | GET | `/api/v1/audit-logs/{audit_id}` | `audit.read` | AUDIT-008 |
| 12 | GET | `/api/v1/auth/.well-known/jwks.json` | RBX-006 | AUTH-004 |
| 13 | POST | `/api/v1/auth/email/cancel` | RBX-003 | USER-007 |
| 14 | POST | `/api/v1/auth/email/verify` | RBX-003 | USER-007 |
| 15 | POST | `/api/v1/auth/invite/accept` | RBX-003 | AUTH-011 |
| 16 | POST | `/api/v1/auth/login` | RBX-001 | AUTH-001 |
| 17 | POST | `/api/v1/auth/logout` | RBX-002 | AUTH-007 |
| 18 | POST | `/api/v1/auth/logout-all` | RBX-002 | AUTH-007 |
| 19 | GET | `/api/v1/auth/me` | `profile.read` | USER-004 |
| 20 | PATCH | `/api/v1/auth/me` | `profile.update` · If-Match | USER-004 |
| 21 | PUT | `/api/v1/auth/me/email` | RBX-004 | USER-007 |
| 22 | GET | `/api/v1/auth/mfa` | `profile.read` | MFA-001 |
| 23 | POST | `/api/v1/auth/mfa/enroll/confirm` | RBX-004 | MFA-014 |
| 24 | POST | `/api/v1/auth/mfa/enroll/start` | RBX-004 | MFA-014 |
| 25 | DELETE | `/api/v1/auth/mfa/factor` | RBX-004 | MFA-003 |
| 26 | POST | `/api/v1/auth/mfa/recovery` | RBX-001 | MFA-013 |
| 27 | POST | `/api/v1/auth/mfa/recovery-codes` | RBX-004 | MFA-005 |
| 28 | POST | `/api/v1/auth/mfa/step-up` | RBX-004 | MFA-011 |
| 29 | POST | `/api/v1/auth/mfa/verify` | RBX-001 | MFA-001 |
| 30 | POST | `/api/v1/auth/password/change` | RBX-004 | AUTH-012 |
| 31 | POST | `/api/v1/auth/password/forgot` | RBX-003 | AUTH-008 |
| 32 | POST | `/api/v1/auth/password/reset` | RBX-003 | AUTH-008 |
| 33 | POST | `/api/v1/auth/reauth` | RBX-004 | MFA-011 |
| 34 | POST | `/api/v1/auth/refresh` | RBX-002 | AUTH-005 |
| 35 | GET | `/api/v1/auth/sessions` | `session.read` | AUTH-016 |
| 36 | DELETE | `/api/v1/auth/sessions/{session_id}` | `session.revoke` | AUTH-016 |
| 37 | POST | `/api/v1/founder-actions` | `user.founder.manage` | RBAC-021 |
| 38 | GET | `/api/v1/leads` | `lead.read` | LEAD-013 |
| 39 | POST | `/api/v1/leads` | `lead.create` | LEAD-003 |
| 40 | DELETE | `/api/v1/leads/{lead_id}` | `lead.delete` · If-Match | LEAD-016 |
| 41 | GET | `/api/v1/leads/{lead_id}` | `lead.read` | LEAD-013 |
| 42 | PATCH | `/api/v1/leads/{lead_id}` | `lead.update` · If-Match | LEAD-024 |
| 43 | GET | `/api/v1/leads/{lead_id}/activities` | `lead_activity.read` | ACT-001 |
| 44 | POST | `/api/v1/leads/{lead_id}/activities` | `lead_activity.create` | ACT-001 |
| 45 | DELETE | `/api/v1/leads/{lead_id}/activities/{activity_id}` | `lead_activity.delete` · If-Match | ACT-002 |
| 46 | PATCH | `/api/v1/leads/{lead_id}/activities/{activity_id}` | `lead_activity.update` · If-Match | ACT-002 |
| 47 | POST | `/api/v1/leads/{lead_id}/activities/{activity_id}/cancel` | `lead_activity.update` · If-Match | ACT-003 |
| 48 | POST | `/api/v1/leads/{lead_id}/activities/{activity_id}/complete` | `lead_activity.update` · If-Match | ACT-003 |
| 49 | POST | `/api/v1/leads/{lead_id}/assign` | `lead.assign` · If-Match | LEAD-007 |
| 50 | POST | `/api/v1/leads/{lead_id}/consent/withdraw` | `lead.update` · If-Match | LEAD-027 |
| 51 | POST | `/api/v1/leads/{lead_id}/duplicate-resolution` | `lead.update` | LEAD-010 |
| 52 | POST | `/api/v1/leads/{lead_id}/erasure` | `lead.erase` · If-Match | LEAD-029 |
| 53 | GET | `/api/v1/leads/{lead_id}/history` | `lead.read` + `audit.read` | AUDIT-006 |
| 54 | GET | `/api/v1/leads/{lead_id}/notes` | `lead_note.read` | NOTE-001 |
| 55 | POST | `/api/v1/leads/{lead_id}/notes` | `lead_note.create` | NOTE-001 |
| 56 | DELETE | `/api/v1/leads/{lead_id}/notes/{note_id}` | `lead_note.delete` · If-Match | NOTE-002 |
| 57 | PATCH | `/api/v1/leads/{lead_id}/notes/{note_id}` | `lead_note.update` · If-Match | NOTE-002 |
| 58 | POST | `/api/v1/leads/{lead_id}/restore` | `lead.restore` · If-Match | LEAD-016 |
| 59 | POST | `/api/v1/leads/{lead_id}/spam-resolution` | `lead.update` · If-Match | LEAD-018 |
| 60 | POST | `/api/v1/leads/{lead_id}/status` | `lead.status.change` / `lead.reopen` (any) · If-Match | LEAD-005 |
| 61 | GET | `/api/v1/leads/duplicates` | `lead.read` | LEAD-010 |
| 62 | GET | `/api/v1/leads/summary` | `lead.read` | LEAD-014 |
| 63 | GET | `/api/v1/lookups` | `lookup.read` | PLAT-009 |
| 64 | GET | `/api/v1/lookups/{category_code}` | `lookup.read` | PLAT-009 |
| 65 | POST | `/api/v1/lookups/{category_code}/values` | `lookup.manage` | PLAT-009 |
| 66 | PATCH | `/api/v1/lookups/{category_code}/values/{value_id}` | `lookup.manage` · If-Match | PLAT-009 |
| 67 | GET | `/api/v1/notifications` | `notification.read` | NOTIF-001 |
| 68 | POST | `/api/v1/notifications/{notification_id}/read` | `notification.read` | NOTIF-001 |
| 69 | POST | `/api/v1/notifications/read-all` | `notification.read` | NOTIF-001 |
| 70 | GET | `/api/v1/permissions` | `permission.read` | RBAC-004 |
| 71 | GET | `/api/v1/permissions/{permission_id}` | `permission.read` | RBAC-004 |
| 72 | PATCH | `/api/v1/permissions/{permission_id}` | `permission.manage` · If-Match | RBAC-004 |
| 73 | GET | `/api/v1/permissions/{permission_id}/holders` | `permission.read` + `user.read` | RBAC-016 |
| 74 | POST | `/api/v1/public/leads` | RBX-005 | LEAD-001 |
| 75 | GET | `/api/v1/roles` | `role.read` | RBAC-008 |
| 76 | POST | `/api/v1/roles` | `role.manage` | RBAC-008 |
| 77 | DELETE | `/api/v1/roles/{role_id}` | `role.manage` · If-Match | RBAC-008 |
| 78 | GET | `/api/v1/roles/{role_id}` | `role.read` | RBAC-008 |
| 79 | PATCH | `/api/v1/roles/{role_id}` | `role.manage` · If-Match | RBAC-008 |
| 80 | GET | `/api/v1/roles/{role_id}/permissions` | `role.read` | RBAC-008 |
| 81 | PUT | `/api/v1/roles/{role_id}/permissions` | `role.manage` | RBAC-009 |
| 82 | GET | `/api/v1/roles/{role_id}/users` | `role.read` + `user.read` | RBAC-008 |
| 83 | GET | `/api/v1/security-events` | `security_event.read` | SEVT-005 |
| 84 | GET | `/api/v1/security-events/{event_id}` | `security_event.read` | SEVT-005 |
| 85 | GET | `/api/v1/users` | `user.read` | USER-001 |
| 86 | POST | `/api/v1/users` | `user.create` | USER-001 |
| 87 | DELETE | `/api/v1/users/{user_id}` | `user.delete` · If-Match | USER-001 |
| 88 | GET | `/api/v1/users/{user_id}` | `user.read` | USER-001 |
| 89 | PATCH | `/api/v1/users/{user_id}` | `user.profile.update` · If-Match | RBAC-019 |
| 90 | GET | `/api/v1/users/{user_id}/effective-permissions` | `user.read` + `permission.read` | RBAC-016 |
| 91 | POST | `/api/v1/users/{user_id}/email-change` | `user.email.change` · If-Match | USER-007 |
| 92 | POST | `/api/v1/users/{user_id}/invite/resend` | `user.create` | AUTH-011 |
| 93 | PUT | `/api/v1/users/{user_id}/mfa-requirement` | `user.mfa.require` · If-Match | MFA-003 |
| 94 | POST | `/api/v1/users/{user_id}/mfa/reset` | `user.mfa.reset` · If-Match | MFA-007 |
| 95 | POST | `/api/v1/users/{user_id}/password-reset` | `user.password.reset` | AUTH-008 |
| 96 | GET | `/api/v1/users/{user_id}/permissions` | `user.read` | RBAC-006 |
| 97 | POST | `/api/v1/users/{user_id}/permissions` | `user.permission.manage` | RBAC-006 |
| 98 | DELETE | `/api/v1/users/{user_id}/permissions/{grant_id}` | `user.permission.manage` | RBAC-006 |
| 99 | POST | `/api/v1/users/{user_id}/restore` | `user.restore` | USER-001 |
| 100 | GET | `/api/v1/users/{user_id}/roles` | `user.read` | RBAC-008 |
| 101 | PUT | `/api/v1/users/{user_id}/roles` | `user.role.manage` | RBAC-009 |
| 102 | POST | `/api/v1/users/{user_id}/sessions/revoke` | `user.session.revoke` | AUTH-016 |
| 103 | POST | `/api/v1/users/{user_id}/status` | `user.status.manage` · If-Match | RBAC-019 |
| 104 | POST | `/api/v1/users/{user_id}/unlock` | `user.status.manage` | AUTH-010 |
| 105 | GET | `/api/v1/users/assignable` | `lead.assign` | LEAD-007 |

### A.5 UI screens (`app/`, 09 §4)

Login · MFA challenge · recovery · recovery-mode shell · enrollment (paths A–D) · recovery codes · forgot/reset password
· accept invitation · verify/cancel email change · change password · dashboard · lead list (filters, spam-review queue,
mobile cards) · lead detail (stepper, transitions, assignment, timeline, notes, activities, duplicate/spam review,
consent withdrawal, delete, erasure, history) · lead create/edit · follow-ups · users (invite; profile/access/security/
sessions) · roles (matrix editor; FOUNDER locked) · permissions · audit log and security events · approvals · Founder
actions · profile · notifications tray · command palette · step-up and version-conflict dialogs · no-access page.
Break-glass cancel page `/approvals/cancel` (DEV-005). Website: enquiry-form states of 09 §4.11.

### A.6 Permissions and role mappings (06 §6, code registry `api/veda/platform/rbac/registry.py`)

45 permissions, 16 sensitive. ALL/OWN = scope; ✓ = granted without scope; — = not granted. SALES holds no sensitive
permission; `user.founder.manage` exists only in FOUNDER (asserted by migration 0003 and unit tests).

| Permission | Module | Sensitivity | Grant path | FOUNDER | ADMIN | SALES |
|---|---|---|---|---|---|---|
| `profile.read` | platform | — | STANDARD | ✓ | ✓ | ✓ |
| `profile.update` | platform | — | STANDARD | ✓ | ✓ | ✓ |
| `session.read` | platform | — | STANDARD | OWN | OWN | OWN |
| `session.revoke` | platform | — | STANDARD | OWN | OWN | OWN |
| `notification.read` | platform | — | STANDARD | OWN | OWN | OWN |
| `lookup.read` | platform | — | STANDARD | ✓ | ✓ | ✓ |
| `user.read` | platform | — | STANDARD | ✓ | ✓ | — |
| `user.create` | platform | — | STANDARD | ✓ | ✓ | — |
| `user.profile.update` | platform | — | STANDARD | ✓ | ✓ | — |
| `user.email.change` | platform | ACCOUNT_CONTROL | STANDARD | ✓ | ✓ | — |
| `user.status.manage` | platform | ACCOUNT_CONTROL | STANDARD | ✓ | ✓ | — |
| `user.delete` | platform | ACCOUNT_CONTROL | STANDARD | ✓ | — | — |
| `user.restore` | platform | — | STANDARD | ✓ | — | — |
| `user.password.reset` | platform | — | STANDARD | ✓ | ✓ | — |
| `user.session.revoke` | platform | ACCOUNT_CONTROL | STANDARD | ✓ | ✓ | — |
| `user.role.manage` | platform | ACCESS_CONTROL | STANDARD | ✓ | ✓ | — |
| `user.permission.manage` | platform | ACCESS_CONTROL | STANDARD | ✓ | — | — |
| `user.mfa.reset` | platform | ACCOUNT_CONTROL | STANDARD | ✓ | ✓ | — |
| `user.mfa.require` | platform | ACCOUNT_CONTROL | STANDARD | ✓ | ✓ | — |
| `user.founder.manage` | platform | ACCOUNT_CONTROL | FOUNDER_WORKFLOW_ONLY | ✓ | — | — |
| `role.read` | platform | — | STANDARD | ✓ | ✓ | — |
| `role.manage` | platform | ACCESS_CONTROL | STANDARD | ✓ | ✓ | — |
| `permission.read` | platform | — | STANDARD | ✓ | ✓ | — |
| `permission.manage` | platform | ACCESS_CONTROL | STANDARD | ✓ | — | — |
| `audit.read` | platform | SECURITY_DATA | STANDARD | ✓ | ✓ | — |
| `security_event.read` | platform | SECURITY_DATA | STANDARD | ✓ | ✓ | — |
| `lookup.manage` | platform | — | STANDARD | ✓ | ✓ | — |
| `lead.create` | crm | — | STANDARD | ✓ | ✓ | ✓ |
| `lead.read` | crm | — | STANDARD | ALL | ALL | OWN |
| `lead.update` | crm | — | STANDARD | ALL | ALL | OWN |
| `lead.status.change` | crm | — | STANDARD | ALL | ALL | OWN |
| `lead.reopen` | crm | — | STANDARD | ALL | ALL | — |
| `lead.assign` | crm | — | STANDARD | ALL | ALL | — |
| `lead.delete` | crm | DESTRUCTIVE | STANDARD | ALL | ALL | — |
| `lead.restore` | crm | — | STANDARD | ✓ | ✓ | — |
| `lead.erase` | crm | DESTRUCTIVE | STANDARD | ✓ | — | — |
| `lead.export` | crm | BULK_DATA | STANDARD | ✓ | — | — |
| `lead_note.create` | crm | — | STANDARD | ✓ | ✓ | ✓ |
| `lead_note.read` | crm | — | STANDARD | ALL | ALL | ALL |
| `lead_note.update` | crm | — | STANDARD | ALL | ALL | OWN |
| `lead_note.delete` | crm | — | STANDARD | ALL | ALL | OWN |
| `lead_activity.create` | crm | — | STANDARD | ✓ | ✓ | ✓ |
| `lead_activity.read` | crm | — | STANDARD | ALL | ALL | ALL |
| `lead_activity.update` | crm | — | STANDARD | ALL | ALL | OWN |
| `lead_activity.delete` | crm | — | STANDARD | ALL | ALL | OWN |

