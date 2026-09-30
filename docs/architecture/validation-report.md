# Architecture Validation Report — Final Minor Remediation

Generated 2026-09-29 on `architecture/p0-foundation-freeze`. Previous remediation commit `c3aae47a7d9b12fc0cb1491865991fde28abcf55`. Focused independent re-review `06a4f6e` (verdict **CERTIFIED WITH MINOR CONDITIONS**). Machine-readable: [validation-report.json](validation-report.json). Coverage: [coverage-gate.md](coverage-gate.md). Gates: [gate-registry.md](gate-registry.md). Findings: [review-remediation-matrix.md](review-remediation-matrix.md).

## Method and limits

- Baseline = focused independent re-review classification per requirement. Only DATA-011, DATA-014, MFA-015 and RBAC-021 differ; they are author assessments pending targeted independent check TG-07. Navigation references are resolvability-checked only.
- Validation scripts run in the authoring session; not committed per the 'no implementation code' instruction (advisory N-A8 accepted). Non-vacuity was exercised by injected defects for the new checks.
- These checks are structural and textual. They cannot certify design adequacy; that is the purpose of the targeted independent check (TG-07).

## Result: 37 of 37 checks passed

| # | Check | Result | Details |
|---|---|---|---|
| V01 | All Requirement IDs (and named registers) resolve | **PASS** | 221 registered IDs; 0 unresolved references; 0 missing from 01; named registers EXC 11, RBX 6, ASM 13, OWNER-INPUT 4, TG 8, AX 10; 0 unresolved named refs |
| V02 | No duplicate Requirement IDs | **PASS** | 221 IDs, 221 unique |
| V03 | All cross-document references resolve | **PASS** | 1663 section references, 110 relative links, 759 registry navigation references checked |
| V04 | JSON files are syntactically valid | **PASS** | 4 JSON files parsed |
| V05 | No physical table named user | **PASS** | 24 inventory tables, 24 table definitions scanned; app_user.id referenced 36 times |
| V06 | All complete example and seeded IDs follow the UUIDv7 32-hex contract | **PASS** | 12 complete 32-hex identifiers found in documents (elided examples ending in … are excluded); validation pattern and INVALID_ID documented |
| V07 | No hardcoded role-name authorization | **PASS** | 1 mentions, all in prohibition context |
| V08 | No default Sales security-event access | **PASS** | Matrix cell blank for Sales; ALL-only; 05 §9.5 prohibition; /auth/me example; negative tests present |
| V09 | No recovery-code-only (or password-only) authenticator enrollment | **PASS** | Two-proof enrollment paths A–D; recovery requires password + code; login returns no enrollment token |
| V10 | No direct generic email replacement or mass assignment of security attributes | **PASS** | PATCH DTOs profile-only; email only via proposed-email workflow; user.update retired |
| V11 | Founder and last-administrator protection exists (service and database-safe) | **PASS** | G3/G4/G9/G11/G12, invariants I1/I2 under write lock, nightly check, protection_level attribute, error codes |
| V12 | All three MAJOR findings substantively resolved (contradiction probes) | **PASS** | F-01: no sensitive permission in the Sales column, Sales MFA optional, MFA-gated activation. F-02: no single-factor enrollment, restricted recovery session, cooling-off. F-03: granular sensitive account-control permissions, G9 over email/status, Founder protection. |
| V13 | Every finding (35 original + 4 MINOR and 9 ADVISORY from re-review) dispositioned; every MINOR resolved or tracked | **PASS** | 35 original + 13 re-review findings dispositioned |
| V14 | No secret material | **PASS** | Scanned for cloud keys, private keys, tokens, complete JWTs and the published example TOTP key (A-10) |
| V15 | No implementation code added; only architecture documentation changed; no review artifact touched | **PASS** | 21 changed paths, all under docs/architecture/ and all .md/.json |
| V16 | dist/ unchanged | **PASS** | No dist/ diff vs c3aae47 or working tree; content SHA-256 8986bdfaa44dd800968183d338ddfa63c6cae2ef915d1ae41e7ad4939363c9a8 |
| V17 | Every table follows the audit contract; exception registry complete (incl. F-08 indexes) | **PASS** | 24 tables; 24 unique indexes checked against the predicate rule or EXC-007 |
| V18 | Every foreign key uses the canonical ID type; non-FK correlation ids are registered | **PASS** | 45 reference columns checked; correlation ids registered in EXC-009 |
| V19 | SQLite and PostgreSQL mappings are explicit | **PASS** | Types used: ['BIGINT', 'BOOL', 'CHAR(n)', 'CODE(n)', 'DATE', 'GUID', 'INTEGER', 'JSON', 'MONEY_MINOR', 'SMALLINT', 'TEXT', 'UTCDATETIME', 'VARCHAR(n)'] |
| V20 | Public lead API reveals no internal fields; property type optional and consistent | **PASS** | Response keys ⊆ {reference, message}; request limited to ADR-005 fields incl. optional property_type_code; identical honeypot response; seeds APARTMENT…OTHER |
| V21 | Security-event logs contain no secrets | **PASS** | 20 columns checked; prohibition list present; API excludes hash/chain |
| V22 | Deferred modules not promoted into P0 | **PASS** | No roadmap tables, endpoints or permissions; doc 10 banner present |
| V23 | Accessibility fixes documented as tokens; light and dark contrast verified | **PASS** | 22 token/background combinations recomputed; AX-01…AX-10 defined |
| V24 | No undecided text or invented RPO/RTO/availability/retention/volume values | **PASS** | Scanned for sign-off, TBD/TODO, invented volumes, RPO/RTO/availability figures and retention defaults |
| V25 | Money in integer minor units with currency; UTC storage and local display explicit | **PASS** | Monetary columns use MONEY_MINOR + currency; 03 §2.2 time rules |
| V26 | Coverage model is substantive (no citation-derived coverage); every requirement assessed | **PASS** | No Traces lines; every requirement has a classification and history; every upgrade from the focused re-review baseline is flagged for TG-07 |
| V27 | N-01: canonical Founder approval rules consistent everywhere | **PASS** | 06 §7.2 is the single definition; ADR-010, ADR-006, 05, 08 and 09 defer to it; no permissive eligibility text or retired action names remain |
| V28 | N-01: no direct Founder-power grant path remains | **PASS** | G13 + grant_path flags + seed lock + registry rule 5; generic role, permission and role-definition APIs reject; negative tests G4–G6; matrix grants user.founder.manage only to Founder |
| V29 | No requester can approve their own request (Founder and standard dual control) | **PASS** | DB CHECK + service eligibility (06 §7.2.3, §7.4) + API error + tests G1/G3 |
| V30 | N-02: ten FK-less identifier columns registered and constrained; rule 3 exact; tests present | **PASS** | 10 registry rows, each with 10 documented fields; allow-list equals the required set |
| V31 | Every ID-like column has a FK or is exactly a registered FK-less column | **PASS** | 45 ID-like columns scanned across 24 table definitions |
| V32 | N-03: six test designs are concrete (all ten fields, requirement IDs) | **PASS** | TD-A…TD-F each state requirement IDs, purpose, preconditions, fixtures, action, expected result, events, negative assertion, cleanup and evidence |
| V33 | F-19 resolved or enforceably tracked | **PASS** | 13 F-19 deficiencies mapped; tracked items reference registry gates with owner, acceptance and evidence |
| V34 | Every RG, PG and TG gate has all mandatory attributes; failure never defaults to pass | **PASS** | 27 gates × 18 attributes; owners are categories; all gate references resolve; PG-DAST has no invented numeric threshold |
| V35 | TG-01 remains pending; no owner approval is fabricated | **PASS** | TG-01 status Pending; scan for approval claims found only negated or pending statements; decision-log disclaimer present |
| V36 | Requirement counts consistent (221 / 208 P0 / 10 P1 / 3 P2) | **PASS** | requirements.json and 01 agree with the focused re-review recount |
| V37 | No P0 contradiction (or partial/uncovered) remains in the author's classification | **PASS** | P0 author classification {'Fully covered': 206, 'Not testable pending owner input': 2}; the four corrected requirements are flagged for TG-07 |

## Evidence (failures and listings)

### V07

- 06-rbac.md:33: 1. **Code checks permission codes only.** Nothing references role codes (`FOUNDER`, `ADMIN`, `SALES`), "is_admin" flags 

### V23

- --vs-on-copper-strong on --vs-copper-strong [light] 7.10
- --vs-on-copper-strong on --vs-copper-strong [dark] 9.51
- --vs-on-danger on --vs-danger [light] 6.57
- --vs-on-danger on --vs-danger [dark] 6.16
- --vs-ink [light on #FBF7EF] 15.77
- --vs-ink [dark on #171614] 15.89
- --vs-ink [dark on #201F1C] 14.48
- --vs-ink-muted [light on #FBF7EF] 6.68
- --vs-ink-muted [dark on #171614] 8.43
- --vs-ink-muted [dark on #201F1C] 7.68
- --vs-copper-text [light on #FBF7EF] 5.36
- --vs-copper-text [dark on #171614] 8.32
- --vs-copper-text [dark on #201F1C] 7.58
- --vs-danger [light on #FBF7EF] 6.15
- --vs-danger [dark on #171614] 6.16
- --vs-danger [dark on #201F1C] 5.61
- --vs-success [light on #FBF7EF] 5.76
- --vs-success [dark on #171614] 8.01
- --vs-success [dark on #201F1C] 7.30
- --vs-warning [light on #FBF7EF] 5.33
- --vs-warning [dark on #171614] 9.35
- --vs-warning [dark on #201F1C] 8.52

