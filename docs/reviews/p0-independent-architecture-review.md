# P0 Independent Architecture Review — Veda Spaces

Review ID `VEDA-SPACES-P0-INDEPENDENT-ARCHITECTURE-REVIEW-01` · 2026-09-29 · Machine-readable version: [p0-independent-architecture-review.json](p0-independent-architecture-review.json)

This is an independent certification review. The reviewer did not author the architecture. Every author claim was treated as unverified and checked against the repository at the frozen SHA. No architecture file, `dist/` file or implementation code was changed, and nothing was merged or deployed.

## Summary

| Item | Value |
|---|---|
| A. Reviewed commit | `4dce177745a2b8f0b9fdb21de2e563ccd022fb0e` (branch `architecture/p0-foundation-freeze`, parent `13276a017a137c4a86b15fea0306ea2e83ac2729`) |
| B. Review branch | `review/p0-foundation-independent-review` (created from the frozen SHA; contains only `docs/reviews/*` changes) |
| C. Review commit | Recorded in the review branch history. A file cannot contain its own commit id. |
| D. Push status | Pushed to `origin` without force (see the final response) |
| E. Requirement recount | 203 total · 186 P0 · 14 P1 · 3 P2. No duplicates. **Matches the author's claim.** |
| F. Coverage (independent, P0) | Fully 158 · Partial 22 · Contradictory 4 · Not testable 2 · Referenced-only 0 · Not covered 0 · Ambiguous 0. **The author's 100% is not confirmed.** |
| G. Findings | BLOCKER 0 · **MAJOR 3** · MINOR 18 · ADVISORY 14 |
| H. Assumptions | 7 acceptable for P0 · 2 need an owner decision before implementation (ASM-005, ASM-012) · 3 before production (ASM-006, ASM-009, ASM-011) · 0 immediate |
| I. Owner decisions | OWNER-INPUT-001…003, plus new decisions for F-01, ASM-005 and ASM-012 (§13) |
| J. Architecture files unmodified | The review commit changes only `docs/reviews/` (§15) |
| K. `dist/` unchanged | Tree `d1d3efc…` and content SHA-256 `8986bdfa…c9a8` are identical at the parent, the frozen commit and the working tree |
| L. **Verdict** | **NOT CERTIFIED** |
| M. Next authorized action | §16 |

**Overall judgment.** This is a strong, unusually thorough foundation. The audit contract, UUIDv7 mapping, permission-only RBAC, outbox isolation, security-event separation and SQLite operating constraints are well reasoned and mostly internally consistent. Certification is withheld for three MAJOR security-design defects: a contradiction between the MFA policy and the seeded role matrix (F-01), password-only MFA re-enrollment after recovery (F-02), and account-control operations that bypass the stronger-target guard (F-03). All three are correctable with targeted edits. None requires rethinking the architecture.

## 1. Phase 1 — Repository and scope verification

| Command | Result |
|---|---|
| `git fetch origin` | remote reachable; no new refs |
| `git rev-parse origin/architecture/p0-foundation-freeze` | 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e |
| `git cat-file -t 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e` | commit |
| `git merge-base --is-ancestor 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e origin/architecture/p0-foundation-freeze` | exit 0 (reachable) |
| `git log --oneline 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e..origin/architecture/p0-foundation-freeze` | (empty): no later commits on the branch |
| `git status --porcelain (before review)` | (empty): clean working tree |
| `git log -1 --format=%P 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e` | 13276a017a137c4a86b15fea0306ea2e83ac2729 |
| `git diff --name-status 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e^ 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e \| grep -v '^A\sdocs/architecture/'` | (empty): all 26 changes are additions under docs/architecture/ |
| `git diff --quiet 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e^ 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e -- dist` | exit 0: dist identical to parent |
| `git ls-tree 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e^ dist ; git ls-tree 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e dist` | both tree d1d3efced8aa4ee67c2d832aae075d0f3f136cf9 |
| `dist content SHA-256 (sha256 of sorted 'sha256  path' lines over git ls-files dist, LC_ALL=C)` | 8986bdfaa44dd800968183d338ddfa63c6cae2ef915d1ae41e7ad4939363c9a8 at parent, frozen commit and working tree |
| `git diff --numstat 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e^ 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e \| awk '$1=="-"'` | (empty): no binary files added |
| `git grep -I -E 'AKIA[0-9A-Z]{16}\|-----BEGIN\|otpauth://\|[a-z]+://[^ ]*:[^ @]+@' 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e` | only documentation otpauth examples with an elided or example secret (A-10) |
| `git ls-tree -r --name-only 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e \| grep -iE '\.env\|\.pem\|\.key\|\.p12\|credentials'` | (empty) |
| `python3 -m json.tool validation-report.json / requirements.json` | both valid JSON |

Conclusions:

- The branch exists remotely, the commit exists and is the branch head, and no later commit was included.
- The review was performed against the exact frozen SHA, with a clean working tree.
- All 26 changes in the frozen commit are additions under `docs/architecture/` (9,712 insertions). There is no implementation code, no binary, no environment file and no credential. The only secret-like strings are documentation examples: an elided `secret=…` and the public example key `JBSWY3DPEHPK3PXP` (A-10).
- `dist/` is byte-identical to the parent. The author's SHA-256 value is not recorded in the repository, so it could not be compared. The reproducible content hash above replaces it.

## 2. Phase 2 — Document inventory and integrity

| File | Lines | Bytes |
|---|---|---|
| `docs/architecture/README.md` | 77 | 6283 |
| `docs/architecture/01-requirements-traceability.md` | 378 | 38113 |
| `docs/architecture/02-platform-architecture.md` | 522 | 34450 |
| `docs/architecture/03-database-schema.md` | 738 | 47073 |
| `docs/architecture/04-lead-management.md` | 387 | 23091 |
| `docs/architecture/05-authentication.md` | 429 | 25657 |
| `docs/architecture/06-rbac.md` | 254 | 18817 |
| `docs/architecture/07-audit.md` | 205 | 10173 |
| `docs/architecture/08-api-design.md` | 980 | 48341 |
| `docs/architecture/09-ui-ux-design.md` | 573 | 51332 |
| `docs/architecture/10-future-roadmap.md` | 221 | 15900 |
| `docs/architecture/11-production-readiness.md` | 256 | 17857 |
| `docs/architecture/12-test-strategy.md` | 234 | 17154 |
| `docs/architecture/coverage-gate.md` | 117 | 6243 |
| `docs/architecture/requirements.json` | 3260 | 75392 |
| `docs/architecture/validation-report.json` | 419 | 13361 |
| `docs/architecture/validation-report.md` | 64 | 6776 |
| `docs/architecture/decisions/ADR-001-app-user-table.md` | 54 | 2461 |
| `docs/architecture/decisions/ADR-002-uuidv7-identifiers.md` | 80 | 3213 |
| `docs/architecture/decisions/ADR-003-audit-contract.md` | 71 | 3648 |
| `docs/architecture/decisions/ADR-004-security-event-log.md` | 74 | 3853 |
| `docs/architecture/decisions/ADR-005-lead-required-fields.md` | 67 | 3372 |
| `docs/architecture/decisions/ADR-006-mfa-policy.md` | 73 | 3066 |
| `docs/architecture/decisions/ADR-007-technology-stack.md` | 54 | 2390 |
| `docs/architecture/decisions/ADR-008-aws-hosting.md` | 55 | 2723 |
| `docs/architecture/decisions/ADR-009-p0-scope.md` | 70 | 1937 |

- 12 numbered documents, README, ADR-001…009, validation-report.json/.md, coverage-gate.md and requirements.json are present. No file is empty or a placeholder.
- Both JSON files are valid. requirements.json holds 203 unique IDs, and every registry ID appears in 01.
- An independent resolver checked 873 `NN §x.y` references and every relative link: 0 broken. It found no TBD, TODO or FIXME markers outside the validation report's description of its own check.
- Terminology is consistent: User/`app_user`, actor, scope, step-up and outbox follow the README glossary.
- **Circularity.** The 119 `> Traces:` lines were injected from the registry, and 'covered' is defined as 'the section cites the ID'. Citation coverage is therefore self-fulfilling (F-21). Substantive coverage was assessed independently in §5.

## 3. Phase 3 — Requirement recount

| Priority | Count |
|---|---|
| P0 | 186 |
| P1 | 14 |
| P2 | 3 |
| **Total** | **203** |

The test dimension applies to 199 IDs: all 186 P0, plus 13 of the 17 deferred. The four deferred IDs without verification (LEAD-022, ACT-005, NOTIF-006, NOTIF-007) are correctly reported by the author. Of the 186 P0 test references, 11 point only to method, environment or CI sections rather than a test design (F-19).

## 4. Coverage by dimension (independent)

| Dimension | Assessment | Notes |
|---|---|---|
| Architecture | Substantive | Modular monolith, layering, module rules and outbox are coherent (02 §3, §10). |
| Data model | Substantive, with defects | Contract, GUID mapping and constraints are strong. Registry gaps (F-08), purge/FK conflicts and missing session retention (F-07), and a column size (F-13). |
| APIs | Substantive, with defects | 85 endpoint rows, closed schemas, RFC 9457, If-Match. Idempotency contradiction (F-04); account-control guard gap (F-03). |
| UI/UX | Substantive, with defects | Every in-scope screen has empty, loading, error and permission states. Dark-mode contrast (F-14), missing note restore (F-20), no staff-facing security-event self view beyond the admin drawer and Profile › Security. |
| Authentication | Substantive, with MAJOR defects | Argon2id, ES256, rotation, enumeration safety. MFA-policy contradiction (F-01), password-only re-enrollment (F-02), revocation latency (F-10). |
| Authorization | Substantive, with a MAJOR defect | Permission-only checks, DENY precedence, scopes, guards G1–G10. G9 does not cover email change or deactivate (F-03); expiry bypasses G4 (F-16). |
| Security | Substantive | Edge, origin lock, CSP, CORS, secrets and KMS are well designed. Findings F-01–F-03, F-05, F-09, F-11. |
| Auditability | Substantive | Atomic unit-of-work audit, parent linkage, redaction, immutable stores. The SENSITIVE_ACTION read contradiction (F-06). |
| Observability | Substantive | Structured logs, masking, request-id correlation, metrics and alerts. Readiness coupling (F-12). |
| Operations | Substantive, gated | Single-instance SQLite on encrypted EBS, Litestream, restore verification. Owner inputs are pending; rollback procedures are inconsistent (F-12). |
| Test strategy | Broad but shallow in places | Verification methods for all P0 IDs, but 11 map to method, environment or CI sections, and several security suites are missing (F-19). |
| Migration | Substantive | Type mapping, dual-engine CI, rehearsal and checksum runbook. Chain canonicalization is undefined (F-11). |
| Recovery | Substantive, owner-gated | Mechanisms are designed. RPO/RTO/availability are not approved (OWNER-INPUT-001). |

## 5. Independent P0 requirements coverage matrix

Each cited section was read. A `Traces:` line was not accepted as evidence. 'Fully covered' means the design content is sufficient to implement and verify the requirement as written.

| Classification | Count |
|---|---|
| Fully covered | 158 |
| Partially covered | 22 |
| Contradictory | 4 |
| Not testable | 2 |
| Referenced but not substantively covered | 0 |
| Not covered | 0 |
| Ambiguous | 0 |

| ID | Verify | Classification | Findings | Note |
|---|---|---|---|---|
| PLAT-001 | RV | Fully covered | — | — |
| PLAT-002 | RV | Fully covered | — | — |
| PLAT-003 | OP | Fully covered | — | — |
| PLAT-004 | IT | Fully covered | — | — |
| PLAT-005 | RV | Fully covered | — | — |
| PLAT-006 | RV | Fully covered | — | — |
| PLAT-007 | UT | Fully covered | — | — |
| PLAT-008 | RV | Fully covered | — | — |
| PLAT-009 | IT | Fully covered | — | — |
| PLAT-010 | IT | Fully covered | — | — |
| PLAT-011 | RV | Fully covered | — | — |
| PLAT-012 | RV | Fully covered | — | — |
| PLAT-013 | SL | Fully covered | — | — |
| DATA-001 | SL | Fully covered | — | — |
| DATA-002 | SL, UT | Fully covered | — | — |
| DATA-003 | UT | Fully covered | — | — |
| DATA-004 | SL | Fully covered | — | — |
| DATA-005 | SL, IT | Fully covered | — | — |
| DATA-006 | IT | Fully covered | — | — |
| DATA-007 | IT | Fully covered | — | — |
| DATA-008 | IT | Fully covered | — | — |
| DATA-009 | RV | Partially covered | F-07 | Purge rules conflict with RESTRICT FKs; session retention is undefined. |
| DATA-010 | IT | Fully covered | — | — |
| DATA-011 | SL | Fully covered | — | — |
| DATA-012 | SL | Fully covered | — | — |
| DATA-013 | IT | Fully covered | — | — |
| DATA-014 | SL | Partially covered | F-08, F-07 | The registry omits three unique indexes and the purge/FK conflicts. |
| DATA-015 | IT | Fully covered | — | — |
| DATA-016 | SL | Fully covered | — | — |
| AUDIT-001 | IT | Fully covered | — | — |
| AUDIT-002 | IT | Fully covered | — | — |
| AUDIT-003 | IT | Fully covered | — | — |
| AUDIT-004 | IT | Fully covered | — | — |
| AUDIT-005 | UT | Fully covered | — | — |
| AUDIT-006 | IT | Fully covered | — | — |
| AUDIT-008 | E2E | Fully covered | — | — |
| AUDIT-010 | UT | Fully covered | — | — |
| AUDIT-012 | IT | Fully covered | — | — |
| AUTH-001 | E2E | Fully covered | — | — |
| AUTH-002 | UT | Fully covered | — | — |
| AUTH-003 | UT | Fully covered | — | — |
| AUTH-004 | IT | Fully covered | — | — |
| AUTH-005 | IT | Partially covered | F-10 | Grace-window behavior is unspecified. |
| AUTH-006 | IT | Partially covered | F-10 | 'Immediately' versus a ≤ 30 s per-process cache. |
| AUTH-007 | IT | Fully covered | — | — |
| AUTH-008 | IT | Fully covered | — | — |
| AUTH-009 | IT | Fully covered | — | — |
| AUTH-010 | IT | Partially covered | F-09 | The per-IP limiter is per worker process. |
| AUTH-011 | IT | Fully covered | — | — |
| AUTH-012 | IT | Fully covered | — | — |
| AUTH-013 | IT | Fully covered | — | — |
| AUTH-014 | OP | Fully covered | — | — |
| AUTH-015 | E2E | Partially covered | F-01, F-02 | Enforcement is designed; the policy is contradictory and post-reset enrollment is password-only. |
| AUTH-017 | IT | Partially covered | F-10 | Same cache latency as AUTH-006. |
| AUTH-018 | IT | Contradictory | F-01 | Sales persona 'configurable MFA' is contradicted by the seeded matrix. |
| SEVT-001 | IT | Fully covered | — | — |
| SEVT-002 | IT | Fully covered | — | — |
| SEVT-003 | UT | Fully covered | — | — |
| SEVT-004 | OP | Fully covered | — | — |
| SEVT-005 | IT | Fully covered | — | — |
| SEVT-006 | UT | Partially covered | F-11 | The chain is unkeyed; the anchor is in the DB; canonicalization is undefined. |
| SEVT-008 | IT | Fully covered | — | — |
| SEVT-009 | OP | Fully covered | — | — |
| SEVT-010 | RV | Fully covered | — | — |
| SEVT-011 | IT | Fully covered | — | — |
| MFA-001 | E2E | Fully covered | — | — |
| MFA-002 | IT | Fully covered | — | — |
| MFA-003 | IT | Contradictory | F-01 | Sales holds sensitive security_event.read (OWN), so MFA is mandatory, not configurable. |
| MFA-004 | IT | Fully covered | — | — |
| MFA-005 | IT | Fully covered | — | — |
| MFA-006 | IT | Fully covered | — | — |
| MFA-007 | IT | Partially covered | F-02 | The reset workflow is sound; re-enrollment after reset is not bound to an out-of-band proof. |
| MFA-008 | RV | Fully covered | — | — |
| MFA-009 | UT | Fully covered | — | — |
| MFA-010 | IT | Partially covered | F-13 | Envelope encryption is sound; the key-reference column is likely undersized. |
| MFA-011 | IT | Fully covered | — | — |
| RBAC-001 | SL | Fully covered | — | — |
| RBAC-002 | RV | Fully covered | — | — |
| RBAC-003 | SL | Fully covered | — | — |
| RBAC-004 | IT | Fully covered | — | — |
| RBAC-005 | IT | Fully covered | — | — |
| RBAC-006 | UT | Fully covered | — | — |
| RBAC-008 | IT | Fully covered | — | — |
| RBAC-009 | IT | Partially covered | F-03 | Grant escalation is covered (G1/G2); account-control escalation (email change, deactivate) is not. |
| RBAC-010 | IT | Fully covered | — | — |
| RBAC-011 | IT | Partially covered | F-03, F-16 | G4 is transactional only; time-bound expiry and disabling co-admins are not covered. |
| RBAC-012 | IT | Fully covered | — | — |
| RBAC-013 | IT | Fully covered | — | — |
| RBAC-014 | IT | Fully covered | — | — |
| RBAC-015 | IT | Fully covered | — | — |
| RBAC-017 | IT | Contradictory | F-06 | 'Every use emits SENSITIVE_ACTION' conflicts with 05 §9.5 for reads. |
| USER-001 | IT | Partially covered | F-03 | User administration lacks stronger-target and step-up controls for email change and deactivate. |
| USER-002 | UT | Fully covered | — | — |
| USER-003 | IT | Fully covered | — | — |
| USER-004 | IT | Fully covered | — | — |
| USER-005 | IT | Fully covered | — | — |
| USER-006 | E2E | Fully covered | — | — |
| LEAD-001 | E2E | Fully covered | — | — |
| LEAD-002 | SL | Fully covered | — | — |
| LEAD-003 | E2E | Fully covered | — | — |
| LEAD-004 | SL | Fully covered | — | — |
| LEAD-005 | UT | Fully covered | — | — |
| LEAD-006 | IT | Fully covered | — | — |
| LEAD-007 | IT | Fully covered | — | — |
| LEAD-008 | IT | Fully covered | — | — |
| LEAD-009 | UT | Fully covered | — | — |
| LEAD-010 | IT | Fully covered | — | — |
| LEAD-011 | IT | Fully covered | — | — |
| LEAD-012 | IT | Fully covered | — | — |
| LEAD-013 | IT | Fully covered | — | — |
| LEAD-014 | E2E | Fully covered | — | — |
| LEAD-015 | IT | Fully covered | — | — |
| LEAD-016 | IT | Fully covered | — | — |
| LEAD-018 | IT | Partially covered | F-05, F-04 | Honeypot false-positive risk; Turnstile checked before idempotency. |
| LEAD-019 | E2E | Partially covered | F-05 | 02 §2.4 fallback triggers omit 429 and CAPTCHA; inconsistent with 09 §4.11. |
| LEAD-020 | IT | Fully covered | — | — |
| LEAD-023 | IT | Fully covered | — | — |
| LEAD-024 | IT | Fully covered | — | — |
| LEAD-025 | IT | Fully covered | — | — |
| LEAD-026 | E2E | Fully covered | — | — |
| NOTE-001 | IT | Fully covered | — | — |
| NOTE-002 | IT | Partially covered | F-20 | The UI Undo needs a nonexistent restore endpoint. |
| NOTE-004 | SL | Fully covered | — | — |
| ACT-001 | IT | Fully covered | — | — |
| ACT-002 | IT | Fully covered | — | — |
| ACT-003 | IT | Fully covered | — | — |
| ACT-004 | IT | Fully covered | — | — |
| NOTIF-001 | IT | Fully covered | — | — |
| NOTIF-002 | IT | Fully covered | — | — |
| NOTIF-003 | IT | Fully covered | — | — |
| NOTIF-004 | IT | Fully covered | — | — |
| NOTIF-005 | RV | Fully covered | — | — |
| NOTIF-008 | IT | Fully covered | — | — |
| NOTIF-009 | IT | Fully covered | — | — |
| LOG-001 | RV | Fully covered | — | — |
| LOG-002 | IT | Fully covered | — | — |
| LOG-003 | UT | Fully covered | — | — |
| LOG-004 | OP | Fully covered | — | — |
| LOG-005 | IT | Partially covered | F-12 | Readiness is coupled to outbox lag, which reflects email-provider health. |
| LOG-006 | OP | Fully covered | — | — |
| SEC-001 | OP | Fully covered | — | — |
| SEC-002 | IT | Fully covered | — | — |
| SEC-003 | IT | Fully covered | — | — |
| SEC-004 | UT | Fully covered | — | — |
| SEC-005 | RV | Fully covered | — | — |
| SEC-006 | OP | Fully covered | — | — |
| SEC-007 | OP | Fully covered | — | — |
| SEC-008 | OP | Fully covered | — | — |
| SEC-009 | RV | Partially covered | F-15 | No P0 retention, withdrawal or erasure procedure. |
| SEC-011 | IT | Partially covered | F-09 | Application limits are per worker process. |
| API-001 | IT | Fully covered | — | — |
| API-002 | IT | Fully covered | — | — |
| API-003 | IT | Fully covered | — | — |
| API-004 | IT | Fully covered | — | — |
| API-005 | IT | Fully covered | — | — |
| API-006 | IT | Fully covered | — | — |
| API-007 | IT | Contradictory | F-04 | 04 §5.1 and 08 §2.8 disagree; the schema cannot detect body mismatch. |
| API-008 | RV | Fully covered | — | — |
| API-009 | RV | Fully covered | — | — |
| UI-001 | E2E | Fully covered | — | — |
| UI-002 | E2E | Fully covered | — | — |
| UI-003 | E2E | Fully covered | — | — |
| UI-004 | E2E | Fully covered | — | — |
| UI-005 | E2E | Fully covered | — | — |
| UI-006 | E2E | Fully covered | — | — |
| UI-007 | E2E | Fully covered | — | — |
| UI-008 | E2E | Fully covered | — | — |
| UI-009 | E2E | Fully covered | — | — |
| UI-010 | RV | Fully covered | — | — |
| UI-011 | E2E | Partially covered | F-14 | Dark-mode primary button fails contrast. |
| UI-012 | E2E | Fully covered | — | — |
| UI-013 | E2E | Fully covered | — | — |
| UI-014 | RV | Partially covered | F-14 | No on-color token; the dark theme is not verified. |
| UI-015 | E2E | Fully covered | — | — |
| OPS-001 | OP | Fully covered | — | — |
| OPS-002 | OP | Fully covered | — | — |
| OPS-003 | RV | Fully covered | — | — |
| OPS-004 | OP | Partially covered | F-12 | 02 §12.2 and 11 §2 B3 describe different rollback procedures. |
| OPS-005 | OP | Not testable | F-19 | RPO/RTO are pending OWNER-INPUT-001; the mechanism is designed. |
| OPS-006 | OP | Fully covered | — | — |
| OPS-007 | OP | Fully covered | — | — |
| OPS-008 | RV | Fully covered | — | — |
| OPS-009 | OP | Fully covered | — | — |
| NFR-001 | IT | Fully covered | — | — |
| NFR-002 | OP | Not testable | F-19 | The availability target is pending OWNER-INPUT-001. |
| NFR-003 | IT | Fully covered | — | — |

## 6. Phase 4 — ADR consistency

| ADR | Result | Evidence |
|---|---|---|
| ADR-001 | **Consistent** | No physical `user` table in any table section, inventory or DDL. All 23 tables carry actor FKs to `app_user.id`. API and permission terminology remain User. The approval record it cites is absent (F-18). |
| ADR-002 | **Consistent** | UUIDv7, 32 lowercase hex, pattern `^[0-9a-f]{12}7[0-9a-f]{3}[89ab][0-9a-f]{15}$`. SQLite CHAR(32) plus CHECK and PostgreSQL native uuid are explicit (03 §12). The seeded ids `…7000800…0001-3` validate against the pattern. No integer domain ids exist; `chain_seq`, `next_value` and counters are internal. UUIDv7 timestamps are visible to staff only. |
| ADR-003 | **Consistent, with defects** | Nine columns on all 23 tables. NOT NULL actor FKs are operationally possible through seeded SYSTEM, WEB_INTAKE and ANONYMOUS users (SYSTEM self-references at bootstrap). Optimistic concurrency is implementable. Immutable evidence tables keep contract columns with fixed semantics (EXC-001), and the documents prohibit mutation; see §6.1. Registry gaps F-07 and F-08. |
| ADR-004 | **Consistent, with defects** | Append-only, prohibited-content list, allow-listed detail, retention, archival, indexes, alerts and access are designed. Responsibilities are separated from audit_log (entity changes versus access telemetry). SENSITIVE_ACTION overlaps by design but reads are contradictory (F-06). Tamper evidence is overstated for P0 (F-11). Its access model triggers F-01. |
| ADR-005 | **Consistent, with defects** | Required and optional fields, E.164 with IN default, duplicates flagged not rejected, Turnstile, rate limits and honeypot, accessible errors, WhatsApp fallback, non-disclosure. Defects: idempotency (F-04), silent-drop paths (F-05), live-form mapping (F-17). |
| ADR-006 | **NOT consistent** | Custom roles cannot bypass MFA for sensitive permissions (rule 3 is independent of role flags). TOTP, keyed recovery-code hashes, audited privileged reset and step-up are sound. However, 'configurable for Sales' contradicts the seeded matrix (F-01), and account recovery weakens MFA (F-02). Note that a custom role with broad data access (`lead.read`=ALL) and no sensitive permission needs no MFA; this is consistent with the policy as written, but the owner should confirm it. |
| ADR-007 | **Consistent** | Lit + TypeScript, Flask, SQLAlchemy and Alembic with service and repository layers, /api/v1, RFC 9457, Pydantic, OpenAPI. Email is sent after commit from the outbox, so it cannot undo a lead (02 §10.3, 12 §4.7). |
| ADR-008 | **Consistent, owner-gated** | Single active instance, dedicated KMS-encrypted EBS (`DeleteOnTermination=false`), Litestream, snapshots, automated restore verification, SSM/Secrets Manager/KMS, health, logs, metrics and alerts. No horizontal-scaling claim. The PostgreSQL gate is explicit. RPO/RTO and region are not yet decided. |
| ADR-009 | **Consistent, with a defect** | No roadmap-module table, endpoint, permission or migration in P0 (verified against 03 §11, 02 §8.3, 08 §1 and 06 §6). Deferred P1 features leak into P0 surfaces (F-16). |

### 6.1 Contract columns on append-only evidence tables

Carrying `updated_on`, `updated_by`, `is_deleted`, `deleted_on`, `deleted_by` and `version` on `audit_log` and `security_event_log` is semantically empty, but it is **acceptable** as implemented:

- EXC-001 fixes their values for life (`updated_on = created_on`, `updated_by = created_by`, `version = 1`, `is_deleted = false`).
- 07 §6 forbids mutation at the application layer and adds database guards (SQLite triggers; PostgreSQL grants plus triggers).
- Retention uses a hard delete after archival (EXC-002), never a soft delete.
- The only sanctioned mutation is audited PII erasure (07 §8.2, P1).

The semantics are accurate and documented. The residual weakness is that SQLite guards can be dropped by the application connection (A-02).

### 6.2 Other checks

- **Floating-point money.** None. MONEY_MINOR is BIGINT with `currency`, and budget ranges are lookup attributes in minor units.
- **Unindexed search.** Contains-search is unindexed by design on SQLite (acknowledged in 11 S4).
- **Case-sensitive uniqueness.** `email_normalized` covers emails; role names are case-sensitive (A-04).
- **Nullable actors.** None. `deleted_by` is nullable, correctly.
- **Recursive audit.** The IMMUTABLE_STORE and EVENT_ONLY policies prevent audit-of-audit.
- **Deleted referenced users.** Users are soft-deleted only; FKs are RESTRICT.
- **Sequential-volume leakage.** No public exposure: `lead_number` is staff-only and `chain_seq` is never returned.
- **Engine differences.** Mapped in 03 §12, with the exceptions A-03 and F-11.

## 7. Phase 6 — Authentication and session security

Sound elements:

- Argon2id (64 MiB, t = 3, p = 1, rehash on login).
- NIST-style password policy.
- Uniform 401 responses and dummy-hash timing.
- ES256 access tokens (15 min, memory-only) carrying a `sid` checked against the server session.
- Opaque, rotated refresh tokens in `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth` cookies, with Origin plus a custom header for CSRF.
- An exact-origin CORS allowlist.
- Password-reset tokens in the URL fragment, hashed, 30 minutes, with all sessions revoked on reset.
- TOTP with replay (`last_used_step`) and attempt limits, and keyed-hash recovery codes.
- Session fixation is not possible: sessions are created only after successful authentication, and no pre-auth session is carried over.

Paths identified:

| Threat | Path | Finding |
|---|---|---|
| Authentication bypass / unauthorized MFA enrollment | Password alone enrolls a new factor after an MFA reset, or when policy newly requires MFA | F-02 (MAJOR) |
| Privilege escalation / account takeover | `user.update` changes a stronger user's email, then a password reset | F-03 (MAJOR) |
| Last-administrator lockout | An Admin disables the Founder (G4 satisfied by the Admin); time-bound expiry removes an admin silently | F-03, F-16 |
| Stale authorization / token replay | 30 s per-process cache; undefined refresh grace behavior | F-10 |
| Brute force | Per-worker in-memory limiter; lockout DoS | F-09, A-01 |
| CSRF | Not found: SameSite=Strict plus Origin plus custom header on the only cookie endpoints | — |
| User enumeration | Not found on login, forgot-password or reset. `POST /users` returns 409 DUPLICATE only to privileged `user.create` holders | — |
| Unauthorized MFA reset | Guarded by permission, step-up, no-self and G9 | Sound, apart from F-02 |
| Secret redaction | Prohibited-content list, allow-listed `detail`, API never returns hashes | Sound |
| Session cleanup and retention | `user_session` has no retention and is pinned by evidence FKs | F-07 |

## 8. Phase 7 — RBAC and authorization

Authorization is permission-based:

- A lint bans role-code literals, and the MFA policy uses data flags.
- Precedence is deny-by-default, DENY beats GRANT, and the broadest scope wins. The explicit exception register covers 6 RBX entries.
- Self-edit (G3), escalation through grants and roles (G1/G2) and last administrator (G4) are guarded.
- Permission changes propagate through `authz_version` within 30 s.
- Sensitive-permission MFA is independent of role flags, so a custom role cannot hold a sensitive permission without MFA.
- Service accounts are seeded non-login users.

Privilege-escalation search results:

- **Grant paths.** None found: Admin cannot assign FOUNDER or create a super-role (G2), and cannot edit roles it holds (G3).
- **Account-control paths.** Found (F-03).
- **Expiry path.** Found (F-16).
- **Role copy.** Safe at assignment time; document it (A-06).
- **Scope.** Horizontal access to leads, notes and activities is constrained by the parent-visibility rule and 404 semantics. The duplicate-resolution target needs a scope check (A-07).

## 9. Phase 8 — Lead workflow trace

| # | Step | Assessment |
|---|---|---|
| 1 | Public form rendering | 09 §4.11. Honeypot markup unspecified (F-05). |
| 2 | Validation | Closed schema, libphonenumber IN default, 04 §13. |
| 3 | Consent | Version, server time, channel, page and IP. Withdrawal not designed (F-15). |
| 4 | CAPTCHA and rate limit | Edge plus application; ordering and single-use token issue (F-04, A-09). |
| 5 | Duplicate detection | Flag only, 180-day phone/email match. Never discards (LEAD-010) ✔. |
| 6 | Persistence | One transaction with activity, audit and outbox ✔. |
| 7 | Audit | CREATE by WEB_INTAKE via PUBLIC_FORM ✔. |
| 8 | Public response | `{reference, message}` only; random 40-bit reference ✔. |
| 9 | Notification | Outbox after commit; email failure cannot undo the lead ✔ (NOTIF-008). |
| 10 | Admin listing | `lead.read` scope-filtered ✔. |
| 11 | Search, filter, sort, pagination | Allow-listed, 422 on unknown params ✔. |
| 12 | Detail access | 404 outside scope ✔. |
| 13 | Status changes | Complete transition table, dedicated endpoint, audited, STATUS_CHANGE activity ✔. The WON path's cancellation of PLANNED activities is stated in 04 §8 but not in the §3 table. |
| 14 | Notes | Parent-visibility plus OWN edit rules ✔. Undo gap (F-20). |
| 15 | Activities | Lifecycle, system rows immutable ✔. |
| 16 | Assignment | `lead.assign`, eligible = active holders of `lead.read` ✔. |
| 17 | Enrichment | PATCH with allow-listed fields ✔. |
| 18 | Follow-up | Derived `next_follow_up_on` in the same transaction ✔. Reminders are P1. |
| 19 | Won/lost | Constraints and reasons ✔. |
| 20 | Retention/deletion | Soft delete and restore ✔. No P0 retention or erasure (F-15). |

A lead cannot be lost to an email failure. Duplicates are never suppressed. Public responses expose no id, number, status, user or volume. PII is masked in logs and never echoed in errors. Accessibility of the public form is testable (axe plus keyboard journeys). The residual silent-drop and misreport risks are in F-04 and F-05.

## 10. Phase 9 — API contract

85 endpoint rows were reviewed. Methods, `/api/v1` versioning, the permission per endpoint, closed request schemas (mass assignment and over-posting are rejected with `UNKNOWN_FIELD`), RFC 9457 errors with a catalog, offset and cursor pagination, allow-listed filter and sort, If-Match on every mutation, rate limits, and safe public responses are specified. Issues:

- Idempotency contradiction (F-04).
- Email change and deactivate guard gap (F-03).
- `DELETE /auth/sessions/{id}` is P0 while AUTH-016 is P1 (F-16).
- Note restore is missing (F-20).
- Duplicate-resolution scope (A-07).
- Undocumented error: `POST /leads/{id}/notes` and activity creation on a soft-deleted lead are not stated. Recommend 404.

## 11. Phase 10 — UI/UX and accessibility

Login, forgot/reset, MFA (enrollment, challenge, recovery, step-up), dashboard, list/board, detail, create/edit, users, roles, permissions and the audit viewer with its Security events tab are designed. The designs include permission-aware rendering, the no-access page, empty/skeleton/error states with request id, 360 px mobile layouts, a focus ring, focus trap and restore, `aria-live`, error summaries, destructive confirmations and the session-expiry banner.

Light-mode token ratios were recomputed independently: ink 15.77, muted 6.68, copper 4.06, copper-text 5.36, white on copper-strong 7.10, warning 5.33, and status chips 5.32–7.87. All match the stated values within ±0.1, and the darker accessibility variants are used consistently. Defects: dark-mode copper-strong (F-14) and note Undo (F-20). There is no staff self-service view of one's own sign-in history outside Profile › Security.

## 12. Phase 11 — Production and operations; is SQLite production-grade?

The topology is coherent:

- Cloudflare proxy, mTLS origin pulls and a Cloudflare-only security group.
- One EC2 host with a dedicated KMS-encrypted EBS volume.
- Litestream to versioned SSE-KMS S3, nightly `VACUUM INTO` with Object Lock, and EBS snapshots.
- Automated restore verification.
- SSM, Secrets Manager and KMS for secrets.
- Health and readiness endpoints, structured logs, metrics and alerts.
- SES isolated behind the outbox.
- An explicit PostgreSQL gate, with no zero-downtime or horizontal-scaling claim.

**Assessment.** The design can honestly be called production-grade **only** as a controlled, single-instance, small-team MVP with an accepted single point of failure. That judgment holds only under the following release gates:

- RG-1 OWNER-INPUT-001 approved, and the measured RPO/RTO from the full rebuild rehearsal meet it.
- RG-2 Automated restore verification green on consecutive scheduled runs, with the alert test-fired.
- RG-3 Exactly one application instance (and one Litestream replicator) enforced by deployment configuration and checked in CI/OP.
- RG-4 Load test at ASM-007 fixture sizes meets NFR-001 and NFR-003 with no sustained SQLITE_BUSY; chain-append latency measured.
- RG-5 Litestream lag, snapshot-missing and disk-usage alerts wired and test-fired.
- RG-6 Database path verified on the dedicated KMS-encrypted volume; `DeleteOnTermination=false` verified.
- RG-7 Migration runbook rehearsed, including rollback (F-12).
- RG-8 PostgreSQL release gate (OPS-008) recorded as a hard precondition for procurement, inventory, finance and multi-instance scale.
- RG-9 No gated module, second instance or BI direct-DB access introduced while SQLite is authoritative.

Operational defects: readiness coupling and rollback inconsistency (F-12), per-worker stores (F-09), Litestream constraints (A-11).

## 13. Phase 13 — Assumptions and owner inputs

| ID | Classification | Note |
|---|---|---|
| ASM-001 | Acceptable for P0 | Validate by monitoring; there is a re-evaluation trigger at the PostgreSQL gate. |
| ASM-002 | Acceptable for P0 | Must be validated by a load test before production (release gate RG-4). |
| ASM-003 | Acceptable for P0 | Qualitative; replace after 30 days. |
| ASM-004 | Acceptable for P0 | Thresholds are configuration values; review after 30 days. |
| ASM-005 | Requires owner decision before implementation | Needed before LEAD-001 (website form) is implemented; see the recommendation below and F-17. |
| ASM-006 | Requires owner decision before production | Legal confirmation of retention (OWNER-INPUT-002). Defaults are configurable, so implementation can proceed. |
| ASM-007 | Acceptable for P0 | Test fixtures only. |
| ASM-008 | Acceptable for P0 | The origin lock depends on it; a change of edge provider triggers re-review. |
| ASM-009 | Requires owner decision before production | Go-live without outbound email must be explicitly accepted (11 §8). |
| ASM-010 | Acceptable for P0 | Validate by benchmark on the chosen instance before production. |
| ASM-011 | Requires owner decision before production | A versioned privacy notice must exist before public intake goes live; development can use a placeholder version. |
| ASM-012 | Requires owner decision before implementation | Needed before any AWS infrastructure (KMS keys, SES region, S3 buckets, data residency) is provisioned. Application code is not blocked. |

| Owner input / decision | Needed | Timing |
|---|---|---|
| OWNER-INPUT-001 | Approved RPO, RTO and API availability target | Before production. Recommended before infrastructure build, because an RPO or RTO that Litestream on a single host cannot meet would reopen ADR-008. NFR-002 and OPS-005 are untestable until provided. No values are proposed here. |
| OWNER-INPUT-002 | Retention durations (audit, security events, closed-lead anonymization) | Before production. Also decide whether lead retention and erasure are P0 (F-15). |
| OWNER-INPUT-003 | Restore-rehearsal cadence | Before production. |
| OWNER-DECISION (new) | Resolve F-01: whether Sales MFA is configurable (split or rescope `security_event.read`) or mandatory (amend ADR-006) | Before implementation of authentication and RBAC. |
| OWNER-DECISION (new) | ASM-005: property_type on the public form | Before LEAD-001 implementation. |
| OWNER-DECISION (new) | ASM-012: AWS region | Before infrastructure provisioning. |

No RPO, RTO, availability or retention values are proposed by this review.

**Recommendation on `property_type` (ASM-005).** Add it to the public form as an **optional** field (amending ADR-005), rather than keeping it staff-enrichment-only. Reasons:

1. The live form already asks it, and asks it as a required field (`dist/index.html:168`), so making it optional reduces friction relative to today and discards nothing users already provide.
2. It helps sales triage before the first call (apartment versus villa scope).
3. The schema, lookup and PATCH path already exist, so the change is additive.
4. The WhatsApp fallback already carries it.

Before implementation, reconcile the options: map 'Independent House / Villa' to `VILLA`, and move 'Home Renovation' to Service (PROJECT_TYPE `RENOVATION`). This is a recommendation only; the architecture was not modified.

## 14. Findings

BLOCKER 0 · MAJOR 3 · MINOR 18 · ADVISORY 14

### F-01 · MAJOR · MFA policy contradiction: every Sales user is forced into mandatory MFA

**Evidence**

- 06 §6.2: `security_event.read` is marked 🔒 (is_sensitive) and granted to Sales at scope O (OWN).
- 05 §9.5 and ADR-004 (Access control): OWN-scope `security_event.read` is granted to 'all roles'.
- 05 §11.1 rule 3, ADR-006 rule 3, 03 §4.4 and 11 §6 R9: holding ANY sensitive permission at ANY scope makes MFA mandatory.
- ADR-006 Decision table, MFA-003, 05 §12 and 11 §7 state Sales MFA is 'Configurable'.
- 08 §4.4 example `/auth/me` for a Sales user omits `security_event.read`, so the documents disagree with the seeded matrix.
- 12 §4.5 requires a test 'Sales without a source doesn't [require MFA]', which cannot pass against the seeded matrix.

**Affected requirements:** MFA-003, MFA-004, AUTH-015, AUTH-018, RBAC-008, SEVT-005, RBAC-017

**Risk:** The seeded matrix and ADR-006 cannot both be implemented. Implementers will either force every Sales user through MFA enrollment, contrary to an accepted owner decision, or add a special case that breaks the 'no role-name logic' rule (RBAC-002, MFA-002). Every Sales read of their own sign-in history would also emit SENSITIVE_ACTION events (see F-07).

**Remediation:** Choose one and propagate it through ADR-006, 05 §11.1, 06 §6.2, 08 §4.4, 11 §6/§7 and 12 §4.5. (a) Split the permission into a non-sensitive `security_event.read_own` (profile self-service) and a sensitive `security_event.read` (ALL), or (b) define sensitivity per (permission, scope) and state that OWN-scope self-service reads never trigger the MFA policy, or (c) amend ADR-006 with owner approval so that MFA is mandatory for every staff user. Add a registry test asserting that the seeded SALES role holds no sensitive permission unless ADR-006 says otherwise.

**Architecture re-review required:** Yes (targeted)

### F-02 · MAJOR · Account recovery weakens MFA: password-only enrollment after an MFA reset or a policy change

**Evidence**

- 05 §11.7 (Effect): after a privileged MFA reset, 'The next login forces enrollment if policy requires it'.
- 05 §3: 'MFA required but no active factor → mfa_challenge(ENROLLMENT) → MFA_ENROLLMENT_REQUIRED'. The only proof required is the password.
- 05 §11.3 / 08 §4.7: `enroll/start` and `enroll/confirm` need only the `mfa_token` from the password step. `enroll/confirm` creates a full session.
- 05 §11.1 ('Policy becomes required later'): a user newly subject to MFA re-authenticates with the password and enrolls on the next login.
- 05 §11.7 break-glass CLI has the same effect for a sole Founder.
- 11 §5 X14 claims MFA-reset takeover is mitigated, but the mitigation covers only who may perform the reset, not who may enroll afterwards.

**Affected requirements:** MFA-007, AUTH-015, MFA-002, MFA-004, USER-006

**Risk:** The most common reason for an MFA reset is a lost device, and resets often follow a suspected compromise. Anyone who holds or phishes the password in the window between the reset and the legitimate user's next login can enroll their own authenticator and obtain a fully MFA-verified session on a Founder or Admin account. The same applies when a role with `mfa_required` is newly assigned. This defeats the purpose of mandatory MFA for privileged roles (ADR-006).

**Remediation:** Bind post-reset and first-time enrollment to a second, out-of-band proof. For example, the reset produces a single-use, short-lived enrollment token delivered to the identity-verified person (email plus the admin-verified channel), and ENROLLMENT challenges require it. Alternatively, an MFA reset also forces a password reset through the emailed token, and enrollment is allowed only inside that reset flow. Treat 'policy becomes required' the same way, or allow enrollment only from an existing session with fresh password re-authentication. Emit a CRITICAL event if enrollment completes from a new IP or device after a reset. Update 05 §3, §11.1, §11.3, §11.7, 08 §4.7, 11 §5 X14 and 12 §4.5, and add a negative test.

**Architecture re-review required:** Yes (targeted)

### F-03 · MAJOR · Stronger accounts can be taken over or disabled through non-sensitive user-administration endpoints

**Evidence**

- 08 §5.4: `PATCH /users/{id}` (permission `user.update`, not sensitive per 06 §6.2) accepts `email`. 'Changing email re-sends verification in P1', so there is no verification in P0.
- 05 §8.1: forgot-password sends the reset link to the account's current email.
- 06 §7 G9 ('No takeover of stronger accounts') covers only MFA reset, admin password-reset link and admin session revocation. It does not cover email change, deactivate/activate (08 §5.5, `user.deactivate`), unlock or invite resend.
- 06 §7 G4 counts only holders of `role.manage` + `user.role.assign`. An Admin satisfies G4, so an Admin can deactivate the Founder.
- 06 §6.4 invites custom roles. A custom role can hold `lead.read`=ALL (all customer PII) without any sensitive permission, so it has no MFA (05 §11.1).

**Affected requirements:** RBAC-009, USER-001, USER-002, AUTH-008, MFA-007, RBAC-011

**Risk:** Horizontal or vertical privilege abuse. (1) A holder of `user.update` changes a stronger user's email to a mailbox they control, then triggers a password reset. For targets without MFA, including custom roles with broad data access, this is a full account takeover. For MFA-protected targets it compromises the password and locks out the owner. (2) An Admin can disable the Founder and every other Admin, which is an organizational takeover with no step-up and no stronger-target check. Neither action is sensitive, so neither emits SENSITIVE_ACTION or requires step-up.

**Remediation:** Extend G9 to email change, deactivate/activate, unlock and invite-resend. Make email change of another user a sensitive action (step-up, reason, notification to the old address, and revocation of sessions and outstanding reset/invite tokens), and either verify the new address in P0 or block password reset to an unverified address. Update 06 §6.2/§7, 08 §5.4/§5.5 and 12 §4.4 (guard tests).

**Architecture re-review required:** Yes (targeted)

### F-04 · MINOR · Public-intake idempotency contract is contradictory and not implementable as specified

**Evidence**

- 04 §5.1 step 6: a stored key → 'return the ORIGINAL 201 body (no new lead)', regardless of body.
- 08 §2.8: 'Same key with a different body → 422 IDEMPOTENCY_KEY_REUSED' and 'key plus actor plus route'. But 04 §2 stores only `lead.intake_idempotency_key` with a UNIQUE index on the key alone. No request fingerprint is stored, so a body mismatch cannot be detected.
- 04 §5.1 orders Turnstile verification (step 4) before the idempotency lookup (step 6). Turnstile tokens are single-use, so a genuine retry or double-submit carries a spent token and receives 422 CAPTCHA_FAILED even though the first request created the lead.

**Affected requirements:** API-007, LEAD-001, LEAD-025, LEAD-018

**Risk:** Retries and double-submits get a CAPTCHA error for a lead that was stored, which confuses enquirers and prompts duplicate submissions. The implementation will diverge from one of the two documents.

**Remediation:** Store a request fingerprint (hash of the canonical body) with the key, look the key up before Turnstile verification (after cheap rate limiting), and make 04 §5.1 and 08 §2.8 state one behavior.

**Architecture re-review required:** No (verify at the next review)

### F-05 · MINOR · Public-intake non-success paths can silently drop or misreport genuine enquiries

**Evidence**

- 04 §5.1 step 3 / 08 §8.4: a non-empty honeypot field (`website`) returns `202 {message:'Thank you.'}` and creates no lead. No markup rule prevents browser or password-manager autofill of a field named 'website' (no `autocomplete=off`, `tabindex=-1` or `aria-hidden` requirement in 09 §4.11).
- 02 §2.4 treats every 2xx as success and shows 'the random public reference'. A honeypot 202 has no reference, and genuine senders get a false 'thank you'.
- 02 §2.4 falls back to WhatsApp only on network error, 5xx or timeout. It does not mention 429, 422 CAPTCHA_FAILED, 428 or 413. 09 §4.11 does cover 429 and CAPTCHA with a WhatsApp link, so the two documents are inconsistent.
- 08 §12 limits public intake to 5/min and 30/hour per IP, which is aggressive for carrier-grade NAT on Indian mobile networks.

**Affected requirements:** LEAD-018, LEAD-019, LEAD-010, LEAD-001

**Risk:** Genuine enquiries lost or misreported: the brief requires that valid submissions are never silently suppressed.

**Remediation:** Specify honeypot markup (off-screen, `tabindex=-1`, `autocomplete=off`, `aria-hidden`, a non-autofillable name). Record honeypot hits with enough detail to review false positives. Align 02 §2.4 with 09 §4.11 so every non-2xx other than field-level 422 offers the WhatsApp path. Make 2xx without a reference distinguishable. Revisit per-IP limits and rely on Turnstile for bot control.

**Architecture re-review required:** No (verify at the next review)

### F-06 · MINOR · SENSITIVE_ACTION on reads is self-contradictory

**Evidence**

- 06 §3, 07 §4.3, 05 §9.1: 'Every use' of an `is_sensitive` permission writes a `SENSITIVE_ACTION` security event. `audit.read` and `security_event.read` are sensitive (06 §6.2).
- 05 §9.5: 'Reading the log is itself a normal API request: it is logged in the application logs, not in security_event_log, to avoid feedback loops.'

**Affected requirements:** RBAC-017, SEVT-005, AUDIT-008

**Risk:** Implementers must guess. One reading produces a SENSITIVE_ACTION row for every audit or security page view (volume, alert noise, feedback loops). The other leaves privileged reads unrecorded in the security log.

**Remediation:** Define 'use' per permission (for example, mutations only, or reads recorded as a de-duplicated `SENSITIVE_READ`) and align 05 §9.1/§9.5, 06 §3 and 07 §4.3.

**Architecture re-review required:** No (verify at the next review)

### F-07 · MINOR · Purge and retention rules conflict with ON DELETE RESTRICT foreign keys; session retention undefined

**Evidence**

- 03 §1: every FK is `ON DELETE RESTRICT`.
- `notification.source_event_id` → `outbox_event.id` (03 §8.2). EXC-004 hard-deletes DONE outbox rows, but EXC-005 purges notifications only 'once read'. An unread notification blocks the outbox purge.
- `audit_log.session_id` and `security_event_log.session_id` → `user_session.id` (03 §5.4, §7), and `refresh_token.session_id` → `user_session.id`. EXC-006 says sessions are never soft-deleted, but no hard-delete or retention rule exists for `user_session`. Sessions therefore accumulate forever and cannot be purged while evidence rows reference them.
- `refresh_token.replaced_by_id` self-FK (RESTRICT) makes the expiry purge (EXC-003) order-dependent.

**Affected requirements:** DATA-009, DATA-014, SEVT-004, NOTIF-004

**Risk:** Purge jobs fail at runtime and session and PII growth is unbounded. This is session cleanup and retention, which the brief lists explicitly.

**Remediation:** Define `user_session` retention (for example, purge N days after revocation or expiry once evidence rows are archived). Make evidence-to-session references non-FK correlation columns, or archive in dependency order. Set `source_event_id` to NULL on outbox purge (a registered exception), or purge notifications first. Document purge ordering for refresh-token chains.

**Architecture re-review required:** No (verify at the next review)

### F-08 · MINOR · Exception registry is incomplete: unique indexes without the soft-delete predicate are not registered

**Evidence**

- 03 §2.7 rule 5 fails CI on any unique index on business columns without `is_deleted = false`, unless it is allow-listed in §2.9.
- `ux_lead__public_reference` (04 §2, no predicate), `ux_lead__intake_idempotency_key` (predicate `IS NOT NULL` only) and `ux_notification__event_recipient` (03 §8.2) are not listed in EXC-007.
- The validation report's C03 'PASS' did not detect this.

**Affected requirements:** DATA-014, DATA-011, DATA-007

**Risk:** The conformance check will fail on the first migration, or the check will be weakened ad hoc. It also shows that automated validation C03 did not inspect index predicates.

**Remediation:** Add these indexes to EXC-007 with a justification (global uniqueness of public references and idempotency keys is intended), or add the predicate.

**Architecture re-review required:** No (verify at the next review)

### F-09 · MINOR · In-process rate-limit and idempotency stores are per gunicorn worker

**Evidence**

- 02 §3.5: gunicorn sync workers '2×CPU+1' (multiple processes) and 'Flask-Limiter with an in-memory store (single host)'.
- 08 §2.8: idempotency for authenticated creates uses an 'in-process TTL store'.
- 11 §1.2 S2 assumes one instance means one cache. With several worker processes, each has its own store.

**Affected requirements:** SEC-011, AUTH-010, API-007, MFA-009

**Risk:** Effective per-IP and per-email limits are multiplied by the worker count and are inconsistent. Idempotent replays that land on another worker create duplicates. Account lockout (database counters) is unaffected.

**Remediation:** Use a shared store even on one host (SQLite table, file-backed limiter storage or local Redis), or state and test the multiplied effective limits.

**Architecture re-review required:** No (verify at the next review)

### F-10 · MINOR · Revocation latency and the refresh-reuse grace window are under-specified

**Evidence**

- AUTH-006 and AUTH-017 require immediate revocation, but 05 §5 and 06 §9 cache session and user status for up to 30 s per process. With multiple workers, a revoked session remains usable for up to 30 s on other workers.
- 05 §6: a 'used token outside the 20 s multi-tab grace window revokes the session'. The behavior inside the window (return the successor? issue another?) is unspecified in 05 and 08 §4.2. Issuing new tokens inside the window allows replay.
- 12 §4.5 has no test for token use after revocation or for the grace window.

**Affected requirements:** AUTH-005, AUTH-006, AUTH-017, RBAC-013

**Risk:** Token replay window and stale authorization after disable, logout or password change.

**Remediation:** Specify grace behavior (for example, return the same successor, bound to the same session and client, at most once). Either make the session check uncached (a single indexed read on local SQLite) or reword the requirement to '≤ 30 s'. Add tests for both.

**Architecture re-review required:** No (verify at the next review)

### F-11 · MINOR · P0 tamper evidence of security_event_log is overstated

**Evidence**

- 05 §9.6: `row_hash = SHA-256(prev_hash ‖ canonical_json(...))` is unkeyed. The external anchor (SEVT-007) is deferred to P1. The archival anchor (05 §9.4 step 4) is recorded in the database.
- 11 §4 A2 claims 'The security-event hash chain detects tampering' by someone with direct file access. That attacker can recompute the whole chain.
- 'Canonical JSON' is not defined (key order, number and datetime formatting, SQLite microsecond text versus PostgreSQL `timestamptz`, GUID form), yet 11 §3.4 requires the chain to recompute identically after the PostgreSQL migration.

**Affected requirements:** SEVT-006, SEVT-004, OPS-004

**Risk:** False assurance. Cross-engine chain verification may fail spuriously during the PostgreSQL migration.

**Remediation:** Use an HMAC keyed from SSM or KMS (or promote the daily S3 Object Lock anchor to P0). Store archival anchors outside the database. Specify the canonicalization (for example, RFC 8785 JCS over application-level representations, with a fixed datetime precision).

**Architecture re-review required:** No (verify at the next review)

### F-12 · MINOR · Operational coupling and inconsistent rollback procedures

**Evidence**

- 02 §9 and 08 §3: `/health/ready` fails when outbox lag exceeds 5 min. An SES outage therefore fails readiness, and 02 §12.2 rolls back a deploy whose readiness check fails.
- 02 §12.2: deploy runs `alembic upgrade head` and then 'rollback to the previous image on failure'. The previous image runs against an already-migrated schema, and there is no down-migration policy.
- 11 §2 B3: 'Pause the worker → snapshot → migrate → … Rollback by snapshot restore'. This differs from 02 and does not state data-loss implications for writes after the snapshot.

**Affected requirements:** LOG-005, OPS-004, NOTIF-008, NOTIF-004

**Risk:** Email-provider outages cause spurious rollbacks and alerting. A failed deploy rollback can leave code and schema out of step.

**Remediation:** Report outbox lag as a separate degraded signal, not readiness. Define one deploy/migration runbook: maintenance mode for the public API, snapshot, expand-only migrations compatible with N-1 code, and explicit rollback semantics.

**Architecture re-review required:** No (verify at the next review)

### F-13 · MINOR · `user_mfa_factor.secret_key_ref` VARCHAR(200) is likely too small

**Evidence**

- 03 §5.5: `secret_key_ref` VARCHAR(200) holds 'wrapped data key and KMS key id'. A KMS `GenerateDataKey` ciphertext blob for a symmetric key is typically about 184 bytes, which is about 248 base64 characters before the key ARN is added. 03 §12 generates a length CHECK on SQLite, and PostgreSQL enforces varchar(n).

**Affected requirements:** MFA-010, MFA-001

**Risk:** MFA enrollment fails at insert time in production.

**Remediation:** Store the wrapped key as TEXT (or a separate column sized from measured KMS output) and the key ARN separately. Add a test with a real KMS blob.

**Architecture re-review required:** No (verify at the next review)

### F-14 · MINOR · Dark-mode primary button fails contrast; no on-color token

**Evidence**

- 09 §2.1: `--vs-copper-strong` dark value `#E0B394` is the primary button background with 'white text'. White on `#E0B394` is 1.90:1 (independently recomputed). The light-mode ratios claimed in 09 §2.1/§2.5 were recomputed and match within ±0.1. The dark ink `#171614` on `#E0B394` is 9.51:1.

**Affected requirements:** UI-011, UI-014, UI-010

**Risk:** WCAG 2.2 AA failure on the most prominent control in dark mode.

**Remediation:** Add `--vs-on-copper-strong` (light: white; dark: `--vs-ink`) and extend the automated token contrast check (12 §4.8) to dark mode.

**Architecture re-review required:** No (verify at the next review)

### F-15 · MINOR · No P0 design for lead retention, erasure or consent withdrawal (DPDP)

**Evidence**

- 11 §5.6: closed-lead anonymization is a proposed default (3 y, ASM-006) with no job, requirement ID or test.
- 07 §8.2 describes erasure, but it is AUDIT-011 (P1). 11 §5.6 says data-principal rights are 'a manual process'.
- No consent-withdrawal flow or state exists in 04 §2 (`consent_contact` only).

**Affected requirements:** SEC-009, LEAD-012, AUDIT-011

**Risk:** Lead PII has no enforced lifecycle in P0. Manual erasure against immutable audit rows has no P0-approved procedure.

**Remediation:** Either add P0 requirements (retention job, withdrawal recording, erasure procedure) or record an explicit owner decision deferring them, with a go-live condition.

**Architecture re-review required:** No (verify at the next review)

### F-16 · MINOR · Deferred P1 capabilities are embedded in P0 surfaces (scope ambiguity)

**Evidence**

- AUTH-016 is P1, yet endpoints 13, 14 and 27 (08 §1), permissions `session.read`, `session.revoke` and `user.session.revoke` (06 §6.1–6.2) and the UI Sessions tab (09 §4.6) are specified without a P1 marker.
- RBAC-007 (time-bound grants) is P1, yet `valid_from` and `valid_until`, the resolver `live(now)` (06 §5), the worked example, 08 §5.6/§5.7 payloads and the UI ⏱ indicator are in P0 designs.
- RBAC-016 is P1, yet endpoint 33 and the 'EFFECTIVE PERMISSIONS (explain)' UI are unmarked.
- Time-bound expiry can remove the last administrator without any transaction, so G4 (06 §7) cannot fire.

**Affected requirements:** PLAT-012, RBAC-011, AUTH-016, RBAC-007, RBAC-016

**Risk:** Unplanned P0 scope. The last-administrator safeguard can be bypassed by expiry.

**Remediation:** Mark each deferred surface as P1 in 06, 08 and 09, or promote the requirements to P0. Forbid `valid_until` on any grant that G4 depends on, or evaluate G4 at expiry.

**Architecture re-review required:** No (verify at the next review)

### F-17 · MINOR · Website form mapping drops live data (ASM-005)

**Evidence**

- Live form (`dist/index.html:168–169`): 'Property Type' is a **required** select with Apartment / Flat, Independent House / Villa, **Home Renovation** and Other. 'Service Required' is also required.
- 03 §6.2 seeds PROPERTY_TYPE as `APARTMENT`, `VILLA`, `OTHER`. 'Home Renovation' exists only as PROJECT_TYPE `RENOVATION`.
- 04 §5.1: Property Type is 'not accepted by the public API', so a field users are required to answer today is discarded.

**Affected requirements:** LEAD-023, LEAD-001, LEAD-002

**Risk:** Loss of data the business captures today. Lookup semantics are inconsistent with the live site.

**Remediation:** The owner decides ASM-005 (see §13 recommendation). Either way, reconcile the lookup codes with the live options before LEAD-001 is implemented.

**Architecture re-review required:** No (verify at the next review)

### F-18 · MINOR · ADR acceptance evidence is not in the repository

**Evidence**

- ADR-001: 'owner approval recorded in the architecture sign-off'. No sign-off artifact exists in the frozen tree.
- ADR-002…009 are 'Accepted' with no decision owner, approver or approval reference.

**Affected requirements:** PLAT-006

**Risk:** Governance: owner acceptance of nine binding decisions cannot be independently verified.

**Remediation:** Record approver, date and approval reference in each ADR, or add a signed decision log.

**Architecture re-review required:** No (verify at the next review)

### F-19 · MINOR · Test-strategy gaps behind the reported 199-requirement coverage

**Evidence**

- 11 requirements map their 'test' dimension only to method, environment or CI sections (12 §1, §2, §3, §5): PLAT-001, PLAT-002, PLAT-004, PLAT-006, MFA-008, SEC-007, SEC-009, SEC-010, OPS-001, OPS-003, OPS-008. These are review checklists or CI gates, not tests.
- Not designed: Alembic upgrade-with-data and downgrade/rollback tests per revision; explicit CSRF negative tests for `/auth/refresh` and `/auth/logout`; access-token use after revocation or logout; refresh grace-window replay; SQLite write-contention (`SQLITE_BUSY`, `BEGIN IMMEDIATE`) tests; a browser and device matrix (only 360 px is specified); DAST or penetration testing before go-live (ASVS is P1, and the OWASP review is only a checklist item in 11 §8).
- NFR-002 and OPS-005 cannot be tested until OWNER-INPUT-001 exists.

**Affected requirements:** PLAT-006, OPS-001, OPS-004, AUTH-005, AUTH-006, SEC-002, SEC-010, NFR-002, OPS-005

**Risk:** Coverage by reference overstates verification depth in exactly the areas where the findings above sit.

**Remediation:** Add the missing suites to 12 §4, and report RV/OP-only requirements separately from tested ones in the coverage gate.

**Architecture re-review required:** No (verify at the next review)

### F-20 · MINOR · Note 'Undo' depends on a restore endpoint that does not exist

**Evidence**

- 09 §3.2: 'Note deleted · Undo within 8 s, which calls restore'. 08 §9.1 has no note-restore endpoint, and 06 §6.3 has no `lead_note.restore` permission.

**Affected requirements:** NOTE-002, UI-004

**Risk:** The UI cannot be built as designed without inventing an API and permission.

**Remediation:** Add endpoint and permission, or drop Undo for notes.

**Architecture re-review required:** No (verify at the next review)

### F-21 · MINOR · Validation and coverage evidence is largely self-referential

**Evidence**

- validation-report.md: 'Section-level Traces: lines were generated from the reviewed registry mapping'. Coverage = the section 'explicitly cites the ID', which the injected Traces lines guarantee.
- coverage-gate.md: natively cited before injection is Schema 27/79, API 16/75 and UI 22/53.
- Independent substantive assessment (§5) finds 28 P0 requirements that are not fully covered, against the claimed 100%.

**Affected requirements:** —

**Risk:** Coverage percentages cannot be used as certification evidence.

**Remediation:** Report semantic coverage separately from citation coverage in future gates, and keep the independent matrix (§5) as the baseline.

**Architecture re-review required:** No (verify at the next review)

### A-01 · ADVISORY · Account-lockout denial of service against privileged users

**Evidence**

- 05 §4: 5 password failures lock the account (escalating to 24 h). Anyone who knows a Founder's email can lock it repeatedly.

**Affected requirements:** AUTH-010

**Risk:** Availability of privileged accounts.

**Remediation:** Prefer progressive delays or Turnstile challenges per account and IP over hard locks, or allow password + MFA to succeed during lock.

**Architecture re-review required:** No (verify at the next review)

### A-02 · ADVISORY · SQLite immutability is convention-level

**Evidence**

- 07 §6.2: the retention procedure drops and recreates the DELETE trigger. The application's connection can therefore drop triggers. 11 §3.3 acknowledges 'No DB roles or grants'.

**Affected requirements:** AUDIT-004, SEVT-001

**Risk:** Accepted MVP risk; honestly documented.

**Remediation:** Run retention from a separate CLI process and alert on trigger DDL, or verify trigger presence in `/health/ready`.

**Architecture re-review required:** No (verify at the next review)

### A-03 · ADVISORY · Case-insensitive search differs between engines for non-ASCII text

**Evidence**

- 03 §12 uses `lower(col) LIKE lower(:q)`. SQLite `lower()` and `LIKE` fold ASCII only (without ICU). PostgreSQL folds Unicode.

**Affected requirements:** PLAT-004, LEAD-013

**Risk:** Different search results after migration.

**Remediation:** Normalize searchable shadow columns in the application (casefold), or add non-ASCII dual-engine tests.

**Architecture re-review required:** No (verify at the next review)

### A-04 · ADVISORY · Case-sensitive uniqueness of role names and lookup codes

**Evidence**

- `ux_role__name` (03 §4.3) is on the raw name, so 'Sales' and 'sales' can coexist.

**Affected requirements:** RBAC-015

**Risk:** Confusable roles.

**Remediation:** Unique on a normalized name.

**Architecture re-review required:** No (verify at the next review)

### A-05 · ADVISORY · Invite-link interception yields password and MFA enrollment

**Evidence**

- 05 §8.4 and §10: the invite token alone sets the password, and the first login then enrolls MFA with that password.

**Affected requirements:** AUTH-011, AUTH-014

**Risk:** Inherent to email invites; relevant to F-02.

**Remediation:** Short invite expiry for privileged roles, and confirmation to the inviter on acceptance.

**Architecture re-review required:** No (verify at the next review)

### A-06 · ADVISORY · State that G2 applies to `copy_from_role_id`

**Evidence**

- 08 §6.1: `POST /roles` with `copy_from_role_id` lists only `409 DUPLICATE`. Assignment-time G2 prevents escalation, but copy-time behavior is unstated.

**Affected requirements:** RBAC-009

**Risk:** Low.

**Remediation:** Document ESCALATION_DENIED on copy.

**Architecture re-review required:** No (verify at the next review)

### A-07 · ADVISORY · Duplicate-resolution target must be scope-checked

**Evidence**

- 08 §8.8: `duplicate_of_lead_id` is client-supplied. Existence outside scope could leak through error differences.

**Affected requirements:** RBAC-014, LEAD-010

**Risk:** Existence oracle.

**Remediation:** Resolve through the scoped repository (404).

**Architecture re-review required:** No (verify at the next review)

### A-08 · ADVISORY · `?next=` redirect validation

**Evidence**

- 09 §4.1: 'only relative paths allowed'. Implementations commonly miss `//host` and `/\host`.

**Affected requirements:** UI-001

**Risk:** Open redirect.

**Remediation:** Allow only `^/[^/\\]` paths, and test.

**Architecture re-review required:** No (verify at the next review)

### A-09 · ADVISORY · Order app-level rate limiting before server-to-server Turnstile verification

**Evidence**

- 04 §5.1 steps 4–5 call Turnstile before the application rate limit.

**Affected requirements:** LEAD-018, NFR-003

**Risk:** Unnecessary outbound calls under abuse.

**Remediation:** Swap steps 4 and 5.

**Architecture re-review required:** No (verify at the next review)

### A-10 · ADVISORY · Example TOTP secret in docs

**Evidence**

- 08 §4.7 and 09 §4.10 show `JBSWY3DPEHPK3PXP`, the widely published documentation example key. It is not a real secret.

**Affected requirements:** —

**Risk:** Secret-scanner noise only.

**Remediation:** Replace with an obvious placeholder.

**Architecture re-review required:** No (verify at the next review)

### A-11 · ADVISORY · Litestream operational constraints

**Evidence**

- 02 §12.3 relies on Litestream but does not state its constraints (single replicating process, no external `wal_checkpoint(TRUNCATE)`, version pinning, restore-tooling version compatibility).

**Affected requirements:** OPS-002, OPS-009

**Risk:** Silent replication gaps.

**Remediation:** Document and monitor the constraints in the restore runbook.

**Architecture re-review required:** No (verify at the next review)

### A-12 · ADVISORY · `audit.read` exposes lead PII regardless of lead scope

**Evidence**

- 08 §10 masks only entity labels outside `lead.read` scope. `old_value` and `new_value` still carry PII.

**Affected requirements:** AUDIT-008

**Risk:** Relevant for future custom roles.

**Remediation:** Document, or mask `pii_fields` for out-of-scope entities.

**Architecture re-review required:** No (verify at the next review)

### A-13 · ADVISORY · PostgreSQL chain advisory lock is held for the whole business transaction

**Evidence**

- 05 §9.6 and 03 §2.8: SUCCESS events share the business transaction, so the transaction-scoped lock serializes all such writes.

**Affected requirements:** SEVT-006, NFR-001

**Risk:** Throughput after migration.

**Remediation:** Measure in rehearsal (already listed as A8), and consider a sequence plus deferred chaining.

**Architecture re-review required:** No (verify at the next review)

### A-14 · ADVISORY · Honeypot response status differs from success

**Evidence**

- 08 §8.4: honeypot returns 202 while success returns 201.

**Affected requirements:** LEAD-018

**Risk:** Lets bots detect the trap.

**Remediation:** Return an indistinguishable shape; see F-05.

**Architecture re-review required:** No (verify at the next review)

## 15. Proof of non-modification

- The review branch was created from `4dce177745a2b8f0b9fdb21de2e563ccd022fb0e`. The review commit adds only `docs/reviews/p0-independent-architecture-review.md` and `docs/reviews/p0-independent-architecture-review.json`.
- Verify with `git diff --name-only 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e review/p0-foundation-independent-review` (expected: exactly those two paths) and `git diff --quiet 4dce177745a2b8f0b9fdb21de2e563ccd022fb0e review/p0-foundation-independent-review -- docs/architecture dist` (expected: exit 0).
- `architecture/p0-foundation-freeze` was not modified, and nothing was merged, force-pushed or deployed.

## 16. Final verdict and next authorized action

**NOT CERTIFIED.** Three MAJOR findings (F-01, F-02, F-03) exist, and an owner decision is needed to resolve F-01.

**Next authorized action.**

1. The architecture author corrects F-01, F-02 and F-03 in a new commit on `architecture/p0-foundation-freeze`, with a new freeze SHA.
2. The author records tracking for every MINOR finding.
3. The owner decides F-01 (Sales MFA), ASM-005 and ASM-012.
4. A targeted independent re-review is then requested against the new SHA.

Implementation, merge and deployment remain unauthorized. A future CERTIFIED verdict would still require separate owner authorization before implementation begins.
