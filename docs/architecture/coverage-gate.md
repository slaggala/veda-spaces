# Coverage Gate — P0 Architecture after Remediation 01

Generated 2026-09-29. Source: [requirements.json](requirements.json) (per-requirement classification and basis), [validation-report.json](validation-report.json).

## Author verdict

**READY FOR FOCUSED INDEPENDENT RE-REVIEW**

This is the **author's** verdict. It is not a certification: only a fresh independent reviewer can certify the corrected architecture.

Production release remains blocked by the owner inputs and release gates in 11 §7 (owner Decision 6).

## Totals

| Metric | Value |
|---|---|
| Total requirements | 221 (frozen: 203) |
| P0 in scope | 208 (frozen: 186; +4 promoted, +18 new) |
| P1 / P2 deferred | 10 / 3 |

## P0 classification (independent-review taxonomy)

| Classification | Independent baseline (186 P0) | After remediation 01 (author assessment, 208 P0) |
|---|---|---|
| Fully covered | 158 | 206 |
| Partially covered | 22 | 0 |
| Contradictory | 4 | 0 |
| Referenced but not substantively covered | 0 | 0 |
| Not covered | 0 | 0 |
| Not testable pending owner input | 2 | 2 |
| Deferred | 0 | 0 |

**How to read this table.**

- **109** P0 requirements keep the reviewer's own *Fully covered* classification unchanged.
- **49** were *Fully covered* at baseline but revised in remediation 01. They need re-review.
- **26** were partial or contradictory and are now assessed *Fully covered* by the author. They need re-review.
- **22** are new or promoted, assessed by the author. They need re-review.

Nothing is marked covered because of a citation. Traces lines were removed (F-21).

## Partial → fully covered (author assessment, re-review required)

AUTH-005, AUTH-006, AUTH-010, AUTH-015, AUTH-017, DATA-009, DATA-014, LEAD-018, LEAD-019, LOG-005, MFA-007, MFA-010, NOTE-002, OPS-004, RBAC-009, RBAC-011, SEC-009, SEC-011, SEVT-006, UI-011, UI-014, USER-001

## Contradictions removed

| Requirement | Former contradiction | Resolution |
|---|---|---|
| AUTH-018 | Sales persona 'configurable MFA' contradicted by the seeded matrix | Sales holds no sensitive permission; MFA optional by default (Decision 1) |
| MFA-003 | Sales held sensitive `security_event.read` (OWN), making MFA mandatory | `security_event.read` removed from Sales, ALL-only (Decision 1) |
| RBAC-017 | 'Every use emits SENSITIVE_ACTION' vs reads logged only in app logs | `SENSITIVE_ACTION` for mutations, de-duplicated `SENSITIVE_READ` for reads (F-06) |
| API-007 | 04 §5.1 vs 08 §2.8 idempotency; no fingerprint | Stored request fingerprint; lookup before CAPTCHA; one behavior (F-04) |

## New or promoted P0 requirements (author assessment, re-review required)

AUDIT-011, AUTH-016, DATA-017, LEAD-027, LEAD-028, LEAD-029, LEAD-030, MFA-012, MFA-013, MFA-014, MFA-015, OPS-010, OPS-011, RBAC-016, RBAC-018, RBAC-019, RBAC-020, RBAC-021, SEVT-007, UI-016, UI-017, USER-007

## Requirements dependent on production owner inputs

| Requirement | Owner input | Classification | Effect |
|---|---|---|---|
| AUDIT-009 | OWNER-INPUT-002 | Deferred | Designed and testable with test configuration. Production enablement is gated. |
| DATA-017 | OWNER-INPUT-002 | Fully covered | Designed and testable with test configuration. Production enablement is gated. |
| LEAD-028 | OWNER-INPUT-002 | Fully covered | Designed and testable with test configuration. Production enablement is gated. |
| MFA-015 | OWNER-INPUT-004 | Fully covered | Designed and testable with test configuration. Production enablement is gated. |
| NFR-002 | OWNER-INPUT-001 | Not testable pending owner input | Untestable until provided |
| OPS-002 | OWNER-INPUT-003 | Fully covered | Designed and testable with test configuration. Production enablement is gated. |
| OPS-005 | OWNER-INPUT-001 | Not testable pending owner input | Untestable until provided |
| OPS-009 | OWNER-INPUT-003 | Fully covered | Designed and testable with test configuration. Production enablement is gated. |
| RBAC-021 | OWNER-INPUT-004 | Fully covered | Designed and testable with test configuration. Production enablement is gated. |
| SEVT-004 | OWNER-INPUT-002 | Fully covered | Designed and testable with test configuration. Production enablement is gated. |

## Test-design depth (P0)

| Test design | Count | Meaning |
|---|---|---|
| Automated (concrete 12 §4 row) | 166 | UT / IT / E2E / SL |
| Review only (RV) | 21 | Checklist, not a test (F-19) |
| Operational only (OP) | 19 | Drill or scheduled verification |
| Owner-gated | 2 | Untestable until owner input |

Review- or operational-only P0 requirements: API-008, API-009, AUTH-014, DATA-009, LOG-001, LOG-004, LOG-006, MFA-008, NOTIF-005, OPS-001, OPS-002, OPS-003, OPS-004, OPS-006, OPS-007, OPS-008, OPS-009, OPS-010, OPS-011, PLAT-001, PLAT-002, PLAT-003, PLAT-005, PLAT-006, PLAT-008, PLAT-011, PLAT-012, RBAC-002, SEC-001, SEC-005, SEC-006, SEC-007, SEC-008, SEC-009, SEVT-004, SEVT-007, SEVT-009, SEVT-010, UI-010, UI-014

## Deferred requirements

| ID | Priority | Requirement |
|---|---|---|
| ACT-005 | P1 | Call and WhatsApp buttons prompt a prefilled activity quick-log. |
| AUDIT-007 | P1 | Bulk exports are audited (who, when, filter, row count). |
| AUDIT-009 | P1 | Configurable audit retention with verified archival. |
| AUDIT-013 | P2 | Tamper-evidence hash chain over audit_log. |
| LEAD-017 | P1 | Leads can be exported to CSV (permission-gated, audited). |
| LEAD-021 | P1 | Quoted amount is recorded in minor units. |
| LEAD-022 | P2 | Auto-assignment (round robin). |
| NFR-004 | P1 | Initial JS below 200 KB gzipped and LCP below 2.5 s on 4G. |
| NOTE-003 | P1 | Notes can be pinned. |
| NOTIF-006 | P1 | Follow-up reminders and daily digest. |
| NOTIF-007 | P2 | WhatsApp Business API notifications. |
| RBAC-007 | P1 | Time-bound grants (P1): disabled in P0 with 422; when enabled, never allowed on sensitive permissions. |
| SEC-010 | P1 | Target OWASP ASVS v4 Level 2. |

## Assumptions, exceptions and gates

- **Assumptions:** 11 §10 (ASM-001…013). ASM-005 and ASM-012 are resolved by owner Decisions 4 and 5. ASM-006 is replaced by OWNER-INPUT-002.
- **Exceptions:** audit-contract behavioral exceptions EXC-001…010 (03 §2.9). Non-permission endpoints RBX-001…006 (06 §11).
- **Owner inputs (production gates):** OWNER-INPUT-001…004 (11 §7.2).
- **Production release gates:** RG-1…RG-9, PG-DAST, PG-RET, PG-BG, PG-EMAIL, PG-PRIV (11 §7.3).
- **Tracked gates:** TG-01…TG-06 (11 §11).

## Unresolved blockers (architecture)

None.

