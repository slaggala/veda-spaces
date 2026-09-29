# Architecture Validation Report

Generated 2026-09-29 on branch `architecture/p0-foundation-freeze`. Machine-readable version: [validation-report.json](validation-report.json). Coverage gate: [coverage-gate.md](coverage-gate.md).

## Method

- **Coverage rule.** A dimension is covered only if its registry reference resolves to a numbered section and that section explicitly cites the requirement ID.
- **Trace annotations.** Section-level 'Traces:' lines were generated from the reviewed registry mapping to make each mapping visible in the covered section. 'natively_cited_before_trace_annotation' shows how many were already cited in prose. Semantic adequacy of each mapping is for the independent reviewer.
- **Tooling.** Validation scripts were run in the authoring session and are intentionally not committed (no code in this freeze).

## Result: 14 of 14 checks passed

| # | Check | Result | Details |
|---|---|---|---|
| C01 | Every requirement ID resolves | **PASS** | 203 registered IDs; 0 unresolved references; 0 registry IDs missing from matrix; 0 duplicates; named registers: 8 EXC, 6 RBX, 12 ASM, 3 OWNER-INPUT; 0 unresolved named refs |
| C02 | Every cross-document reference resolves | **PASS** | 1032 section references and 69 relative links checked; 0 bad refs; 0 bad links |
| C03 | Every table follows the audit contract | **PASS** | 23 tables in inventory; 23 column-definition sections; contract defines all 9 columns; every table registered in 07 §2; behavioral exceptions registered for 10 tables (03 §2.9) |
| C04 | Every foreign key uses the canonical ID type | **PASS** | 41 id/reference columns checked across 23 tables plus 3 contract actor FKs per table; allow-listed non-FK: {'request_id': 'correlation string, not an entity reference'} |
| C05 | No table named user exists | **PASS** | Checked table sections, inventory, and FK/DDL-style references in all documents |
| C06 | app_user is used consistently | **PASS** | 32 references to app_user.id; no stale names (user.id, auth_event, audit.security.read, intake_submission_id, phone_is_valid) |
| C07 | No hardcoded Admin-role authorization exists | **PASS** | 3 mentions found, all in prohibition context; 0 unqualified |
| C08 | Every privileged endpoint maps to permissions | **PASS** | 85 endpoint rows checked; 41 permissions in catalog (06 §6); non-permission endpoints limited to RBAC exception register (6 entries) |
| C09 | SQLite and PostgreSQL mappings are explicit | **PASS** | Types used in schema: ['BIGINT', 'BOOL', 'CHAR(n)', 'CODE(n)', 'DATE', 'GUID', 'INTEGER', 'JSON', 'MONEY_MINOR', 'SMALLINT', 'TEXT', 'UTCDATETIME', 'VARCHAR(n)']; all mapped in 03 §12 |
| C10 | Public lead APIs expose no internal fields | **PASS** | 2 public response bodies checked (keys ⊆ {reference, message}); request schema limited to ADR-005 fields; only POST /public/leads is public |
| C11 | Security-event logs contain no secrets | **PASS** | 19 columns checked against prohibited names; prohibition list present in 05 §9.3; API output excludes hash and chain columns |
| C12 | All old undecided text is resolved or removed | **PASS** | Scanned for sign-off/confirm/decide/TBD/revisit markers and invented volume, RPO/RTO or availability figures; 0 matches are validation triggers inside the assumptions/owner-input registers |
| C13 | Deferred modules are not promoted into P0 | **PASS** | P0 table inventory, migration order, endpoint index and permission catalog contain no roadmap-module objects; doc 10 carries the ADR-009 banner |
| C14 | Accessibility fixes are documented as design-system tokens | **PASS** | 6 token decisions in 09 §2.5; ratios recomputed |

## Evidence and notes

### C07 No hardcoded Admin-role authorization exists

- 06-rbac.md:32: 1. **Code checks permission codes only.** Nothing in the code references role codes (`FOUNDER`, `ADMIN`), "is_admin" flags, or specific user
- decisions/ADR-006-mfa-policy.md:41: \| Check the role code (`if role in [FOUNDER, ADMIN]`) \| Violates RBAC-002 \|
- decisions/ADR-006-mfa-policy.md:41: \| Check the role code (`if role in [FOUNDER, ADMIN]`) \| Violates RBAC-002 \|

### C14 Accessibility fixes are documented as design-system tokens

- copper-text: computed 5.36 vs stated 5.4
- copper: computed 4.06 vs stated 4.1
- warning: computed 5.33 vs stated 5.3
- white on copper-strong: computed 7.10 vs stated 7.1
- copper on site paper: computed 3.81 vs stated 3.8

## Checks and how they were performed

| # | What was verified |
|---|---|
| C01 | Every requirement ID mentioned anywhere resolves to the registry. Every registry ID appears in the 01 matrix. No duplicates. Every EXC, RBX, ASM and OWNER-INPUT reference resolves to its register. |
| C02 | Every `NN §x.y` reference (including chained `§` lists) resolves to a numbered heading. Every relative Markdown link and every ADR-00x mention resolves to a file. |
| C03 | Every table in the 03 §11 inventory has a column-definition section and an audit-policy registration (07 §2). No table redefines contract columns. The contract defines all nine columns and forbids omission. Behavioral exceptions are registered (03 §2.9). |
| C04 | Every `*_id` and actor/semantic reference column in every table definition has the GUID type. The only allow-listed exception is `request_id`, a correlation string, not an FK. |
| C05 | No table section, inventory row or DDL/FK-style reference names a `user` table |
| C06 | `app_user.id` is the FK target throughout. No stale names from the pre-decision draft remain. |
| C07 | Scan for role-name authorization patterns. Every hit must be in a prohibition context. |
| C08 | Every row of the 08 endpoint index names a catalog permission or a registered RBX exception. Every backticked permission-like code in 04, 05, 08 and 09 is a catalog permission, a table field or a documented outbox event. |
| C09 | Every logical type used in any table definition has an explicit SQLite and PostgreSQL mapping in 03 §12 |
| C10 | Public intake response bodies contain only `reference` and `message`. The request schema is limited to ADR-005 fields. The only public endpoint is `POST /public/leads`. |
| C11 | `security_event_log` has no secret-bearing column names. 05 §9.3 prohibits each secret class. The API example exposes no hash, chain or token data. |
| C12 | No sign-off, confirm, decide, TBD, TODO or revisit markers, and no invented volume, RPO/RTO or availability numbers, outside the assumptions and owner-input registers |
| C13 | No roadmap-module tables, endpoints, permissions or migrations in P0. Doc 10 carries the ADR-009 banner. |
| C14 | Accessibility corrections are recorded as tokens in 09 §2.5, reference tokens defined in 09 §2.1, and stated contrast ratios match recomputation within ±0.1 |

