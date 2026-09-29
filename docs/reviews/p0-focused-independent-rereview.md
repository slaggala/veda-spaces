# P0 Focused Independent Re-review — Veda Spaces

Review ID `VEDA-SPACES-P0-FOCUSED-INDEPENDENT-REVIEW-02` · 2026-09-29 · Machine-readable version: [p0-focused-independent-rereview.json](p0-focused-independent-rereview.json) · Original review: [p0-independent-architecture-review.md](p0-independent-architecture-review.md)

This is an independent re-review of the remediation at the exact SHA. The author's summary, remediation matrix and validation report were treated as claims. Every conclusion below comes from reading the architecture at the remediation SHA in a detached worktree. No architecture, `dist/` or implementation file was changed, and nothing was merged or deployed.

## Summary

| Item | Value |
|---|---|
| A. Remediation SHA reviewed | `c3aae47a7d9b12fc0cb1491865991fde28abcf55` |
| B. Review branch | `review/p0-foundation-independent-review` (was `7515b23`; this commit adds only the two re-review files) |
| C. Re-review commit | Recorded in the review branch history |
| D. Push status | Normal push to `origin` (see the final response) |
| E. Repository and diff | Pass (§1) |
| F. Original findings | RESOLVED 31 · REGRESSION INTRODUCED 1 · ACCEPTABLY TRACKED 1 · PARTIALLY RESOLVED 1 · ACCEPTED (rationale documented; gate not measurable) 1 (35 of 35 reconciled) |
| G. F-01 | **RESOLVED** |
| H. F-02 | **RESOLVED** (test gaps in N-03) |
| I. F-03 | **RESOLVED** (the dual-control eligibility defect is recorded as new finding N-01) |
| L. Recount | 221 total · 208 P0 · 10 P1 · 3 P2. 18 added, 4 promoted, 0 removed. **Matches the author's claim.** |
| M. Coverage (P0, independent) | Fully 202 · Partial 3 · Contradictory 1 · Not testable pending owner input 2 · Referenced-only 0 · Not covered 0. **The author's 206 is not confirmed; the independent count is 202.** |
| O. New findings | BLOCKER 0 · MAJOR 0 · **MINOR 4** (N-01…N-04, including 1 regression) · ADVISORY 9 |
| U. **Verdict** | **CERTIFIED WITH MINOR CONDITIONS** |

## 1. Frozen-SHA and diff verification

| Command | Result |
|---|---|
| `git fetch origin` | no new refs |
| `git cat-file -t c3aae47a7d9b12fc0cb1491865991fde28abcf55` | commit |
| `git rev-parse origin/architecture/p0-foundation-freeze` | c3aae47a7d9b12fc0cb1491865991fde28abcf55 (the remediation commit is the branch head) |
| `git merge-base --is-ancestor 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e c3aae47a7d9b12fc0cb1491865991fde28abcf55` | exit 0 (the original commit is an ancestor) |
| `git log --format='%H %P' 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e..origin/architecture/p0-foundation-freeze` | c3aae47a7d9b12fc0cb1491865991fde28abcf55 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e — exactly one commit, whose parent is the frozen SHA; nothing later |
| `git rev-parse origin/review/p0-foundation-independent-review` | 7515b232e7407c0bb20afc5abd9656da2c246d0b (the original review branch is unchanged) |
| `git status --porcelain` | (empty) — clean working tree |
| `git diff --name-status 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e c3aae47a7d9b12fc0cb1491865991fde28abcf55 \| grep -vE '^[AM]\s+docs/architecture/'` | (empty) — all 30 paths (3 added, 27 modified) are .md/.json under docs/architecture/ |
| `git diff --quiet 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e c3aae47a7d9b12fc0cb1491865991fde28abcf55 -- dist ; git ls-tree c3aae47a7d9b12fc0cb1491865991fde28abcf55 dist` | exit 0; tree d1d3efced8aa4ee67c2d832aae075d0f3f136cf9 (unchanged) |
| `git diff --numstat 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e c3aae47a7d9b12fc0cb1491865991fde28abcf55 \| awk '$1=="-"'` | (empty) — no binaries |
| `git diff --name-only 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e c3aae47a7d9b12fc0cb1491865991fde28abcf55 \| grep -iE '\.env\|\.pem\|\.key\|credential\|\.(py\|js\|ts\|sh)$'` | (empty) — no environment, key or code files |
| `git diff 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e c3aae47a7d9b12fc0cb1491865991fde28abcf55 \| grep '^+' \| grep -cE 'AKIA[0-9A-Z]{16}\|-----BEGIN\|eyJ…\.…\.\|JBSWY3DP'` | 0 — the only otpauth string uses the placeholder <BASE32-SECRET-SHOWN-ONCE> |
| `git worktree add --detach <scratch> c3aae47a7d9b12fc0cb1491865991fde28abcf55` | all reading was done at the exact remediation SHA |

The diff contains documentation only: 3 added files (ADR-010, decision-log.md, and the remediation matrix .md/.json) and 27 modified files, all under `docs/architecture/`. It adds no code, secrets, credentials, production data or environment files. `dist/` is unchanged.

## 2. Finding-by-finding reconciliation (35 of 35)

The author's matrix contains all 35 findings, and original severities, titles and affected-requirement lists match the original review JSON exactly (independently compared). Nothing was renamed, merged, omitted or downgraded.

| ID | Original severity | Re-review disposition | Evidence / notes |
|---|---|---|---|
| F-01 | MAJOR | **RESOLVED** | Sales column in 06 §6.2 is blank for `security_event.read`, which is `supports_scope=false` (ALL-only, 06 §4). An independent parse of 06 §6 found that the Sales grants include none of the 16 🔒 codes. Classification is one mechanism (`sensitivity_class`, with `is_sensitive` derived by CHECK, 03 §4.4, 06 §3.1). Activation requires an ACTIVE factor plus an MFA-verified FULL session (06 §5 step 8). MFA reset or factor removal suspends it through `authz_version` and an uncached per-request read (06 §9, 05 §5). Negative tests: 12 §4.3 'Access' and 06 §10. ADR-006, ADR-004, 05 §9.5/§12, 08 §4.4/§10.1 and 09 §4.10 agree. |
| F-02 | MAJOR | **RESOLVED** | Password-only enrollment is removed. Login with MFA required and no factor returns no token and emails an enrollment link (05 §3). There are four two-proof paths (05 §11.3). Recovery requires password re-entry plus a code and creates a RECOVERY session with a 15-minute limit, no refresh token, an allow-list and a Layer 0 gate (05 §11.5, 06 §8). Other sessions are revoked, the verified email is notified, codes are rotated and cooling-off applies. Admin reset uses separate `user.mfa.reset`, G3/G9/G11, dual control for privileged targets, and delivers the enrollment link to the target's verified email. Residual test gaps are in N-03. Note: the re-review brief paraphrases F-02 as 'a recovery code could enable…'. The original finding was password-only enrollment after an MFA reset or policy change. Both readings were verified. |
| F-03 | MAJOR | **RESOLVED** | `user.update` is retired. `user.profile.update` has a closed DTO, and security fields return 422 FIELD_NOT_UPDATABLE (08 §5.4, 06 §10 mass-assignment tests). Email change uses the proposed-email workflow: step-up, verification of the new address, cancel alert to the current one, hashed single-use tokens, sessions revoked, and the verified email stays the reset destination (05 §8.6, 08 §4.8/§5.5). G9 covers all account-control actions. G3 covers self-deactivation. `protection_level` backs G11. I1/I2 are enforced under the write lock (06 §7.3). An Admin cannot deactivate or modify the Founder (G9 + G11). The dual-control **eligibility** text is inconsistent; that is recorded as a new finding (N-01), not a failure of F-03's core defect. |
| F-04 | MINOR | **RESOLVED** | A fingerprint is stored (`intake_request_fingerprint`). Lookup happens before Turnstile. One behavior is specified in 04 §5.1 and 08 §2.8. Tests are in 12 §4.6. |
| F-05 | MINOR | **RESOLVED** | A honeypot hit is stored as SUSPECTED with an identical 201. Markup is specified. 02 §2.4, 04 §5.1 and 09 §4.11 are aligned, and every non-field-422 offers WhatsApp. Limits are relaxed. Advisory N-A3 covers spam-queue ageing. |
| F-06 | MINOR | **RESOLVED** | Mutations produce `SENSITIVE_ACTION`. Reads produce `SENSITIVE_READ`, de-duplicated per 15 minutes. 05, 06, 07 and ADR-004 agree. |
| F-07 | MINOR | **REGRESSION INTRODUCED** | The original defect is fixed: session retention, EXC-009 correlation ids and purge order (03 §2.10). However, the remediation broadened conformance rule 3 to reject any FK-less `*_id` outside EXC-009, which now conflicts with seven unregistered polymorphic or correlation columns (N-02). |
| F-08 | MINOR | **RESOLVED** | The three indexes are in EXC-007 with a justification, and the conformance allow-list is exact. |
| F-09 | MINOR | **RESOLVED** | There is one gunicorn gthread worker process (OPS-010), with a deployment check (RG-3). Throughput is validated by ASM-013 and RG-4. |
| F-10 | MINOR | **RESOLVED** | The per-request read is uncached. Grace-window semantics are exact (access token only, once, `grace_used_on`). Tests are in 12 §4.5. |
| F-11 | MINOR | **RESOLVED** | The chain uses HMAC with a key held in SSM. RFC 8785 canonicalization is fully specified. The Object Lock anchor is promoted to P0 (SEVT-007). Residual root-on-host risk is documented. |
| F-12 | MINOR | **RESOLVED** | Readiness excludes outbox and email health. There is one runbook (02 §12.4) with expand-only N-1 migrations and both rollback paths. |
| F-13 | MINOR | **RESOLVED** | The key reference is split into `wrapped_data_key` TEXT and `kms_key_arn` VARCHAR(2048). Runtime proof is tracked as TG-02. |
| F-14 | MINOR | **RESOLVED** | `--vs-on-copper-strong` is added. Independently recomputed: 7.10:1 (light) and 9.51:1 (dark). AX-05 checks both themes. |
| F-15 | MINOR | **RESOLVED** | LEAD-027/028/029 and AUDIT-011 are now P0 with designs (04 §5.4, §14; 07 §8.2). The retention job ships disabled until OWNER-INPUT-002. |
| F-16 | MINOR | **RESOLVED** | AUTH-016 and RBAC-016 are promoted. Time-bound grants return 422 in P0 and can never carry sensitive permissions. P1 rows are marked in 08. |
| F-17 | MINOR | **RESOLVED** | `property_type` is optional on the public form (owner Decision 4). 'Home Renovation' maps to PROJECT_TYPE RENOVATION. Unknown codes go to `intake_unmapped`. |
| F-18 | MINOR | **ACCEPTABLY TRACKED** | The decision log and ADR approval records exist and explicitly state they are not signatures. TG-01 (owner PR approval before implementation) is a valid gate and does **not** claim approval exists. It is correctly **not** marked resolved. |
| F-19 | MINOR | **PARTIALLY RESOLVED** | Most requested suites were added: upgrade-with-data and N-1, CSRF, token-after-revocation, grace window, contention, browser matrix, DAST gate. However, two earlier test designs were dropped and some recovery cases are missing (N-03). |
| F-20 | MINOR | **RESOLVED** | Undo is removed. No note-restore endpoint exists, and 04/08/09 are consistent. |
| F-21 | MINOR | **RESOLVED** | 0 `Traces:` lines remain (independently verified). The coverage model is substantive, and author upgrades are explicitly flagged for re-review. |
| A-01 | ADVISORY | **RESOLVED** | Per-(account, network) throttling. MFA-enrolled users are never globally blocked. |
| A-02 | ADVISORY | **RESOLVED** | No DDL from application processes; maintenance CLI only; readiness checks triggers. |
| A-03 | ADVISORY | **RESOLVED** | Casefolded `search_text` with a dual-engine test. |
| A-04 | ADVISORY | **RESOLVED** | `role.name_normalized` unique index. |
| A-05 | ADVISORY | **RESOLVED** | 24-hour invite expiry for sensitive roles; enrollment inside the invite flow; inviter notified. |
| A-06 | ADVISORY | **RESOLVED** | G2 applies to `copy_from_role_id`. |
| A-07 | ADVISORY | **RESOLVED** | Scoped repository lookup, with 404 for out-of-scope targets. |
| A-08 | ADVISORY | **RESOLVED** | Regex `^/(?![/\\])` plus tests. |
| A-09 | ADVISORY | **RESOLVED** | Rate limit, then idempotency, then Turnstile. |
| A-10 | ADVISORY | **RESOLVED** | Placeholder secret; independently confirmed that no published example key remains. |
| A-11 | ADVISORY | **RESOLVED** | Constraints documented and monitored (02 §12.3). |
| A-12 | ADVISORY | **RESOLVED** | PII masked for out-of-scope leads. |
| A-13 | ADVISORY | **ACCEPTED (rationale documented; gate not measurable)** | The rationale is sound: atomicity of SUCCESS events. But 'measured in rehearsal (RG-4)' has no pass/fail threshold, and RG-4 is a SQLite pre-production test, while the lock applies only to PostgreSQL. No P0 correctness or security gap is concealed, because PostgreSQL is post-P0. The acceptance criterion belongs in the PostgreSQL migration rehearsal (11 §3.4) and is folded into N-04. |
| A-14 | ADVISORY | **RESOLVED** | Identical 201 with a real reference. |

## 3. F-01 — Sales MFA and security-event access: **RESOLVED**

| Check | Result |
|---|---|
| Default Sales lacks `security_event.read` | ✔ 06 §6.2 (blank). The migration asserts it (03 §10). Registry rule 3 (06 §3.1). |
| No Sales path to all, scoped, own, or export/search | ✔ The permission is ALL-only with no OWN variant (06 §4). Only `GET /security-events[/{id}]` exist (08 row 87). Sales lacks `audit.read`, so there's no route through history or the audit viewer. `/auth/sessions` is not event data. |
| Restricted to privileged users | ✔ Founder and Admin only, effective only in MFA-verified sessions |
| One canonical sensitivity mechanism | ✔ `sensitivity_class` in the code registry. `is_sensitive` is derived by CHECK. The API cannot reclassify. |
| No role-name checks | ✔ 06 §2.1. The lint is kept. MFA posture is derived from data. |
| Unusable until MFA enrolled and verified | ✔ Resolver step 8 (06 §5) |
| Disabling or resetting MFA suspends it | ✔ `authz_version`++ on factor changes (06 §9). PERMISSION_SUSPENDED events. |
| Next-request propagation | ✔ An uncached session/user read per request. The map cache is keyed by version, MFA flag and cooling-off. |
| Cross-document consistency | ✔ ADR-006/ADR-004/05/06/08/09/11/12 agree. The /auth/me example shows no `security_event.read`. |
| Negative tests | ✔ 12 §4.3 'Access': 403 on list, `?subject_user_id=self` and own-event detail. 12 §4.8: no Sales UI request. |

No alternate authorization path was found.

## 4. F-02 — MFA recovery: **RESOLVED**

| Check | Result |
|---|---|
| Password plus one unused code | ✔ 05 §11.5 step 2. Fresh Argon2 verify. Uniform 401. |
| A code alone cannot enroll, reset, change email, grant or administer | ✔ Recovery needs the login `mfa_token` (password) plus password re-entry. The RECOVERY session allow-list is `me`, `enroll/*` and `logout` only (Layer 0, 06 §8). The resolver returns ∅ for RECOVERY. No API tokens exist in P0. |
| Restricted short-lived session bound to account and purpose | ✔ `session_type = RECOVERY`, 15 minutes, no refresh token, `stp` claim |
| Other sessions revoked; verified email notified | ✔ |
| Codes: storage, use, rotation, redaction, invalidation | ✔ HMAC with an SSM key, single use, new batch on every (re-)enrollment, never logged or returned |
| Cooling-off precise and enforceable | ✔ An enumerated list, a configuration value with an initial 24 h, and resolver enforcement. Advisory N-A2 on scope. |
| No self-reset; privileged reset needs separate authorization; Founder multi-person or break-glass | ✔ G3, G12, G11, 06 §7.5 |
| Complete events | ✔ The 05 §9.1 catalog |
| No replay; no enumeration | ✔ Code single use; recovery has no refresh token. Recovery only after the password. The login `mfa_token` completion on recovery is not stated (N-03). |
| Tests | ✔ replay, wrong password, used code, revocation, restricted-session denial, self-reset, Founder rules. ✗ expired recovery session and re-enrollment failure (N-03). |

Bypass search: none found. The residual (N-A1) is that path A after a new sensitive grant relies on proofs derived from the password. That matches the original review's accepted option and is advisory.

## 5. F-03 — Account takeover and privileged-account protection: **RESOLVED**

| Check | Result |
|---|---|
| Generic editing cannot change security attributes | ✔ Closed DTOs (08 §5.4, `PATCH /auth/me`). `FIELD_NOT_UPDATABLE`. `POST /users` cannot set protection, MFA or status. |
| Granular permissions | ✔ Eight codes; seven account/access-control codes are sensitive |
| No mass assignment | ✔ Closed schemas; tests in 12 §4.4 |
| Email workflow | ✔ Step-up (MFA for enrolled or privileged users), `proposed_email*` columns, cancel alert to verified, verification to proposed (60 min), SHA-256 single-use tokens, reset stays on verified, audit and security events, all sessions revoked |
| No admin direct overwrite | ✔ Admins can only initiate; privileged targets need dual control; Founder targets use the Founder workflow |
| Admin cannot deactivate the Founder; no self-deactivation | ✔ G9 + G11; G3 |
| Last Founder / last recovery admin | ✔ I1/I2 under `BEGIN IMMEDIATE` / `FOR UPDATE`, plus a nightly check. Advisory N-A4. |
| Founder changes: step-up plus dual control | ◐ ADR-010 is unambiguous, but 06 §7.2's eligibility parenthetical and unrestricted FOUNDER-role / `user.founder.manage` grants let one Founder manufacture an approver (**N-01**) |
| Layers consistent | ✔ Database (CHECKs, protection_level), service guards, API, UI (09 §4.6/§4.12/§4.13), audit and tests. Advisory N-A5 notes index omissions. |
| Negative tests | ✔ generic email, mass assignment, Admin-versus-Founder, self-deactivation, last admin/Founder, old-email reset, expired and reused tokens |

Takeover or escalation construction: no path for a non-Founder was found. The single-Founder separation-of-duties gap is N-01.

## 6. MINOR findings disposition

See §2. Summary of the 18 MINORs: 15 RESOLVED, 1 ACCEPTABLY TRACKED (F-18 / TG-01), 1 PARTIALLY RESOLVED (F-19), 1 REGRESSION INTRODUCED (F-07 → N-02). Specific attention items:

- **Lead-form idempotency, CAPTCHA order and retry:** resolved.
- **Silent loss and WhatsApp fallback:** resolved.
- **Purge ordering:** resolved; the regression is N-02.
- **Hash chain:** resolved.
- **Timezone:** 03 §2.2 has explicit input, storage and display rules; resolved.
- **Dark-mode contrast:** resolved.
- **Retention, withdrawal and erasure:** resolved, with values owner-gated.
- **Coverage accuracy:** the model is corrected, but the author's 206 overstates coverage (§8).
- **SQLite and PostgreSQL:** resolved.
- **Testing depth:** partial (N-03).
- **Owner approval:** correctly tracked; TG-01 does not claim approval exists.

## 7. Advisory findings

- 13 of the 14 advisories are substantively remediated (§2).
- A-13 is accepted with a sound rationale, but its acceptance gate is not measurable and is attached to the wrong rehearsal. It is folded into N-04.
- No advisory should be upgraded, and no accepted advisory hides a P0 correctness or security gap: the PostgreSQL lock cost is post-P0.

## 8. Requirement recount and independent coverage

- The recount matches the author: 221 total, 208 P0 (186 + 18 new + 4 promoted), 10 P1, 3 P2. No IDs were removed.
- **New:** DATA-017, LEAD-027, LEAD-028, LEAD-029, LEAD-030, MFA-012, MFA-013, MFA-014, MFA-015, OPS-010, OPS-011, RBAC-018, RBAC-019, RBAC-020, RBAC-021, UI-016, UI-017, USER-007.
- **Promoted:** AUDIT-011, AUTH-016, SEVT-007, RBAC-016. Each promotion is justified by F-15, F-16 or F-11.
- **Duplicates:** none exact. There are overlaps (N-A7).

| Classification | Count |
|---|---|
| Fully covered | 202 |
| Partially covered | 3 |
| Referenced but not substantively covered | 0 |
| Contradictory | 1 |
| Not covered | 0 |
| Not testable pending owner input | 2 |
| Deferred (P1/P2, not in the P0 count) | 13 |

Disagreements with the author's classification: DATA-011 (Partially covered), DATA-014 (Partially covered), MFA-015 (Partially covered), RBAC-021 (Contradictory).

All 26 previously partial or contradictory requirements were re-read against the corrected design. 25 are now fully covered. DATA-014 remains partial (N-02). The two owner-gated requirements are correctly classified.

| ID | Group | Verify | Author | Reviewer | Findings | Note |
|---|---|---|---|---|---|---|
| ACT-001 | baseline | IT | Fully covered | Fully covered | — | — |
| ACT-002 | baseline | IT | Fully covered | Fully covered | — | — |
| ACT-003 | baseline | IT | Fully covered | Fully covered | — | — |
| ACT-004 | baseline | IT | Fully covered | Fully covered | — | — |
| API-001 | baseline | IT | Fully covered | Fully covered | — | — |
| API-002 | baseline | IT | Fully covered | Fully covered | — | — |
| API-003 | baseline | IT | Fully covered | Fully covered | — | — |
| API-004 | baseline | IT | Fully covered | Fully covered | — | — |
| API-005 | baseline | IT | Fully covered | Fully covered | — | — |
| API-006 | baseline | IT | Fully covered | Fully covered | N-03 | Design sufficient; test design gap (N-03) |
| API-007 | previously partial/contradictory | IT | Fully covered | Fully covered | — | — |
| API-008 | baseline | RV | Fully covered | Fully covered | — | — |
| API-009 | baseline | RV | Fully covered | Fully covered | — | — |
| AUDIT-001 | baseline | IT | Fully covered | Fully covered | — | — |
| AUDIT-002 | baseline | IT | Fully covered | Fully covered | — | — |
| AUDIT-003 | baseline | IT | Fully covered | Fully covered | — | — |
| AUDIT-004 | baseline | IT | Fully covered | Fully covered | — | — |
| AUDIT-005 | baseline | UT | Fully covered | Fully covered | — | — |
| AUDIT-006 | baseline | IT | Fully covered | Fully covered | — | — |
| AUDIT-008 | baseline | E2E | Fully covered | Fully covered | — | — |
| AUDIT-010 | baseline | UT | Fully covered | Fully covered | — | — |
| AUDIT-011 | new or promoted | IT | Fully covered | Fully covered | — | — |
| AUDIT-012 | baseline | IT | Fully covered | Fully covered | — | — |
| AUTH-001 | baseline | E2E | Fully covered | Fully covered | — | — |
| AUTH-002 | baseline | UT | Fully covered | Fully covered | — | — |
| AUTH-003 | baseline | UT | Fully covered | Fully covered | — | — |
| AUTH-004 | baseline | IT | Fully covered | Fully covered | — | — |
| AUTH-005 | previously partial/contradictory | IT | Fully covered | Fully covered | — | — |
| AUTH-006 | previously partial/contradictory | IT | Fully covered | Fully covered | — | — |
| AUTH-007 | baseline | IT | Fully covered | Fully covered | — | — |
| AUTH-008 | baseline | IT | Fully covered | Fully covered | — | — |
| AUTH-009 | baseline | IT | Fully covered | Fully covered | — | — |
| AUTH-010 | previously partial/contradictory | IT | Fully covered | Fully covered | — | — |
| AUTH-011 | baseline | IT | Fully covered | Fully covered | — | — |
| AUTH-012 | baseline | IT | Fully covered | Fully covered | — | — |
| AUTH-013 | baseline | IT | Fully covered | Fully covered | — | — |
| AUTH-014 | baseline | OP | Fully covered | Fully covered | — | — |
| AUTH-015 | previously partial/contradictory | E2E | Fully covered | Fully covered | — | — |
| AUTH-016 | new or promoted | IT | Fully covered | Fully covered | — | — |
| AUTH-017 | previously partial/contradictory | IT | Fully covered | Fully covered | — | — |
| AUTH-018 | previously partial/contradictory | IT | Fully covered | Fully covered | — | — |
| DATA-001 | baseline | SL | Fully covered | Fully covered | — | — |
| DATA-002 | baseline | SL, UT | Fully covered | Fully covered | — | — |
| DATA-003 | baseline | UT | Fully covered | Fully covered | — | — |
| DATA-004 | baseline | SL | Fully covered | Fully covered | — | — |
| DATA-005 | baseline | SL, IT | Fully covered | Fully covered | — | — |
| DATA-006 | baseline | IT | Fully covered | Fully covered | N-03 | Design sufficient; test design gap (N-03) |
| DATA-007 | baseline | IT | Fully covered | Fully covered | — | — |
| DATA-008 | baseline | IT | Fully covered | Fully covered | — | — |
| DATA-009 | previously partial/contradictory | RV | Fully covered | Fully covered | — | — |
| DATA-010 | baseline | IT | Fully covered | Fully covered | — | — |
| DATA-011 | baseline | SL | Fully covered | Partially covered | N-02 | Rule 3 conflicts with unregistered polymorphic columns |
| DATA-012 | baseline | SL | Fully covered | Fully covered | — | — |
| DATA-013 | baseline | IT | Fully covered | Fully covered | — | — |
| DATA-014 | previously partial/contradictory | SL | Fully covered | Partially covered | N-02 | Registry incomplete for FK-less GUID columns |
| DATA-015 | baseline | IT | Fully covered | Fully covered | — | — |
| DATA-016 | baseline | SL | Fully covered | Fully covered | — | — |
| DATA-017 | new or promoted | IT | Fully covered | Fully covered | — | — |
| LEAD-001 | baseline | E2E | Fully covered | Fully covered | — | — |
| LEAD-002 | baseline | SL | Fully covered | Fully covered | — | — |
| LEAD-003 | baseline | E2E | Fully covered | Fully covered | — | — |
| LEAD-004 | baseline | SL | Fully covered | Fully covered | — | — |
| LEAD-005 | baseline | UT | Fully covered | Fully covered | — | — |
| LEAD-006 | baseline | IT | Fully covered | Fully covered | — | — |
| LEAD-007 | baseline | IT | Fully covered | Fully covered | — | — |
| LEAD-008 | baseline | IT | Fully covered | Fully covered | — | — |
| LEAD-009 | baseline | UT | Fully covered | Fully covered | — | — |
| LEAD-010 | baseline | IT | Fully covered | Fully covered | N-03 | Design sufficient; test design gap (N-03) |
| LEAD-011 | baseline | IT | Fully covered | Fully covered | — | — |
| LEAD-012 | baseline | IT | Fully covered | Fully covered | — | — |
| LEAD-013 | baseline | IT | Fully covered | Fully covered | — | — |
| LEAD-014 | baseline | E2E | Fully covered | Fully covered | — | — |
| LEAD-015 | baseline | IT | Fully covered | Fully covered | — | — |
| LEAD-016 | baseline | IT | Fully covered | Fully covered | — | — |
| LEAD-018 | previously partial/contradictory | IT | Fully covered | Fully covered | — | — |
| LEAD-019 | previously partial/contradictory | E2E | Fully covered | Fully covered | — | — |
| LEAD-020 | baseline | IT | Fully covered | Fully covered | — | — |
| LEAD-023 | baseline | IT | Fully covered | Fully covered | — | — |
| LEAD-024 | baseline | IT | Fully covered | Fully covered | — | — |
| LEAD-025 | baseline | IT | Fully covered | Fully covered | — | — |
| LEAD-026 | baseline | E2E | Fully covered | Fully covered | — | — |
| LEAD-027 | new or promoted | IT | Fully covered | Fully covered | — | — |
| LEAD-028 | new or promoted | IT | Fully covered | Fully covered | — | — |
| LEAD-029 | new or promoted | IT | Fully covered | Fully covered | — | — |
| LEAD-030 | new or promoted | IT | Fully covered | Fully covered | — | — |
| LOG-001 | baseline | RV | Fully covered | Fully covered | — | — |
| LOG-002 | baseline | IT | Fully covered | Fully covered | — | — |
| LOG-003 | baseline | UT | Fully covered | Fully covered | — | — |
| LOG-004 | baseline | OP | Fully covered | Fully covered | — | — |
| LOG-005 | previously partial/contradictory | IT | Fully covered | Fully covered | — | — |
| LOG-006 | baseline | OP | Fully covered | Fully covered | — | — |
| MFA-001 | baseline | E2E | Fully covered | Fully covered | — | — |
| MFA-002 | baseline | IT | Fully covered | Fully covered | — | — |
| MFA-003 | previously partial/contradictory | IT | Fully covered | Fully covered | — | — |
| MFA-004 | baseline | IT | Fully covered | Fully covered | — | — |
| MFA-005 | baseline | IT | Fully covered | Fully covered | — | — |
| MFA-006 | baseline | IT | Fully covered | Fully covered | — | — |
| MFA-007 | previously partial/contradictory | IT | Fully covered | Fully covered | — | — |
| MFA-008 | baseline | RV | Fully covered | Fully covered | — | — |
| MFA-009 | baseline | UT | Fully covered | Fully covered | — | — |
| MFA-010 | previously partial/contradictory | IT | Fully covered | Fully covered | — | — |
| MFA-011 | baseline | IT | Fully covered | Fully covered | — | — |
| MFA-012 | new or promoted | IT | Fully covered | Fully covered | — | — |
| MFA-013 | new or promoted | IT | Fully covered | Fully covered | N-03 | Design sufficient; test design gap (N-03) |
| MFA-014 | new or promoted | IT | Fully covered | Fully covered | — | — |
| MFA-015 | new or promoted | IT | Fully covered | Partially covered | N-01 | Founder MFA reset depends on the eligibility rule in N-01 |
| NFR-001 | baseline | IT | Fully covered | Fully covered | — | — |
| NFR-002 | baseline | OP | Not testable pending owner input | Not testable pending owner input | — | OWNER-INPUT-001 |
| NFR-003 | baseline | IT | Fully covered | Fully covered | — | — |
| NOTE-001 | baseline | IT | Fully covered | Fully covered | — | — |
| NOTE-002 | previously partial/contradictory | IT | Fully covered | Fully covered | — | — |
| NOTE-004 | baseline | SL | Fully covered | Fully covered | — | — |
| NOTIF-001 | baseline | IT | Fully covered | Fully covered | — | — |
| NOTIF-002 | baseline | IT | Fully covered | Fully covered | — | — |
| NOTIF-003 | baseline | IT | Fully covered | Fully covered | — | — |
| NOTIF-004 | baseline | IT | Fully covered | Fully covered | — | — |
| NOTIF-005 | baseline | RV | Fully covered | Fully covered | — | — |
| NOTIF-008 | baseline | IT | Fully covered | Fully covered | — | — |
| NOTIF-009 | baseline | IT | Fully covered | Fully covered | — | — |
| OPS-001 | baseline | OP | Fully covered | Fully covered | — | — |
| OPS-002 | baseline | OP | Fully covered | Fully covered | — | — |
| OPS-003 | baseline | RV | Fully covered | Fully covered | — | — |
| OPS-004 | previously partial/contradictory | OP | Fully covered | Fully covered | — | — |
| OPS-005 | baseline | OP | Not testable pending owner input | Not testable pending owner input | — | OWNER-INPUT-001 |
| OPS-006 | baseline | OP | Fully covered | Fully covered | — | — |
| OPS-007 | baseline | OP | Fully covered | Fully covered | — | — |
| OPS-008 | baseline | RV | Fully covered | Fully covered | — | — |
| OPS-009 | baseline | OP | Fully covered | Fully covered | — | — |
| OPS-010 | new or promoted | OP | Fully covered | Fully covered | — | — |
| OPS-011 | new or promoted | OP | Fully covered | Fully covered | — | — |
| PLAT-001 | baseline | RV | Fully covered | Fully covered | — | — |
| PLAT-002 | baseline | RV | Fully covered | Fully covered | — | — |
| PLAT-003 | baseline | OP | Fully covered | Fully covered | — | — |
| PLAT-004 | baseline | IT | Fully covered | Fully covered | — | — |
| PLAT-005 | baseline | RV | Fully covered | Fully covered | — | — |
| PLAT-006 | baseline | RV | Fully covered | Fully covered | — | — |
| PLAT-007 | baseline | UT | Fully covered | Fully covered | — | — |
| PLAT-008 | baseline | RV | Fully covered | Fully covered | — | — |
| PLAT-009 | baseline | IT | Fully covered | Fully covered | — | — |
| PLAT-010 | baseline | IT | Fully covered | Fully covered | — | — |
| PLAT-011 | baseline | RV | Fully covered | Fully covered | — | — |
| PLAT-012 | baseline | RV | Fully covered | Fully covered | — | — |
| PLAT-013 | baseline | SL | Fully covered | Fully covered | — | — |
| RBAC-001 | baseline | SL | Fully covered | Fully covered | — | — |
| RBAC-002 | baseline | RV | Fully covered | Fully covered | — | — |
| RBAC-003 | baseline | SL | Fully covered | Fully covered | — | — |
| RBAC-004 | baseline | IT | Fully covered | Fully covered | — | — |
| RBAC-005 | baseline | IT | Fully covered | Fully covered | — | — |
| RBAC-006 | baseline | UT | Fully covered | Fully covered | N-03 | Design sufficient; test design gap (N-03) |
| RBAC-008 | baseline | IT | Fully covered | Fully covered | — | — |
| RBAC-009 | previously partial/contradictory | IT | Fully covered | Fully covered | — | — |
| RBAC-010 | baseline | IT | Fully covered | Fully covered | — | — |
| RBAC-011 | previously partial/contradictory | IT | Fully covered | Fully covered | — | — |
| RBAC-012 | baseline | IT | Fully covered | Fully covered | — | — |
| RBAC-013 | baseline | IT | Fully covered | Fully covered | — | — |
| RBAC-014 | baseline | IT | Fully covered | Fully covered | — | — |
| RBAC-015 | baseline | IT | Fully covered | Fully covered | — | — |
| RBAC-016 | new or promoted | E2E | Fully covered | Fully covered | — | — |
| RBAC-017 | previously partial/contradictory | IT | Fully covered | Fully covered | — | — |
| RBAC-018 | new or promoted | IT | Fully covered | Fully covered | — | — |
| RBAC-019 | new or promoted | IT | Fully covered | Fully covered | — | — |
| RBAC-020 | new or promoted | IT | Fully covered | Fully covered | — | — |
| RBAC-021 | new or promoted | IT | Fully covered | Contradictory | N-01 | Approver eligibility contradicts itself between 06 §7.2 and ADR-010, 06 §7.4 and 08 §5.11 |
| SEC-001 | baseline | OP | Fully covered | Fully covered | — | — |
| SEC-002 | baseline | IT | Fully covered | Fully covered | — | — |
| SEC-003 | baseline | IT | Fully covered | Fully covered | — | — |
| SEC-004 | baseline | UT | Fully covered | Fully covered | — | — |
| SEC-005 | baseline | RV | Fully covered | Fully covered | — | — |
| SEC-006 | baseline | OP | Fully covered | Fully covered | — | — |
| SEC-007 | baseline | OP | Fully covered | Fully covered | — | — |
| SEC-008 | baseline | OP | Fully covered | Fully covered | — | — |
| SEC-009 | previously partial/contradictory | RV | Fully covered | Fully covered | — | — |
| SEC-011 | previously partial/contradictory | IT | Fully covered | Fully covered | — | — |
| SEVT-001 | baseline | IT | Fully covered | Fully covered | — | — |
| SEVT-002 | baseline | IT | Fully covered | Fully covered | — | — |
| SEVT-003 | baseline | UT | Fully covered | Fully covered | — | — |
| SEVT-004 | baseline | OP | Fully covered | Fully covered | — | — |
| SEVT-005 | baseline | IT | Fully covered | Fully covered | — | — |
| SEVT-006 | previously partial/contradictory | UT | Fully covered | Fully covered | — | — |
| SEVT-007 | new or promoted | OP | Fully covered | Fully covered | — | — |
| SEVT-008 | baseline | IT | Fully covered | Fully covered | — | — |
| SEVT-009 | baseline | OP | Fully covered | Fully covered | — | — |
| SEVT-010 | baseline | RV | Fully covered | Fully covered | — | — |
| SEVT-011 | baseline | IT | Fully covered | Fully covered | — | — |
| UI-001 | baseline | E2E | Fully covered | Fully covered | — | — |
| UI-002 | baseline | E2E | Fully covered | Fully covered | — | — |
| UI-003 | baseline | E2E | Fully covered | Fully covered | — | — |
| UI-004 | baseline | E2E | Fully covered | Fully covered | — | — |
| UI-005 | baseline | E2E | Fully covered | Fully covered | — | — |
| UI-006 | baseline | E2E | Fully covered | Fully covered | — | — |
| UI-007 | baseline | E2E | Fully covered | Fully covered | — | — |
| UI-008 | baseline | E2E | Fully covered | Fully covered | — | — |
| UI-009 | baseline | E2E | Fully covered | Fully covered | — | — |
| UI-010 | baseline | RV | Fully covered | Fully covered | — | — |
| UI-011 | previously partial/contradictory | E2E | Fully covered | Fully covered | — | — |
| UI-012 | baseline | E2E | Fully covered | Fully covered | — | — |
| UI-013 | baseline | E2E | Fully covered | Fully covered | — | — |
| UI-014 | previously partial/contradictory | RV | Fully covered | Fully covered | — | — |
| UI-015 | baseline | E2E | Fully covered | Fully covered | — | — |
| UI-016 | new or promoted | E2E | Fully covered | Fully covered | — | — |
| UI-017 | new or promoted | E2E | Fully covered | Fully covered | — | — |
| USER-001 | previously partial/contradictory | IT | Fully covered | Fully covered | — | — |
| USER-002 | baseline | UT | Fully covered | Fully covered | — | — |
| USER-003 | baseline | IT | Fully covered | Fully covered | — | — |
| USER-004 | baseline | IT | Fully covered | Fully covered | — | — |
| USER-005 | baseline | IT | Fully covered | Fully covered | — | — |
| USER-006 | baseline | E2E | Fully covered | Fully covered | — | — |
| USER-007 | new or promoted | IT | Fully covered | Fully covered | — | — |

## 9. Test-depth review

- The author's split is confirmed numerically: 166 automated · 21 review · 21 operational (19 + 2 owner-gated).
- The RV and OP classifications are appropriate or conservative (N-A9).
- Rows were judged concrete only if they state preconditions, action, expected result, negatives and assertions.

| Area | Rating | Note |
|---|---|---|
| Authentication | Concrete | 12 §4.5 login outcomes, throttling, tokens after revocation, CSRF negatives |
| MFA | Concrete | Policy sources, TOTP vectors, drift, replay, enrollment proofs A–D, including negatives |
| Recovery | Mostly concrete; gaps | Password/code matrix, restricted-session denials, rotation, cooling-off. Missing: session expiry, `mfa_token` single use, re-enrollment failure (N-03) |
| Refresh-token rotation | Concrete | Grace window, third use, and post-20 s theft path |
| Replay resistance | Concrete | TOTP `last_used_step`, used recovery code, email and verification token reuse, refresh reuse |
| RBAC | Concrete | Generated matrix test plus scope tests |
| Sensitive-permission enforcement | Concrete | Registry rules, activation, suspension on reset, cooling-off |
| Direct grants | Gap | The DENY-precedence and broadest-scope resolution test was removed (N-03). Only reason, time-bound 422 and mass assignment remain. |
| Permission-cache invalidation | Concrete | 'Propagation': next request, no cache window |
| Email change | Concrete | Full workflow, including expired and reused tokens, old-email reset destination, approvals |
| Founder protection | Concrete; eligibility gap | Admin-versus-Founder negatives, pool-insufficient, break-glass same-principal. Missing: non-FOUNDER approver negative (N-01) |
| Last-administrator protection | Concrete | I1/I2 plus a two-writer concurrency test on both engines |
| Lead submission | Concrete | Required and optional fields, unmapped codes, consent, phone rules, public response property test |
| Duplicate detection | Gap | No concrete row after remediation (N-03) |
| CAPTCHA | Concrete | Lookup before Turnstile (mock call count), spent-token replay |
| WhatsApp fallback | Concrete | E2E for CAPTCHA failure, 429 and API blocked |
| Notification failure | Concrete | Adapter forced to fail: lead committed, 201 |
| Audit atomicity | Concrete | Forced exception after flush: no business, audit or outbox row |
| Security-event integrity | Concrete | Keyed chain, wrong key, gap and tamper detection, cross-engine JCS bytes, anchor role |
| Retention and deletion | Concrete | Purge ordering with FKs on, retention job with test configuration, erasure PENDING→COMPLETED, audit PII scan |
| Restore testing | Operational (appropriate) | OPS-009 scheduled restore plus rebuild rehearsal |
| Accessibility | Concrete | AX-01…AX-10, including dual-theme token contrast failing the build |
| SQLite/PostgreSQL compatibility | Concrete | Dual-engine IT/SL, non-ASCII search, cross-engine JCS |
| Optimistic concurrency | Thin | 'If-Match 428/409' only (N-03) |

## 10. New-design regression review

| Question | Result |
|---|---|
| MFA enforcement deadlocks | None. Invite path B, emailed path C and recovery path D cover every state. They depend on email in production (PG-EMAIL). |
| Recovery session reaching other endpoints | No. Layer 0 blocks before permission logic, and the resolver returns ∅. |
| Dual control stranding the Founder | No. Self-service recovery and break-glass exist (which needs OWNER-INPUT-004). Break-glass is also the only path for a 2-person team's privileged resets. |
| A recovery-capable admin is guaranteed without weakening separation of duties | I2 guaranteed. Separation of duties is weakened by N-01; see N-A4 on suspended holders. |
| Next-request permission changes versus existing tokens | Compatible. The JWT carries no permissions, and the per-request DB read decides. |
| Session revocation enforceable | Yes: an uncached read on every request, and a single process |
| ADR-010 versus ADR-003/004/006 | No conflict. ADR-003 was amended (EXC-009/010). The ADR-010/06 §7.2 conflict is N-01. |
| New tables follow the contracts | `admin_approval_request` and `user_action_token`: GUID, nine columns, registered exceptions, indexes and FKs are correct. The polymorphic-column registry gap is N-02; column sizing is N-A6. |
| No role-name authorization reintroduced | Confirmed; protection is `protection_level` |
| Public API | Still `{reference, message}` only; honeypot identical; no ids, status, users or volume |
| property_type optional and consistent | Yes: 03 §6.2, 04, 08 §8.4, ADR-005 and seeds |
| Renovation under project type | Yes |
| ap-south-1 configurable, no multi-region claim | Yes (ADR-008, 02 §12) |

## 11. Production and tracked gates

No invented values were found: a scan for retention days, RPO/RTO and availability figures returned no matches. The owner inputs correctly gate production rather than implementation.

| Gate | Owner | Trigger | Acceptance | Evidence | Failure behavior | Phase | Completeness |
|---|---|---|---|---|---|---|---|
| OWNER-INPUT-001 | Owner | Before production | Approved values recorded | Decision log entry | Production release blocked | Production | Complete (11 §7.2) |
| OWNER-INPUT-002 | Owner | Before enabling any purge/archival/anonymization | Approved values | Configuration record | Jobs refuse to run | Production | Complete |
| OWNER-INPUT-003 | Owner | Before production | Cadence approved | Decision log | Production release blocked | Production | Complete |
| OWNER-INPUT-004 | Owner | Before production | Two IAM custodians named | IAM group membership plus decision log | Production release blocked; Founder recovery unavailable | Production | Complete |
| RG-1…RG-9 | Not named | Before production (implied) | Stated | Not stated | Not stated | Production | Incomplete (N-04) |
| PG-DAST, PG-RET, PG-BG, PG-EMAIL, PG-PRIV | Not named (PG-RET/PG-BG implied owner) | Before production | Stated | Partly (via TG-03/TG-04) | Not stated | Production | Incomplete (N-04) |
| TG-01 | Owner | Before implementation | Owner PR approval or signed decision log | Link recorded in decision log | Not stated (implicitly: implementation must not start) | Implementation | Mostly complete |
| TG-02…TG-06 | Named | Stated | Stated | Stated | Not stated | Implementation or production | Mostly complete |

## 12. Validation claims (26 checks)

The author's checks are structural and textual. By the author's own statement they cannot prove design adequacy, and they are not committed (N-A8). Key checks were reproduced independently, and V18 missed N-02.

| Check | Result | Detail |
|---|---|---|
| Requirement ID integrity | Reproduced | 221 unique IDs; 0 unresolved references across all .md files; no ID removed from the frozen set |
| Cross-document links | Reproduced | 1,244 `NN §x.y` references and all relative links resolve (0 broken) |
| JSON validity | Reproduced | requirements.json, validation-report.json, review-remediation-matrix.json parse |
| Traces removal | Reproduced | 0 `Traces:` lines |
| Default Sales permissions / sensitivity | Reproduced | 16 sensitive codes; Sales grants ∩ sensitive = ∅ |
| Remediation matrix completeness | Reproduced | 35/35 findings; severity, title and affected requirements identical to the original review JSON |
| Audit contract / ID types | Reproduced, with a defect | Rule 3 versus FK-less columns fails (N-02); V18 did not detect it |
| Recovery restrictions | Manual | 05 §11.5, 06 §8 Layer 0, 08 §4.7 consistent |
| Email-change restrictions | Manual | 05 §8.6, 08 §4.8/§5.4/§5.5, ADR-010 consistent |
| Founder / last-admin protection | Manual, with a defect | Invariants consistent; approver eligibility inconsistent (N-01) |
| Architecture-only diff | Reproduced | 30 paths, all .md/.json under docs/architecture/ |
| dist/ immutability | Reproduced | Tree d1d3efc… identical |
| Secret scanning | Reproduced | 0 matches in added lines |
| Contrast | Reproduced | on-copper-strong 7.10 (light) / 9.51 (dark) |

## 13. New findings

### N-01 · MINOR · Founder dual-control approver eligibility is contradictory, and Founder powers can be granted outside the Founder workflow

**Evidence**

- 06 §7.2 'Approver eligibility': '…both FOUNDER-protected **(or both holding `user.founder.manage` and satisfying G9 against the target)**'.
- ADR-010 §3.5, 06 §7.4 ('for Founder actions, is FOUNDER-protected') and 08 §5.11 (`APPROVER_NOT_ELIGIBLE` when 'not FOUNDER-protected for Founder actions') require FOUNDER-protected approvers. The documents disagree.
- No rule restricts assigning the FOUNDER role, or granting `user.founder.manage` through a custom role (`role.manage`) or a direct grant (`user.permission.manage`), to the GRANT_FOUNDER workflow. G2 lets a Founder do it single-handedly (step-up only). Such a grantee is `protection_level = STANDARD` but holds Founder powers.
- Under the permissive 06 §7.2 reading, one Founder can create an eligible 'second approver' and then satisfy dual control alone, for example DEACTIVATE_FOUNDER against a co-Founder.

**Affected requirements:** RBAC-021, MFA-015, RBAC-020

**Risk:** Separation of duties for Founder-level changes (owner Decision 3) can be defeated by a single compromised or malicious Founder, if the permissive reading is implemented.

**Required remediation:** Remove the parenthetical from 06 §7.2 so that Founder actions require FOUNDER-protected requester and approver. Make the FOUNDER role `is_assignable=false`, and make `user.founder.manage` grantable only by the GRANT_FOUNDER workflow (reject it in `PUT /users/{id}/roles`, `POST /users/{id}/permissions` and `PUT /roles/{id}/permissions` with 409 SYSTEM_OBJECT or 403 FOUNDER_PROTECTED). Add negative tests: a non-FOUNDER-protected holder of `user.founder.manage` cannot approve; FOUNDER role direct assignment is rejected.

**Re-review scope:** Targeted: 06 §6.2/§7.2/§7.4, 08 §5.7/§5.8/§5.11, 12 §4.4

**Implementation blocked?** Blocks implementation of the Founder workflow and approvals stories (RBAC-021, MFA-015) until corrected. Does not block other work.

### N-02 · MINOR · Regression: broadened conformance rule 3 rejects unregistered FK-less GUID columns

**Evidence**

- 03 §2.7 rule 3 now fails any table that 'has an `*_id` column without a FK other than the EXC-009 correlation columns'. The 12 §4.1 negative fixture asserts the same.
- EXC-009 lists only `audit_log.session_id`, `security_event_log.session_id` and `refresh_token.replaced_by_id`.
- FK-less `*_id` GUID columns that are **not** registered: `audit_log.entity_id`, `audit_log.parent_entity_id`, `audit_log.transaction_id`, `security_event_log.target_entity_id`, `outbox_event.aggregate_id`, `notification.entity_id` and `user_mfa_recovery_code.batch_id`. These are polymorphic references or group ids by design (03 §5.4, §5.6, §7, §8).
- Validation V18 reports PASS, so the author's check did not evaluate rule 3 against these columns.

**Affected requirements:** DATA-011, DATA-014, DATA-012

**Risk:** The first migration fails the conformance gate, or the gate is weakened ad hoc during implementation. This is the same class of defect as original F-08.

**Required remediation:** Register these columns (for example in EXC-009, or a new EXC-011 'polymorphic references and group ids') with a justification, and state that the conformance allow-list is exactly that set.

**Re-review scope:** Targeted: 03 §2.7, §2.9

**Implementation blocked?** Blocks implementation of the conformance check (DATA-011) until corrected.

### N-03 · MINOR · Test-design regressions and gaps in recovery, direct grants and duplicate detection

**Evidence**

- The frozen 12 §4.4 'Resolution' test (DENY beats GRANT; broadest scope wins; validity windows) was removed. RBAC-006 now has no concrete test row beyond the generic matrix.
- The frozen 12 §4.7 'duplicate submissions stored and flagged, never dropped' was removed. LEAD-010 (180-day match, flag only, scope-limited display) has no concrete test design in the remediated 12 §4.7.
- 12 §4.5 'Recovery' has no case for: an expired RECOVERY session (15 min); reuse of the login `mfa_token` after a successful recovery (05 does not state that the LOGIN challenge is completed on recovery); `enroll/confirm` failure inside a recovery session (wrong code, retry limits, expiry, and the user's state afterwards).
- Optimistic concurrency is a single line (12 §4.6 'If-Match 428/409') with no concurrent-writer scenario.

**Affected requirements:** RBAC-006, LEAD-010, MFA-013, MFA-014, API-006, DATA-006

**Risk:** Security-relevant paths pass CI without evidence. The coverage gate reports 166 'automated' designs that include these thin or missing rows.

**Required remediation:** Restore the resolution and duplicate tests with preconditions, action and assertions. Add the recovery-expiry, `mfa_token` single-use (and state it in 05 §11.5) and re-enrollment-failure cases. Add a two-writer If-Match conflict test on both engines.

**Re-review scope:** Targeted: 12 §4.4–§4.7 and 05 §11.5 wording

**Implementation blocked?** Blocks the corresponding stories (recovery, RBAC resolver, duplicate detection) until the test designs exist. Does not block other work.

### N-04 · MINOR · Production and tracked gates lack required attributes

**Evidence**

- 11 §7.3 RG-1…RG-9 and PG-DAST/PG-RET/PG-BG/PG-EMAIL/PG-PRIV give a condition and a source only. They name no owner, evidence artifact or failure behavior.
- 11 §11 TG-01…TG-06 give an owner, phase, acceptance and evidence, but no failure behavior.
- The A-13 acceptance ('measured') has no pass/fail threshold, and is attached to RG-4 (SQLite) although it concerns PostgreSQL.

**Affected requirements:** OPS-005, OPS-008, NFR-002, SEC-007

**Risk:** Gates can be declared met without agreed evidence, or bypassed without a defined consequence.

**Required remediation:** Add owner, trigger, acceptance, evidence, failure behavior and phase to every gate, using the table in §11 of this re-review as a template. Move the A-13 criterion into the PostgreSQL migration rehearsal with an explicit threshold (for example, NFR-001 p95 met with chain appends enabled).

**Re-review scope:** None (verify at the pre-production readiness review)

**Implementation blocked?** Does not block implementation. Must be completed before production readiness sign-off.

### Advisories

| ID | Title | Evidence | Recommendation | Requirements |
|---|---|---|---|---|
| N-A1 | Path A enrollment after a new sensitive grant relies on a password-derived session | 05 §11.1 / §11.3 A: a FULL session obtained with password only (MFA not required at the time) plus password re-entry can enroll after a sensitive grant. Both proofs derive from the password. | When enrollment is triggered by a new sensitive grant, prefer path C (emailed link) or require the grant's approver to confirm. | MFA-014, MFA-012 |
| N-A2 | Cooling-off does not suspend SECURITY_DATA, DESTRUCTIVE or BULK_DATA | 05 §11.5 and 06 §5 step 8 suspend only ACCOUNT_CONTROL and ACCESS_CONTROL. `lead.erase`, `lead.delete` and `audit.read` stay usable right after recovery. | Consider extending cooling-off to DESTRUCTIVE and BULK_DATA. | MFA-013, MFA-012 |
| N-A3 | The spam queue has no ageing alert | 04 §5.5 and 09 §4.3: quarantined leads raise no notification. A false positive waits until someone opens the chip. | Add a daily count or an age alert for SUSPECTED leads. | LEAD-018, LEAD-019 |
| N-A4 | Invariant I2 counts suspended holders | 06 §7.3: I2 ignores suspension, so the only 'recovery administrator' may lack MFA and have no effective permissions. Recovery then depends on break-glass. | Have the nightly job also report whether at least one **effective** recovery administrator exists (High alert). | RBAC-020 |
| N-A5 | Endpoint index omits step-up and G11 on two rows | 08 §1 row 31 / §5.6 `unlock` (ACCOUNT_CONTROL, so G10 applies per 06 §7.1) shows no step-up. Row 43 `mfa-requirement` omits G11. The general guard rules in 06 still apply. | Align the rows with 06 §7.1. | RBAC-019, RBAC-021 |
| N-A6 | Break-glass ARN columns are VARCHAR(200) | 03 §5.8 `external_requester_ref` and `external_approver_ref` are VARCHAR(200), while `kms_key_arn` uses 2048. IAM role paths can make ARNs longer. | Size to 2048. | RBAC-021 |
| N-A7 | Overlapping new requirements | RBAC-020 overlaps RBAC-010 and RBAC-011. MFA-015 overlaps RBAC-021 and MFA-007. These are refinements, not duplicates. | Cross-reference, or mark the parent/child relationship in requirements.json. | RBAC-020, MFA-015 |
| N-A8 | Architecture validation automation is not committed | validation-report.md: the scripts are 'intentionally not committed'. The 26 checks are not reproducible from the repository. This review reproduced the key ones independently (§12). | Implementation CI (12 §5) supersedes this for code. For future architecture changes, commit the checks or keep independent reproduction as the gate. | PLAT-006 |
| N-A9 | Some RV and OP classifications understate automation | RBAC-002 (lint), PLAT-008 (secret scan), PLAT-011 (import lint), SEVT-004 and SEVT-007 (IT rows in 12 §4.3) are listed as RV or OP. | Reclassify after implementation. This is conservative, not misleading. | RBAC-002, PLAT-008, PLAT-011 |

## 14. Certification conditions

| ID | Source | Owner | Gate | Acceptance | Evidence | If not met |
|---|---|---|---|---|---|---|
| C-1 | TG-01 (F-18) | Veda Spaces owner | Before any implementation begins | The owner approves the architecture PR (or signs the decision log) from the owner's account | Link recorded in docs/architecture/decisions/decision-log.md | Implementation must not start |
| C-2 | N-01 | Architecture author | Before implementing RBAC-021 / MFA-015 (Founder workflow, approvals) | 06 §7.2 requires FOUNDER-protected requester and approver; FOUNDER role and `user.founder.manage` are grantable only through GRANT_FOUNDER; negative tests added in 12 §4.4 | Architecture commit plus targeted independent verification | Those stories stay blocked |
| C-3 | N-02 | Architecture author | Before implementing the schema conformance check (DATA-011) | All FK-less GUID `*_id` columns registered, with the allow-list stated exactly | Architecture commit plus targeted independent verification | Conformance-check story blocked; the check must not be weakened ad hoc |
| C-4 | N-03 | Architecture author (test strategy) | Before implementing recovery, RBAC resolver, duplicate-detection and concurrency stories | Concrete test designs (preconditions, action, assertion, negative) for the listed gaps; 05 §11.5 states that the LOGIN challenge is completed on recovery | 12 and 05 diff reviewed | Those stories are not Done |
| C-5 | N-04 | Architecture author plus owner | Before production readiness sign-off | Every RG/PG/TG gate lists owner, trigger, acceptance, evidence, failure behavior and phase; A-13 has a threshold in the PostgreSQL rehearsal | 11 §7.3/§11 diff | Production release blocked |

**Remaining owner inputs (production):**
- OWNER-INPUT-001: RPO, RTO and availability target.
- OWNER-INPUT-002: retention periods.
- OWNER-INPUT-003: restore-rehearsal cadence.
- OWNER-INPUT-004: named break-glass custodians.

**Remaining production gates:** RG-1…RG-9, PG-DAST, PG-RET, PG-BG, PG-EMAIL, PG-PRIV, TG-02…TG-06. None of these values is needed to start implementation safely.

## 15. Proof of non-modification

- This commit is on `review/p0-foundation-independent-review`, parent `7515b232e7407c0bb20afc5abd9656da2c246d0b`, and adds only `docs/reviews/p0-focused-independent-rereview.md` and `docs/reviews/p0-focused-independent-rereview.json`.
- The original review artifacts are unchanged.
- `architecture/p0-foundation-freeze` remains at `c3aae47a7d9b12fc0cb1491865991fde28abcf55`.
- `dist/` tree `d1d3efc…` is unchanged at the remediation SHA.
- Verify with `git diff --name-only 7515b232e7407c0bb20afc5abd9656da2c246d0b <rereview-commit>`.

## 16. Verdict and next authorized action

**CERTIFIED WITH MINOR CONDITIONS.**

- All three original MAJOR findings are substantively resolved.
- There are no BLOCKER or MAJOR findings.
- The remaining MINOR conditions (C-1…C-5) have owners, gates, acceptance criteria, evidence and failure behavior.
- Each condition blocks only the affected work, or production.

**Next authorized action.**

1. The owner completes C-1 (TG-01).
2. The owner separately and explicitly authorizes an implementation workstream.
3. Before the affected stories start, the architecture author corrects N-01, N-02 and N-03 (C-2…C-4) in a new commit.
4. A targeted independent verification of that commit confirms the corrections.

This review authorizes no implementation, merge or deployment.
