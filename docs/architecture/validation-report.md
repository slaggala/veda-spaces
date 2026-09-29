# Architecture Validation Report — Remediation 01

Generated 2026-09-29 on `architecture/p0-foundation-freeze`. Previous architecture commit `4dce177745a2b8f0b9fdb21de2e563ccd022fb0e`. Independent review `review/p0-foundation-independent-review` @ `7515b23` (verdict NOT CERTIFIED). Machine-readable: [validation-report.json](validation-report.json). Coverage gate: [coverage-gate.md](coverage-gate.md). Remediation matrix: [review-remediation-matrix.md](review-remediation-matrix.md).

## Method

- **Coverage.** Substantive classification per requirement using the independent reviewer's taxonomy; the reviewer's matrix is the baseline. Classifications changed by remediation 01 are author assessments that require independent re-review. Navigation references are checked only for resolvability and are not coverage evidence (F-21).
- **Tooling.** Validation scripts were run in the authoring session and are intentionally not committed (no code in the architecture).
- **Non-vacuity.** The new security checks (V08, V09, V10, V12) were exercised against deliberately injected defects: a Sales grant of `security_event.read`, recovery-code-only enrollment, and `email` in the generic PATCH DTO. All four checks failed as expected, then passed after the files were restored.
- **Limits.** These checks are structural and textual. They prove resolvability, consistency and the absence of known contradictions. **They cannot certify design adequacy.** That is the independent re-reviewer's role.

## Result: 26 of 26 checks passed

| # | Check | Result | Details |
|---|---|---|---|
| V01 | All Requirement IDs (and named registers) resolve | **PASS** | 221 registered IDs; 0 unresolved references; 0 missing from 01; named registers EXC 10, RBX 6, ASM 13, OWNER-INPUT 4, TG 6, AX 10; 0 unresolved named refs |
| V02 | No duplicate Requirement IDs | **PASS** | 221 IDs, 221 unique |
| V03 | All cross-document references resolve | **PASS** | 1465 section references, 103 relative links, 759 registry navigation references checked |
| V04 | JSON files are syntactically valid | **PASS** | 3 JSON files parsed |
| V05 | No physical table named user | **PASS** | 24 inventory tables, 24 table definitions scanned; app_user.id referenced 35 times |
| V06 | All complete example and seeded IDs follow the UUIDv7 32-hex contract | **PASS** | 12 complete 32-hex identifiers found in documents (elided examples ending in … are excluded); validation pattern and INVALID_ID documented |
| V07 | No hardcoded role-name authorization | **PASS** | 1 mentions, all in prohibition context |
| V08 | No default Sales security-event access | **PASS** | Matrix cell blank for Sales; ALL-only; 05 §9.5 prohibition; /auth/me example; negative tests present |
| V09 | No recovery-code-only (or password-only) authenticator enrollment | **PASS** | Two-proof enrollment paths A–D; recovery requires password + code; login returns no enrollment token |
| V10 | No direct generic email replacement or mass assignment of security attributes | **PASS** | PATCH DTOs profile-only; email only via proposed-email workflow; user.update retired |
| V11 | Founder and last-administrator protection exists (service and database-safe) | **PASS** | G3/G4/G9/G11/G12, invariants I1/I2 under write lock, nightly check, protection_level attribute, error codes |
| V12 | All three MAJOR findings substantively resolved (contradiction probes) | **PASS** | F-01: no sensitive permission in the Sales column, Sales MFA optional, MFA-gated activation. F-02: no single-factor enrollment, restricted recovery session, cooling-off. F-03: granular sensitive account-control permissions, G9 over email/status, Founder protection. |
| V13 | Every finding dispositioned; every MINOR resolved or explicitly tracked | **PASS** | 35 findings; status {'Resolved': 33, 'Tracked before implementation': 1, 'Accepted advisory with reason': 1} |
| V14 | No secret material | **PASS** | Scanned for cloud keys, private keys, tokens, complete JWTs and the published example TOTP key (A-10) |
| V15 | No implementation code added; only architecture documentation changed | **PASS** | 30 changed paths, all under docs/architecture/ and all .md/.json |
| V16 | dist/ unchanged | **PASS** | No dist/ diff vs 4dce177 or working tree; content SHA-256 8986bdfaa44dd800968183d338ddfa63c6cae2ef915d1ae41e7ad4939363c9a8 |
| V17 | Every table follows the audit contract; exception registry complete (incl. F-08 indexes) | **PASS** | 24 tables; 23 unique indexes checked against the predicate rule or EXC-007 |
| V18 | Every foreign key uses the canonical ID type; non-FK correlation ids are registered | **PASS** | 45 reference columns checked; correlation ids registered in EXC-009 |
| V19 | SQLite and PostgreSQL mappings are explicit | **PASS** | Types used: ['BIGINT', 'BOOL', 'CHAR(n)', 'CODE(n)', 'DATE', 'GUID', 'INTEGER', 'JSON', 'MONEY_MINOR', 'SMALLINT', 'TEXT', 'UTCDATETIME', 'VARCHAR(n)'] |
| V20 | Public lead API reveals no internal fields; property type optional and consistent | **PASS** | Response keys ⊆ {reference, message}; request limited to ADR-005 fields incl. optional property_type_code; identical honeypot response; seeds APARTMENT…OTHER |
| V21 | Security-event logs contain no secrets | **PASS** | 20 columns checked; prohibition list present; API excludes hash/chain |
| V22 | Deferred modules not promoted into P0 | **PASS** | No roadmap tables, endpoints or permissions; doc 10 banner present |
| V23 | Accessibility fixes documented as tokens; light and dark contrast verified | **PASS** | 22 token/background combinations recomputed; AX-01…AX-10 defined |
| V24 | No undecided text or invented RPO/RTO/availability/retention/volume values | **PASS** | Scanned for sign-off, TBD/TODO, invented volumes, RPO/RTO/availability figures and retention defaults |
| V25 | Money in integer minor units with currency; UTC storage and local display explicit | **PASS** | Monetary columns use MONEY_MINOR + currency; 03 §2.2 time rules |
| V26 | Coverage model is substantive (no citation-derived coverage); every requirement assessed | **PASS** | No Traces lines; every requirement has a classification; every upgrade from the independent baseline is flagged for re-review |

## Evidence

### V07 No hardcoded role-name authorization

- 06-rbac.md:33: 1. **Code checks permission codes only.** Nothing references role codes (`FOUNDER`, `ADMIN`, `SALES`), "is_admin" flags 

### V23 Accessibility fixes documented as tokens; light and dark contrast verified

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

