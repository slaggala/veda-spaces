# Veda Spaces P0 — Final Targeted Independent Check

**Review ID:** VEDA-SPACES-P0-FINAL-TARGETED-INDEPENDENT-CHECK-02
**Date:** 2026-09-29
**Final verdict:** **CERTIFIED WITH TECHNICAL CONDITIONS**

**This verdict does not authorize merge, staging or production.**
- All five merge blockers are independently resolved: RR-01, RR-02, RR-03, RR-04 and RR-11.
- No BLOCKER remains, and no merge-scope MAJOR remains.
- Some amendments needed before merge are **INCOMPLETE** rather than technically sound: AM-7, and the wording of AM-13 and AM-4. This is why the verdict is not "technically certified for owner decision".
- Owner decisions and gates remain explicit and open, including TG-01 and TG-08.

> This document covers technical artifacts only.
> - It modifies no implementation, architecture or `dist/` file.
> - It approves no amendment and completes no gate.
> - It complements the earlier reviews at `1aaf019` and `15d25a7`.

| Item | Value |
|---|---|
| Certified architecture | `778aa8fdd918da48340319696ada3ff673e9fb8e` |
| Previous targeted-review SHA | `2f6b59a0a6a59dbc41a597dddc7e6512dcd581fe` |
| **Remediation SHA reviewed** | **`6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`** |
| SHA as written in the brief | `6ec2e76f156e963c7363c4ad9ce93d0bc0b11f41`: **does not exist** (one-character transcription difference `…d0bc0b11f41` vs `…d0bccb11f41`; see §1) |
| Implementation branch head | `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41` (no later commit) |
| Review branch | `review/p0-independent-implementation-review` (previous commit `15d25a759cfc0342bdca45ba4a9c51550270f305`) |
| Machine-readable twin | [p0-final-targeted-independent-check.json](p0-final-targeted-independent-check.json) |

## 1. Scope verification (Phase 1)

**Target identity**

The brief's SHA `6ec2e76f156e963c7363c4ad9ce93d0bc0b11f41` is not a valid object:
- `git cat-file` fails on it.
- `git rev-parse --disambiguate=6ec2e76` returns only `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`.

That commit is:
- the remote head of `implementation/p0-foundation`;
- a child of `2f6b59a`;
- titled "Resolve final P0 implementation merge blockers";
- the head SHA of CI run **36574695736**.

The review therefore targets `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`, and the discrepancy is recorded as FC-A01.

| Check | Result | Evidence |
|---|---|---|
| Remediation SHA exists remotely and is branch head | Yes | `git ls-remote` → `refs/heads/implementation/p0-foundation 6ec2e76f156e963c7363c4ad9ce93d0bccb11f41` |
| Previous reviewed SHA is ancestor | Yes | parent of `6ec2e76` is `2f6b59a` |
| No force push or rewrite | Yes | remote-tracking reflog `9236aa3 → 6fd249c → 2f6b59a → 6ec2e76` (fast-forward pushes) |
| Nothing merged | Yes | `origin/main` = `13276a0`, a single commit from 2026-09-28; none of `778aa8f`, `9236aa3`, `2f6b59a` or `6ec2e76` is in `main` |
| Nothing deployed | No deployment evidence; `main` unchanged (merge to `main` would deploy `dist/`) | README.md:43-45 |
| Certified architecture byte-identical | **Yes.** `git diff 778aa8f 6ec2e76 -- docs/architecture` is empty | The 12 amendment files moved out of `docs/architecture/amendments/` (resolves RR-A23) |
| Amendments separated | Yes | `docs/proposals/amendments/` (AM-1 … AM-13, README, json) |
| All amendments PROPOSED, NOT APPROVED | Yes (md and json) | Ops verifier |
| Existing review artifacts unchanged | Yes | review branch head `15d25a7`; the implementation branch contains no `docs/reviews/` |
| Public lead API disabled | Yes | `dist/index.html:11-12` both metas empty; browser: 0 API or Turnstile requests |
| Secrets, databases, tokens, OTP secrets, recovery codes, keys, env files, raw artifacts | None | pattern scan of added paths; regex scan of added lines; no `XXXXX-XXXXX` code strings in evidence; CI now excludes `founder.json` from failure artifacts |
| Diff `2f6b59a..6ec2e76` | 118 files (66 added, 39 modified, 12 deleted, 1 renamed), +23 425 / −831 | Every change relates to the remediation. Code: auth/limiter, governance, archive, CLI logging, ratchet, deploy, site 404/form, UI restore. Tests. Docs, proposals and evidence. `0009_mfa_challenge_binding.py` changed **docstring only** (path of AM-11) |

## 2. Verdicts on the targeted items (Phases 2–11)

| Item | Prior severity (scope) | **Verdict** | Evidence | Blocking scope now |
|---|---|---|---|---|
| RR-01 | MAJOR (merge) | **RR-01 RESOLVED** | dist/404.html now links /assets/404.css; 0 inline <style>/<script>/on*= in dist/*.html; dist/_headers byte-identical to 2f6b59a (no 'unsafe-inline'). Browser under exact _headers: unknown paths and /privacy → HTTP 404 styled page; 0 CSP violations on home, 404, unknown, /privacy; 360 px single column; visible keyboard focus; axe WCAG 2.0/2.1/2.2 AA 0 violations without bypassCSP. Control: 2f6b59a still shows the unstyled page. Homepage unchanged. Real Cloudflare 404 behaviour inferred from Pages docs (no preview run) | — |
| RR-02 | MAJOR (merge) | **RR-02 RESOLVED** | rbac/users.py restore_user refuses FOUNDER-protected targets (403 FOUNDER_PROTECTED + FOUNDER_GOVERNANCE_BYPASS_BLOCKED). Restore only via FOUNDER_STATUS_CHANGE status=RESTORE with a second distinct eligible Founder; requester/target/duplicate approval refused; eligibility re-checked under the governance lock at execution; stale approval fails closed (DUPLICATE on reissued email); generic user/status/role/permission paths refuse; I1–I3 and nightly job hold; audit actor = approving Founder; custodians/break-glass cannot restore; concurrent requests/approvals/invite-vs-restore serialised, no 5xx. SQLite and PostgreSQL. AM-12 PROPOSED, NOT APPROVED | — |
| RR-03 | MAJOR (merge) | **RR-03 RESOLVED** | rbac/governance.py revalidate_after_escalation on promotion clears proposals no longer authorised (EMAIL_CHANGE_CANCELLED reason TARGET_BECAME_FOUNDER); verify_email_change takes the governance lock and recomputes class (fails closed). N17 and break-glass, out-of-band, DENY-removal and concurrent variants closed on both engines; only clean 409 VERSION_CONFLICT under concurrency, no deadlock, no 5xx. Residual FC-RBAC-1 (MINOR). AM-13 PROPOSED, NOT APPROVED | — |
| RR-04 | MAJOR (merge) | **RR-04 RESOLVED** | Layered limiter (kernel/ratelimit.py:16-45; auth/routes.py:57,251): per-IP, wide network (/24, /64), keyed-hash email+network, plus an account-wide password-failure budget that applies to MFA holders via CAPTCHA escalation without lockout. Original RR-AUTH-1 probe: 10 evaluated (was 40), 30 CAPTCHA-refused; correct password without CAPTCHA no longer yields MFA_REQUIRED; reset emails 3 (was 18). CAPTCHA-solving attacker: 94 guesses/simulated hour. Optimal-attacker victim: 31/40 sign-ins succeed, 9 delayed ≤ 30 s, never locked out. Known vs unknown identical; keys hold keyed hash only; spoofed CF-Connecting-IP/X-Forwarded-For from untrusted peer ignored; IR-23 fairness preserved. Residual FC-AUTH-1 (MINOR) | — |
| RR-05 | MAJOR (production) | **RR-05 RESOLVED (repository)** | Forged-manifest attack C11 now detected ('archive export missing'); altered/missing exports, missing middle manifest, truncated archive sequence and unannounced manifests detected on both engines. The separate latest-anchor-only weakness is FC-AUD-1 | Production (S3 Object Lock staging evidence) |
| RR-06 | MAJOR (production) | **RR-06 RESOLVED** | Two-phase archive: injected failures before/at/after commit, at finalise, pending/export write, os._exit at four stages, retry and two concurrent archivers — each leaves rows online without alarm or an alarmed 'archive not finalised' state repaired by the next run; C12 false alarm gone; no false alarm after legitimate recovery; no false-success manifest becomes authoritative | — |
| RR-07 | MAJOR (staging) | **RR-07 NOT RESOLVED (narrowly)** | Fixed: CLI/worker/scheduler configure logging and emit EMF lines (cli/main.py:29-36); scheduler records exit codes (ScheduledJobFailed=1, exit_code=3; cli/main.py:201-210); verify-chain records anchor-store errors. Remaining: FC-AUD-2 — the NoEffectiveRecoveryAdmin metric value is redacted by the log scrubber (kernel/logging.py:22 DENYLIST contains 'recovery'; maintenance.py:663), so the runbook alarm (api-runbooks.md:199) can never fire | Staging (alarm acceptance); recommended one-line fix before merge |
| RR-08 | MAJOR (production) | **RR-08 RESOLVED** | Path A confirm and change_password link replaced_by_id within the same session; original reproducer: old cookie within 20 s → access token, no new cookie, no reuse alarm; second use, use after 21 s, and new-then-old → theft → session revoked; logout-all, reset and stale tokens correct; forced mid-confirm failure commits nothing; no token material in logs; SQLite and PostgreSQL consistent. Pre-existing PG race FC-AUTH-4 (MINOR) | — |
| RR-11 | MINOR (merge) | **RR-11 RESOLVED** | dist/assets/app.js validates before every hand-off (consent only when intake on). Empty, missing name, missing phone and 7 invalid-phone cases never open WhatsApp; aria-invalid + linked error text + role=alert summary with focus; values retained; valid submissions (click, Enter, 360 px tap) open correctly encoded wa.me URLs (special characters decode exactly); no consent claim, honeypot, idempotency key, Turnstile or API configuration in the message; 0 API/Turnstile requests; one meta alone keeps intake off | — |
| RR-16 | MINOR (staging) | **RR-16 RESOLVED** | 38 cases: exit 2 for mypy absent/corrupt, invalid TOML, malformed baseline, baseline growth beyond CEILING (157), baseline naming a renamed file, exclude/files shrinking the checked set; exit 1 for new-file error, extra error, renamed-file error, bare '# type: ignore', ignore_errors/disable_error_code in pyproject; --update refused under CI (exit 2) and never admits new errors. Residual FC-OPS-1 (MINOR: inline '# mypy:' comments, per-module strict_optional, shadow mypy.ini, spoof package) | — |
| RR-17 | MINOR (production) | **RR-17 RESOLVED** | Runbook prohibits 9236aa3, documents forward-fix, restore requirements and maintenance mode, claims no rehearsal; deploy.sh ROLLBACK_FLOOR hard-coded (env override ineffective); --rollback 9236aa3 and --rollback 2f6b59a refused; readiness evaluated in-container after rollback with all four states. Residual FC-OPS-2 (MINOR): floor enforced only in --rollback mode and refusal is incidental (missing schema-status subcommand); plain './deploy.sh 2f6b59a' would deploy. RG-7 remains a production gate | Production (RG-7) |
| IR-A05 | ADVISORY (optional-auth gap) | **OPTIONAL-AUTH GAP RESOLVED** | Startup rejects optional-auth + permission, public + permission, unregistered/mismatched register entries, private route without permission; accepts valid private and narrowly registered public routes; 105 routes identical to 2f6b59a, none newly public. Residual FC-AUTH-2 (MINOR, latent): an unrecognised auth mode string is not allow-listed | — |

**Staging gate required for S3 Object Lock anchoring: Yes.** Repository behaviour is resolved for RR-05 and RR-06. Real Object Lock, write-once versioning and writer/verifier role separation must be proven in staging (FC-01, FC-03). The local anchor store cannot resist a host attacker holding the app credentials. That is acceptable only because production refuses to start without `VEDA_ANCHOR_BUCKET`.

**AM-7 replacement: INCOMPLETE.** Not approved by this review. Two gaps:
- It does not disclose the reset-link availability residual (FC-05).
- Its Turnstile-outage bound is inaccurate (FC-A06).

## 3. Amendments (Phase 12)

- All thirteen amendments live under `docs/proposals/amendments/` and are marked **PROPOSED, NOT APPROVED**.
- None modifies the certified architecture.
- Staging and production evidence is kept separate from repository testing.

| Amendment | Subject | Classification | Owner decision needed before |
|---|---|---|---|
| AM-1 | 03 §5.5 factor index | TECHNICALLY SOUND | Merge |
| AM-2 | 08 §4.5 invite MFA response | TECHNICALLY SOUND WITH OWNER CONDITIONS (accept invite-link password-overwrite residual) | Merge |
| AM-3 | 08 §4.1/§4.7 optional CAPTCHA | TECHNICALLY SOUND | Merge |
| AM-4 | 04 §5.4 vs 08 §8.5 re-consent | INCOMPLETE (gaps honestly labelled: later-version rule, create-time consent, immutability) | Merge (owner may accept labelled gaps) / completion before production |
| AM-5 | 08 §1, 06 §11, 09 break-glass cancel | TECHNICALLY SOUND WITH OWNER CONDITIONS (outbox retention bound not enforced) | Merge; retention enforcement before production |
| AM-6 | Readiness / rollback | TECHNICALLY SOUND WITH OWNER CONDITIONS (resolve FC-12 release floor) | Merge |
| AM-7 | 08 §12 layered limiter (replacement) | INCOMPLETE (FC-05 reset-link disclosure; FC-A06 outage bound) | Merge — correct text before approval; real-Turnstile staging evidence |
| AM-8 | 05/03 HMAC action tokens | TECHNICALLY SOUND | Production |
| AM-9 | 06 §7.5 hostile sole-Founder veto | INCOMPLETE (no decision; not implemented) | Production |
| AM-10 | 07 §2 PII fields | INCOMPLETE (honestly labelled) | Production |
| AM-11 | 03 §5.7 / 05 §11.3 MFA binding | TECHNICALLY SOUND WITH OWNER CONDITIONS (refresh rule wording FC-A08; N-1 wording FC-12) | Merge; RG-7 before production |
| AM-12 | 06 §7.2.2 Founder RESTORE | TECHNICALLY SOUND WITH OWNER CONDITIONS (FC-A10, FC-A12 wording) | Merge |
| AM-13 | Execution-time governance-class revalidation | TECHNICALLY SOUND WITH OWNER CONDITIONS (correct withdrawal over-claim FC-08, FC-A09) | Merge |

**Required before merge (owner decision, after the text fixes):** AM-1, AM-2, AM-3, AM-4 (or owner acceptance of its labelled gaps), AM-5, AM-6, AM-7 (text corrected), AM-11, AM-12 and AM-13 (text corrected).

**Before production:** AM-8, AM-9, AM-10, the AM-4 completion, and the AM-5 retention enforcement.

## 4. Test and CI verification (Phase 13)

| Suite | Claimed | This check |
|---|---|---|
| SQLite full | 535 | **535 passed** (31.9 s). Plus 12 repeat runs, all 535; one flake in the auth verifier's 9 runs (FC-04) |
| PostgreSQL 16.4 full | 525 / 10 skipped | **525 passed, 10 skipped** (95.2 s; own server on :55433) |
| PostgreSQL 18.4 full | 525 / 10 skipped | **525 passed, 10 skipped** (99.4 s; embedded) |
| PG skips | — | 2 × `test_archive_ordering.py:266`, 6 × `test_backups.py`, `test_schema.py:93`, `test_schema.py:354`: all SQLite-only, identical on 16 and 18 |
| Auth suites + probes | — | 6 auth files 115/115 on both engines; IR-01 20-item + adjacent 52/52 on both |
| Governance | — | head suites 33/16/11/22 on both engines; P01–P17 (22) and N01–N17 (17) pass; 22 new probes pass |
| Audit/leads | — | 135 passed on SQLite; 135 run / 2 skipped on PostgreSQL; 19 failure-injection probes on both |
| Frontend (Node 22.23.3) | pass | npm ci, ESLint, typecheck, lint:tokens, contrast (58 pairs), 52 unit tests, build, `npm audit` 0 / `--omit=dev` 0 |
| Browser | 7/16/31/12 | **workspace 7/7, access 16/16, site 31/31, axe 12/12**. Plus reviewer probes: 404/CSP, disabled form, WhatsApp encoding, restore UI |
| Security tooling | pass | ruff, format, ratchet, openapi_check, secret_scan, bandit (-ll -ii), pip-audit (hashes), deploy-check: all exit 0 |
| Migrations | — | 10 revisions, 1 head; fresh SQLite/PG18 schemas identical to `2f6b59a` |

**CI.** GitHub API, run **36574695736**:
- push, attempt 1, `head_sha=6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`, conclusion `success`;
- all five jobs `success`: api (sqlite), api (postgresql), security, app, browser e2e + axe;
- no non-success steps (only the conditional artifact upload and the SQLite leg's PG-version step were skipped).

**Mandatory checks fail the pipeline.** Run 36558306690 (`6fd249c`) shows it: a single failing step ("Container image scan") concluded the run `failure`. The workflow has no `continue-on-error` or `|| true`. Job logs require authentication and were not read.

## 5. Regression check (Phase 14)

No material regression was found in any of the following areas:
- IR-01 transaction binding;
- MFA enrollment and recovery;
- invitation acceptance, password reset, email change;
- Founder governance, RBAC;
- audit actor attribution, the security-event chain;
- notification failure isolation;
- duplicate lead handling, consent history;
- UUIDv7, schema conformance;
- public API disablement, CSP;
- the live marketing homepage.

**New workspace UI.** For a deleted Founder, the drawer offers only "Restore via Founder actions". The restore request and a second Founder's approval work end to end under the app CSP, with 0 axe violations.

**Pre-existing latent issue found during regression testing.** FC-04 (timestamp race) surfaced once as a flaky CHECK violation. The lead reviewer traced it to `db.py:110` versus `:115`, and it is unchanged since `9236aa3`.

## 6. New findings

Counts: BLOCKER 0 · MAJOR 3 (none merge-scope) · MINOR 12 · ADVISORY 14.

| ID | Severity | Title | Evidence | Requirements | Required remediation | Blocking scope | Working-paper ID |
|---|---|---|---|---|---|---|---|
| FC-01 | **MAJOR** | Security-event verification checks only the latest anchor, so an attacker holding the chain key can rewrite history, recompute the chain and post a new anchor that verifies | api/veda/platform/maintenance.py:426 (store.latest('anchor')); REPRODUCED on both engines with local and S3-model stores | SEVT-006, SEVT-007, 05 §9.6 | Verify against every retained anchor (or a hash-linked anchor chain) and against anchors written by a separate writer role; alarm on any anchor that no longer matches | production (tamper-evidence claim); design residual first noted in the original review E.3 | FC-AUD-1 |
| FC-02 | **MAJOR** | NoEffectiveRecoveryAdmin metric value is redacted by the log scrubber, so its CRITICAL alarm can never fire (RR-07 residual) | api/veda/kernel/logging.py:22 DENYLIST includes 'recovery'; api/veda/platform/maintenance.py:663; docs/operations/api-runbooks.md:199; REPRODUCED via CLI and scheduler | LOG-006, RBAC-011, RG-5 | Exempt EMF metric keys from key-based redaction (or rename the metric); add a subprocess test asserting every runbook alarm metric is emitted unredacted | staging (alarm acceptance); one-line fix recommended before merge | FC-AUD-2 |
| FC-03 | **MAJOR** | S3 anchor/archive store writes without IfNoneMatch and reads the current object version, so an overwrite with the app credential creates a new version that verification trusts | api/veda/platform/anchor_store.py (put_object/get_object); SOURCE-INSPECTED plus simulated versioned store; real S3 not exercised | SEVT-007, 05 §9.6 | Conditional writes (IfNoneMatch='*'), read by first version / version id recorded in the manifest, writer role without s3:PutObject on existing keys; prove in staging | staging evidence / production gate | FC-AUD-3 |
| FC-04 | **MINOR** | Latent timestamp race: begin_unit_of_work reads the clock before acquiring the write lock, so under contention a later-clocked transaction can create a row that an earlier-clocked transaction then updates, violating ck_*__updated_after_created (fail-closed 500) | api/veda/kernel/db.py:110 (tx_time = clock.now()) precedes :115 (session.connection → BEGIN IMMEDIATE); SQLite busy handler is not FIFO; same ordering at 9236aa3 (pre-existing). Observed once in 22 full-suite runs (1/9 auth reviewer, 0/13 lead reviewer); failing test id not captured | DATA-003, DATA-005, NFR availability | Take tx_time after the connection/lock is acquired (and on PostgreSQL use max(tx_time, row.created_on) or DB clock_timestamp()), add a concurrency test | production | FC-AUTH-8 (root cause by lead reviewer) |
| FC-05 | **MINOR** | Per-account reset-email cap (3/hour) lets a third party keep the victim without a usable reset link for about half of every hour; AM-7 does not disclose it | REPRODUCED; api/veda/platform/auth/routes.py:251; links expire after 30 min | AUTH-008, AUTH-010 | Disclose in AM-7 and consider per-requester-network caps for reset delivery or a victim-initiated bypass | AM-7 wording before owner approval; production | FC-AUTH-1 |
| FC-06 | **MINOR** | Route auth mode is not allow-listed; an unrecognised mode string makes a permission-declaring route anonymous and passes startup (latent; no current route) | REPRODUCED in probe copy; api/veda/app.py startup checks, kernel/http.py | RBAC-012, 06 §8 | Allow-list auth modes at declaration and startup | production (latent) | FC-AUTH-2 |
| FC-07 | **MINOR** | PostgreSQL only: change_password racing a refresh returns 500 IntegrityError (pre-existing; fails closed) | REPRODUCED 2/10 (4/10 at 2f6b59a) | AUTH-005, AUTH-012 | Map to 409 / retry | PostgreSQL release gate | FC-AUTH-4 |
| FC-08 | **MINOR** | Adding a sensitive permission to a role blocks but does not withdraw a pending admin-requested email change (no cancel event); AM-13 over-claims withdrawal | REPRODUCED both engines: verify refused while privileged; after role reverted the old link verifies (204) | USER-007, 06 §7.1 | Withdraw on any class escalation, or correct AM-13 to 'blocked while escalated' | AM-13 wording before owner approval; production | FC-RBAC-1 |
| FC-09 | **MINOR** | Invitation link keeps its 72 h lifetime after an ADMIN role is assigned to an INVITED user (05 §8.4 says 24 h for privileged invites); pre-existing | REPRODUCED: accepted after 30 h | AUTH-011, 05 §8.4 | Shorten/reissue on privilege escalation | production | FC-RBAC-2 |
| FC-10 | **MINOR** | Approvals card does not show the requested Founder status, so an approver cannot distinguish RESTORE from DELETE or DISABLE except through the requester's free-text reason (pre-existing UI; server controls unaffected) | app/src/modules/admin/approvals-page.ts:91-95 (unchanged since 9236aa3) | RBAC-021, 06 §7.2 (informed dual control), UI-017 | Render request_payload (status, email) in the card and the approve dialog | staging (before Founders use governance) | FC-FE-2 |
| FC-11 | **MINOR** | mypy ratchet suppression detection incomplete: inline '# mypy:' config comments, per-module strict_optional overrides, shadow mypy.ini/.mypy.ini and a spoof 'mypy' package admit new errors with exit 0 | REPRODUCED; api/tools/mypy_ratchet.py | 12 §5 | Detect inline config comments and extra config files; pin config path; import mypy from the venv explicitly | staging (CI gate integrity) | FC-OPS-1 |
| FC-12 | **MINOR** | Rollback floor is schema-only and enforced only in --rollback mode; a pre-6ec2e76 image that knows 0009 (e.g. 2f6b59a, lacking the RR-02/RR-03 fixes) deploys through the normal path; AM-11 wording admits it | REPRODUCED with stubbed docker; api/deploy/deploy.sh | OPS-004, RR-17 | Enforce a release floor (image label / git SHA allow-list) in every deploy mode; fix AM-11 text | production | FC-OPS-2 |
| FC-13 | **MINOR** | Archive export and pending keys use last_seq only; an abandoned attempt plus a retention change can collide with a later segment (archival fails, alarmed, no data loss) | REPRODUCED both engines | SEVT-004 | Key by (first_seq, last_seq, run id) | production | FC-AUD-4 |
| FC-14 | **MINOR** | On SQLite, archival holds the database write lock across object-store I/O | SOURCE-INSPECTED; api/veda/platform/maintenance.py | NFR availability | Upload outside the write transaction | production | FC-AUD-5 |
| FC-15 | **MINOR** | Site focus-ring colour #c59158 is 2.60:1 on the page background and 2.21:1 on the cream card (below 3:1 non-text contrast); pre-existing since 778aa8f | dist/assets/404.css:8 | UI-011 (site), WCAG 1.4.11 | Darken focus ring | production (site a11y, tracked) | FC-FE-1 |

### Advisories

- **FC-A01** Brief/evidence SHA transcription error: the brief names 6ec2e76f156e963c7363c4ad9ce93d0bc0b11f41, which does not exist; the only object matching 6ec2e76 is 6ec2e76f156e963c7363c4ad9ce93d0bccb11f41 (remote head, parent 2f6b59a, CI run 36574695736). Owner records should cite the correct SHA.
- **FC-A02** Owner decisions OD-2/OD-3 are recorded as 'given' in the matrix and deviation register (DEV-009/DEV-010) with no decision-log citation; the matrix also renumbers ODs relative to the re-review. The owner must confirm them in a decision record (FC-OPS-4).
- **FC-A03** Merge-safety plan's pre-merge list omits TG-01 PASS and amendment approval, which the registry marks merge-blocking (FC-OPS-3).
- **FC-A04** Unknown permission codes are accepted at startup (FC-AUTH-3).
- **FC-A05** Account budget check-then-record not atomic on PostgreSQL (FC-AUTH-5).
- **FC-A06** AM-7 claims a '≤ 15 min' bound during a Turnstile outage that is false under sustained attack (FC-AUTH-6).
- **FC-A07** Per-challenge 5-code limit exceeded under parallelism on both engines (FC-AUTH-7, pre-existing IR-A01 residual).
- **FC-A08** AM-11 refresh rule 'whenever assurance changes' is broader than implemented (step-up does not rotate).
- **FC-A09** Admin-issued password-reset and MFA-enrollment links survive promotion to Founder (FC-RBAC-3).
- **FC-A10** Custodian CLI refuses a restore as 'unknown target' with no FAILURE event instead of SECOND_FOUNDER_REQUIRED as AM-12 states (FC-RBAC-4).
- **FC-A11** Request/executed/failed security events do not name RESTORE (FC-RBAC-5).
- **FC-A12** A restored and reactivated Founder signs in with pre-deletion password and MFA factor; AM-12 silent (FC-RBAC-6).
- **FC-A13** E2E static server binds all interfaces (FC-FE-3).
- **FC-A14** A PostgreSQL server from a different local session was listening on 127.0.0.1:55432 during this check; this review used its own instance on :55433 and did not touch it.

## 7. Blocking scope

**Merge — technical conditions** (bounded, text-level):
1. Correct the amendment text for AM-7 (FC-05, FC-A06), AM-13 (FC-08, FC-A09), AM-11 (FC-A08, FC-12 wording) and AM-12 (FC-A10, FC-A12). Complete AM-4, or have the owner explicitly accept its labelled gaps.
2. Correct the SHA in owner and governance records to `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41` (FC-A01).
3. Recommended before merge: the one-line FC-02 fix (unredacted `NoEffectiveRecoveryAdmin` metric).

**Merge — owner decisions and gates** (not technical; this review cannot complete them):
- Approve or reject AM-1 … AM-7 and AM-11 … AM-13.
- Confirm OD-2 and OD-3 in a decision record (FC-A02).
- Complete TG-01 and TG-08.
- Approve the site production deployment that a merge to `main` triggers (README.md:43-45; merge-safety plan, and FC-A03 for the missing TG-01 entry).

**Staging:**
- FC-02 / RR-07 alarm acceptance.
- FC-03, with S3 Object Lock evidence.
- FC-10 approvals status visibility.
- FC-11 ratchet suppression gaps.
- Carried from the re-review: RR-09 custodian identity rehearsal, RR-10, RR-14, RR-15, and IR-06/IR-11/IR-12 acceptance.

**Production:**
- FC-01, FC-04, FC-05, FC-06, FC-08, FC-09, FC-12, FC-13, FC-14, FC-15.
- Carried from the re-review: RR-12, RR-13, RR-18, IR-03, IR-27, IR-37, IR-38, IR-A10, IR-A14, AM-8/AM-9/AM-10 decisions.
- All 27 gates: OWNER-INPUT-001..004, RG-1..9 (including the RG-7 rollback rehearsal and RG-5 alarm test-fire), PG-DAST, PG-RET, PG-BG, PG-EMAIL, PG-PRIV.

**Public-intake enablement:**
- Privacy Notice (PG-PRIV).
- Turnstile keys, with a real-key 422 → reset → 201 run.
- CSP `connect-src` for the API origin.
- CORS, rate limits and trusted proxy settings.
- Staging verification and production approval.

**PostgreSQL release gate (PGM-1):** IR-33, IR-A01, IR-A16, FC-07, FC-A05, FC-A07.

## 8. Final report (A–AH)

| Key | Item | Result |
|---|---|---|
| A | Remediation SHA reviewed | `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41` (brief's `6ec2e76f156e963c7363c4ad9ce93d0bc0b11f41` does not exist; FC-A01) |
| B | Review branch | `review/p0-independent-implementation-review` |
| C | Review commit SHA | The commit adding this file (see branch log; parent `15d25a7`) |
| D | Repository scope | Verified: single fast-forward commit on `2f6b59a`; architecture byte-identical; amendments under `docs/proposals/`; nothing merged or deployed; no secrets; intake disabled; every change remediation-relevant |
| E | RR-01 | **RR-01 RESOLVED** |
| F | RR-02 | **RR-02 RESOLVED** |
| G | RR-03 | **RR-03 RESOLVED** |
| H | RR-04 | **RR-04 RESOLVED**. AM-7 replacement: **INCOMPLETE** |
| I | RR-05 | **RESOLVED** (repository). Staging gate required: Yes |
| J | RR-06 | **RESOLVED** |
| K | RR-07 | **NOT RESOLVED** (narrowly: FC-02; staging-scope) |
| L | RR-08 | **RR-08 RESOLVED** |
| M | RR-11 | **RR-11 RESOLVED** |
| N | RR-16 | **RR-16 RESOLVED** (residual FC-11) |
| O | RR-17 | **RR-17 RESOLVED** (residual FC-12; RG-7 remains a gate) |
| P | Optional-auth | **OPTIONAL-AUTH GAP RESOLVED** (residual FC-06, latent) |
| Q | Amendments | Sound: AM-1, AM-3, AM-8. Sound with owner conditions: AM-2, AM-5, AM-6, AM-11, AM-12, AM-13. Incomplete: AM-4, AM-7, AM-9, AM-10. None unsound or unnecessary. All PROPOSED, NOT APPROVED |
| R | SQLite | 535 passed (plus 12 repeats, all 535) |
| S | PostgreSQL 16 | 16.4: 525 passed, 10 skipped |
| T | PostgreSQL 18 | 18.4: 525 passed, 10 skipped |
| U | Frontend | Node 22.23.3: ESLint, typecheck, tokens, contrast, 52 tests, build, audit 0/0 |
| V | Browser | 7/7, 16/16, 31/31, 12/12; 404/CSP, disabled form and WhatsApp fallback verified by reviewer probes |
| W | Security | MFA bypass, step-up bypass, IDOR, mass assignment, refresh replay, limiter abuse, audit-chain failure injection and route-registry validation probes pass; scanners clean |
| X | CI | Run 36574695736 on `6ec2e76`: 5/5 jobs success; failure propagation demonstrated by run 36558306690 |
| Y | Regression | No material regression. Pre-existing latent FC-04 found |
| Z | Remaining BLOCKER | None |
| AA | Remaining merge-scope MAJOR | None |
| AB | Remaining MINOR | FC-04 … FC-15 (12). Carried MINORs from the re-review per §7 |
| AC | Staging gates | §7 Staging |
| AD | Production gates | §7 Production and all 27 gates |
| AE | Required owner decisions | Amendment decisions (AM-1 … AM-7, AM-11 … AM-13 before merge; AM-8 … AM-10 before production); confirm OD-2 and OD-3 in a decision record; TG-01; TG-08; site production deployment on merge; custodian credential model (OWNER-INPUT-004); OWNER-INPUT-001..003 |
| AF | Merge-safety requirements | Text corrections to AM-4/7/11/12/13; correct SHA in records; recommended FC-02 one-line fix; owner decisions; TG-01 and TG-08 PASS; explicit acceptance that merge deploys `dist/` (RR-01/RR-11 fixes verified; intake stays disabled); no rollback to `9236aa3` or `2f6b59a` (FC-12 until fixed) |
| AG | Exact next authorized action | **Owner decision only.** No merge, staging or production step is authorized. The owner decides whether to authorize (a) an amendment-text correction increment (optionally with the FC-02 one-liner), followed by a document-level confirmation, and then (b) the owner decisions above and TG-01/TG-08. Merge proceeds only after those are recorded |
| AH | Final verdict | **CERTIFIED WITH TECHNICAL CONDITIONS** |

### Verdict rationale

- **All five merge blockers are independently resolved on both engines**, with reviewer-run probes and browser checks.
- **No BLOCKER and no merge-scope MAJOR remains.** The three new MAJOR findings are staging or production gates:
  - FC-01 and FC-03 concern external tamper-evidence;
  - FC-02 is an alarm metric.
- **No material regression was found.**
- **Why not TECHNICALLY CERTIFIED FOR OWNER DECISION:** four amendments that must be decided before merge contain inaccurate or incomplete text (AM-4, AM-7, AM-13, AM-11 wording). Those are bounded, document-level conditions, so CERTIFIED WITH TECHNICAL CONDITIONS applies.
- **Merge safety is maintained if:**
  - the conditions in §7 are met;
  - the owner decisions are recorded;
  - the owner explicitly accepts that merging deploys `dist/` to production.

---

## Appendices

Appendices B to F are the verifiers' working tables, included verbatim as evidence. Local IDs map to consolidated IDs as follows:

| Working-paper ID | Consolidated ID |
|---|---|
| FC-AUD-1 | FC-01 |
| FC-AUD-2 | FC-02 |
| FC-AUD-3 | FC-03 |
| FC-AUTH-8 | FC-04 (root cause by lead reviewer) |
| FC-AUTH-1 | FC-05 |
| FC-AUTH-2 | FC-06 |
| FC-AUTH-4 | FC-07 |
| FC-RBAC-1 | FC-08 |
| FC-RBAC-2 | FC-09 |
| FC-FE-2 | FC-10 |
| FC-OPS-1 | FC-11 |
| FC-OPS-2 | FC-12 |
| FC-AUD-4 | FC-13 |
| FC-AUD-5 | FC-14 |
| FC-FE-1 | FC-15 |

The remaining items are advisories, listed in §6.

### Appendix A — Lead reviewer commands

```
git fetch origin --prune; git ls-remote origin
git cat-file -t 6ec2e76f156e963c7363c4ad9ce93d0bc0b11f41                # fatal: could not get object info
git rev-parse --disambiguate=6ec2e76       # 6ec2e76f156e963c7363c4ad9ce93d0bccb11f41
git diff --name-status 2f6b59a 6ec2e76; git diff 778aa8f 6ec2e76 -- docs/architecture   # empty
VEDA_TEST_ENGINES=sqlite python -m pytest -q -rs           # 535 passed (×13)
VEDA_TEST_DATABASE_URL_PG=postgresql+psycopg://postgres@127.0.0.1:55433/postgres VEDA_TEST_ENGINES=postgresql python -m pytest -q -rs   # 525 / 10 skipped (16.4)
VEDA_PG_DATA=<scratch>/pgdata18c VEDA_TEST_ENGINES=postgresql python -m pytest -q -rs    # 525 / 10 skipped (18.4)
curl https://api.github.com/repos/slaggala/veda-spaces/actions/runs/36574695736(/jobs)  # success ×5
```

### Appendix B — Auth, limiter, refresh, route registration

#### B.1 Layer map

| Layer | Key | Limit / behaviour | Evidence |
|---|---|---|---|
| Source IP | client IP (IPv6 by /64) | login 10/min, forgot 5/min, MFA verify/recovery/enroll start/confirm/step-up 10/min, email verify/cancel 10/min (new), reset 5/min | `kernel/ratelimit.py:15-19`, `net.py:48-53`, `auth/routes.py:57,215,229,251,271,304,384,403,427,449,457` |
| Wide network | IPv4 /24, IPv6 /48 | login 30/min, forgot 20/min, MFA verify/recovery 30/min | `ratelimit.py:22-27`, `net.py:38-44` |
| Identifier × network | HMAC(normalized email)[:32] and /24 or /64 | login 5/min, forgot 3/hour (IR-23 preserved) | `ratelimit.py:30-45` |
| Account × network pair | account key and /24 or /64 | at 5 failures, Turnstile plus escalating block up to 15 min (certified) | `throttle.py:171-195` |
| Account across networks (new) | user id, or `unknown:`+HMAC | ≥10 failures in 15 min: Turnstile on every attempt. ≥20: spacing 2 s doubling to 30 s (429 + Retry-After). Success does not reset. | `throttle.py:128-160`, `service.py:401-408,423,447` |
| Global lock, non-MFA (certified) | user | ≥5 distinct networks in 15 min: `locked_until` 15 min. Factor holders exempt. | `service.py:433,452-470` |
| Aggregate (new) | process | 200 failures in 5 min: Turnstile for every sign-in | `throttle.py:131,158` |
| MFA / recovery / enroll-confirm / step-up | user | 10 failures in 15 min: MFA 429 for 15 min | `mfa.py:78-93,128,167,456,551` |
| Re-auth / change-password | user | 10 in 15 min (IR-24) | `service.py:736-805` |
| Reset emails (new) | user | ≤3 per account per hour across networks, answered identically | `throttle.py:163-174`, `service.py:694-704` |
| Client address | CF-Connecting-IP only from a trusted-proxy peer; `validate_environment` refuses prefixes broader than /24 or /64 | `net.py:62-73`, `config.py:364-371` |
| Cardinality | `MAX_TRACKED` 50 000 per table, stale entries evicted first, then oldest | `throttle.py:106-113` |

#### B.2 RR-04 20-item probe table

Probes: `$S/probes3/auth/api/tests/integration/test_fc_limiter.py`, `test_fc_resetdos.py`, `test_rr_dev007.py`, `test_rr_misc.py`. All 19 limiter probes pass on both engines. Every number below is identical on SQLite and PostgreSQL unless stated.

| # | Scenario | Result (REPRODUCED) | OK? |
|---|---|---|---|
| 1 | One network → one MFA account, 12 tries | 5 evaluated (5th flags captcha), then 7× 429 from the identifier×network limit | Yes |
| 2 | One network → many accounts | Single IP: 10× 401 then 429. Rotating hosts in one /24: 30× 401 then 5× 429. | Yes |
| 3 | Many networks → one account, attacker solves every Turnstile, 1 simulated hour, rotating /48s | **94 evaluated guesses/h** (60× 429, 154 requests), about 2.2k/day. The certified per-email limit (5/min) allowed 300/h with no challenge. | Bounded |
| 4 | MFA victim | Budget applies (item 12). Oracle closed after 10 failures. | Yes |
| 5 | Non-MFA victim, 5 networks | Correct password refused even with Turnstile; works after 16 min. This is the certified 05 §4 lock, disclosed in AM-7 (7). | Certified |
| 6 | Nonexistent account | Same budget under the `unknown:` key; same sequence as a real account (item 20) | Yes |
| 7 | Rotating IPv4 /24s → one MFA account | 9 unflagged plus 1 flagged evaluated, then Turnstile. Hosts in one /24: 30 then 429. | Yes |
| 8 | IPv6 | /64 rotation inside one /48: 30 then 429 (wide key). Rotation across /48s: 35× 401 from the source layers, while the account budget still bounds any single account. | Yes |
| 9 | Spoofed CF-Connecting-IP / X-Forwarded-For / X-Real-IP from an untrusted peer | All keyed on the peer: `[401×5, 429×7]`, one network recorded (`127.0.0.0/24`). XFF is never read (no ProxyFix). | Yes |
| 10 | Trusted peer (127.0.0.1) | CF-Connecting-IP honoured: 12 distinct networks recorded | Yes |
| 11 | Victim DoS | See the breakdown below this table. | Bounded (MFA); certified (non-MFA) |
| 12 | Original RR-AUTH-1 re-run (40 guesses/min from 8 /64s, MFA holder) | **10 evaluated, 30 refused with captcha_required** (was 40 evaluated). Correct password without Turnstile: 401 captcha_required (was 200 MFA_REQUIRED). With Turnstile: 200 MFA_REQUIRED. **Reset emails: 3 of 18** (was 18). | **Fixed** |
| 13 | Correct password after attack | MFA holder: needs Turnstile, then MFA_REQUIRED (≤30 s wait in the delay tier). Non-MFA holder: certified lock. | Yes |
| 14 | CAPTCHA escalation | 15 attempts with a failing token: all 401 captcha_required; the budget stays at 10 (unsolved attempts are not counted and not evaluated). | Yes |
| 15 | Recovery | `/mfa/recovery` one IP: 10 then 429. Account: 10 failures, then MFA 429 (author test and my run). Reset flow: see FC-AUTH-1. | Yes (FC-AUTH-1) |
| 16 | MFA confirmation limits | Verify: 10 wrong codes from 12 /64s, then 429, including for the correct code, clearing after 15 min (certified; needs the password). Enroll-confirm failures count: `mfa_blocked=True` after 10 (matches the AM-7 claim). | Yes |
| 17 | Concurrent attempts (40 parallel from 40 /48s, fresh account) | SQLite: budget exactly 10 (serialised by BEGIN IMMEDIATE). **PostgreSQL: 13 recorded**, overshooting by the thread count (FC-AUTH-5). | SQLite yes; PG advisory |
| 18 | Logs, keys and events | Limiter keys are `email:<HMAC32>\|<net>`. Raw email appears in 0 keys, 0 log lines and 0 events (keyed HMAC, `security_events.py:224`). | Yes |
| 19 | Cardinality | Budgets capped at 50 001 (the victim entry is evicted after 50 005 fresh ids, but the aggregate tier is then on; over HTTP this costs about 50k Turnstile solves in 15 min). Pairs are bounded. `_accounts` has no cap on the MFA/re-auth paths, but it is keyed by real user ids. Flask-Limiter MemoryStorage: 3 keys per (email, /64), each with a TTL. | Yes (advisory) |
| 20 | Known vs unknown | 25-step login sequences (status, code, captcha flag, Retry-After, RateLimit-* headers) are identical. Forgot bodies are identical (202). | Yes |

**Item 11 detail (victim DoS):**

- **MFA victim, optimal attacker.** The attacker solves Turnstile and fires at each Retry-After expiry. The victim tries every 45 s for 30 min: 31 of 40 attempts succeeded (MFA_REQUIRED), and 9 got 429 lasting at most 30 s. This cost the attacker 64 solved challenges.
- **Victim honouring Retry-After:** 1 try.
- **Non-MFA victim:** can be kept out indefinitely by 5 failures per 15 min from 5 networks. This is the certified 05 §4 lock, not a regression.
- **Reset links:** see FC-AUTH-1.

**RR-04 RESOLVED.**

- A cross-network, network-independent bound now applies to every identifier, including MFA holders and nonexistent addresses.
- The MFA_REQUIRED oracle is closed after 10 failures.
- Reset emails are capped at 3 per account per hour.
- IR-23 still holds: the victim's other /24 got 200 in `test_DEV007_keys`.

**AM-7 check.** These claims match behaviour:

- the thresholds;
- the endpoint list, including email verify/cancel and enroll confirm;
- identical known and unknown behaviour;
- the HMAC-only keys;
- the /24 and /64 proxy bound;
- the 50 000 cap, which is correct for the budget, pair and reset tables;
- "at most one attempt per 30 s" (measured about 1 per 38 s in steady state).

These are inaccurate or missing (see FC-AUTH-1 and FC-AUTH-6):

- the reset-link DoS trade-off is not disclosed;
- "fails closed ... until the window drains (≤ 15 minutes)" is false under sustained attack;
- the "capped per table" claim does not hold for `_accounts`, which is minor.

**Classification: INCOMPLETE.**

#### B.3 RR-08

**Rotation sites:**

- `grep used_on|replaced_by` finds exactly three refresh-token writers:
  - the normal refresh (`service.py:600-612`, linked);
  - path A confirm (`mfa.py:447-449,509` → `service.rotate_session_refresh`);
  - `change_password` (`service.py:794` → the same helper).
- `rotate_session_refresh` (`service.py:753-774`) inserts and flushes the successor, then marks every live token of **this session only** with `used_on` and `replaced_by_id=successor.id`.
- Step-up changes `mfa_verified_on` without rotating (`mfa.py:576`); see the AM-11 note.

Probes: `test_fc_refresh.py`, `test_fc_race2.py`, `test_rr_race.py`. Both engines unless stated.

| Check | SQLite | PostgreSQL | OK? |
|---|---|---|---|
| Original RR-AUTH-2 reproducer (path A, old cookie <20 s) | 200 access token, **no Set-Cookie**, 0 reuse events, elevated token still valid (was 401 + CRITICAL + revoked) | same | **Fixed** |
| Same for change_password | 200, session not revoked (was theft) | same | **Fixed** |
| DB linkage after path A and after pw-change | 2 tokens: 1 live, 1 linked, 0 unlinked-used | same | Yes |
| Second old-cookie use (grace already used) | 401, REFRESH_REUSE_DETECTED, session TOKEN_REUSE, new cookie then 401 (family revoked) | same | Yes (05 §6.1) |
| Old cookie after 21 s | 401, TOKEN_REUSE | same | Yes |
| New cookie used, then old (<20 s) | 200, then 401 theft (successor already used) | same | Yes |
| Cross-session | S1 rotated 3 tokens: 1 live, 2 linked, all successors in S1. S2 untouched (1 live, 0 linked) and survives S1 revocation (200). | same | Yes |
| Stale gen-0 cookie after two rotations | 401, S1 revoked, S2 unaffected | same | Yes |
| Logout-all after path A | old 401, new 401 | same | Yes |
| Password reset (recovery) after pw-change rotation | old 401, new 401 | same | Yes |
| Race: path A confirm ‖ refresh(old), ×8 | 8/8: both 200, 1 live token, no revoke | 8/8: confirm **409 VERSION_CONFLICT**, refresh 200, 1 live token; retry of the same challenge → 200 pwd+totp | Yes (transient 409) |
| Race: change_password ‖ refresh(old), ×8–10 | all 204/200, 1 live token | 7/10 204; 1/10 409; **2/10 500 IntegrityError** `ck_refresh_token__updated_after_created`; password unchanged (fail closed). **At 2f6b59a: 4/10 500**, so pre-existing (FC-AUTH-4) | SQLite yes; PG pre-existing MINOR |
| 6 parallel old-cookie refreshes after path A | 1 grace, then 5 theft → revoked (same as the certified ordinary rotation on SQLite) | 1 grace, then 5× 409, not revoked | Consistent with prior engine behaviour (RR-AUTH-5) |
| Atomicity (inject failure after rotation in confirm) | 500; tokens unchanged (1 live, 0 linked); old cookie still refreshes | same | Yes |
| Token material in logs (raw or sha256) | 0 | 0 | Yes |

**RR-08 RESOLVED.**

#### B.4 Route registration

Probe: `$S/probes3/auth/routecheck.py`. It registers a synthetic blueprint and runs `create_app`. Output is in `routecheck_fc.txt` and `routecheck_rr.txt`.

| Case | 6ec2e76 | 2f6b59a |
|---|---|---|
| optional-auth + permission (registered RBX) | **REJECTED** | ACCEPTED (the gap) |
| optional-auth + permission, no rbx | **REJECTED** | ACCEPTED |
| optional-auth, no rbx/permission | REJECTED | REJECTED |
| public + permission / + any_of | REJECTED | REJECTED |
| public, RBX-999 (not in register) | REJECTED | REJECTED |
| public, known RBX, path not listed | REJECTED | REJECTED |
| public, no rbx | REJECTED | REJECTED |
| bearer, no permission, no rbx | REJECTED | REJECTED |
| registry method mismatch (GET vs POST) / path mismatch / wrong RBX id | REJECTED ×3 | REJECTED ×3 |
| **VALID** bearer + permission | ACCEPTED; anonymous → 401 AUTH_REQUIRED | same |
| **VALID** public, narrowly registered | ACCEPTED; anonymous → 200 | same |
| bearer + invalid permission code / any_of code | ACCEPTED (fails closed: nobody holds it) | same, FC-AUTH-3 |
| auth mode `"Public"` / `"cookie"` / `"none"` + permission, no rbx | **ACCEPTED; anonymous → 200 (permission never enforced)** | same, FC-AUTH-2 |

**Runtime inventory:**

- 105 routes: 89 bearer, 14 public, 2 optional (enroll start/confirm, RBX-004, no permission).
- (method, rule, auth, permission, any_of, rbx, recovery_allowed, pwd_change_allowed) is **identical** between 2f6b59a and 6ec2e76 (`inv_rr.json` vs `inv_fc.json`).
- No route became public.

**OPTIONAL-AUTH GAP RESOLVED.**

#### B.5 Regression

| Suite | SQLite | PostgreSQL (embedded) |
|---|---|---|
| Head: test_mfa_binding, test_auth, test_mfa, test_auth_remediation, test_layered_limiter, test_final_merge_blockers | **115 passed** | **115 passed** |
| IR-01 20-item and adjacent probes (test_rr_ir01/misc/race/dev007) | **52 passed** | **52 passed** |
| New probes (fc_limiter 19, fc_refresh 5, fc_race2 3, fc_resetdos 1) | 28 passed | 27 passed (resetdos run on SQLite only) |
| Full suite (excluding probes) | 535 passed ×8; **1 failed ×1** (`ck_user_action_token__updated_after_created`, test id not captured; FC-AUTH-8) | not run |

**IR-01 20 items:** unchanged from the re-review on both engines.

- Every cross-principal, cross-session, cross-path and replay combination gets 401 MFA_CHALLENGE_INVALID or ENROLLMENT_PROOF_INVALID.
- Item 13 injected failures commit nothing.
- Item 17 improved: the old cookie now gets grace.
- Item 20 refusals are indistinguishable.

**Adjacent flows**, all as before:

- MFA enrollment (paths A–D) and recovery (1 RECOVERY session under parallel use).
- Invitation accept, replay and resend.
- Password reset (MFA link survives the reset, as before).
- Email change: verify 204, replay 400, cross-token 400. The new governance lock does not break the ordinary path.

**Pre-existing items unchanged:**

- Path C start password guesses are still unthrottled (RR-AUTH-7: 15 wrong, then correct → 200).
- A PENDING factor survives challenge expiry (RR-AUTH-9).
- The per-challenge 5-code limit is exceeded under parallelism: FC-AUTH-7 (now also seen on SQLite, 5–7 of 9, identically at 2f6b59a).

### Appendix C — Founder governance

#### C.1 RR-02

The new workflow is `POST /founder-actions {action: FOUNDER_STATUS_CHANGE, status: RESTORE}`. One eligible Founder requests it, and a second, distinct eligible Founder approves it in-app. The account comes back DISABLED and FOUNDER-protected; reactivation is a separate dual-control ACTIVE request.

- The route loads the deleted target only for RESTORE (`routes.py:518-520`).
- `_validate_founder_action` requires `is_deleted == is_restore` (`governance.py:276-287`).
- Break-glass is refused at request (`:323`), at execution (`:400`) and on the custodian request path (`:764`).

Probes were run on both engines, with identical outcomes unless stated.

| # | Requirement | Probe | Actual outcome (SQLite = PG) | Result |
|---|---|---|---|---|
| 1 | One Founder cannot restore a deleted Founder | N11, P11, R01 | `POST /users/{F3}/restore` by F1 → **403 FOUNDER_PROTECTED** (was 200 at 2f6b59a). F3 stays deleted, DISABLED, FOUNDER. `FOUNDER_GOVERNANCE_BYPASS_BLOCKED` is recorded (created_by F1, `{action: restore}`). An ADMIN gets 403 PERMISSION_DENIED. | PASS |
| 2 | Two distinct eligible humans | R01, R02 | F1 request → 202 IN_APP; F2 approve → EXECUTED. With F2 in cooling-off, F1's request → **409 SECOND_FOUNDER_REQUIRED** and no row is created. | PASS |
| 3 | Requester cannot approve | R01 | 403 APPROVER_NOT_ELIGIBLE | PASS |
| 4 | Target cannot approve | R01 | F3's sessions were revoked at deletion. The pre-deletion token gives 401 SESSION_INVALID on `/auth/me`, on approve, and on a self-request. `approve()` also excludes the target id (`governance.py:510`). | PASS |
| 5 | No double approval | R01 | F2 again → 409 INVALID_STATE; F4 after execution → 409 | PASS |
| 6 | Generic PATCH cannot restore | R01 | `PATCH /users/{F3}` → 404 | PASS |
| 7 | Generic status endpoints cannot restore | R01 | `/status ACTIVE`, `/invite/resend`, and FOUNDER_STATUS_CHANGE ACTIVE on the deleted F3 → 404. RESTORE on a live Founder → 409 "not deleted". After restore, generic ACTIVE → 403 FOUNDER_PROTECTED. | PASS |
| 8 | Role and permission APIs cannot restore Founder power | R01, P02, P03 | PUT roles [FOUNDER] or a `user.founder.manage` grant on the deleted F3 → 404. GRANT_FOUNDER on the deleted F3 → 404. On live users these give 403 FOUNDER_GOVERNANCE_REQUIRED (P02). | PASS |
| 9 | Approver eligibility checked at execution | R02 | Approver in cooling-off → 403 (the message wrongly reads "Requires user.mfa.reset"; carry-over A4). Requester made ineligible → CANCELLED REQUESTER_INELIGIBLE, nothing applied. `approve()` re-checks under `lock_governance` plus `s.refresh(req)` (`:504-518`) and `execute()` re-checks the requester (`:464`), in one transaction. | PASS |
| 10 | Stale approval fails closed | R04; author's stale test re-run | Address reissued to an invitee → FAILED DUPLICATE with `FOUNDER_ACTION_FAILED {reason: DUPLICATE}`; F3 stays deleted. Another live user's *proposed* address equal to F3's → FAILED DUPLICATE. Expired request → 409. | PASS |
| 11 | Concurrency | R05, R06, R07 (4, 3 and 1 iterations per engine) | Concurrent requests → [202, 409 REQUEST_ALREADY_OPEN]. Concurrent approvals → [200 EXECUTED, 409]; exactly one FOUNDER_TRANSITION. Restore approval vs invitation of the same address: SQLite 3× restore wins (invite 409 DUPLICATE) and 1× invite wins (restore FAILED); PostgreSQL 4× invite wins (restore FAILED). Always exactly one live holder of the address and no 5xx. Restore vs the requester's own step-down: SQLite serialises restore first (both EXECUTED, which is valid); PostgreSQL serialises step-down first, so the restore is CANCELLED REQUESTER_INELIGIBLE. | PASS |
| 12 | Invariants I1–I3, including the nightly job | R01, R04, R08 | `guards.evaluate` and `maintenance.check_invariants()` give i1, i2, i3 = true with no problems, both while deleted and after restore. I3 counts only live accounts (`guards.py:176-192`); a restored account keeps its FOUNDER role and protection level, so it stays consistent. | PASS |
| 13 | Audit actor | R01 | The audit row `RESTORE` on `app_user` is performed_by **F2** (the approver) via API. DELETE was also F2. The request row shows requested_by F1 and approver F2. | PASS |
| 14 | Security events complete and redacted | R09 (both engines) | BYPASS_BLOCKED (F1) → FOUNDER_ACTION_REQUESTED (F1, IN_APP) → SENSITIVE_ACTION request (F1) → FOUNDER_ACTION_APPROVED (F2) → SENSITIVE_ACTION approve (F2) → **FOUNDER_TRANSITION {action: RESTORE}** (F2) → FOUNDER_ACTION_EXECUTED (F2). No event detail contains the unmasked address. Gap: the REQUESTED, EXECUTED and FAILED details do not name RESTORE (FC-RBAC-5, advisory). | PASS |
| 15 | Break-glass cannot bypass | R02, R03, author tests re-run | Single-Founder in-app channel → 409 SECOND_FOUNDER_REQUIRED. Custodian CLI (`--payload '{"status":"RESTORE"}'`) → **rc 2 "unknown target"**, because the CLI loads targets without `include_deleted` (`cli/main.py:290`); no row is created. The governance-level call → SECOND_FOUNDER_REQUIRED. Execution also refuses channel BREAK_GLASS. Custodians cannot restore in any mode (FC-RBAC-4 covers the wording and missing event). | PASS |
| 16 | Email and account reuse | R04, R08 | An invite to a deleted Founder's address → 201: a new STANDARD INVITED account, with no Founder power inherited. Restore then FAILS DUPLICATE until the address is free. A pending FOUNDER_EMAIL_CHANGE proposal is cleared at deletion; its verify link → 400 before and after restore, and no live tokens remain. A deleted ex-Founder (REVOKE, then generic delete) is STANDARD and may be restored by a single actor, which is correct: not a Founder. RESTORE of a deleted STANDARD user via founder-actions → 409 "not a Founder". | PASS |
| 17 | AM-12 status | Document | "PROPOSED, NOT APPROVED"; no approval is claimed | PASS |

Other observations:
- A restored and reactivated Founder signs in with the **pre-deletion password and MFA factor**: login gives MFA_REQUIRED and the factor is ACTIVE (FC-RBAC-6, advisory).
- There are 4 active Founders after the R01 flow, as expected.

**RR-02 RESOLVED.**

#### C.2 RR-03

###### How the fix works (source)

- **Governance class** (`governance.py:108-112`):
  - FOUNDER_GOVERNANCE if `protection_level == FOUNDER`;
  - otherwise DUAL_CONTROL if the user holds any sensitive permission, suspended ones included;
  - otherwise STANDARD_CONTROL.
- **Proposal authorising class** (`:114-135`) is looked up from an EXECUTED EMAIL_CHANGE or FOUNDER_EMAIL_CHANGE request with the same requester and `executed_on == proposed_email_requested_on`.
  - Both timestamps come from the same unit's `tx_time`. X09 confirms they match on both engines through the scheduler break-glass path.
  - A self-requested proposal has no authorising class and always stands.
- **Withdrawal on escalation** (`:142-160`) runs inside the escalating transaction. It is called from:
  - GRANT_FOUNDER (`:404-414`; the in-app and custodian paths share `_execute_founder`);
  - `set_roles` (`users.py:412`);
  - `add_permission` (`:493`);
  - `remove_permission` (`:543`).
- **Verification** (`auth/service.py:940-972`) takes the governance lock *before* consuming the token, then refuses when the account is DISABLED or the proposal's class is weaker than the current class. The refusal is recorded with deferred events.
- **STANDARD approvals** execute atomically inside `approve()`, under the lock plus refresh, and re-check G11 and G9 (`standard_still_permitted`). Founder-class approvals re-validate against the current target (`_execute_founder` → `_validate_founder_action`).

###### Revalidation across flows

"Req. before" means the target's class when the work was requested or approved; "Class after" is the class it reaches before the work completes.

| Flow | Req. before | Class after | Completion under old approval | Evidence | Engines |
|---|---|---|---|---|---|
| Email change, STANDARD request executed, pending verify (N17) | DUAL | FOUNDER (in-app GRANT) | Proposal cleared in the promotion transaction. `EMAIL_CHANGE_CANCELLED {masked, TARGET_BECAME_FOUNDER, DUAL_CONTROL->FOUNDER_GOVERNANCE}`. No mail to the attacker; Founder email unchanged. | N17, author test re-run | SQ + PG |
| Same, promoted by custodian break-glass | DUAL | FOUNDER | Cleared, same event; attacker verify → 400 | X01 | SQ + PG |
| Same, promotion done out of band (no cleanup) | DUAL | FOUNDER | Verify → 400 EMAIL_TOKEN_INVALID; `EMAIL_CHANGE_VERIFIED FAILURE {GOVERNANCE_CLASS_CHANGED}` and BYPASS_BLOCKED | Author test re-run | SQ + PG |
| Direct admin email change on a STANDARD user, then role assignment | STANDARD | DUAL | Cleared (TARGET_BECAME_PRIVILEGED, STANDARD_CONTROL->DUAL_CONTROL); verify 400 | Author test, X03 variant | SQ + PG |
| Same, escalated by **removing a DENY** | STANDARD | DUAL | Cleared; verify 400 | X03 | SQ + PG |
| Same, escalated by a **role-definition** change (PUT /roles/{id}/permissions) | STANDARD | DUAL | **Not withdrawn** (no event; the proposal stays pending and blocks the address). Verify → 400 while DUAL. After the role is reverted, the verify link → **204**. | X02 → FC-RBAC-1 | SQ + PG |
| FOUNDER_EMAIL_CHANGE executed, target later REVOKEd | FOUNDER | STANDARD | Completes (204); stronger authorisation, correct | X06 | SQ + PG |
| Single-Founder break-glass FOUNDER_EMAIL_CHANGE run by the scheduler job | FOUNDER | FOUNDER | EXECUTED; verify 204 (no false fail-closed) | X09 | SQ + PG |
| Verify after the account is DISABLED | STANDARD | DISABLED | The disable clears the proposal; verify 400 | X07 | SQ + PG |
| MFA reset, STANDARD request pending (N01) | DUAL | FOUNDER | CANCELLED TARGET_BECAME_FOUNDER; later approve → 409; factor still ACTIVE; new request → 403 FOUNDER_PROTECTED | N01, author test | SQ + PG |
| MFA reset, promotion out of band | DUAL | FOUNDER | Approve → 403 APPROVER_NOT_ELIGIBLE (G9); nothing applied | N02 | SQ + PG |
| MFA reset request, custodian promotion | DUAL | FOUNDER | CANCELLED TARGET_BECAME_FOUNDER | N03 | SQ + PG |
| MFA reset direct (STANDARD), then promotion | STANDARD | FOUNDER | The reset had already executed; its MFA_ENROLLMENT link to the owner's mailbox survives (30 min) | X08 → FC-RBAC-3 (advisory) | SQ |
| Admin-sent password-reset link, then promotion | STANDARD | FOUNDER | Link survives; the new Founder resets their own password (204) | X05 → FC-RBAC-3 (advisory) | SQ + PG |
| Account status (Founder request recalculated) | FOUNDER | STANDARD | FAILED INVALID_STATE | Author test re-run | SQ + PG |
| Founder governance: approved GRANT_FOUNDER break-glass, target disabled after approval | STANDARD | DISABLED | FAILED INVALID_STATE (execution re-validates) | Author test re-run | SQ + PG |
| Invitation: invited as SALES (72 h link), then set_roles ADMIN while INVITED | STANDARD | DUAL | **Accepted after 30 h** (MFA enrollment required); a direct ADMIN invite expired at 24 h | X04 → FC-RBAC-2 | SQ + PG |
| Invitation, then GRANT_FOUNDER while INVITED | — | — | 409 "Only active staff can become Founders" | X04 | SQ + PG |
| Recovery (stale approver, cooling-off requester) | — | — | 403 / CANCELLED REQUESTER_INELIGIBLE | N15 | SQ + PG |
| Withdrawn or superseded request | — | — | A cancelled request cannot be approved (409) or cancelled (409). One open Founder-class request per target (409). | N01, P09, R01 | SQ + PG |

**Transaction placement (code):**
- `approve()` and `deny()`: `lock_governance` plus `s.refresh(req)`, then execute in the same unit.
- `verify_email_change`: lock first, fresh `s.get`.
- `set_roles`, `add_permission` and `remove_permission`: the lock is taken inside `InvariantGuard`, before `before = governance_class(...)`. The `target` ORM object was loaded before the lock. On PostgreSQL this is covered by the `app_user` version column (`kernel/base.py:118-121`): the losing writer gets **409 VERSION_CONFLICT** (X10, X11, X13), and verification re-checks anyway.

**Concurrency** (threads with a barrier; all 2xx/4xx; no 5xx, deadlock or StaleDataError in RR-03 paths):

| Race | SQLite | PostgreSQL | Safe? |
|---|---|---|---|
| GRANT_FOUNDER approval vs STANDARD email-change approval (N14) | Both EXECUTED; proposal cleared | Both EXECUTED; proposal cleared | Yes |
| Verify vs GRANT_FOUNDER (X12, 5×) | 4× verify first (204, then promotion); 1× promotion first (verify 400) | 5× verify first | Yes (linearisable) |
| Verify vs set_roles ADMIN (X11, 6×) | 1× roles first (verify 400); 5× verify first | 1× roles first; 5× verify first, set_roles 409 VERSION_CONFLICT | Yes |
| set_roles ADMIN vs direct email change (X10, 6×) | 6× roles first → proposal cleared | 6× email change first → set_roles 409 VERSION_CONFLICT (target stays STANDARD; later verify 204 is legitimate) | Yes |
| Direct MFA reset vs set_roles ADMIN (X13, 5×) | Serialised (1× 409 VERSION_CONFLICT) | 5× reset first, set_roles 409 | Yes |
| Author `test_RR03_concurrent_promotion_and_verification` | pass | pass | Yes |

**Audit and security-event trail:** `APPROVAL_REQUESTED` → `EMAIL_CHANGE_REQUESTED {masked, administrator}` → `FOUNDER_TRANSITION GRANT` / `SENSITIVE_ACTION set_roles` → `APPROVAL_CANCELLED {TARGET_BECAME_FOUNDER}` / `EMAIL_CHANGE_CANCELLED {masked, reason, "A->B"}` → on a late verify, `EMAIL_CHANGE_VERIFIED FAILURE {GOVERNANCE_CLASS_CHANGED}` plus `FOUNDER_GOVERNANCE_BYPASS_BLOCKED`. The audit rows of cancelled requests carry CREATE and UPDATE(status, status_reason, decided_on) (N01). The masked address is `b***@evil.test`.

**AM-13 status:** "PROPOSED, NOT APPROVED".

**RR-03 RESOLVED.** The reproduced exploit (N17) and its break-glass, out-of-band, DENY-removal and concurrent variants are closed on both engines. Verification is the fail-closed backstop, run under the governance lock. The residuals (FC-RBAC-1, FC-RBAC-2) never let a weaker authorisation complete against a *Founder*, and they do not reopen N17.

#### C.3 Regression

| Suite | SQLite | PostgreSQL |
|---|---|---|
| `test_rbac.py` | 33 passed | 33 passed |
| `test_founder_governance.py` | 16 passed | 16 passed |
| `test_governance_remediation.py` | 11 passed | 11 passed |
| `test_final_merge_blockers.py` (RR-02 ×9, RR-03 ×9, RR-08 ×4) | 22 passed | 22 passed |
| Reviewer P01–P17 (`test_probe_rbac.py`, 22 tests, 154 records) | 22 passed | 22 passed |
| Reviewer N01–N17 (`test_probe2_new.py`) | 17 passed | 17 passed |
| New R01–R09 and X01–X13 (`test_probe3_final.py`, 22 tests) | 22 passed | 22 passed |

Differences from the previous run (probes2):
- **Fixed:** P11/N11 (403, F3 stays deleted), N17 (no verification mail; email unchanged), N14 (proposal cleared).
- **Unchanged:** every other P and N outcome.
  - P04 IR-A06: an ADMIN can still PATCH its own ADMIN role `mfa_required=false` → 200.
  - N06: `NoCredentialsError` is still uncaught (RR-09, production scope).
  - N10: PostgreSQL still raises `StaleDataError` (RR-RBAC-A2, advisory).
  - Race winners in N12 and N13 vary by timing; the invariants hold.

RBAC basics at the target:

| Check | Outcome |
|---|---|
| Default deny | SALES on `/users`, `/security-events`, `/audit-logs` → 403 |
| DENY over GRANT | P08: DENY `lead.read` → 403 on `/leads` with the same token |
| IDOR | P06, P07: 404 or 403, lead list count 0; ADMIN GET of a Founder-class approval → 404 |
| Mass assignment | P05: 12/12 → 422 |
| Founder-power isolation | P02, P03: 5 BYPASS events, I3 holds; role copy, custom role with `user.founder.manage`, and permission metadata changes are all refused |

**No new authz/governance defect ≥ MAJOR.**

### Appendix D — Audit archiving

#### D.1 Protocol

`maintenance.archive_security_events` (lines 548-637) runs in this order:

1. `_finalise_committed_archives` repairs earlier runs. For each *pending* manifest whose rows are gone **and** that is announced online, it writes the matching *archive* manifest.
2. `through` is computed from the *archive* manifests.
3. A write unit of work opens. On SQLite this is `BEGIN IMMEDIATE`.
4. It selects the contiguous prefix of rows that are older than the cutoff, and checks that the prefix continues from `through`.
5. It verifies the segment's chain.
6. It writes the local file, then `put_blob(export, last_seq)`, then `put(pending, last_seq)`.
7. It records `SECURITY_LOG_ARCHIVED{through_seq, anchor=sha[:16]}`.
8. It drops the immutability guard, deletes the range, asserts the row count, restores the guard and commits.
9. After the commit, it writes `put(archive, last_seq)`.

`verify_chain` (lines 414-487) does the following:

- It reads only `store.latest("anchor")` (line 426).
- It checks each archive manifest (lines 364-411) for:
  - contiguity from sequence 1;
  - a matching export (SHA-256, count and range);
  - an HMAC chain across the export that carries over between segments;
  - the latest anchor matching, when that anchor falls inside the archived range;
  - an announcement, either in an online event or inside an exported row.
- A pending manifest whose rows are gone is reported as `archive not finalised`.
- Any store exception is reported as `anchor store unavailable`, with a CRITICAL log line and a `SECURITY_LOG_CHAIN_BROKEN` event.
- `ChainVerificationFailed` is emitted on every run.

**Write-once semantics:**

- `LocalAnchorStore` (lines 39-56) refuses an overwrite with different content **only inside the application**. The host user can `rm` or overwrite any file. No OS immutability (such as `chflags`/`chattr`) is used.
- `S3AnchorStore.put`/`put_blob` (lines 85-103) calls `put_object` **without `IfNoneMatch`**. `get_object`/`_get` (lines 105-125) reads the **current version**. Object Lock protects existing *versions*, but a PutObject to an existing key adds a new current version.
- The test `FakeS3` (in `test_chain_integrity.py`) overwrites silently, so no author test exercises write-once behaviour on the S3 path.

#### D.2 Failure injection

All rows behaved **identically on SQLite and PostgreSQL** except F6, where the two engines serialise differently.

| # | Injection | Expected | Observed on SQLite | Observed on PostgreSQL | Verdict |
|---|---|---|---|---|---|
| F1 | Export and pending staged, then `Session.commit` raises | Rows stay online; verify ok (no false alarm); retry succeeds | Raised `OperationalError`. 2/2 rows online. Store held pending (1,2) and no archive. Verify ok=True. The retry (segment now 1..4) archived 4 rows and verify was ok. The abandoned pending (1,2) was ignored | Same | PASS (REPRODUCED) |
| F2 | DB commit succeeds; the final `archive` put fails | Durable alarmed state; the next run repairs it; no alarm afterwards | Verify ok=False with `archive not finalised`. The next run returned `recovered=1`. Verify ok=True (after an intervening anchor) | Same | PASS |
| F3 | The `pending` put fails, after the export blob is written | Rows online; an orphan export is harmless; retry ok | Orphan `000000000002.jsonl` left behind. Verify ok. The retry re-wrote the identical blob and verify was ok | Same | PASS |
| F3b | Abandoned attempt for 1..L, then retention lengthened (archive 1..M, M<L), then the next segment M+1..L | Should archive | `RuntimeError: anchor object 000000000004.jsonl already exists`, because the export key is `last_seq` only. Alarmed (`SecurityLogArchiveFailed`). No data loss. Verify stays ok. It clears only when a later segment ends at a different sequence | Same | FC-AUD-4 (MINOR) |
| F4a | `os._exit(9)` in a real subprocess after the export put | Rows online; verify ok; retry ok | Child exited 9. 2/2 rows online. Verify ok. Retry archived 2 and verify was ok | Same | PASS |
| F4b | `os._exit` after the pending put | Same as F4a | Same as F4a | Same | PASS |
| F4c | `os._exit` after delete, before commit | Rolled back; verify ok | 2/2 rows online; verify ok; retry ok | Same | PASS |
| F4d | `os._exit` after commit, before the final put | `archive not finalised` alarm, then repaired | Rows 2 → 1. Verify ok=False with `archive not finalised`. Retry returned `recovered=1` and verify was ok | Same | PASS |
| F5 | Retry after partial state (covered by F1/F3/F4 retries, and a larger segment in F1) | Idempotent; no stranded state | Identical objects are re-accepted. A new segment gets a new key. No false alarm after recovery | Same | PASS |
| F6 | Two concurrent archiver **processes** (2 s delay inside the transaction) | One archives; the other does nothing or fails safely; one announcement | `BEGIN IMMEDIATE` serialises them: one archived 3 rows, the other archived 0. One `SECURITY_LOG_ARCHIVED`. Verify ok | Both selected 1..3. The loser blocked on the chain advisory lock, then failed with `archival deleted 0 rows but exported 3` and rolled back. One announcement; verify ok | PASS. On PostgreSQL there is one false `SecurityLogArchiveFailed`/`MaintenanceJobFailed` alarm (advisory) |
| F7a | Archived row modified in the export file (host overwrite) | Detected | `archive export hash mismatch` | Same | PASS |
| F7b | Archived row deleted from the export | Detected | `archive export hash mismatch` | Same | PASS |
| F7c | F7b plus the manifest SHA and count rewritten (no chain key) | Detected | `archive export count mismatch` | Same | PASS |
| F7d | Online middle row deleted, plus manifest 1 removed | Detected | `archive manifests not contiguous` | Same | PASS |
| F8 | Middle archive manifest removed | Detected and persists (not auto-repaired) | `archive manifests not contiguous`. It persists after the next archival run | Same | PASS |
| F9a | Last archive manifest removed, pending kept | Alarm, then repair from the faithful pending | `archive not finalised`, then `recovered=1` and ok | Same | PASS |
| F9b | Last archive manifest **and** pending removed | Detected | `prefix removed` | Same | PASS |
| F9c | A middle export blob removed | Detected | `archive export missing` | Same | PASS |
| C11 | Prior attack: forged manifest (dummy SHA, no export) plus prefix delete through the anchor | Detected | `archive export missing`, ok=False (it was ok=True at 2f6b59a) | Same | PASS: the RR-05 finding as written is fixed |
| C11b | Host exports rows 1..2 **genuinely**, writes a manifest, self-announces through the app, then deletes | Nothing is hidden, so ok is acceptable | ok=True | Same | Informational: early archival without data loss |
| C12 | Prior attack: failure after the pending manifest, before commit | No false alarm; no wedge | ok=True; retry archived 2; ok=True (it was a false `prefix removed` at 2f6b59a) | Same | PASS |
| C13 | Anchor store unavailable during verify | Fail closed and recorded | ok=False, `anchor store unavailable`. Two CRITICAL lines, `ChainVerificationFailed=1`, a `SECURITY_LOG_CHAIN_BROKEN` event | Same | PASS |
| T1 | Host attacker with the chain key and the anchor-writer credential edits row 2, recomputes rows 2..head, then runs the app's `anchor_chain()` (local store) | Detected, because the earlier anchor at 3 is contradicted | Before re-anchoring: `anchor mismatch at 3`. **After the new anchor at 7: ok=True** | Same | **FC-AUD-1 REPRODUCED** |
| T1b | Same as T1 through `S3AnchorStore` on a versioned Object Lock model, with an archive and 2 anchors | Detected | Before: `anchor mismatch at 7`. **After the attacker's anchor at 9: ok=True** | Same | **FC-AUD-1 REPRODUCED** (SIMULATED store) |
| T2 | `S3AnchorStore.put` over an existing archive key with a different body | Refused, as the local store does | **Accepted** (2 versions). Verification reads the new one | Same | **FC-AUD-3** (SIMULATED; S3 semantics SOURCE-INSPECTED) |
| T3 | Local store: host `rm` of the anchor file, then truncation of the tail below the anchor | Local store cannot resist | ok=True (undetected) | Same | Expected: local store has no host resistance |

Probe runs: SQLite 19/19 and PostgreSQL 19/19 completed. Behavioural expectations are asserted for F1-F9 and C11-C13. T1, T1b, T2 and T3 print `REPRODUCED` rather than asserting.

#### D.3 CLI metrics

| Command | rc | EMF metrics on stdout | CRITICAL lines |
|---|---|---|---|
| `maintenance anchor-chain` (success) | 0 | `MaintenanceJobFailed=0[anchor-chain]` | 0 |
| `maintenance anchor-chain`, store not writable | 1 | `ChainAnchorFailed=1`, `MaintenanceJobFailed=1[anchor-chain]` | 2 |
| `maintenance verify-chain` | 0 | `ChainVerificationFailed=0`, `MaintenanceJobFailed=0` | 0 |
| `maintenance verify-chain`, corrupt anchor object (store error) | **3** | `ChainVerificationFailed=1`, `MaintenanceJobFailed=1`, plus `security_log_anchor_store_unavailable` and `security_log_chain_broken` events | 2 |
| `maintenance invariants` (empty DB, 2 problems) | 0 | `GovernanceInvariantFailures=2.0`, **`NoEffectiveRecoveryAdmin="[REDACTED]"`**, `MaintenanceJobFailed=0` | 1 |
| `maintenance snapshot` | 0 | `SnapshotCompleted=1`, `SnapshotBytes`, `MaintenanceJobFailed=0` | 0 |
| `maintenance restore-verify` | 0 | `RestoreVerified=1`, `MaintenanceJobFailed=0` | 0 |
| `maintenance disk-usage` | 0 | `DiskUsed=85.6`, `MaintenanceJobFailed=0` | 0 |
| `maintenance archive-security-events` (no retention configured) | 1 | `MaintenanceJobFailed=1` | 1 |
| `maintenance purge` | 0 | `MaintenanceJobFailed=0` | 0 |
| `worker` (long-running, 8 s, one DEAD event) | 0 (SIGTERM) | `OutboxDead=1.0`, `OutboxDepth`, `OutboxOldestAge`, plus an `outbox_dead_events` error line | 0 |
| `worker --once` | 0 | none (outbox metrics are emitted only by `run_forever`) | 0 |
| `scheduler`, one real cycle (13 jobs, verify-chain made to fail) | killed | `ScheduledJobFailed=0` for 12 jobs; **`ScheduledJobFailed=1[verify-chain]`** plus `scheduled_job_failed job=verify-chain exit_code=3` (ERROR) | as for the child jobs |

The `NoEffectiveRecoveryAdmin` value is redacted because `kernel/logging.py:22` lists `"recovery"` in `DENYLIST`, and `_scrub` (lines 37-38) replaces the value of any key containing it. The resulting EMF document carries a non-numeric metric value. The same thing happens in the scheduler output. See FC-AUD-2.

#### D.4 Regression

The following files were run: `test_audit_security`, `test_chain_integrity`, `test_archive_ordering`, `test_leads`, `test_leads_remediation`, `test_consent_dev004` and `test_final_merge_blockers`.

| Engine | Tests | Failed | Errors | Skipped |
|---|---|---|---|---|
| SQLite | 135 | 0 | 0 | 0 |
| PostgreSQL | 135 | 0 | 0 | 2 (SQLite-only snapshot and disk-usage cases) |

Security-event chain, audit actor attribution, notification failure isolation, duplicate lead handling and consent history show no regression. The probe suite passed 19/19 on each engine.

### Appendix E — Operations and tooling

#### E.1 RR-16 ratchet cases

Baseline at the target: 157 errors in 24 files; `CEILING = 157`, so there is no slack. Exit codes: 0 = OK, 1 = ratchet FAIL, 2 = check not performed (fail-closed).

| # | Case | Exit | Result |
|---|---|---|---|
| c00 | Unmodified target | 0 | `157 errors (baseline 157); OK` |
| c01 | mypy absent (venv without mypy) | **2** | "mypy produced no summary … No module named mypy" |
| c02 | mypy cannot execute (corrupt `mypy/__main__.py` raising) | **2** | no summary |
| c03 | Invalid TOML in `[tool.mypy]` | **2** | "mypy exited 2 (crash or configuration error)" |
| c03b | `python_version = "banana"` | 0 | mypy ignores the value and still runs a full check (157 errors); harmless |
| c03c | Unknown mypy option | 0 | same as c03b; harmless |
| c04 | Malformed baseline JSON | **2** | "baseline … is unreadable" |
| c05 | Baseline count raised (+1) | **2** | "baseline total 158 exceeds the reviewed ceiling 157" |
| c05b | Baseline entry added for a clean file | **2** | refused (ceiling / entry checks) |
| c05c | Debt moved between files, same total | 1 | the real per-file count exceeds the new entry |
| c05d | Zero count in baseline | **2** | "must be a positive integer" |
| c06 | New file with an error | **1** | "— new file" |
| c06b | Extra error in a baselined file | **1** | 2 > 1 |
| c07 / r1 | File renamed, baseline unchanged | **2** | "baseline entry … does not exist (renamed files start at zero)" |
| r3 | Renamed file, old key removed | **1** | the renamed file starts at zero |
| r3u | `--update` after a rename | **1** | "refusing to admit veda/kernel/seqs.py" |
| r2 | Renamed file **and** baseline key moved by hand | 0 | Allowed. It is a visible two-line diff in `mypy-baseline.json`, the total is unchanged, and it cannot exceed CEILING, so it cannot launder debt. Acceptable. |
| c07c | Copy of a file that has an error | **1** | new file |
| c08a / a3 | Bare `# type: ignore` / `#type:ignore` | **1** | broad suppression |
| c08a2 | Coded `# type: ignore[assignment]` | 0 | allowed by design; `warn_unused_ignores` is on |
| c08b | `ignore_errors = true` (global) | **1** | detected |
| c08c | Per-module `ignore_errors` override | **1** | detected |
| c08d | `disable_error_code` in pyproject | **1** | detected |
| c08e / h4 | Inline `# mypy: ignore-errors` / `ignore-errors=True` | **1** | detected |
| **c08f / h2** | Inline `# mypy: disable-error-code="union-attr"` (+ a new error in the same file) | **0** | **Not detected**: 157 → 107/95 errors, reported OK. The new `return-value` error is admitted against service.py's unused headroom (62). |
| **h3** | Inline `# mypy: strict-optional=False` | **0** | **Not detected** (157 → 95) |
| **h5** | Inline `# mypy: ignore_errors` (underscore spelling) | **0** | **Not detected** (156, OK); the regex matches only `ignore-errors` |
| **c08h / h1** | pyproject override `strict_optional = false` for one module, plus a new error there | **0** | **Not detected**: 96 errors, OK. Debt swapped silently. |
| c08g | Global `strict_optional = false` | 1 | Fails only by accident: new errors appear in other files |
| c08i | `follow_imports = "skip"` for `veda.*` | 0 | No effect (files are listed explicitly; still 157) |
| **c08j / c08m** | Shadow `mypy.ini` / `.mypy.ini` with `ignore_errors = True` (mypy reads it before pyproject) | **0** | **Not detected**: `0 errors (baseline 157); OK`. The ratchet inspects only pyproject.toml. |
| c08l | `setup.cfg` `[mypy]` | 0 | pyproject wins; no effect (157) |
| c09 | `--update` with `CI=true` | **2** | "--update never runs in CI" |
| c09b | `--update` with only `GITHUB_ACTIONS=true` | 0 | Runs. This is theoretical: Actions always sets `CI=true`, and nothing in CI commits the result. |
| c09c | `--update` locally with a new error | **1** | refuses and writes nothing |
| c09d | `--update` locally, no change | 0 | rewrites an identical file and prints the diff lines; CEILING must be lowered by hand in code |
| c10 | `exclude` one file | **2** | "mypy checked 87 source files; the package has 88" |
| c10c | `files = ["veda/kernel"]` | **2** | checked 24 < 88 |
| c10b | `exclude` handlers.py + `files += migrations` | 0 | Still 157 (the excluded module is followed through imports); no effect |
| **x1** | `exclude` auth/service.py + `files += migrations` (pads the count) + override `follow_imports = "skip"` for that module | **0** | **Not detected**: 95 errors, OK. The checked-count guard is satisfied by the padding. |
| **c02b** | Local `api/mypy/__main__.py` printing a fake success summary (shadows the real mypy under `python -m`) | **0** | **Spoofed**: `0 errors; OK` |

Confirmations:

- Update mode is explicit (`--update`) and is refused under `CI`.
- `--update` never raises a count or admits a file. It prints `file: old -> new` lines.
- Manual baseline growth is capped by CEILING = 157, which equals the current total.
- Baseline edits appear as a JSON diff.
- "Debt cannot silently increase" holds **only** for the mechanisms the tool inspects. The bold rows above show that inline config comments, per-module `strict_optional`, a shadow `mypy.ini`, or exclude with padding and `follow_imports=skip` hide errors. New errors can then be added under the freed per-file headroom with exit 0. Each bypass needs a visible change to source or config, so this is a gap in the gate, not a way to bypass it silently through the baseline (FC-OPS-1).

#### E.2 RR-17 checklist

| # | Item | Result | Evidence | Mode |
|---|---|---|---|---|
| 1 | Rollback to 9236aa3 prohibited | YES. The runbook states it, the tooling refuses it, and AM-6/AM-11 agree. | `docs/operations/api-runbooks.md:36-38`, `:90-91`; `api/deploy/deploy.sh:7-10,13,58-61`; merge-safety plan §5 | REPRODUCED |
| 2 | deploy.sh enforces a floor | **Partly.** `ROLLBACK_FLOOR="0009_mfa_challenge_binding"` is hard-coded (line 13); `ROLLBACK_FLOOR=0001_kernel ./deploy.sh …` is still refused (D4), and there is no flag or env bypass. The check runs `schema-status --require-known` inside the **target** image (exit 4 if the floor is unknown). D1 `--rollback 9236aa3` → EXIT 1, refused. D2 `--rollback 2f6b59a` → EXIT 1, refused. Both refusals happen because those images **lack the `schema-status` subcommand** (argparse exit 2), not because of a revision comparison. For 2f6b59a, which does know 0009, the "predates rollback floor" message is inaccurate. D3 `--rollback 6ec2e76` → EXIT 0 with readiness `head`. **The floor applies only in `--rollback` mode.** D5 `./deploy.sh 9236aa3` fails at `migrate` (alembic "Can't locate revision 0009"; EXIT 1; worker and scheduler left stopped; the API untouched): fail-closed, but by accident. **D6 `./deploy.sh 2f6b59a` → EXIT 0, readiness 200 `head`: the image is deployed.** 2f6b59a lacks the RR-02 and RR-03 MAJOR fixes (code-only; `git diff --stat 2f6b59a 6ec2e76 -- api/veda`: rbac/users.py, governance.py, auth/service.py …). | deploy.sh:16,52-70; `probes3/ops/deploy_results.txt` | REPRODUCED (docker stubbed via a PATH shim; the CLI and readiness ran from each image's source tree) |
| 3 | Readiness after rollback | YES. `ready "$EXPECTED"` runs inside the container. States verified: behind → 503; ahead_undeclared → 503; ahead with the revision declared → 200 `ahead`; head → 200. The bridge peer sees `{status}` only. | deploy.sh:21-40,71-79; health.py:55-62 | REPRODUCED |
| 4 | DB compatibility checked | YES in `--rollback` mode: floor known, `state ∈ {head, ahead (declared value matched in /etc/veda/api.env)}`, otherwise refused. Precondition "expand-only since target" is a policy check on release notes. | deploy.sh:58-69; runbook §2.3 | SOURCE-INSPECTED (the ahead path depends on the /etc path, which was not writable here) |
| 5 | Forward-fix conditions | Documented | runbook §2.2 | SOURCE-INSPECTED |
| 6 | Restore requirements | Documented (restore point, SHA-256, restore-verify, swap, lost window). The RR-15 gaps are cross-referenced. | runbook §3 | SOURCE-INSPECTED |
| 7 | Maintenance mode | Documented: not needed for a normal rollback (§2.3.1); stop api/worker/scheduler with the WhatsApp fallback for a restore (§3.1) | runbook | SOURCE-INSPECTED |
| 8 | No unperformed rehearsal claimed | YES. The only hits for 'rehears', 'verified' or 'tested' are "none has been rehearsed" (l.4), "not been rehearsed (RG-7 open)" (l.86), "not rehearsed (RG-1, RG-2, RG-7 open)" (l.119) and "not been verified against real S3" (l.140). | grep | REPRODUCED |
| 9 | Rehearsals remain gates | RG-1, RG-2 and RG-7 are Pending in the registry and in `gate-registry.json`. RR-17 production impact is "Blocks until RG-7". | P0-open-issues.json | REPRODUCED |
| 10 | Operators cannot select an unsafe commit by accident | **No for 2f6b59a via the normal path** (D6). The runbook names only 9236aa3. AM-11:21 says "An N-1 image is acceptable only if it knows 0009", which 2f6b59a satisfies. That contradicts runbook §2.1 ("no valid N-1 image for this release") and AM-12/AM-13 ("Remove the checks: RR-0x returns"). Likelihood is low: 2f6b59a was never released, and deployment tooling and images do not exist yet. | FC-OPS-2 | REPRODUCED |

#### E.3 Registry audit

- 162 items, no duplicates. Complete sets:
  - IR-01…39 and IR-A01…A25: all 64 originals;
  - RR-01…18 and RR-A01…A25;
  - AM-1…13, DEV-001…010, OWNER-INPUT-001…004.
- Every JSON id appears in the `.md`.
- **All 27 gates match `docs/architecture/gate-registry.json`** (same status stem, with the suffix "not executed or recorded in this workstream"). TG-01 and TG-08 are `PENDING`; all RG and PG gates are Pending or Blocked; PGM-1 is N/A. **No production gate is closed.**
- RR-16 is "RESOLVED" (agreed). RR-17 is "RESOLVED IN CODE AND DOCUMENTATION — RG-7 REHEARSAL REQUIRED; production: Blocks until RG-7" (agreed; FC-OPS-2 should be added as a residual).
- Owner-decision claims: OD-1…OD-5 are presented as owner decisions "given" through the remediation brief. The re-review defines OD-2 and OD-3 as decisions; the matrix states that no amendment is approved and that OD-4 is unchanged. No claim of owner **approval** of an amendment, of TG-01/TG-08, or of the merge was found. Whether OD-2 and OD-3 were actually decided cannot be verified from the repository: no decision-log entry is cited. ADVISORY.
- Merge-safety plan (`P0-merge-safety-plan.md`):
  - It correctly states that Pages publishes `dist/` from `main` within about a minute with no gate, and that merging is a production site release.
  - Its list of 6 changed `dist/` files matches `git diff --stat 778aa8f HEAD -- dist`.
  - Intake metas are empty (verified: `dist/index.html:11-12`).
  - Options A–D are laid out; none is executed; each needs owner approval.
  - Minor inconsistency: §2.6 says only that TG-01 and TG-08 "remain PENDING" and that a merge "does not complete or imply" them. The registry marks TG-01 as "Blocks merge", and the matrix (OD-1, OD-4) says owner approval of the amendments is required for merge. The plan's "What must hold before any merge" list omits both preconditions. ADVISORY (FC-OPS-3).

#### E.4 Tooling

| Tool | Exit | Output |
|---|---|---|
| `ruff check veda tests migrations tools` (0.16.9) | 0 | All checks passed |
| `ruff format --check …` | 0 | 141 files already formatted |
| `python tools/mypy_ratchet.py` | 0 | 157/157 OK |
| `python tools/openapi_check.py` | 0 | matches snapshot |
| `api/tools/secret_scan.sh` (repo root) | 0 | no new candidates |
| `bandit -q -r veda -ll -ii` (1.9.4) | 0 | no findings |
| `pip-audit -r requirements.txt --require-hashes --disable-pip --strict` (2.10.1) | 0 | No known vulnerabilities |
| `python -m veda.cli deploy-check` | 0 | OK |
| `pytest tests/unit/test_mypy_ratchet.py` | 0 | 17 passed |

#### E.5 Migrations

- `alembic heads`: one head, `0009_mfa_challenge_binding`. `alembic history`: **10 revisions**, linear: 0001 → … → 0008 → 0100_crm_leads → 0009.
- `git diff 2f6b59a 6ec2e76 -- api/migrations`: one docstring line in 0009 (`docs/architecture/amendments/AM-11` → `docs/proposals/amendments/AM-11`). **Docstring-only.** `models.py` and `render_migrations.py` are unchanged.
- Fresh SQLite `veda.cli migrate` from the 6ec2e76 and 2f6b59a trees: both exit 0 at `0009_mfa_challenge_binding`. `.schema` is identical (1240 lines), and the non-INSERT DDL in the full `.dump` is identical. Seed counts are equal (47 lookup values, 45 permissions, 3 roles, 3 system users); the data differs only in timestamps and generated ids.
- Embedded PostgreSQL **18.0.4** (`pixeltable_pgserver.get_server('$S/probes3/ops/pg18')`), fresh DBs: both migrate exit 0 at 0009. Columns (505), constraints (610), indexes (97), triggers (4) and functions (1) are **IDENTICAL** between 6ec2e76 and 2f6b59a. The server was stopped afterwards.

### Appendix F — Site and frontend

#### F.1 RR-01 12-item table

Server: `site-server.mjs <abs dist> 8201 --keep-uir`. It serves `dist/_headers` exactly, including `upgrade-insecure-requests`, and returns 404.html with HTTP 404 for unknown paths. `dist/_redirects` does not exist at 6ec2e76 (nor at 2f6b59a or 778aa8f). A second run on :8202 without UIR gave identical results. Raw output is in `out/fc-exact-rr01.json` and `out/fc-nouir-rr01.json`. The controls are 2f6b59a (`out/base2f6-rr01.json`), which still reproduces the defect, and 778aa8f (`out/base778-rr01.json`).

| # | Check | Result | Evidence | Label |
|---|---|---|---|---|
| 1 | 404 styling from an external asset | PASS. `dist/404.html:15` is `<link rel="stylesheet" href="/assets/404.css">`. `document.styleSheets` = [Google Fonts, `/assets/404.css`], with 0 `<style>` elements and 0 `[style]` attributes. Styles are unchanged from the old inline block except `--copper` (#ad6d54→#8f5640) and the footer colour (#7a736a→var(--muted)) | dist/404.html:15; dist/assets/404.css:1-30 | REPRODUCED |
| 2 | No `'unsafe-inline'` in CSP | PASS. `git diff 2f6b59a 6ec2e76 -- dist/_headers` is empty. There is no unsafe-inline, hash or nonce in any directive | dist/_headers:2 | REPRODUCED |
| 3 | No inline `<script>` in dist/*.html | PASS. The only script is `index.html:199 <script src="assets/app.js">`. 404.html has 0 scripts | grep plus DOM count | REPRODUCED |
| 4 | No inline `on*=` handlers in dist HTML | PASS. grep found 0, and a DOM attribute scan found 0 on all 404 variants and index | — | REPRODUCED |
| 5 | CSP still restrictive (diff vs 2f6b59a) | PASS. The CSP is byte-identical to 2f6b59a: `default-src 'self'`, `script-src 'self'` plus Turnstile and CF Insights, `style-src 'self'` plus Google Fonts, `object-src 'none'`, `frame-ancestors 'none'`, `base-uri 'self'`, `form-action 'self'`, UIR | dist/_headers:1-8 | REPRODUCED |
| 6 | Invalid routes return HTTP 404 | PASS under emulation. `/no-such-page`, `/privacy` and `/deep/nested/unknown/path?x=1` return 404 with the 404.html body. `/404.html` returns 200. Real Cloudflare behaviour is **inferred** from the Pages docs: with a top-level `404.html` and no `_redirects`, unknown paths are served `404.html` with status 404, and `_headers` `/*` rules apply. It was not exercised on a Pages preview | out/fc-exact-rr01.json `pages.*.status` | REPRODUCED (emulated) |
| 7 | 404 renders styled under production headers | PASS. body bg `rgb(251,247,239)`, body font Manrope, h1 "Cormorant Garamond" 89.6px, eyebrow `rgb(143,86,64)`, `main` grid `547px 448px`, 5 webfonts loaded. Screenshot `out/fc-exact-404_no_such_page.png`. The 2f6b59a control renders unstyled (Times, transparent bg, grid none, style-src-elem violation), which confirms the defect was real and is now fixed | screenshots | REPRODUCED |
| 8 | 0 CSP violations on index, 404, unknown paths and /privacy | PASS. `securitypolicyviolation` listener and console both show 0 on `/`, `/no-such-page`, `/404.html`, `/privacy` and the deep path, desktop and 360 px. 2f6b59a shows 1 per 404 page | out/fc-exact-rr01.json `csp`, `consoleCsp` | REPRODUCED |
| 9 | 404 at 360 px | PASS. `scrollWidth` 360 = `clientWidth` 360, `main` one column (320px), both action buttons 320px wide (full width). 2f6b59a control: scrollWidth 410 | out/fc-exact-404-360.png | REPRODUCED |
| 10 | Keyboard focus visible and usable on 404 links | PASS. Tab order: logo (aria-label "Veda Spaces home"), Back to Home, View Our Work, tel, WhatsApp, mailto, Send an enquiry. Each has `:focus-visible` with a 2px solid #c59158 outline and 4px offset. Enter on "Back to Home" navigates to `/`. Advisory: the ring colour contrasts at only 2.60:1 on paper and 2.21:1 on cream (FC-FE-1, identical in 778aa8f) | out/fc-exact-404-focus.png | REPRODUCED |
| 11 | axe (wcag2a/aa/21a/21aa/22aa) and contrast on 404, **without bypassCSP** | PASS. 0 violations and 0 incomplete. axe was injected with `page.evaluate` in a normal context (no bypassCSP). Manual contrast: eyebrow 5.50, "Get in touch" 4.69 (on cream), lead 6.26, footer 6.26, all ≥ 4.5. The 778aa8f control shows 4 color-contrast failures (3.85/3.28/4.37/4.37), which matches the author's claim | out/fc-exact-rr01.json `axe`, `contrast` | REPRODUCED |
| 12 | Homepage not regressed vs 2f6b59a and 778aa8f | PASS. Stylesheets: fonts + styles.css + enhancements.css. Fonts are Cormorant 400/400i and Manrope 400/500/600. 27 images, 0 broken (also after a full scroll). `html.js` is set. Reveal: 30 targets, 28 visible after scroll (the same 28/30 in all three builds). The project modal opens ("Warm Contemporary"), closes on Esc and returns focus to its trigger. At 360 px the mobile nav opens on tap (`aria-expanded=true`), Esc closes it and refocuses the button, and there is no horizontal scroll. 4 wa.me links have `target=_blank rel=noopener` (the same as 2f6b59a; 778aa8f had 2). 0 CSP violations, 0 console errors, 0 failed requests, 0 API/Turnstile requests | out/*-rr01.json `home` | REPRODUCED |

**RR-01 RESOLVED.**

#### F.2 RR-11 15-item table

Server: :8201 with exact headers. `window.open` is replaced in `addInitScript` so that each call records `[url, target, features]`. All requests are captured. Raw output is in `out/fc-rr11.json` and `logs/rr11-fc.log`. A separate un-intercepted run (`probe-meta.mjs`, wa.me stubbed with `route.fulfill`) confirmed that the real popup opens under user activation with `window.opener === null`.

| # | Check | Result | Label |
|---|---|---|---|
| 1 | Empty submit does not open WhatsApp | PASS. `opened=0`, summary "Please fix 2 things". Whitespace-only name and phone also give opened=0 | REPRODUCED |
| 2 | Missing name | PASS. opened=0, name `aria-invalid=true`, "Enter your name." A 1-char name ("A") is rejected too | REPRODUCED |
| 3 | Missing phone | PASS. opened=0, phone `aria-invalid=true`, "Enter a valid phone number." | REPRODUCED |
| 4 | Invalid phone | PASS. All 7 values are rejected with opened=0: `abc`, `12345`, `95151abc25153`, `+91 95151 25153 ext 4`, `1234567890123456` (16 digits), `++919515125153`, `<script>9515125153`. An invalid email is rejected as well | REPRODUCED |
| 5 | Accessible validation errors | PASS. Invalid fields get `aria-invalid="true"`. Per-field `.field-error` text is linked by `aria-describedby`. The `#form-summary` has `role="alert"` and `tabindex=-1`, is shown and **focused**, and lists links to `#cf-name` and `#cf-phone`. Activating a summary link moves focus to the field (`cf-phone`). After a fix and resubmit, the errors clear (`aria-invalid=false`, summary hidden). axe on `#contact` in the error state shows 0 violations in the form; the one pre-existing hit is `.contact-copy > .eyebrow` (#ad6d54 on #f1e5d7, 3.32:1), which is outside the form and tracked as OI-11 in the suite ("18 tracked outside the form") | REPRODUCED |
| 6 | Entered values retained | PASS. Name, phone, email, location and brief are unchanged after a failed submit (for example `Priya Sharma` / `123` / `priya@example.com` / `Gachibowli` / `Two BHK`). Leading and trailing spaces are kept in the field and trimmed only in the message | REPRODUCED |
| 7 | Valid fallback opens a correctly encoded wa.me message | PASS. See the decoded URLs below. `target=_blank`, `features=noopener`, origin `https://wa.me/919515125153`, single query parameter `text` | REPRODUCED |
| 8 | Special characters safely encoded | PASS. The decoded `text` equals the expected string **exactly** (`match: true`). The raw URL contains no raw `#`, `&` (inside text), space, `<` or `"`. Values are `%23`, `%26`, `%3F`, `%25`, `%22`, `%3C…%3E`, `%0A`, and UTF-8 for ë, 😀, 🏠 and U+202E. `'`, `(` and `)` stay literal, which is safe (encodeURIComponent unreserved) | REPRODUCED |
| 9 | No uncaptured consent claim | PASS. The message is limited to "Hello Veda Spaces, I would like to discuss my home interiors." plus field lines. It contains no "agree", "consent" or policy version. The consent checkbox stays `hidden` (`label.consent[data-intake-only]`), and consent is validated only when `apiBase` is set (app.js:137, 173) | REPRODUCED + SOURCE |
| 10 | No internal fields in the message | PASS. With honeypot `company_website_url=http://spam.example/HONEYPOT` filled, the message has no honeypot text. The idempotency key and Turnstile token never appear in the message (the builder uses only name, phone, email, 3 option labels, location and brief; app.js:72-83) | REPRODUCED + SOURCE |
| 11 | No API configuration disclosed | PASS. The message and URL carry no API base, site key or policy version. Both metas are empty in the committed `dist/index.html:11-12`. Advisory: when only `veda-api-base` is set, the page logs `console.warn('veda: intake disabled — veda-turnstile-sitekey is not set')`. This is pre-existing (app.js:59), dev-facing only, and does not reveal the URL | REPRODUCED |
| 12 | No network API call | PASS. In every scenario, 0 fetch/XHR and 0 non-static requests after load. There were no requests to `/api/`, `api.vedaspaces.com`, `challenges.cloudflare.com` or `127.0.0.1:9` (api-only variant). No Turnstile script is injected | REPRODUCED |
| 13 | Mobile (360 px, touch) and keyboard Enter | PASS. Enter in the phone field on an empty form gives errors, opened=0 and focus on the summary; on a valid form it gives opened=1. A 360 px `tap()` on an empty form gives errors and focus on the summary, with no horizontal scroll (360/360); a valid tap gives opened=1 | REPRODUCED |
| 14 | Screen readers receive the error | PASS. The Chromium AX tree for `#cf-phone` reports invalid=`true`, required=`true`, and the description "⚠ Enter a valid phone number.". The summary is `role=alert` (a live region), is revealed with new content, and is focused | REPRODUCED |
| 15 | Public website remains operational | PASS (RR-01 #12). Home, nav, modal, reveal, images, fonts and WhatsApp links all work, with 0 CSP violations | REPRODUCED |

Decoded WhatsApp messages (all synthetic data):

- 7 valid full: `https://wa.me/919515125153?text=…`, which decodes to:
  ```
  Hello Veda Spaces, I would like to discuss my home interiors.

  Name: Priya Sharma
  Phone: +91 95151 25153
  Email: priya@example.com
  Property: Apartment / Flat
  Service: Bedrooms & Wardrobes
  Budget: ₹10–20 L
  Location: Kondapur, Hyderabad
  Requirements: Two bedrooms and a modular kitchen.
  ```
- 7b minimal (also Enter and 360 px tap): Name `Priya Sharma`, Phone `+91 95151 25153`. Every other line is `Not provided`.
- 5 after correction: raw `https://wa.me/919515125153?text=Hello%20Veda%20Spaces%2C%20I%20would%20like%20to%20discuss%20my%20home%20interiors.%0A%0AName%3A%20Priya%20Sharma%0APhone%3A%209515125153%0AEmail%3A%20priya%40example.com%0AProperty%3A%20Not%20provided%0AService%3A%20Not%20provided%0ABudget%3A%20Not%20provided%0ALocation%3A%20Gachibowli%0ARequirements%3A%20Two%20BHK`
- 8 special characters plus honeypot. Input name was `  Zoë & Co #1 ? 100% "quoted" 'single' <script>alert(1)</script> 😀  `, phone ` +91 (951) 512-5153 `, email `a+b&c@example.com`, location `Banjara Hills #12 & Co?x=1%20`, brief `Line one & two⏎Line #2 ? 50% off⏎<img src=x onerror=alert(1)> 🏠 "done" U+202E evil`, and honeypot filled. Raw:
  `https://wa.me/919515125153?text=Hello%20Veda%20Spaces%2C%20I%20would%20like%20to%20discuss%20my%20home%20interiors.%0A%0AName%3A%20Zo%C3%AB%20%26%20Co%20%231%20%3F%20100%25%20%22quoted%22%20'single'%20%3Cscript%3Ealert(1)%3C%2Fscript%3E%20%F0%9F%98%80%0APhone%3A%20%2B91%20(951)%20512-5153%0AEmail%3A%20a%2Bb%26c%40example.com%0AProperty%3A%20Not%20provided%0AService%3A%20Not%20provided%0ABudget%3A%20Not%20provided%0ALocation%3A%20Banjara%20Hills%20%2312%20%26%20Co%3Fx%3D1%2520%0ARequirements%3A%20Line%20one%20%26%20two%0ALine%20%232%20%3F%2050%25%20off%0A%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E%20%F0%9F%8F%A0%20%22done%22%20%E2%80%AEevil`
  The decoded text equals the expected value exactly: values are trimmed, newlines are preserved as `%0A`, there is no honeypot, and there is only one query parameter.

**RR-11 RESOLVED.**

#### F.3 Commands

All frontend commands ran in `$S/probes3/fe/app` with Node 22.23.3 on PATH. Logs are under `$S/probes3/fe/logs/`.

| Command | Exit | Result |
|---|---|---|
| `npm ci` | 0 | installed; "found 0 vulnerabilities" |
| `npm run lint` | 0 | clean |
| `npm run typecheck` | 0 | clean |
| `npm run lint:tokens` | 0 | "no raw colour values outside src/design-system/tokens.css" |
| `npm run test:contrast` | 0 | 58 pairs, light and dark |
| `npm test` (wtr) | 0 | 6/6 files, **52 passed, 0 failed** |
| `npm run build` | 0 | built (tsc + vite) |
| `npm audit` | 0 | 0 vulnerabilities |
| `npm audit --omit=dev` | 0 | 0 vulnerabilities |
| `API_PYTHON=$S/venv2/bin/python bash app/e2e/run-all.sh` (from `$S/probes3/fe`) | 0 | see below |
| `node probe-rr01.mjs 8201 fc-exact` / `8202 fc-nouir` / `8203 base2f6` / `8204 base778` | 0 ×4 | RR-01 table |
| `node probe-rr11.mjs 8201 fc` | 0 | RR-11 table |
| `node probe-meta.mjs 8201 8205 8206` | 0 | real popup plus meta combinations |
| `node probe-founder.mjs` / `probe-founder2.mjs` (after migrate and seed of scratch `var/fc3.db`) | 0 / 0 | workspace restore UI |

###### E2E counts (run here vs author claim)

| Script | Here | Claim |
|---|---|---|
| workspace.e2e.mjs | 7/7 | 7/7 |
| access.e2e.mjs | 16/16 | 16/16 |
| site.e2e.mjs | 31/31 | 31/31 |
| axe.e2e.mjs | 12/12 (including "404 page" and "website form, intake off (error state)") | 12/12 |

These match the author's `evidence/final-merge-blockers/e2e.txt`. Test-harness note: `app/e2e/static-server.mjs:54` calls `listen(port)` with no host, so it binds all interfaces while the suite runs. This is harness-only; see FC-FE-3.

#### F.4 Regression

| Area | Result | Label |
|---|---|---|
| Public API disablement | Both metas are empty in the committed `dist/index.html:11-12`, and app.js:58 requires both. api-only variant: intake stays off, consent is hidden, WhatsApp opens, 0 API calls, one console.warn. Sitekey-only variant: the same with no warn. Committed build: 0 API calls, 0 Turnstile loads | REPRODUCED |
| CSP on all pages | `/`, `/404.html`, unknown paths and `/privacy` all show 0 violations at desktop and 360 px, with and without UIR | REPRODUCED |
| Live homepage | No regression vs 2f6b59a or 778aa8f (RR-01 #12) | REPRODUCED |
| Workspace app CSP (production build under `app/dist/_headers` = `app/public/_headers`, SPA fallback per `_redirects`, same-origin `/api` proxy) | 0 CSP violations while navigating `/`, `/admin/users`, `/admin/founder-actions`, `/approvals`, `/admin/roles`, `/audit` and running the full restore flow **without axe**. When axe runs, one `connect-src` report per run appears for fonts.googleapis.com. That report is caused by the probe (axe fetches cross-origin stylesheets) and is not an app defect | REPRODUCED |
| `user-drawer.ts` (deleted Founder) | Security tab shows the link "Restore via Founder actions" (`href=/admin/founder-actions`) and 0 generic "Restore" buttons. Keyboard: Tab reaches the link with `:focus-visible` (2px solid rgb(164,109,66)), and Enter performs SPA navigation to `/admin/founder-actions`. axe on users page plus open drawer: 0 | REPRODUCED |
| `user-drawer.ts` (deleted standard user) | Generic "Restore" button present (1), Founder link absent. `POST /users/{id}/restore` returns 200 | REPRODUCED |
| `founder-actions-page.ts` restore | Option "Restore a deleted Founder (returns deactivated)". Person list = deleted Founders only (`Chitra Founder (f3@…)`). No status select. POST body `{action: FOUNDER_STATUS_CHANGE, status: RESTORE, target_user_id, reason}` returns 202 IN_APP with a success banner. When no Founder is deleted, the Person list is empty (0 options). axe before and after submit: 0 | REPRODUCED |
| Approval by a second Founder | F2 Approvals shows Approve… then a dialog with a reason, and the API returns 200 `EXECUTED`. F3 is then `is_deleted=false`, `status=DISABLED`, `protection_level=FOUNDER`. axe on the approve dialog: 0. The card does not show that the request is a **restore** (FC-FE-2) | REPRODUCED |
| Founder-status "Delete" option sends `DELETED` | Not a defect: routes.py:500/522 normalise `DELETED` to `DELETE`. Returned 202 | REPRODUCED + SOURCE |
