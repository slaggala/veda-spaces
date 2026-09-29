# P0 Final Targeted Independent Check — Veda Spaces

Check ID `VEDA-SPACES-P0-FINAL-TARGETED-INDEPENDENT-CHECK` · 2026-09-29 · Machine-readable version: [p0-final-targeted-check.json](p0-final-targeted-check.json)

**Scope.** This check verifies only N-01…N-04, the closure of F-19, and regressions in the listed areas, at the exact SHA. Earlier reviews: [original](p0-independent-architecture-review.md) · [focused re-review](p0-focused-independent-rereview.md).

No architecture, `dist/` or implementation file was changed. Nothing was merged or deployed.

## Verdict: **CERTIFIED WITH MINOR CONDITIONS**

| Target | Result |
|---|---|
| 1. N-01 Founder governance | **RESOLVED** |
| 2. N-02 Conformance exceptions | **NOT RESOLVED** (MINOR residual R-01; blocks only the conformance-check story) |
| 3. N-03 Test designs | **RESOLVED** |
| 4. N-04 Gate registry | **RESOLVED** |
| 5. F-19 closure | **RESOLVED** |
| Regression check | **NO REGRESSION** |

## 0. Commit and diff verification

| Command | Result |
|---|---|
| `git rev-parse origin/architecture/p0-foundation-freeze` | `73e74d3a74b32f5d5587f8358af912e273689fdd` (the branch head) |
| `git log --format='%H %P' c3aae47..origin/architecture/p0-foundation-freeze` | Exactly one commit, `73e74d3`, whose parent is `c3aae47` |
| `git rev-parse origin/review/p0-foundation-independent-review` (before this commit) | `06a4f6e7d535e84c9b4ff427d4d8bedbf96e0ba7` |
| `git diff --name-status c3aae47 73e74d3 \| grep -vE '^[AM]\s+docs/architecture/'` | Empty. 21 files: `gate-registry.md` and `gate-registry.json` added, the rest modified, all `.md`/`.json` under `docs/architecture/`. |
| `git diff --quiet c3aae47 73e74d3 -- dist` | Exit 0 (`dist/` unchanged) |
| Secret scan of the added lines | 0 matches |
| Reading | Done in a detached worktree at `73e74d3` |

## 1. N-01 Founder governance — RESOLVED

| # | Check | Evidence |
|---|---|---|
| 1 | Single canonical workflow | 06 §7.2 is declared the single authoritative definition. 08 §5.11 and ADR-010 refer to it. The contradictory "or" clause in the old 06 §7.2 is removed. |
| 2 | No direct Founder grant | G13 (06 §7.1). FOUNDER role `is_assignable = false` and `grant_path = FOUNDER_WORKFLOW_ONLY` (03 §4.3, §10 seed). |
| 3 | No direct `user.founder.manage` grant | G13 blocks it through user grants, DENY, role grants, copy and role edits. It exists only inside the FOUNDER role (registry rule 5 plus a migration assertion). I3 bans any `user_permission` row for it. |
| 4–7 | Requester ≠ approver; target cannot approve; no duplicate approver; no self-approval | 06 §7.2.3. DB CHECKs `approver_user_id <> requested_by`, `approver_user_id <> target_user_id`, and `requested_by <> target_user_id` except in-app self step-down (03 §5.8). A second approval returns `409 INVALID_STATE`. Eligibility is re-checked at request, approval and execution time. |
| 8 | Generic APIs cannot bypass | G13 lists every generic path. Rejections return `403 FOUNDER_GOVERNANCE_REQUIRED` plus a CRITICAL `FOUNDER_GOVERNANCE_BYPASS_BLOCKED`. The Founder policy itself has no runtime API. |
| 9 | Bootstrap safe | 05 §10 / 06 §7.2.4: the CLI refuses if any non-deleted Founder exists or a `BOOTSTRAP_FOUNDER` event exists, and creates only an INVITED Founder with MFA enrollment in the invite flow. (After event archival the event check lapses, but I1 guarantees a non-deleted Founder always exists, so the first condition still blocks.) |
| 10 | Single-Founder mode safe | The sole Founder requests, and a custodian mapped to a **different human** approves, with cooling-off and a cancel window (06 §7.2.4, §7.5). A Founder can never self-approve. |
| 11 | Break-glass coherent | The custodian register maps each principal to one human. Four separation rules. Two distinct humans. ARNs are sized 2048 (N-A6 fixed). `not_before`. |
| 12 | Last-Founder protection | I1 is checked at request **and** execution under the write lock. One open Founder request per target (`ux_admin_approval_request__open_founder_target`). The concurrent-REVOKE race resolves to one FAILED (`LAST_FOUNDER`). I3 has a nightly drift check. |

Tests: TD-G, cases G1–G14 (12 §4.12).

**Advisory A-F1.** Any notified party, including the target, may cancel a break-glass request (06 §7.5 step 5). That lets a hostile or absent sole Founder block custodian actions indefinitely. This is a governance choice, not a defect. The owner should confirm it when designating custodians (OWNER-INPUT-004).

## 2. N-02 Conformance exceptions — NOT RESOLVED (MINOR residual)

What is correct:

- The registry exists (03 §2.11) and lists exactly 10 columns: EXC-009 ×3 and EXC-011 ×7.
- All seven original columns are present, each with purpose, reason, discriminator, pair CHECK, format CHECK, index, retention and approval.
- The UUIDv7 format CHECK is required per column.
- Append-only rules and FK protections are unchanged, and purge order is re-tested (TD-H H8).
- Unregistered GUID columns fail the check (TD-H H2).
- No loophole for GUID columns was introduced.

**Residual R-01 (MINOR).** Rule 3 (03 §2.7) now treats as ID-like any column whose name ends in `_id`, `_by` or `_to`, or that is GUID-typed. It then requires a FK or membership in the 10-column GUID-only allow-list, where 'registered column must be GUID'. Three designed **non-GUID string** columns match the name pattern, have no FK, and cannot be registered:

- `audit_log.request_id` VARCHAR(64) (03 §7)
- `security_event_log.request_id` VARCHAR(64) (03 §5.4)
- `outbox_event.locked_by` VARCHAR(64) (03 §8.1): a worker identifier, not an entity reference

So TD-H H1 ('the real schema passes') cannot pass as specified, and validation V31 ('45 ID-like columns… PASS') did not evaluate string columns.

Reviewer's note: `request_id` also matched the earlier `*_id` wording and was missed in my N-02 enumeration of the focused re-review. `locked_by` is new with the broadened pattern.

- **Required remediation.** Restrict the name heuristic to GUID-typed columns, or add an explicit, documented list of non-entity string correlation columns (`request_id` ×2, `locked_by`) exempt from rule 3. Update TD-H with a positive case for them and a negative case for an undocumented string `*_id`.
- **Re-review scope.** 03 §2.7/§2.11 and 12 §4.12 TD-H only.
- **Implementation blocked?** Only the schema-conformance-check story (DATA-011) until corrected. Nothing else.

## 3. N-03 Test designs — RESOLVED

TD-A through TD-F (12 §4.12) each state preconditions, fixtures, action, expected result, security and audit events, negative assertions, cleanup and CI evidence. TD-H also inherits R-01.

| Required design | Location | Verified content |
|---|---|---|
| DENY-over-GRANT | TD-A | Role, direct and OWN grants against a DENY; the same access token on the next request → 403; a 3×3 resolver table |
| Duplicate lead detection | TD-B | 180-day match flagged `SUSPECTED` and stored; different key → new lead; spent-token retry → identical 201 without a Turnstile call; key reuse → 422; no disclosure |
| Expired recovery | TD-C | Clock +15 min 1 s → 401 on the whole allow-list; consumed code not restored; PENDING factor abandoned |
| Challenge reuse | TD-D | M1 completed, M2 invalidated, `MFA_CHALLENGE_REPLAY_BLOCKED`, S1/S2 revoked; prohibited-content scan. The specification is also added in 05 (§11.5). |
| Failed re-enrollment | TD-E | 5 wrong codes, forced DB failure during confirm → full rollback; single PENDING; no sensitive permission effective. Commit rule specified in 05 §11.5. |
| Optimistic concurrency | TD-F | Two-writer barrier on both engines → one 200 and one 409 with `current_version`; no audit row for the loser; UI conflict dialog |

## 4. N-04 Gate registry — RESOLVED

- A canonical `gate-registry.md` and `gate-registry.json` exist with 27 gates: OWNER-INPUT-001…004, TG-01…TG-08, RG-1…RG-9, the five PG-* gates and PGM-1.
- A programmatic check found every gate has an owner category, trigger point, acceptance criteria, required evidence plus storage location, failure behavior and release phase, plus approver, freshness and revalidation.
- The rule is stated: a missing or stale evaluation is FAIL.
- **TG-01 is 'Pending — no verifiable owner approval exists'**, and the registry states that no gate is passed.
- A-13 now has a measurable gate: PGM-1 requires NFR-001 p95 on PostgreSQL with chain appends under the advisory lock.

## 5. F-19 closure — RESOLVED

Every test gap raised across the reviews is either designed or gated:

- **Designed:** upgrade-with-data and N-1 tests, CSRF, token after revocation, grace window, contention, the browser matrix, and TD-A…TD-H.
- **Gated:** DAST and penetration testing through TG-03 / PG-DAST (Security Owner, report evidence, acceptance 'no open High/Critical'). RPO/RTO and availability through OWNER-INPUT-001 / RG-1.

The coverage gate now reports automated tests separately from RV/OP and owner-gated items.

## 6. Regression check — NO REGRESSION

| Area | Result |
|---|---|
| MFA design | Intact. Path A no longer serves enrollment triggered by a new sensitive grant (advisory N-A1 addressed). |
| Recovery design | Intact, and strengthened: challenge completion and atomic confirm are specified |
| Email-change workflow | Unchanged (no diff in 05 §8.6 or 08 §4.8/§5.5) |
| Founder protections | Strengthened (§1) |
| Sales permission model | Re-verified: Sales grants ∩ the 16 sensitive codes = ∅ |
| Audit architecture | Intact. Actor FKs and append-only unchanged. |
| Security-event architecture | Intact. New event types are allow-listed and CRITICAL where appropriate. |
| UUIDv7 contract | Intact. Format CHECKs are now also required on FK-less columns. |
| Audit contract | Intact. R-01 concerns only the conformance rule wording, not the contract. |

Structural rechecks at `73e74d3`:

- 221 requirements (208 P0 / 10 P1 / 3 P2), none added or removed since `c3aae47`.
- All JSON files parse.
- 0 broken references or links.
- 0 `Traces:` lines.

## 7. Certification answers

1. **Reviewed SHA:** `73e74d3a74b32f5d5587f8358af912e273689fdd`
2. **Review commit:** recorded in the review branch history (the final response gives the SHA).
3. **Remaining owner approvals:**
   - Before implementation: TG-01 (verifiable approval of the architecture) and TG-08 (explicit implementation authorization).
   - Before production: OWNER-INPUT-001…004.
4. **Remaining production gates:** RG-1…RG-9, PG-DAST, PG-RET, PG-BG, PG-EMAIL, PG-PRIV, TG-02…TG-06. PGM-1 applies later, at the PostgreSQL migration.
5. **Can TG-01 now be completed?** Yes. This check satisfies TG-07 (independent confirmation) for N-01, N-03, N-04 and F-19. N-02 has one tracked MINOR residual (R-01) that blocks only DATA-011. The owner may approve now with R-01 as a recorded condition, or after the author's small R-01 fix.
6. **Is the architecture branch ready for merge?** From a review standpoint, there is no blocker once the owner completes TG-01 (PR approval). The reviewer recommends including the R-01 fix before merge, because it is a small documentation edit. Merging is the owner's action; this review does not merge.
7. **May an implementation workstream be authorized?** Yes, by the owner (TG-08), after TG-01. Condition: the DATA-011 conformance-check story must not start until R-01 is corrected and verified. All other stories may proceed under the existing gates.

Implementation has not been started by this review.
