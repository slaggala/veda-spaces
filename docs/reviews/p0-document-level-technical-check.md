# Veda Spaces P0 — Document-Level Technical Check

**Review ID:** VEDA-SPACES-P0-DOCUMENT-LEVEL-TECHNICAL-CHECK-01
**Date:** 2026-09-29
**Final verdict:** **READY WITH DOCUMENT CONDITIONS**

- No implementation blocker remains, and no regression was found.
- The owner decision package is ready.
- The recommended merge-safety Option C is **not executable as written** (DC-01). Its plan, together with a small set of amendment and guard corrections, must be fixed before the consolidated owner decision.
- None of the corrections requires new implementation behaviour.

> This document covers technical artifacts only.
> - It changes no implementation, amendment, architecture or `dist/` file.
> - It approves nothing and selects no merge-safety option.
> - It completes neither TG-01 nor TG-08.
> - It authorizes no merge or deployment.

| Item | Value |
|---|---|
| Certified architecture | `778aa8fdd918da48340319696ada3ff673e9fb8e` |
| Previously reviewed SHA | `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41` |
| **SHA reviewed** | **`3f5920b17d21214b39414d080d34246746c8c40d`** (branch head; no later commit) |
| Review branch | `review/p0-independent-implementation-review` (previous commit `56c20ba992b519daa79aa3802a28343aab8c0b41`) |
| Twin | [p0-document-level-technical-check.json](p0-document-level-technical-check.json) |

## 1. Scope verification (Phase 1)

| Check | Result |
|---|---|
| SHA exists remotely; reachable from `origin/implementation/p0-foundation` | Yes. It is the head (`git ls-remote`) |
| Previously reviewed SHA is ancestor; linear, no rewrite | Yes. Single child of `6ec2e76`; remote-tracking reflog `… → 6ec2e76 → 3f5920b` (fast-forward pushes) |
| Certified architecture unchanged | Yes. `git diff 778aa8f 3f5920b -- docs/architecture` is empty |
| Existing review artifacts unchanged | Yes. Review branch at `56c20ba`; no `docs/reviews/` on the implementation branch |
| Amendments under `docs/proposals/amendments/`; none approved | Yes. AM-1 … AM-13 all PROPOSED, NOT APPROVED |
| TG-01 / TG-08 | Pending (gate registry unchanged) |
| Public intake disabled | Yes. `dist/` byte-identical to `6ec2e76`; both metas empty; 0 API calls in browser |
| Nothing merged or deployed | Yes. `origin/main` = `13276a0` (unchanged); no implementation commit in `main` |
| No secrets or unredacted artifacts | Yes. Pattern and regex scans of the 72 changed files clean |
| Diff within closure scope | Yes. 72 files, +10 228/−334. Code: `db.py`/`audit_hook.py` (FC-04), `logging.py`/`metrics.py` (FC-02), `http.py`/`app.py` (FC-06), `mypy_ratchet.py` (FC-11), `deploy.sh`/`release.py`/`cli`/`health.py` (FC-12). `passwords.py` is comment-only. Plus tests, amendments, owner package, merge-safety plan, runbook, registers, evidence |

## 2. Verdicts

| Item | **Verdict** | Evidence |
|---|---|---|
| SHA references | **SHA REFERENCES VALID** | Every 40-hex and short SHA in the governance documents resolves; the nonexistent brief variant …bc0b11f41 appears 6× and is labelled 'does not exist' each time; 3f5920b is correctly absent from its own tree (owner package line 15 explains). Guard weakness: DC-04 |
| FC-02 | **FC-02 RESOLVED** | Approved metric names handled structurally; NoEffectiveRecoveryAdmin emitted as 1.0 by the `maintenance invariants` CLI and the scheduled job (separate processes), namespace/dimensions match the runbook alarm; recovery codes, tokens, recovery-session ids and unknown recovery keys still redacted; a string/bool/dict/list under an approved metric name is redacted (no smuggling); no alarm routing or test-fire claimed (RG-5 pending) |
| FC-04 | **FC-04 RESOLVED** | api/veda/kernel/db.py: clock read after session.connection() (BEGIN IMMEDIATE) — lead reviewer read the diff; audit_hook.py: updated_on = max(now, created_on). With both reverted all three new tests fail; each fix caught by its own test; 30/30 SQLite and 10/10 PostgreSQL repeats pass, no deadlock. Also fixes the PG change_password‖refresh 500 (40/40 clean vs 5/30 errors at 6ec2e76). Residual DC-06 |
| FC-06 | **FC-06 RESOLVED** | Blank, unknown, malformed and case-variant modes rejected at declaration, at startup and at request time (mutated spec → 500 before handler); optional/public + permission rejected; private without permission rejected; runtime inventory byte-identical to 6ec2e76 (105 routes) |
| FC-11 | **FC-11 NOT RESOLVED** | All previously named vectors now fail (37-case matrix). New bypass DC-05: a `.pyi` stub beside a module makes mypy check the stub, hiding that module's 62 baselined errors and any new one; the file-count check enumerates only *.py (tools/mypy_ratchet.py:67, confirmed by lead reviewer). MINOR, staging (CI gate integrity) |
| FC-12 | **FC-12 RESOLVED** | deploy.sh step 0 refuses 9236aa3, 2f6b59a, 6ec2e76 (no release field), malformed/wrong-type output and a missing image in normal AND rollback mode, before snapshot/stop/migrate; env vars, BASH_ENV and extra flags cannot override; floor derived from the image (release sequence + known revisions), not DB state (lead reviewer read deploy.sh:40-60, cli schema-status); runbook prohibits vulnerable rollback, documents forward-fix, claims no rehearsal; RG-7 remains a gate |

## 3. Amendments (Phase 3)

All 13 contain every required element: status, certified and proposed behaviour, requirements, security/data/API/UI/compatibility impact, rollback or forward-fix, tests, staging evidence, production evidence, owner decision and failure behaviour. None alters the certified architecture: the `docs/architecture` tree hash equals `778aa8f`'s.

| Amendment | Classification |
|---|---|
| AM-1 | TECHNICALLY SOUND |
| AM-2 | TECHNICALLY SOUND WITH OWNER CONDITIONS |
| AM-3 | TECHNICALLY SOUND |
| AM-4 | INCOMPLETE — states 422 where code/tests return 409; 'later version' has no ordering rule; the immutability option conflicts with erasure rewriting consent notes (DC-02) |
| AM-5 | TECHNICALLY SOUND WITH OWNER CONDITIONS |
| AM-6 | TECHNICALLY SOUND WITH OWNER CONDITIONS |
| AM-7 | TECHNICALLY SOUND WITH OWNER CONDITIONS — upgraded from INCOMPLETE: every claim verified against kernel/ratelimit.py, auth/throttle.py, auth/service.py; discloses reset-link suppression and that a Turnstile outage is fail-closed with unbounded availability impact under attack; makes none of the forbidden claims |
| AM-8 | TECHNICALLY SOUND |
| AM-9 | INCOMPLETE — owner decision not yet taken; repository/staging/production/provider/owner evidence are separated, but the policy itself is undecided |
| AM-10 | INCOMPLETE — omits PII entering outbox_event.last_error from SQL and handler exception text (DC-03) |
| AM-11 | TECHNICALLY SOUND WITH OWNER CONDITIONS |
| AM-12 | TECHNICALLY SOUND WITH OWNER CONDITIONS |
| AM-13 | TECHNICALLY SOUND WITH OWNER CONDITIONS |

Counts: TECHNICALLY SOUND 3 · WITH OWNER CONDITIONS 7 · INCOMPLETE 3 · UNSOUND 0 · UNNECESSARY 0. No amendment is approved by this review.

## 4. Owner decision package (Phase 9): **READY FOR OWNER DECISION**

The package covers AM-1 … AM-13 with:
- classification;
- risks and conditions;
- staging and production dependencies;
- implementation behaviour;
- recommended disposition;
- the decision required.

Nothing in it records a decision:
- No owner decision is recorded.
- TG-01, TG-08, the merge-safety decision and production approval are all **PENDING**.
- OD-2 and OD-3 are identified as implementation assumptions awaiting formal owner confirmation.

Corrections (DC-07):
- The reviewer-classification column should quote the reviewer verbatim.
- The provenance note is stale.
- "OD-2/OD-3 given" wording persists in two other documents.

## 5. Merge-safety plan (Phase 10): **OPTION C TECHNICALLY SOUND WITH CONDITIONS**

**What Option C gets right.**
- Options A, B and C each state preconditions, repository changes, Cloudflare implications, validation, rollback, risks, owner action and evidence.
- `main`'s `dist/` (34 files) can be reproduced blob-identically.
- It keeps the live site, the WhatsApp fallback, the custom domain and intake-off unchanged, with no CSP or form release.
- It defers the site release to a separately reviewable Option A step.

**Why it is not executable as written (DC-01).** The lead reviewer identified (a) to (c), and the document verifier reproduced them together with (d):
- (a) The CI browser job would fail on `merge-prep`, and `main` would be red after the merge.
- (b) The revert trap hides the site changes from all future merges and creates branch/`main` divergence.
- (c) The integrity check cites `6ec2e76` rather than `3f5920b`.
- (d) The restore command leaves `404.css` behind.

The owner may instead select Option A or Option B. This review does not select an option.

## 6. Regression check (Phase 11): **no regression**

| Area | Result |
|---|---|
| IR-01 binding (20 items + adjacent) | 52/52 SQLite and PostgreSQL |
| Founder restoration, execution-time revalidation (RR-02, RR-03) | Reviewer probes P (22), N (17), R/X (22) on both engines; outcomes unchanged |
| Layered limiter (RR-04) | Unchanged numbers (94 evaluated / 60 × 429 / 154; victim 31/9) |
| Refresh successor (RR-08) | Grace < 20 s OK; 21 s → theft |
| Audit archive protocol | 19/19 failure-injection probes on both engines |
| Optional-auth / route registration | Inventory byte-identical (105) |
| UUIDv7, schema conformance | 42/42 |
| Disabled form, 404/CSP, homepage | Probe output identical to `6ec2e76` apart from the port; 0 CSP violations |

**FC-04 effect.** No adverse effect on grace windows, throttling, cooling-off or chain ordering. It also removes the earlier PostgreSQL `change_password‖refresh` 500 (40/40 clean vs 5/30 errors at `6ec2e76`).

## 7. Evidence and CI (Phase 12)

| Suite | Result |
|---|---|
| SQLite full | **611 passed** (42.4 s) |
| PostgreSQL 16.4 full | **601 passed, 10 skipped** (108.4 s; SQLite-only skips) |
| PostgreSQL 18.4 (embedded) | 600 passed + 11 skipped in the regression verifier's copy. The extra skip is the SHA-history test, which has no `.git` in a copy (DC-04) |
| Focused suites | Auth 115/115, RBAC 60/60, audit 136/136, limiter/refresh 28/28, UUIDv7/schema 42/42 (both engines) |
| Frontend (Node 22.23.3) | npm ci, lint, typecheck, lint:tokens, contrast (58), test 52/0, build, `npm audit` 0 / `--omit=dev` 0 |
| Browser | workspace 7/7, access 16/16, site 31/31, axe 12/12; CSP/404 and form probes identical |
| Security tooling | ruff, format, ratchet (157/157), openapi_check, secret scan, bandit, pip-audit: clean |

**CI.** Run **36594775516**:
- push, attempt 1, `head_sha=3f5920b17d21214b39414d080d34246746c8c40d`, conclusion `success`;
- all 5 jobs `success`;
- only conditional steps skipped (failure-artifact upload; the PG-version step on the SQLite leg).

`ci.yml` is unchanged since the verified gate set. Failure propagation was previously demonstrated by run 36558306690. The first-run failures listed in the author's evidence (`summary-run1.tsv`) were corrected before the final run.

**No false-green hard gate, but one soft spot:** the SHA-history test self-skips in CI (DC-04).

## 8. Findings

| ID | Severity | Title | Evidence | Required correction | Needed before |
|---|---|---|---|---|---|
| DC-01 | **MAJOR (document)** | Merge-safety Option C is not executable as written | (a) app/e2e/run-all.sh:32-33 serves the repo's dist/ and app/e2e/site.e2e.mjs / axe.e2e.mjs assert the new site (404.css ~l.192, flag-off validation ~l.142-155); on a simulated merge-prep tree with main's dist/ the check fails (test_public_intake_disabled reproduced failing), so 'CI passes on merge-prep' cannot be met and main CI would be red after merge. (b) Revert trap: after C, later merges never reintroduce the site changes; merging main back into the branch strips its CSP and 404 fix; a later 404.css fix hits a modify/delete conflict (simulated). (c) The plan branches from and diffs against 6ec2e76 (integrity diff 72 files) — must be 3f5920b (diff 0). (d) `git checkout origin/main -- dist/` leaves dist/assets/404.css behind; needs `git rm -r dist` first or `git restore --source origin/main --staged --worktree dist` | Correct the plan: branch from 3f5920b; exact dist restore command; a reviewed CI treatment for merge-prep/main (e.g., site journeys run against a site-fixture or are split into a site-release job) or explicit owner acceptance; a documented procedure for the later site release (revert of the 'keep live site' commit) and for keeping the branch and main in sync; evidence list updated | Before owner decision on merge safety (owner may instead select Option A or B) |
| DC-02 | **MINOR (document)** | AM-4 incomplete | See amendment table | Correct AM-4 text | Before owner decision on AM-4 |
| DC-03 | **MINOR (document)** | AM-10 incomplete | api/veda/platform/notifications/worker.py stores str(exc)[:300] in outbox_event.last_error, including SQL/handler exception text | Extend AM-10 scope | Before production (AM-10 is a production-stage decision) |
| DC-04 | **MINOR (CI/document guard)** | SHA-reference guard does not run in CI and is narrow | api/tests/unit/test_governance_docs.py:82-97 skips when history is unavailable; .github/workflows/ci.yml sets no fetch-depth (depth-1 checkout) so it skips in CI (author evidence also skipped); covers 8 docs and lowercase 40-hex only; a bad SHA in runbooks/README/open-issues.json, a bad short SHA, or a real-but-wrong SHA pass (planted and confirmed) | fetch-depth: 0 for the job running it (or a dedicated job); widen the document set and patterns; assert the specific expected SHAs | Before owner decision (so the package's SHA assurance is enforced) — or owner accepts manual verification |
| DC-05 | **MINOR** | FC-11 residual: .pyi stub bypass of the mypy ratchet | tools/mypy_ratchet.py:67 enumerates only *.py; stub beside a module hides 62 baselined errors and new ones (REPRODUCED) | Refuse *.pyi under veda/ (or include stubs in the count) | Staging (CI gate integrity) |
| DC-06 | **MINOR** | FC-04 residual (PostgreSQL): when the guard fires updated_on exceeds the unit's clock reading, so audit history can show UPDATE before CREATE, contradicting 03 §2.8 ('one clock reading per unit of work') without an amendment; raw updates in sync-permissions and sequence allocation are unguarded (fail-and-rollback, no corruption) | api/veda/kernel/audit_hook.py:231-237 (REPRODUCED on embedded PostgreSQL) | Document in an amendment (or use a DB-side monotonic clock); guard or document raw update paths | PostgreSQL release gate; amendment text before production |
| DC-07 | **MINOR (document)** | Owner package and registers: reviewer-classification column paraphrases the reviewer (adds '— corrected', rewords AM-6/AM-12); 'implemented at this commit' provenance is stale (code from 6ec2e76); 'OD-2/OD-3 given' wording persists in P0-final-merge-blocker-matrix.md and the deviations register although the owner package correctly marks them as assumptions | docs/implementation/P0-owner-decision-package.md; P0-final-merge-blocker-matrix.md; P0-implementation-deviations.md | Quote reviewer classifications verbatim; fix provenance; align OD-2/OD-3 wording everywhere | Before owner decision |
| DC-08 | **MINOR (pre-existing)** | PostgreSQL deadlock between a Founder RESTORE approval and an invite of the same address returns 503 (retryable); exactly one live holder of the address always | REPRODUCED 3/24 at 3f5920b, 4/24 at 6ec2e76 | Consistent lock ordering or retry | PostgreSQL release gate |

### Advisories

- **DC-A01** health.current_revision() maps any DBAPIError to None, so `schema-status` reports state 'missing' with exit 0 during a DB outage/lock/auth failure; no automated path acts unsafely (readiness runs its own query; rollback refuses 'missing'); the manual runbook step could mislead and its output description is stale (DC-TECH-7, DC-REG-2; lead reviewer traced deploy.sh and health.py)
- **DC-A02** Ratchet: a coded ignore with any justification text passes (DC-TECH-2); code under `if not TYPE_CHECKING:` is unchecked (DC-TECH-3)
- **DC-A03** On PostgreSQL the FC-04 concurrency test passes even with the guard removed; only the deterministic test covers the race there
- **DC-A04** Remaining documentation advisories from the document working paper §6 (appendix)

## 9. Final report (A–AB)

| Key | Item | Result |
|---|---|---|
| A | Exact SHA reviewed | `3f5920b17d21214b39414d080d34246746c8c40d` |
| B | Review branch | `review/p0-independent-implementation-review` |
| C | Review commit SHA | The commit adding this file (parent `56c20ba`) |
| D | Scope verification | Verified (§1) |
| E | SHA references | **SHA REFERENCES VALID** (guard condition DC-04) |
| F | AM-1 … AM-13 | Sound: AM-1, AM-3, AM-8. With owner conditions: AM-2, AM-5, AM-6, AM-7, AM-11, AM-12, AM-13. Incomplete: AM-4, AM-9, AM-10. None approved |
| G | FC-02 | **FC-02 RESOLVED** |
| H | FC-04 | **FC-04 RESOLVED** (residual DC-06) |
| I | FC-06 | **FC-06 RESOLVED** |
| J | FC-11 | **FC-11 NOT RESOLVED** (`.pyi` bypass DC-05; MINOR, staging) |
| K | FC-12 | **FC-12 RESOLVED** |
| L | Owner package | **READY FOR OWNER DECISION** (wording corrections DC-07) |
| M | Merge safety | **OPTION C TECHNICALLY SOUND WITH CONDITIONS**. Not executable as written (DC-01) |
| N | Regression | None |
| O | Focused SQLite | Auth 115, RBAC 60, audit 136, limiter/refresh 28, schema 42: all pass |
| P | Full SQLite | 611 passed |
| Q | PostgreSQL 16 | 601 passed, 10 skipped |
| R | Frontend | All pass; 52 tests; audit 0/0 |
| S | Browser/CSP | 7/7, 16/16, 31/31, 12/12; 0 CSP violations; 404 styled; intake off |
| T | Security | Scanners clean; bypass/IDOR/replay/limiter/failure-injection probes unchanged |
| U | CI | Run 36594775516: 5/5 success on `3f5920b` |
| V | Remaining technical blockers | None |
| W | Remaining document conditions | DC-01 (merge-safety plan), DC-02 (AM-4), DC-04 (SHA guard in CI), DC-07 (owner-package and register wording). DC-03 (AM-10) before production |
| X | Staging gates | DC-05 (FC-11 `.pyi`); carried: FC-03 S3 Object Lock, FC-10, RR-09 custodian rehearsal, RR-10, RR-14, RR-15, IR-06/11/12 acceptance, RG-5 alarm test-fire |
| Y | Production gates | DC-06, DC-08 (PostgreSQL gate), FC-01, FC-05 … FC-09, FC-13 … FC-15, carried re-review items, all 27 gates incl. RG-1/RG-2/RG-7 |
| Z | Required owner decisions | AM-1 … AM-13 dispositions (AM-8 … AM-10 may wait for production); OD-2 and OD-3 formal confirmation; merge-safety option (A, B or corrected C); TG-01; TG-08; production site-deployment approval; OWNER-INPUT-001 … 004 |
| AA | Exact next authorized action | **Owner decision only.** No merge or deployment is authorized. Next, the owner decides whether to authorize a documentation/CI-guard correction increment (DC-01, DC-02, DC-04, DC-07; optionally DC-05), followed by a brief confirmation check. Alternatively, the owner selects a different merge-safety option. The consolidated owner decision (amendments, OD-2/OD-3, merge-safety option, TG-01, TG-08) follows |
| AB | Final verdict | **READY WITH DOCUMENT CONDITIONS** |

---

## Appendices

Appendices B to D are the verifiers' working tables, included verbatim. Working-paper IDs map to consolidated IDs as follows:

| Working-paper ID | Consolidated ID |
|---|---|
| DC-DOC-1, 2, 6, 8 | DC-01 |
| DC-DOC-14 | DC-02 |
| DC-DOC-9 | DC-03 |
| DC-DOC-3 | DC-04 |
| DC-TECH-1 | DC-05 |
| DC-TECH-5, 6 | DC-06 |
| DC-DOC-4, 5, 7 | DC-07 |
| DC-REG-1 | DC-08 |
| DC-TECH-7, DC-REG-2 | DC-A01 |

### Appendix A — Lead reviewer commands

```
git fetch origin --prune; git ls-remote origin; git cat-file -t 3f5920b17d21214b39414d080d34246746c8c40d
git log 6ec2e76..origin/implementation/p0-foundation; git diff --name-status 6ec2e76 3f5920b
git diff --quiet 778aa8f 3f5920b -- docs/architecture; git diff --quiet 6ec2e76 3f5920b -- dist
VEDA_TEST_ENGINES=sqlite python -m pytest -q -rs          # 611 passed
VEDA_TEST_DATABASE_URL_PG=postgresql+psycopg://postgres@127.0.0.1:55433/postgres VEDA_TEST_ENGINES=postgresql python -m pytest -q -rs   # 601 passed, 10 skipped (16.4)
curl https://api.github.com/repos/slaggala/veda-spaces/actions/runs/36594775516(/jobs)   # success × 5
```

### Appendix B — Documents and governance

#### B.1 SHA references

I grepped every 40-hex and 7-hex token in `docs/`, `README.md`, `deployment.md`, `cloudflare-pages.md` and `api/tests`. Every one was resolved with `git cat-file -t`.

| SHA | Count | Resolves | Use | Correct? |
|---|---|---|---|---|
| 6ec2e76f156e963c7363c4ad9ce93d0bccb11f41 | 41 | commit (parent 2f6b59a) | "Reviewed implementation" in AM-1..13, README, amendments.json, the owner package, the merge plan, open issues and the report §00 | Yes. It matches the final check's "Remediation SHA reviewed". |
| 6ec2e76f156e963c7363c4ad9ce93d0bc0b11f41 | 6 | **nonexistent** | owner-package.md:14, owner-package.json:6, impl-report.md:25, open-issues.md:186, open-issues.json:3022, test NONEXISTENT constant | Yes. Every occurrence is labelled "does not exist". No doc at `6ec2e76` cited it, so report line 25 is true. |
| 56c20ba992b519daa79aa3802a28343aab8c0b41 | 23 | commit | final targeted check | Yes. It is the remote head of the review branch. |
| 778aa8fdd918da48340319696ada3ff673e9fb8e | 19 | commit | certified baseline | Yes. `docs/architecture` has the same tree hash at 778aa8f and 3f5920b (`5e305fe0…`). |
| 9236aa3…, 1aaf019…, 15d25a7…, 2f6b59a…, 4dce177…, 7515b23…, 06a4f6e…, c3aae47… | — | all commits | history references | Yes |
| short: 56c20ba, 9236aa3, 2f6b59a, 778aa8f, 6ec2e76, 15d25a7, 13276a0 | — | all commits | — | Yes. 13276a0 is `origin/main`, which ls-remote confirms. |
| 3f5920b | 0 | — | — | Correctly absent. The owner package (line 15) states that a commit cannot contain its own hash. |

**Staleness (not invalid SHAs):**
- **Provenance mislabels.** The phrases "Implemented at this commit" and "refresh successor linking added at this commit" appear in AM-7, AM-11, AM-12 and AM-13 (all at line 17), in amendments.json and in owner-package.md lines 130, 190, 205 and 220. They were carried over unchanged from `6ec2e76`. The owner package defines "this commit" as the closure commit. In fact, `rotate_session_refresh`, `throttle.py` and `governance.py` are unchanged between `6ec2e76` and `3f5920b` (`git diff --stat`). See DC-DOC-5.
- **Stale report lines.** Report line 10 still gives "Reviewed implementation `9236aa3`" in the header table. Line 436 cites `docs/architecture/amendments/`, which no longer exists. See DC-DOC-10.

**`test_governance_docs.py` behaviour.** I ran it in copies; the scripts are in `probes4/docs/plant.sh`.

| Probe | Result |
|---|---|
| Clean copy with git metadata | 20 passed |
| Nonexistent 40-hex in merge plan or open-issues.md | **FAILS** (as intended) |
| Blob SHA (not a commit) | **FAILS** (as intended) |
| Nonexistent 40-hex in `api-runbooks.md`, `P0-implementation-deviations.md`, `README.md` or `open-issues.json` | passes: not in `GOVERNANCE_DOCS` |
| Nonexistent short SHA (`deadbee`) | passes: only 40-hex is checked |
| Uppercase 40-hex | passes: the regex is lowercase only |
| Existing but wrong SHA labelled "current reviewed" (2f6b59a) | passes: existence is checked, not correctness |
| Nonexistent typo SHA on a line that contains the substring "does not exist" | passes |
| Fresh copy without `.git` | `test_cited_shas_exist` is **SKIPPED** ("needs a git checkout"), even with a planted bad SHA |
| Shallow clone (`--depth 1`), clean or with a bad SHA planted | **SKIPPED** ("history not available"), because REVIEWED is absent |

- **The skips are deliberate and disclosed** in `evidence/technical-conditions/README.md:26`.
- **But CI always skips.** `.github/workflows/ci.yml` uses `actions/checkout` with no `fetch-depth`, which gives a depth-1 clone. So the existence check **never runs in CI**, and a bad SHA would pass CI silently.
- **The author's evidence skipped it too** (`pytest-sqlite.txt:11`). Only a full local checkout runs it. I confirmed that it passes there.

**Verdict: SHA REFERENCES VALID.** The references themselves are correct. The weakness of the guard is DC-DOC-3.

#### B.2 Amendment required-element matrix

Key: ✓ = present and substantive. ✓* = present, but thin or mislabelled. "D" = decision request, with the element deferred to the implementation.

| AM | Status P,NA | Certified | Proposed | Affected reqs | Sec | Data | API | UI | Compat | Rollback | Tests | Staging ev. | Prod ev. | Owner decision | Failure |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓* (CI/local evidence in the staging row, labelled) | ✓ | ✓ | ✓ |
| 2 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓* "None" | ✓* (a staging SES item sits in the production row) | ✓ | ✓ |
| 3 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 4 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ "None required" | ✓ | ✓ | ✓* (says 422; code returns 409) |
| 5 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 6 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (RG-7, marked not performed) | ✓ | ✓ | ✓ |
| 7 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 8 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ "None" | ✓ | ✓ | ✓ |
| 9 | ✓ | ✓ | ✓ (R, a, b) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ + D | ✓ | ✓ | ✓ | ✓ (today) |
| 10 | ✓ | ✓ | ✓ | ✓ | ✓* "Privacy." | ✓ | ✓ | ✓ | ✓ | ✓* n/a | D ("— (with the implementation)") | ✓ | ✓ | ✓ | ✓* (today only) |
| 11 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 12 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ "None" | ✓ | ✓ | ✓ |
| 13 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ "None" | ✓ | ✓ | ✓ |

#### B.3 Amendment deep checks

**AM-4 (lead re-consent)**, checked against `api/veda/modules/crm/leads/service.py:552-556` and `:824-873`, and `schemas.py:50-60`.

What the text gets right:
- The labelled gaps match the code. `new_version = lead.consent_policy_version != capture.policy_version` accepts *any* different version, which is gap (a).
- Create-time `ConsentCapture` has no `note`, and creation writes only "Lead created", with no consent activity. That is gap (b).
- Immutability is application-level only (`SYSTEM_ACTIVITY_READ_ONLY`, activities.py:186), which is gap (c).
- The current behaviour is honestly labelled "NOT implemented (RR-12, production blocker)".

What is wrong or missing:
- **(i) Wrong status code.** The Failure-behaviour row (AM-4.md:27) says a re-consent outside the accepted cases returns 422. The code and test return **409 INVALID_STATE** (service.py:839; test_consent_dev004.py:78). The target rule (a) also specifies 422, so either the code or the proposal is wrong.
- **(ii) No ordering rule.** "LATER version" is undefined: `published_policy_versions` is a set of strings, and no ordering is proposed.
- **(iii) Privacy gap: erasure versus immutability.** Option (a), a database-level immutability guard on the consent activity, conflicts with erasure. `anonymize()` (service.py:922-929) rewrites `act.description` (the consent note) on every lead activity. AM-4 does not say whether erasure is exempt from the guard. AM-10 lists "consent notes" as PII, which confirms they must be rewritable.
- **(iv) Withdrawal note not in the snapshot.** The superseded-evidence snapshot omits `consent_withdrawal_note`. It is recoverable only from the withdrawal activity's description, which erasure rewrites, and from audit_log. The web-capture IP is kept only as a boolean.

Classification: **INCOMPLETE**. The gaps are honestly labelled, and the owner may accept them for merge; completion is needed before production.

**AM-7 (layered limiter)**, checked against throttle.py, ratelimit.py, net.py, service.py:359-486 and :681-730, routes.py:57/251, and config.py:359-369. Each claim was verified:

| Claim | Where verified | Result |
|---|---|---|
| Network tiers: login 10/min per IP, 30/min per wide network, 5/min per (email-HMAC, /24 or /64); forgot 5/min, 20/min, 3/h | routes.py:57, :251 | ✓ |
| IPv6 limited per /64, wide network /48 | net.py | ✓ |
| Account budget: 10 failures → challenge; 20 → 2 s doubling to 30 s with 429 + Retry-After | throttle.py:124-139 | ✓ |
| The password is not evaluated without the challenge | service.py:411-414, `verify_dummy` | ✓ |
| A successful sign-in does not reset the budget | `record_password_success` only clears the pair | ✓ (a password *reset* does clear it, at :727; harmless) |
| Aggregate: 200 failures in 5 minutes | `deque(maxlen=200)` | ✓ |
| Reset cap: 3 per hour per account, identical 202 | service.py:694 | ✓ |
| Trusted proxy: only configured peers believed; configuration refuses entries broader than /24 or /64 | net.py:client_ip; config.py:368 | ✓ |
| Privacy: HMAC keys only | ratelimit.py `email_attempt_hash`, `unknown:` + hash | ✓ |

Against the prohibited claims:
- It does **not** claim that per-account throttling alone stops distributed guessing. It says so explicitly.
- It does **not** claim the victim can never be disrupted. It discloses FC-05 (without a usable reset link about half of every hour) and the 30 s spacing.
- It does **not** claim a Turnstile outage has no availability impact. It states that the outage is fail-closed and **not** bounded by 15 minutes, and that an aggregate escalation during an outage refuses *every* password sign-in.
- FC-A05 (non-atomic budget) is disclosed.

Residual advisories (DC-DOC-11):
- The cardinality statement ("in-process tables capped at 50 000") covers only throttle.py. The Flask-Limiter `memory://` store has no cap.
- The mitigation "an administrator can issue a reset" can be defeated: an attacker's in-quota forgot request calls `invalidate_action_tokens(..., "PASSWORD_RESET")` (service.py:705), which also kills an admin-issued link.

Classification: **TECHNICALLY SOUND WITH OWNER CONDITIONS**. The FC-05 and FC-A06 wording conditions are closed. Owner acceptance of the disruption bounds and real-Turnstile staging evidence remain.

**AM-9 (hostile sole-Founder veto)**
- Repository-tested behaviour is named with test ids that exist.
- The staging and production rows are separate, and the owner decision (R, a or b) is separate.
- Option R is plainly marked not implemented.
- Gap: there is no notification-provider evidence (delivery of the cancel link to every notified party through SES), and it is not separated from the custodian rehearsal (DC-DOC-12).

Classification: **INCOMPLETE** (a decision request, production-scope; honest).

**AM-10 (PII fields)**, checked against notifications/worker.py:83-127. The claim is accurate: `last_error = f"{type(exc).__name__}: {str(exc)[:300]}"` is unredacted, and the runbook at line 189 tells operators to read it. Gaps:
- It attributes PII only to *provider* errors. Handler exceptions are stored the same way. SQLAlchemy exceptions include `[parameters: …]`, so emails and phone numbers can reach `last_error` from in-app handlers.
- No redaction point is proposed. It should be at write time in the failure transaction.
- It does not address that `last_error` is overwritten on each retry up to DEAD (8 attempts), or the monitoring impact (a redacted error must stay diagnostic for OutboxDead).
- Required tests are "— (with the implementation)".

Classification: **INCOMPLETE** (honestly labelled, production-scope; DC-DOC-9).

**Earlier wording conditions:**
- **AM-11:** the refresh rule is now "exactly as implemented", and step-up does not rotate. N-1 wording is fixed: an image must know 0009 **and** meet the release floor. ✓ Only the provenance is wrong (DC-DOC-5).
- **AM-12:** the custodian CLI refuses the restore as an "unknown target" with no FAILURE event (FC-A10); RESTORE appears only in the payload and in FOUNDER_TRANSITION (FC-A11); restored Founder credentials are disclosed, with an owner option to force resets (FC-A12). ✓
- **AM-13:** the text now says "blocked, not withdrawn" for role-definition changes (FC-08) and discloses the FC-A09 residual. The withdrawal call sites (governance.py:414; users.py:412, 493, 543) match. ✓
- **AM-6:** the release floor applies in every mode, and `release.py` has RELEASE_SEQUENCE=3 with RELEASE_FLOOR=3 in deploy.sh:16, 59. ✓ The docstring says "3 = the final merge-blocker remediation", but `release.py` first exists at `3f5920b`. The `6ec2e76` image cannot report a release and would be refused, so the reviewed commit itself is undeployable (DC-DOC-13).

#### B.4 Owner decision package

What the package does correctly:
- It covers AM-1..13 in both the .md and the .json. Each amendment has the owner decision required, implementation behaviour, risks, conditions, staging and production dependencies, a recommendation, a proposed disposition, "Owner decision recorded: NONE" and "Status: PROPOSED, NOT APPROVED" (13 of 13 rows each).
- No owner decision is recorded; the test asserts `owner_decision_recorded == NONE`.
- TG-01, TG-08, the merge-safety decision and production deployment approval are all PENDING. The gate registry still shows TG-01 "Pending — no verifiable owner approval exists" and TG-08 "Pending — not authorized", and the tree is unchanged since 778aa8f.
- OD-2 and OD-3 are labelled "IMPLEMENTATION ASSUMPTION AWAITING FORMAL OWNER CONFIRMATION (…no decision-log entry, FC-A02)". The repository contains no evidence of a prior approval.

What needs correcting:
- **Reviewer column not reproduced verbatim (DC-DOC-4).** The "Reviewer classification" column adds author annotations inside the reviewer's classification:
  - "— corrected in this text" (AM-7), "— corrected" (AM-11, AM-12, AM-13), "— completed as a decision request" (AM-9) and "— evidence requirements completed" (AM-10);
  - AM-6 is reworded from "(resolve FC-12 release floor)" to "(release floor, FC-12 — now enforced in every deploy mode)";
  - AM-12 gains FC-A11;
  - AM-4 drops "honestly labelled".

  The package restates the reviewer's classifications rather than reproducing them, and it mixes author claims into the reviewer's column.
- **AM-4 disposition.** AM-4 is proposed as APPROVE WITH CONDITIONS while its target rules are not implemented. The owner needs to know that approval would make the current code a tracked deviation from the approved text. The condition implies this but does not say it.

**Verdict: READY FOR OWNER DECISION**, after the DC-DOC-4 and DC-DOC-5 wording fixes. It is not misleading on status or approvals.

#### B.5 Merge-safety plan

- Options A, B and C each state preconditions, repository changes, the Cloudflare implication, verification, rollback, risks, owner action and evidence. ✓
- §2 now lists TG-01, TG-08, the amendment decisions and OD-2/OD-3 (FC-A03 closed). ✓
- The Cloudflare facts match `cloudflare-pages.md:16-20`: production branch `main`, build command `exit 0`, output `dist`, root `/`. The repository adds no `functions/` or `_routes.json`, so no Pages Functions are introduced.

**Option C, tested in a scratch clone (`probes4/docs/sim`, `probes4/docs/mp`):**

1. **Can reach an exact live `dist/`.** A merge-prep tree built from `3f5920b` with main's `dist/` is blob-identical to `origin/main:dist` (34 files). `origin/main` is 13276a0, which ls-remote confirms, and it is the merge-base, so no divergence was hidden. The live Pages deployment itself was not checked (no Cloudflare contact).
2. **The procedure as written does not produce it (DC-DOC-2).** `git checkout origin/main -- dist/` does **not** delete `dist/assets/404.css`, a file that exists only on the branch. `git diff origin/main merge-prep -- dist` then shows 30 lines, and an orphan public `/assets/404.css` would ship. Step 4 of the plan would catch this, but steps 2 and 4 cannot both pass. The fix is `git rm -r -q dist && git checkout origin/main -- dist`, or `git restore --source=origin/main --staged --worktree dist`. That variant gives an empty diff, which I verified.
3. **"CI passes on merge-prep" cannot be met (DC-DOC-1), which confirms the lead reviewer's point (1).**
   - **Unit test fails.** `api/tests/unit/test_governance_docs.py::test_public_intake_disabled` FAILS on the merge-prep tree (reproduced: main's `index.html` has no `veda-api-base` meta), so the CI `api` job fails.
   - **Browser e2e fails too (source-inspected).** `app/e2e/run-all.sh:32-33` serves `$ROOT/dist`. `site.e2e.mjs` asserts `#fallback-whatsapp`, `cf-consent`, `form-summary` and the flag-off validation (lines 95-189). All four are absent from main's `index.html` (counts: main 0, branch 1). It also asserts `/assets/404.css` and "no inline code" at lines 192-204, but main's `404.html` has an inline `<style>`. `axe.e2e.mjs:89-95` scans the flag-off form and the 404 page as well.
   - **`main` goes red.** CI runs on push to `main` (ci.yml:6-7), so `main` would be red after the merge.
   - **What is needed:** a reviewed CI or test adjustment (for example, site assertions keyed to a site-release marker), or an explicit owner acceptance of the red jobs. As written, the plan's verification step fails.
   - **Precondition §2.7 is vacuous under option C.** The intake metas it checks do not exist in main's `dist/`.
4. **Revert trap and hidden divergence (DC-DOC-8), which confirms the lead reviewer's point (2).** Simulated:
   - **Site changes never return by merge.** A later merge of implementation work into `main` does not reintroduce the site changes, because the dist commits are ancestors and the "Keep live site" commit wins. The future site release must re-apply them explicitly. Option A step 2 (`git checkout <sha> -- dist/`) does this, but the plan never states that a merge will not.
   - **Syncing `main` back strips the branch.** Merging `main` back into the implementation branch silently reverts the branch's `dist/_headers` (the CSP is removed) and `404.html`.
   - **Site fixes conflict.** Any later branch fix to a site file, such as FC-15 in `dist/assets/404.css`, gives a **modify/delete conflict** on both merge directions.
   - **The README contradicts the site.** Under option C, the README text added to `main` (lines 73-75, about the `veda-api-base` meta) would describe markup that main's `dist/` does not contain.
5. **Wrong base and integrity check (DC-DOC-6), which confirms the lead reviewer's point (3).**
   - Step 1 branches "from the reviewed implementation commit", which line 6 defines as `6ec2e76`.
   - The integrity check is `git diff 6ec2e76 merge-prep -- ':!dist'` "is empty, plus the closure commit". In fact that diff is 72 files and +10228 lines.
   - Branching from `6ec2e76` would drop the closure fixes: FC-02, FC-04, FC-06, FC-11, and FC-12 (`release.py` and the deploy floor).
   - `6ec2e76` also cannot pass deploy.sh at all (DC-DOC-13).
   - The plan must name the finally certified head (`3f5920b` or later), and the check must be `git diff <certified> merge-prep -- ':!dist'` = empty. I verified this is 0 lines for `3f5920b`.
6. **Other properties hold.** Given the fixes above, option C keeps:
   - no CSP, the inline 404, the WhatsApp-only `app.js`, and intake disabled (the metas are absent);
   - the custom domain and DNS (untouched; only a same-content Pages deployment);
   - a separately reviewable site release later, through option A.
7. **It works with Pages.** It is compatible with "production branch = main, build output dist" and needs no Cloudflare setting change.

**Verdict: OPTION C TECHNICALLY SOUND WITH CONDITIONS.** Before execution, fix DC-DOC-1, 2, 6 and 8 in the plan, and get owner acceptance of the CI approach. It remains the best of the three options for keeping the live site unchanged.

#### B.6 Governance audit

- **FC coverage.** P0-open-issues.md and .json (191 entries) contain all of FC-01..FC-15 and FC-A01..FC-A14. Severities match the final check, and the statuses are plausible:
  - OPEN: FC-01, 03, 07, 09, 10, 13, 14, 15;
  - RESOLVED as claimed by the author (verified by other reviewers, not here): FC-04, 06, 11;
  - RESOLVED IN CODE with staging or rehearsal remaining: FC-02, 12;
  - DISCLOSED with an owner decision: FC-05, 08, A05, A06, A09, A10, A11, A12;
  - PENDING OWNER CONFIRMATION: FC-A02.
- **Gates.** TG-01 and TG-08 are PENDING in the registry and in open issues, and the certified gate registry is unchanged. No gate is closed.
- **Owner approval.** Nothing claims owner approval of an amendment, a gate, a merge or a deployment.
- **Residue (DC-DOC-7).** Legacy statements "OD-2 given" and "OD-3 given" remain in `P0-final-merge-blocker-matrix.md:66, 86` (and in the .json at lines 96 and 147). `P0-implementation-deviations.md:17-18` still reads "n/a (owner decision OD-2/OD-3)". These contradict FC-A02's PENDING status.

#### B.7 Document findings

| ID | Severity | Title | Evidence | Remediation | Implementation change? | Blocking scope |
|---|---|---|---|---|---|---|
| DC-DOC-1 | **MAJOR** | Option C's verification "CI passes on merge-prep" cannot be met. On main's `dist/`, `test_public_intake_disabled` fails (reproduced), and `site.e2e.mjs`/`axe.e2e.mjs` assert the new site (404.css, the flag-off form). `main` CI would turn red. | P0-merge-safety-plan.md:111; test_governance_docs.py:115-118; app/e2e/run-all.sh:32-33; site.e2e.mjs:95-204; ci.yml:6-7 | Add a reviewed CI/test adjustment (site assertions conditional on the site release, or a separate site job), or have the owner accept red jobs explicitly. Restate §2.7 for option C. | Tests/CI only | Merge (if option C is chosen) |
| DC-DOC-2 | MINOR | Option C step 2 (`git checkout origin/main -- dist/`) leaves `dist/assets/404.css`, so step 4's empty-diff check fails and an orphan public file could ship. | P0-merge-safety-plan.md:99-101; simulated in probes4/docs/sim | Use `git rm -r dist && git checkout origin/main -- dist` or `git restore --source=origin/main --staged --worktree dist`. | No | Merge (option C) |
| DC-DOC-3 | MINOR | The SHA-existence test never runs in CI (depth-1 checkout skips it). It covers only 8 docs and lowercase 40-hex, and checks existence, not correctness. A bad SHA in the runbooks, deviations, README or open-issues.json, or a short SHA, passes. | test_governance_docs.py:21-30, 82-99; ci.yml checkout without fetch-depth; evidence pytest-sqlite.txt:11 | Set `fetch-depth: 0` for the api job (or fail rather than skip in CI when `CI=true`). Extend coverage to all governance docs and short SHAs, and pin "reviewed" SHAs to the known value. | Test/CI only | Staging (governance-gate integrity); advisory for merge |
| DC-DOC-4 | MINOR | The owner package and the amendments README restate the reviewer classifications with author annotations ("— corrected", AM-6 reworded, FC-A11 added to AM-12) instead of reproducing them. | P0-owner-decision-package.md:21-33; .json reviewer_classification; amendments/README.md:7-19 | Reproduce the final-check classification verbatim, and put the author's correction claims in a separate column. | No | Owner decision (before presentation) |
| DC-DOC-5 | MINOR | Provenance: "Implemented at this commit" and "added at this commit", where the package defines "this commit" as the closure commit, but the code dates from `6ec2e76`. | AM-7/11/12/13.md:17; amendments.json:204, 329, 361, 391; owner-package.md:130, 190, 205, 220, :15 | Replace with "Implemented at 6ec2e76, unchanged since". | No | Owner decision |
| DC-DOC-6 | MINOR | The merge plan bases merge-prep on the "reviewed implementation" `6ec2e76`, and its integrity check `git diff 6ec2e76 merge-prep -- ':!dist'` (72 files, not empty) is wrong. Branching there would drop the closure fixes, including the release floor. | P0-merge-safety-plan.md:6, 98, 121 | Name the certified head (currently `3f5920b`, or the SHA this check certifies) and use `git diff <certified> merge-prep -- ':!dist'` = empty. | No | Merge (option C) |
| DC-DOC-7 | MINOR | Legacy "OD-2 given" and "OD-3 given" statements remain (FC-A02 residue). | P0-final-merge-blocker-matrix.md:66, 86; .json:96, 147; P0-implementation-deviations.md:17-18 | Annotate as "implementation assumption awaiting owner confirmation (FC-A02)". | No | Owner decision |
| DC-DOC-8 | MINOR | Option C does not document the resulting `main`/branch `dist/` divergence. Later merges never reintroduce the site; syncing `main` back strips the branch's CSP and 404 fix; site fixes such as FC-15 give modify/delete conflicts; the README text on `main` would describe absent markup. | Simulated in probes4/docs/sim; README.md:73-75 (3f5920b) | Add a divergence section: re-apply by explicit checkout (option A) and never by merge; forbid or guard `main`→branch syncs until the site release; route site fixes through the site-release branch; adjust the README note. | No | Merge (option C) |
| DC-DOC-9 | MINOR | AM-10 attributes `last_error` PII only to provider errors. Handler/SQL exceptions (SQLAlchemy `[parameters: …]`) are stored the same way. No redaction point, retry or monitoring behaviour is proposed. | worker.py:111-127; api-runbooks.md:189; AM-10.md:15 | Extend AM-10: redact at write in the failure transaction for all exceptions; keep the class plus a sanitized code for OutboxDead diagnosis; add tests. | Later implementation | Production |
| DC-DOC-10 | ADVISORY | Stale report lines: header "Reviewed implementation 9236aa3"; line 436 refers to `docs/architecture/amendments/`. | P0-implementation-report.md:10, 436 | Label as historical or update. | No | None |
| DC-DOC-11 | ADVISORY | AM-7 residuals: the cardinality cap excludes the Flask-Limiter memory store; an attacker's in-quota forgot request invalidates an admin-issued reset link. | ratelimit.py:48-54; service.py:705 | Disclose in AM-7. | No | Production |
| DC-DOC-12 | ADVISORY | AM-9 lacks notification-provider evidence (cancel-link delivery to all notified parties). AM-1 and AM-2 put CI or staging items in the wrong evidence rows. | AM-9.md, AM-1.md, AM-2.md evidence rows | Separate the provider evidence and relabel the rows. | No | Production |
| DC-DOC-13 | ADVISORY | `release.py` docstring "3 = the final merge-blocker remediation", but `6ec2e76` has no `release.py`, so the reviewed commit is undeployable; only `3f5920b` or later can pass deploy.sh. | api/veda/release.py:1-9; deploy.sh:49-60 | Correct the docstring and state it in AM-6 and the runbook. | Comment only | None |
| DC-DOC-14 | MINOR | AM-4 wording: the failure row says 422 while the code and tests return 409; "later version" has no ordering rule; option (a) immutability conflicts with erasure's rewrite of consent notes; the withdrawal note is missing from the superseded snapshot. | AM-4.md:15, 27; leads/service.py:839, 842-853, 922-929; test_consent_dev004.py:78 | Correct the code to match, define the version ordering, exempt the erasure rewrite (or choose option b), include the withdrawal note. | Later (RR-12) | Owner decision (wording) / production |

**Counts:** BLOCKER 0, MAJOR 1, MINOR 9, ADVISORY 4.

**Merge-scope items:**
- DC-DOC-1, DC-DOC-2, DC-DOC-6 and DC-DOC-8 matter only when option C is executed. They are plan and CI fixes, not implementation changes.
- DC-DOC-4, DC-DOC-5, DC-DOC-7 and DC-DOC-14 are wording fixes to make before the package goes to the owner.
- Nothing here requires changing production code before merge.

### Appendix C — Technical corrections

#### C.1 FC-02

Change under review:
- `kernel/logging.py:33-44`: `_scrub` skips `exempt_metric_keys(event_dict)`.
- `kernel/metrics.py:25-46`: `APPROVED_METRICS`. A key is exempt only when all three hold: it is declared in `_aws.CloudWatchMetrics[0].Metrics`, it is in the approved set, and its value is an `int`/`float` that is not a `bool`.

###### Scrubber matrix (REPRODUCED, `fc02/scrub_matrix.py`)

| Case | Result |
|---|---|
| Approved `NoEffectiveRecoveryAdmin` = 1.0 inside EMF | kept, `1.0` |
| Approved name + string value `"ABCD-EFGH-2345"` (collision/smuggle attempt) | `[REDACTED]` |
| Approved name + `True` / dict / list | `[REDACTED]` |
| Approved name, int, **no** `_aws` block (plain log key) | `[REDACTED]` |
| Approved name + int 123456 inside a forged `_aws` block | kept (numeric only; see note) |
| Forged `_aws` declaring `recovery_code` + int | `[REDACTED]` (not in approved set) |
| Forged `_aws` (approved) + sibling `recovery_code` string | metric kept; `recovery_code` `[REDACTED]` |
| Unapproved denylisted metric `RecoveryCodesIssued` | `[REDACTED]` |
| Flat `recovery_code`, `recoveryToken`, `recovery_session_id`, `my_recovery_secret`, `RecoveryCode` (int) | all `[REDACTED]` |
| Nested dict or list holding `recovery_code` / `recovery_session_id` | **not scrubbed.** This was already true at 6ec2e76 (the loop never recursed). It is not a regression. No current call site logs nested structures (DC-TECH-8) |
| Extra key inside `_aws` block | not scrubbed (same pre-existing top-level-only behaviour) |
| Dimension key containing a denylist word (`ErrorCode`) | `[REDACTED]` (no current dimension is affected) |

Collision assessment:
- An attacker-controlled key named after an approved metric cannot carry a string, bool or structure.
- It passes only as a number, and only when code also builds an EMF `_aws` declaration.
- No request path builds `_aws` from input, and recovery codes are alphanumeric. Residual risk is negligible.

###### Pipeline checks (REPRODUCED)

- **CLI subprocess.** `python -m veda.cli maintenance invariants` on a fresh migrated DB, exit 0 (`fc02/cli/inv.out`). It emitted this EMF line:
  `{"_aws":{…"Namespace":"Veda/API","Dimensions":[[]],"Metrics":[{"Name":"GovernanceInvariantFailures"…},{"Name":"NoEffectiveRecoveryAdmin"…}]},"GovernanceInvariantFailures":2.0,"NoEffectiveRecoveryAdmin":1.0}`
  The line carries no identity or secret.
- **Scheduler path.** `run_scheduled_job('invariants')`, a real child process, emitted `NoEffectiveRecoveryAdmin: 1.0` and `ScheduledJobFailed: 0` (`fc02/cli/sched.out`).
- **Alarm consumers.** Runbook §9 says namespace `Veda/API` and lists `GovernanceInvariantFailures / NoEffectiveRecoveryAdmin` with no dimensions. The emitted line has the same namespace and dimension set `[[]]`, so they match.
- **Tests.** `test_metric_redaction.py` and `test_RR07_cli_jobs_emit_their_metrics[invariants-NoEffectiveRecoveryAdmin]`: 13 passed, 2 PG-skipped.
- **Docs.** They claim no completed routing or test-fire. The runbook says "Alarm routing and test-fire remain RG-5". Open-issues says "ALARM ROUTING AND TEST-FIRE REMAIN RG-5 (STAGING)".

Verdict: **FC-02 RESOLVED.**

#### C.2 FC-04

Changes under review:
- `db.py:108-118`: `tx_time` is now read after `session.connection()`, so on SQLite it comes after `BEGIN IMMEDIATE`.
- `audit_hook.py:234-237`: `updated_on = max(now, created_on)`.

###### Revert tests (REPRODUCED, `revert_*` copies, SQLite)

| Copy | clock-order test | deterministic interleave test | concurrent test |
|---|---|---|---|
| target (both fixes) | pass | pass | pass |
| both reverted | **FAIL** (`['clock','begin']`) | **FAIL** (CHECK `ck_user_action_token__updated_after_created`) | **FAIL** 2 of 3 runs (IntegrityError) |
| guard reverted only | pass | **FAIL** | pass |
| clock fix reverted only | **FAIL** | pass | pass |

###### Repeated runs (REPRODUCED)

| Run | Result | Artefact |
|---|---|---|
| SQLite, target, 30× | 30 × "3 passed" | `fc04/sqlite30.txt` |
| Embedded PG, target, 10× | 10 × "3 passed" (no deadlock or hang) | `fc04/pg10.txt` |
| PG, guard reverted, 10× | deterministic test fails 10/10; the concurrent test **passes 10/10** | `fc04/pg10_revert_guard.txt` |

The last row shows that on PostgreSQL the concurrency test does not exercise the race. Only the deterministic test covers it there.

###### My own real two-session interleave (no `tx_time` injection, `fc04/test_probe_fc04.py`)

Steps: session A reads its clock, B creates and commits an `app_user`, then A updates that user.

| Engine | Guard | Result |
|---|---|---|
| SQLite | present | B blocks on A's write lock ("database is locked"). Serialized, as designed |
| PG | reverted | `CheckViolation ck_app_user__updated_after_created`, the whole unit rolled back (no partial write) |
| PG | present | commits (`fc04/pg_interleave.txt`) |

Values from the PG run with the guard present:
- A's `tx_time` = `…46.574343`
- `created_on` = `updated_on` = `…46.576584`
- Audit rows: `UPDATE performed_on …46.574343` and `CREATE performed_on …46.576584`

###### Update paths (SOURCE-INSPECTED)

- The ORM guard covers every `AuditedBase` update, which is every contract table.
- `audit_hook.bulk_mutate` is a ban (it raises), not an update path.
- These raw Core updates set `updated_on=now` with no guard:
  - `kernel/sequences.py:39-51`: seeded rows, practically safe.
  - `kernel/migration_support.py:329-333, 350-362, 379-385` (sync-permissions bulk `app_user` update, with `now` read at `:301`).
  - See DC-TECH-6.
- Business stamps (`deleted_on`, `invalidated_on`) still use `tx_time`. Only `updated_on >= created_on` is constrained, so no constraint breaks.

###### Side effects

- On PostgreSQL, when the guard fires, `updated_on` is no longer the unit's single clock reading. This contradicts 03 §2.8 ("UPDATE → updated_on = tx_time").
- The UPDATE audit row is `performed_on` **earlier** than the entity's CREATE audit row, so the audit history (ordered by `performed_on`) shows UPDATE before CREATE.
- `ck_audit_log__performed_matches_contract` still holds, because the audit row's own `created_on = performed_on = tx_time`.
- See DC-TECH-5.

Verdict: **FC-04 RESOLVED.** The constraint can no longer be violated through ORM paths on either engine, the deterministic tests fail without the fix, and there is no deadlock or partial write. The PostgreSQL-only residuals are DC-TECH-5 and DC-TECH-6.

#### C.3 FC-06

Changes under review:
- `http.py:43-45`: `AUTH_MODES`.
- `http.py:485-486`: declaration check.
- `app.py:100-101`: startup check.
- `http.py:583-584`: dispatch check.

###### Declaration / startup / runtime matrix (REPRODUCED, `fc06/matrix.py`, `fc06/matrix.txt`)

| Declaration | Outcome |
|---|---|
| bearer + permission | accepted |
| bearer, no permission, no RBX | startup rejected |
| public + registered RBX-006 pair | accepted |
| public + permission / any_of | startup rejected ("cannot be enforced") |
| public, no RBX | startup rejected |
| optional + registered RBX-004 pair | accepted |
| optional, RBX pair not registered | startup rejected |
| optional + permission | startup rejected |
| optional, no RBX | startup rejected |
| `''`, `' '`, `'Public'`, `'BEARER'`, `'Bearer'`, `'public '`, `'none'`, `'cookie'`, `'anonymous'`, `None`, `0`, `'publıc'` (dotless ı) | declaration rejected (exact, case-sensitive; no canonicalization) |
| spec mutated to `'Public'` after declaration, before startup | startup rejected |
| real app: `/api/v1/auth/me` spec mutated after startup to `Public` / `BEARER` / `''` / `none` | **500**. Dispatch fails closed before any session or handler runs. With `bearer` restored: 401 |

Route inventory:
- Runtime inventory at 6ec2e76 and at 3f5920b is **byte-identical**: 105 routes (bearer 89, public 14, optional 2) (`fc06/inv_*.json`).
- `test_lint.py`: 19 passed.

Verdict: **FC-06 RESOLVED.**

#### C.4 FC-11

Full matrix in `fc11/results.txt` (REPRODUCED). "+err" means a new type error was injected.

| Case | Exit | Correct? |
|---|---|---|
| baseline | 0 | yes |
| +err control | 1 | yes |
| mypy missing (venv without mypy) | 2 | yes |
| mypy crash (exit 139) | 2 | yes |
| invalid TOML / duplicate table | 2 | yes |
| `python_version="banana"` | 1 (outside reviewed config) | yes |
| shadow `mypy.ini` / `setup.cfg [mypy]` / `.mypy.ini` (+err) | 1 | yes |
| `strict_optional=false` / `follow_imports="skip"` / global `ignore_missing_imports` / `plugins` / `check_untyped_defs=false` | 1 | yes |
| override `veda.platform.auth.service` `strict_optional=false`; `veda.*` override; third-party `follow_imports` | 1 | yes |
| override `module="*"` `ignore_missing_imports` + missing `veda.*` import | 1 (mypy still reports it) | yes |
| `exclude` / `files=["veda/kernel"]` | 2 (file count 88<89, 24<89) | yes |
| `# mypy: ignore-errors`, `# mypy: disable-error-code=…`, `# MYPY:` | 1 | yes |
| bare `# type: ignore`, `# type: ignore [code]`, coded without justification, compact `#type:ignore[x]#x` | 1 | yes |
| `# type: ignore[misc]` on the wrong code / multi-code | 1 (`warn_unused_ignores`) | yes |
| **`# type: ignore[return-value]  # x` (trivial justification) + new error** | **0** | allowed by design (DC-TECH-2) |
| new file with error | 1 | yes |
| renamed file (baseline unchanged) | 2 | yes |
| baseline +1 (ceiling unchanged) | 2 | yes |
| CEILING raised in the tool + baseline +1 | 0 | reviewed code change; visible in the diff |
| `--update` with `CI=true` | 2 | yes |
| `--update` with only `GITHUB_ACTIONS=true` | 0 | DC-TECH-4 (GHA always sets CI) |
| `--update` when worse | 1 | yes |
| local `mypy/` package or `mypy.py` in cwd; `site-packages/mypy` inside the tree via PYTHONPATH (+err) | 1 (`-I` isolation) | yes |
| fake **installed** mypy printing "Success" | 0 | supply-chain; CI installs `--require-hashes` (1584 hashes) |
| **`veda/platform/auth/service.pyi` stub + err in `service.py`** | **0** (95 errors: the module's 62 recorded errors and the new one vanish) | **no, DC-TECH-1** |
| **new `veda/probe_stub.py` with error + `.pyi`** | **0** | **no, DC-TECH-1** |
| error under `if not TYPE_CHECKING:` | 0 | DC-TECH-3 |
| `MYPYPATH` stub dir | 1 | yes |

- Allow-list: only 2 inline ignores exist (`logging.py:114`, `passwords.py:48`). Both are coded and justified.
- Historical findings are visible: 157 errors across 24 files.
- The baseline cannot grow without editing `CEILING` in the tool.
- Unit tests: `test_mypy_ratchet.py`, 35 passed.

Verdict: **FC-11 NOT RESOLVED.**
- Every vector named in FC-11 is closed.
- But a same-class whole-module suppression, a `.pyi` stub, still passes with exit 0 and new errors.
- That is exactly the "partial codebase checked" condition. The file-count check does not catch it, because mypy counts the stub.
- The fix is small (DC-TECH-1).

#### C.5 FC-12

Method: stubbed `docker` on PATH (`fc12/shim/docker`).
- It runs the **real** `veda.cli` from a `git archive` of each SHA against a migrated DB (0009).
- It logs every compose call (`fc12/results.txt`).

| Image | Normal deploy | `--rollback` | Calls before exit |
|---|---|---|---|
| 9236aa3 (no `schema-status`) | exit 1, refused | exit 1, refused | schema-status only |
| 2f6b59a (no `schema-status` command at this SHA) | exit 1, refused | exit 1, refused | schema-status only |
| 6ec2e76 (knows 0009, **no `release` field**) | exit 1 ("release 'invalid'") | exit 1 | schema-status only |
| 3f5920b (release 3) | exit 0, all 6 steps | exit 0, state head | full |
| garbage output / no output / trailing non-JSON line | exit 1 | exit 1 | schema-status only |
| release `"3"` / `3.0` / `True` / `-1` | exit 1 | exit 1 | schema-status only |
| release 99 / 10**30 | exit 0 | exit 0 | full (correct) |
| nonexistent tag | exit 1 | exit 1 | schema-status only |
| env `RELEASE_FLOOR=0 ROLLBACK_FLOOR=0001_initial` | exit 1 (ignored) | exit 1 | schema-status only |
| `BASH_ENV` presetting `readonly RELEASE_FLOOR=0` | exit 1 (`readonly variable`, set -e) | — | none |
| `--force` / double `--rollback` | exit 1 (treated as a tag) | — | schema-status only |

- Every refusal happens at step 0, before deploy-check, snapshot, stop, migrate or up.
- The floors are `readonly` constants (`deploy.sh:16-17`) with no flag or env override.
- Readiness validation (step 5) is unchanged.

On 6ec2e76 being refused:
- The refusal is conservative but correct under the stated policy. The image cannot report a release.
- The runbook says "until a later release exists, there is no valid N-1 image".

Runbook and docs:
- §2.1 prohibits both earlier images in every mode.
- §2.2 documents forward-fix.
- §2.3 says "has not been rehearsed (RG-7 open)".
- The implementation report says "no rehearsal is claimed", and the owner package keeps RG-7 as a production condition.

Tests: `test_deploy_floor.py`, 20 passed. The RR17/floor tests pass too.

Verdict: **FC-12 RESOLVED.** Advisory DC-TECH-10 applies.

#### C.6 health.py

REPRODUCED:
- Each of these makes `schema-status` print `state: "missing", current: null` **with exit 0**:
  - an unreachable PostgreSQL (`127.0.0.1:1`);
  - an unopenable SQLite path;
  - an SQLite DB held under an EXCLUSIVE lock.
- The `--require-known` floor still reports correctly, because it reads image code only.

Every caller traced:
- `cmd_schema_status` (`cli/main.py:252`) is the only caller.
- Readiness (`health.py:85-103`) runs its own query and reports `db: unavailable` / 503. It is unaffected.
- `deploy.sh`:
  - Step 0 uses only `release` and the exit code, which do not depend on the DB. That is correct.
  - The rollback branch refuses any state other than head/ahead, so "missing" is refused (fail closed).
  - The normal path's `migrate` fails on a real outage.

No automated unsafe decision was found. The operator procedure (runbook §2.3 step 2) is misleading:
- It documents the output as `{current, image_head, state}`, which is stale because `release` is missing.
- It does not describe `missing`. An outage looks like "never migrated" (DC-TECH-7).

### Appendix D — Regression

#### D.1 Backend

The prior column is taken from `findings3/*.md` and the logs in `probes3/`. Every "now" figure is a junit count from `out/j-*.xml`.

| Probe set | Engine | Prior (6ec2e76) | Now (3f5920b) | Changed outcome? |
|---|---|---|---|---|
| Auth head suites (mfa_binding, auth, mfa, auth_remediation, layered_limiter, final_merge_blockers) | SQLite | 115 passed | **115 passed** | No |
| | PG | 115 passed | **115 passed** | No |
| IR-01 20-item + adjacent (rr_ir01/misc/race/dev007) | SQLite | 52 passed | **52 passed** | No (race-winner mix only, see below) |
| | PG | 52 passed | **52 passed** | No |
| Limiter 20-item + RR-08 + races + reset-DoS (fc_limiter 19, fc_refresh 5, fc_race2 3, fc_resetdos 1) | SQLite | 28 passed | **28 passed** | No |
| | PG | 27 passed (resetdos was SQLite-only) | **28 passed** | **Improved:** PG race IntegrityErrors are gone (FC-AUTH-4) |
| RBAC head (rbac 33, founder_governance 16, governance_remediation 11) | SQLite / PG | 60 / 60 | **60 / 60** | No |
| RR-02/RR-03/RR-08 author tests (in final_merge_blockers, run within auth head) | both | 22 / 22 | passed / passed | No |
| Reviewer P01–P17 (`test_probe_rbac`) | SQLite / PG | 22 / 22 (152 probe records) | **22 / 22**; 152 records, **0 differing** after id/time normalisation | No |
| Reviewer N01–N17 (`test_probe2_new`) | SQLite / PG | 17 / 17 | **17 / 17**. PG: 0 records differ. SQLite: only N13's race winner flips (a↔b; rows=1 either way) | No |
| R01–R09, X01–X13 (`test_probe3_final`) | SQLite / PG | 22 / 22 | **22 / 22**. Only race-winner distributions differ (R05–R07, X10–X13). Invariants hold (one live address holder, one transition). | No. See DC-REG-1 |
| Audit failure injection (`test_fc_audit`, F1–F9, C11–C13, T1–T3) | SQLite / PG | 19 / 19 | **19 / 19**. All `FCA` lines match the prior final results. `run_sqlite.txt` shows C11b ok=False, but that is an earlier probe iteration; `findings3/audit.md` reports ok=True, and it is ok=True now. PG F6 is the same (one loser fails safely, one announcement). | No |
| Audit head (audit_security, chain_integrity, archive_ordering, leads, leads_remediation, consent_dev004, final_merge_blockers) | SQLite / PG | 135 / 135 (2 skip) | **136 / 136** (2 skip on PG). +1 is the new `test_archive_ordering` case. | No |
| UUIDv7 / JCS (`test_ids_time_jcs`) + `test_schema` | SQLite / PG | 42 / 42 (2 skip), re-run here at 6ec2e76 | **42 / 42** (2 skip on PG) | No |
| New `test_timestamp_race` (FC-04) | SQLite / PG | at 6ec2e76 control: **fails 2–3 of 3** per run | **3 / 3 passed** ×4 runs per engine | Fix confirmed |
| Optional-auth / route startup validation (`routecheck.py` + `routecheck2.py`) | n/a | 15 cases as before, **plus** `Public`/`cookie`/`none` + permission ACCEPTED with anonymous 200 (FC-AUTH-2) | The 15 cases are identical. Every non-allow-listed mode (`Public`, `cookie`, `none`, `BEARER`, `'optional '`, `''`, `None`, `public​`) is **REJECTED at decoration**. A spec mutated to `cookie` after decoration is REJECTED by `create_app`. | **Improved:** FC-AUTH-2 closed |
| Route inventory (105 routes: 89 bearer, 14 public, 2 optional) | n/a | `inv_fc.json` | `out/inv_dc.json` is **byte-identical** | No |
| Full API suite (probes excluded) | SQLite | 535 passed; 1 intermittent `ck_user_action_token__updated_after_created` failure in 1 of 9 runs (FC-AUTH-8) | 611 collected. 591 passed and 1 skipped on the first run. The 19 `test_governance_docs`/`test_metric_redaction` failures were my copy missing `docs/`; after copying docs they are 24 passed and 1 skipped. **0 real failures.** | No |
| | PG | not run | **600 passed, 11 skipped, 0 failed** (see §1a) | — |

###### 1a. Full API suite on PostgreSQL

Embedded PostgreSQL, probes excluded, with `docs/` present: **611 collected, 600 passed, 0 failed, 0 errors, 11 skipped** (SQLite-only cases), exit 0 (`out/j-full-pg.xml`). SQLite after the docs fix: 610 passed and 1 skipped. The intermittent FC-AUTH-8 constraint failure did not occur in either run.

The embedded PostgreSQL clusters shut down when the runs finished. The pre-existing servers on 127.0.0.1:55432 and :55433 were still listening; I did not start, use or stop them.

###### 1b. Key numbers (distributed guessing, RR-04; RR-08), identical on both engines unless stated

| Item | Prior | Now |
|---|---|---|
| #3 attacker solving Turnstile, 1 simulated hour, rotating /48s | 94 evaluated, 60× 429, 154 requests | **94 / 60 / 154** |
| #12 RR-AUTH-1 re-run (40 guesses / 8 /64s) | 8–10 evaluated, rest captcha_required; correct pw needs Turnstile | **8 unchallenged, 32 captcha_required**; without Turnstile 401 captcha, with Turnstile 200 MFA_REQUIRED |
| #1 / #2 / #7 / #8 / #9 / #10 | [401×5, 429×7]; 30 then 429; 9 unchallenged; 30 then 429 (/64), 35×401 (/48); spoofed headers keyed on the peer; trusted peer: 12 networks | **identical** |
| #11 victim DoS (MFA victim every 45 s for 30 min) | 31 OK / 9× 429, attacker 64 requests | **31 / 9 / 64** |
| #14 bad Turnstile ×15 | budget 10 | **10** |
| #16 MFA verify 12 wrong, then correct | 10×401, 429, 429; correct → 429; 200 after 16 min | **identical** |
| #17 40 parallel guesses, budget recorded | SQLite 10; PG 13 (FC-AUTH-5) | SQLite **10**; PG **15**. Same advisory overshoot by thread count; the number varies with timing. |
| #19 cardinality | 50 001 cap, 3 000 accounts | **identical** |
| #20 known == unknown | True | **True** (login and forgot) |
| Reset-link DoS (FC-AUTH-1) | [(202,0)]×3 | **[(202,0)]×3** (unchanged; still open) |
| RR-08 path A / change-password successor | live 1, linked 1; old cookie < 20 s → 200 with no Set-Cookie; 2nd use → TOKEN_REUSE; > 21 s → 401 | **identical** on both engines, which confirms the 20 s grace window is not shifted |
| RR-08 cross-session / logout-all / reset / atomicity / token material in logs | S2 untouched; 401/401; 500 with rollback and nothing committed; 0 | **identical** |
| PG `pwchange ‖ refresh(old)` ×10 | 7× 204, 1× 409, **2× 500 IntegrityError** `ck_refresh_token__updated_after_created` | **10× 204, 0 integrity errors**, in 4 runs (40/40). The 6ec2e76 control on the same machine gave 7/10, 9/10 and 9/10, with 500s. |

###### 1c. Did FC-04 change timestamp-dependent behaviour?

Checked by probe:

- Refresh grace window: < 20 s still passes and 21 s still fails.
- Token expiry and reuse detection: unchanged.
- Throttling windows: every limiter number above is unchanged, including 15-min and 16-min recoveries.
- Cooling-off `not_before`: P14, N03, N05 and N08 records are the same apart from the wall-clock value.
- Invite TTL (X04): +3 days, as before.
- Chain ordering: chain_integrity, archive_ordering and fc_audit all pass.

SOURCE-INSPECTED:

- `max(now, created_on)` only affects `updated_on`.
- The only timestamp CHECK in the schema is `updated_on >= created_on` (`kernel/base.py:151`).
- `deleted_on`, `used_on` and `invalidated_on` still take `tx_time`, and nothing constrains them against `created_on`.
- On SQLite, reading the clock after BEGIN IMMEDIATE makes `tx_time` monotonic in commit order. The only observable effect is that time spent waiting on the lock is no longer counted inside the unit's clock.
- PostgreSQL still re-reads the clock after the governance advisory lock (`guards.py:219-228`).

**No adverse behavioural change was found.**

Race-winner distributions: 3 runs of target and control per engine (`out/race-*`). Both trees show the same outcome families: for example SQLite `confirm‖restart` gives 401/200 or 200/409, and PG gives 409 VERSION_CONFLICT variants. The 4th request in the IR-01 A01 recovery-code replay now sometimes returns `MFA_CHALLENGE_INVALID` instead of `MFA_RECOVERY_INVALID`. Both are 401, and exactly one RECOVERY session is created. This is interleaving, not a change in behaviour.

#### D.2 Frontend

| Command | Exit | Result | Prior |
|---|---|---|---|
| `npm ci` | 0 | 0 vulnerabilities | 0 |
| `npm run lint` | 0 | clean | clean |
| `npm run typecheck` | 0 | clean | clean |
| `npm run lint:tokens` | 0 | "no raw colour values outside src/design-system/tokens.css" | same |
| `npm run test:contrast` | 0 | 58 pairs, light and dark | same |
| `npm test` (wtr) | 0 | 6/6 files, **52 passed, 0 failed** | 52 / 0 |
| `npm run build` | 0 | tsc + vite built | built |
| `npm audit` | 0 | 0 vulnerabilities | 0 |
| `npm audit --omit=dev` | 0 | 0 vulnerabilities | 0 |

#### D.3 Browser

| Script (`API_PYTHON=$S/venv2/bin/python bash app/e2e/run-all.sh`, exit 0) | Now | Prior |
|---|---|---|
| workspace.e2e.mjs | **7/7** journeys | 7 |
| access.e2e.mjs | **16/16** | 16 |
| site.e2e.mjs | **31/31** | 31 |
| axe.e2e.mjs | **12/12** (0 serious/critical in scope; 18 tracked outside the form, OI-11) | 12 |

The site probes were re-run with `site-server.mjs <abs dist> 8211 --keep-uir`, which applies the exact `dist/_headers`:

- **RR-01 probe (`probe-rr01.mjs`)** compared with `probes3/fe/out/fc-exact-rr01.json`: **0 differences** apart from the port number.
  - `/no-such-page`, `/privacy` and `/deep/nested/unknown/path?x=1` → 404. `/404.html` → 200.
  - **0 CSP violations** from both the listener and the console, on home and on every 404 variant.
  - The 404 page is styled: `/assets/404.css` is loaded, background rgb(251,247,239), grid layout, one column at 360 px with no overflow, and a visible focus ring.
  - axe: 0 violations.
- **RR-11 probe (`probe-rr11.mjs`)** compared with `fc-rr11.json`: **0 differences** in any field, including the raw and decoded wa.me URLs.
  - Empty, whitespace-only, missing-name, missing-phone and all 7 invalid-phone inputs → `opened=0`.
  - Valid input → `https://wa.me/919515125153?text=…`, encoded exactly as before (`match: true`).
  - **0 fetch/XHR** and 0 non-static requests in every case.
- **dist identity:**
  - `git diff 6ec2e76 3f5920b -- dist app` is empty.
  - `diff -r dc/dist fc/dist` shows no differences.
  - The working copy of dist is identical to `dc/dist`.
- **Public API disablement:** `dist/index.html:11-12` has `veda-api-base` = "" and `veda-turnstile-sitekey` = "". Both are empty.
