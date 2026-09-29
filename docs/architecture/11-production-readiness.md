# 11 — Production Readiness Review

Governing decisions: [ADR-002](decisions/ADR-002-uuidv7-identifiers.md) · [ADR-003](decisions/ADR-003-audit-contract.md) · [ADR-004](decisions/ADR-004-security-event-log.md) · [ADR-006](decisions/ADR-006-mfa-policy.md) · [ADR-008](decisions/ADR-008-aws-hosting.md) · [ADR-010](decisions/ADR-010-account-control-and-privileged-protection.md)

This document critiques documents 02–10, **updated after the independent review** (`review/p0-foundation-independent-review`, verdict NOT CERTIFIED) and remediation 01. The finding-by-finding disposition is in [review-remediation-matrix.md](review-remediation-matrix.md).

| Severity | Meaning |
|---|---|
| **High** | Resolve before go-live |
| **Medium** | Resolve soon after go-live |
| **Low** | Monitor or accept |

**No capacity figure in this document is a measurement.** Sizing statements are assumptions (§10).

## 1. Scalability and capacity

### 1.1 Position

- P0 runs **one application instance with one application process** on SQLite (ADR-008, OPS-006, OPS-010).
- No horizontal scaling is claimed.
- Scaling out requires the PostgreSQL release gate (§3.3).

### 1.2 Findings

| # | Finding | Sev | Recommendation |
|---|---|---|---|
| S1 | A single host is a single point of failure. The website stays up, and enquiries fall back to WhatsApp. | Medium | Accept for the MVP. Rehearsed rebuild, and an owner-approved RTO (RG-1). |
| S2 | In-process stores (limiter, idempotency, permission cache) | Resolved (F-09) | Exactly one gunicorn `gthread` worker process (OPS-010), so the stores are authoritative. Throughput is validated by the RG-4 load test (ASM-013). |
| S3 | Exact counts on large lists | Low | Capped totals |
| S4 | Contains-search | Low | Application-casefolded `search_text` (A-03). `pg_trgm` after the gate. |
| S5 | Live dashboard aggregates | Low | Read model if NFR-001 is missed |
| S6 | Security-event chain serialization | Low | Single writer on SQLite. The advisory-lock cost on PostgreSQL has an explicit acceptance criterion in gate PGM-1: NFR-001 p95 met with chain appends enabled (A-13). |
| S7 | Argon2id memory | Medium | Semaphore in the single process. Host sized by benchmark (ASM-010). |
| S8 | A per-request uncached session read (F-10) | Low | One indexed local read. Measured in RG-4. |

## 2. Availability, backup and recovery (ADR-008)

| # | Finding | Sev | Recommendation |
|---|---|---|---|
| B1 | SQLite file corruption or deletion | High | Litestream, nightly `VACUUM INTO` with Object Lock, and EBS snapshots (02 §12.3, OPS-002) |
| B2 | Untested backups | High | Automated restore verification (OPS-009, RG-2) |
| B3 | Migrations on a live single file | High | **The single runbook, 02 §12.4** (F-12): expand-only, N-1 compatible migrations. Normal rollback = redeploy N-1, with no data loss. Disaster rollback = snapshot restore, with a stated data-loss window and a WhatsApp fallback during maintenance. |
| B4 | Region outage | Low | ap-south-1 only (Decision 5). Optional cross-region backup replication for durability. **No multi-region availability is claimed.** Recovery time for a regional outage is not claimed. |
| B5 | Volume lost on rebuild | Medium | Dedicated volume, `DeleteOnTermination=false` (OPS-007, RG-6) |
| B6 | RPO, RTO and availability targets not approved | High (production) | OWNER-INPUT-001 (§7) |
| B7 | Litestream operational constraints (A-11) | Medium | Documented in 02 §12.3 and monitored |

## 3. SQLite limitations and PostgreSQL migration readiness

### 3.1 PostgreSQL hazards designed out

| Hazard | Mitigation |
|---|---|
| `user` reserved word | `app_user` (ADR-001) |
| Dynamic typing, unenforced lengths | Generated CHECKs (03 §12) |
| Booleans, datetimes, JSON | Kernel types with explicit mappings (03 §12) |
| Case folding differs for non-ASCII | Application-casefolded `search_text` (A-03) |
| FKs off by default | Pragma, verified by readiness |
| Money | Integer minor units (DATA-016) |
| Triggers | Per-engine guards. Readiness verifies presence (A-02). |
| Chain recomputation across engines | JCS over application-level values with fixed datetime precision (05 §9.6, F-11) |
| Correlation ids vs FKs | Evidence rows use non-FK correlation ids (EXC-009), so purges are engine-independent (F-07) |

### 3.2 GUID mapping

`CHAR(32)` on SQLite, native `uuid` on PostgreSQL. The API always carries the 32-hex form (ADR-002). The migration casts `CAST(col AS uuid)` and verifies checksums.

### 3.3 SQLite limits and the release gate (ADR-008, OPS-008)

- **PostgreSQL migration must be complete before any of these goes live:** procurement, inventory, finance, or multi-instance scale.
- Early-warning signals bring the gate forward:
  - sustained `SQLITE_BUSY`;
  - write latency above target;
  - restore time above the approved RTO;
  - a business need for live BI.

### 3.4 Migration runbook (outline)

1. Readiness: dual-engine CI.
2. Rehearsal (twice), verifying:
   - row counts, checksums and FKs;
   - **the keyed security-event chain recomputes identically**;
   - E2E.
3. Cutover with maintenance mode (website falls back to WhatsApp).
4. Rollback window using the read-only SQLite snapshot.
5. After cutover: new owner-approved RPO/RTO.

## 4. Audit and security-event concerns

| # | Finding | Sev | Status / recommendation |
|---|---|---|---|
| A1 | ORM bulk statements and raw SQL bypass the hook | High | Lint ban, `bulk_mutate`, tests (07 §3) |
| A2 | Direct DB file access | Medium | Break-glass SSM access only. **Keyed** HMAC chain with the key in SSM, and a daily Object-Lock anchor (F-11). **Residual, accepted:** root on the host can read the key from memory and rewrite back to the last daily anchor. SQLite has no DB roles, so triggers are convention-level; readiness verifies them (A-02). |
| A3 | PII in audit payloads vs erasure | Resolved | Anonymization procedure is now P0 (AUDIT-011, LEAD-029) |
| A4 | Evidence stores vs contract | Resolved | EXC-001, EXC-002 |
| A5 | Authentication telemetry in the entity audit | Resolved | ADR-004 |
| A6 | Secrets in security events | High | Allow-list writer and prohibited-content test |
| A7 | Failure events lost on rollback | Resolved | SEVT-011 |
| A8 | Chain serialization on PostgreSQL | Low | Advisory lock. Pass/fail criterion in PGM-1. Fallback: deferred chaining (A-13). |
| A9 | Retention durations | Owner input | OWNER-INPUT-002. Nothing is purged until set. |
| A10 | SENSITIVE_ACTION on reads was ambiguous | Resolved (F-06) | `SENSITIVE_ACTION` for mutations, de-duplicated `SENSITIVE_READ` for reads |
| A11 | Purge vs FK conflicts | Resolved (F-07) | 03 §2.10 ordering and EXC-009 |

## 5. Security concerns

| # | Finding | Sev | Status / recommendation |
|---|---|---|---|
| X1 | XSS exposing the access token | High | Strict CSP, Lit escaping, `unsafeHTML` banned |
| X2 | Refresh-token theft | Medium | Rotation, reuse detection, a single-use grace response with no new refresh token (F-10) |
| X3 | Credential stuffing against privileged accounts | Resolved in design | MFA mandatory for Founder, Admin and all sensitive-permission holders. Sensitive permissions are **inactive** without MFA (MFA-012). Per-network throttling (A-01). |
| X4 | Public intake abuse | Medium | Turnstile first. Relaxed per-IP limits for mobile NAT. Honeypot quarantine, not drop (F-05). |
| X5 | Enumeration | Low | Uniform responses |
| X6 | JWT key compromise | Medium | ES256 in SSM, `kid` rotation |
| X7 | CSRF | Low | SameSite=Strict + Origin + header. Negative tests (12 §4.5). |
| X8 | Broken object-level authorization | High | Scoped repositories and 404s. Scoped duplicate target (A-07). |
| X9 | Mass assignment | Resolved (F-03) | Closed profile-only DTOs. Security attributes only via dedicated workflows (ADR-010). |
| X10 | PII in logs and email | Medium | Masking. Security emails only to the verified address. |
| X11 | Supply chain | Medium | Scans (SEC-007) |
| X12 | Origin bypass | Medium | Cloudflare-only SG + mTLS |
| X13 | TOTP secret exposure | High | KMS envelope. Shown once. TEXT column for the wrapped key (F-13). |
| X14 | MFA reset or recovery used for takeover | Resolved in design (F-02) | No single-factor enrollment (MFA-014). Recovery = password + code → restricted session → re-enrollment, revocation of other sessions, notification, cooling-off (MFA-013). Admin reset: separate permission, step-up, G3/G9/G11, dual control for privileged targets, enrollment link to the target's verified email (MFA-015). |
| X15 | Recovery-code theft | Medium | Keyed hashes, single use, rotation after recovery, notification |
| X16 | Malformed or guessable ids | Low | UUIDv7 validation. No sequential public identifiers. |
| X17 | Account takeover via email change | Resolved (F-03) | Proposed-email workflow with alert and cancel to the old address. Reset only to the verified address. G9, G11, dual control (USER-007). |
| X18 | Organizational takeover by disabling the Founder or co-admins | Resolved (F-03) | G3, G4 (I1/I2 under the write lock), G9, G11, break-glass with two IAM custodians |
| X19 | Open redirect via `?next=` | Low | Strict pattern and tests (A-08) |
| X20 | Unverified penetration resistance | High (production) | DAST and penetration test before production (PG-DAST, F-19) |

### 5.6 Privacy and DPDP Act 2023 (SEC-009)

| Obligation | Design response |
|---|---|
| Notice and consent | Versioned consent with timestamp and context (LEAD-012) |
| Withdrawal | Recorded with channel. Contact activities blocked (LEAD-027). |
| Erasure | Audited anonymization, including audit payloads (LEAD-029, AUDIT-011) |
| Retention limitation | Closed-lead anonymization job (LEAD-028). **The period is OWNER-INPUT-002**, and the job ships disabled. |
| Safeguards and breach notification | This document's controls, plus an incident runbook |
| Residency | ap-south-1 (Decision 5) |

## 6. RBAC and MFA-policy concerns

| # | Finding | Sev | Status |
|---|---|---|---|
| R1 | Admin holds access-control permissions | High | G1/G2/G9/G10/G11/G12 |
| R2 | Lockout of all administrators or Founders | High | G4 invariants I1/I2 under the write lock, nightly check, break-glass |
| R3 | Permission explosion | Medium | Grouping, scope |
| R4 | Role explosion | Medium | Direct grants, access review |
| R5 | UI and server drift | Low | Server-computed capability flags |
| R6 | Stale permissions | Resolved (F-10, Decision 1.5) | Uncached per-request session and user read. `authz_version` covers MFA-state changes. |
| R7 | Ambiguous OWN scope | Medium | Per-resource registry |
| R8 | Role-name checks creeping in | Medium | Lint. MFA and Founder protection use data attributes. |
| R9 | Sales forced into MFA by a sensitive permission | Resolved (F-01) | Sales holds no sensitive permission (registry rule 3) |
| R10 | Time-bound grant expiry bypassing G4 | Resolved (F-16) | Time-bound grants are P1, disabled in P0, and never allowed on sensitive permissions |
| R11 | Custom roles with broad data access but no sensitive permission don't require MFA | Accepted (Decision 1) | Owner Decision 1 limits mandatory MFA to Founder, Admin and sensitive holders. `role.mfa_required` is available per role. |
| R12 | One Founder manufacturing a second approver | Resolved (N-01) | Canonical Founder-governance workflow (06 §7.2). FOUNDER role and `user.founder.manage` are grantable only through it (G13). I3 consistency. Custodian as the second principal in single-Founder mode. |
| R13 | Two accounts controlled by one human acting as requester and approver | Residual, procedural | Identity verification for `GRANT_FOUNDER` (reason field records the out-of-band check). Custodian register maps principals to distinct humans. Notifications to all Founders. |

## 7. Decisions, owner inputs and production release gates

### 7.1 Decisions resolved

| Item | Resolution |
|---|---|
| ADR-001 … ADR-009 | Accepted (freeze) |
| Sales MFA and security-event access (F-01) | Owner Decision 1 → ADR-006, ADR-004 |
| MFA recovery (F-02) | Owner Decision 2 → ADR-006 |
| Account control and privileged protection (F-03) | Owner Decision 3 → ADR-010 |
| Property type (ASM-005, F-17) | Owner Decision 4 → ADR-005 |
| AWS region (ASM-012) | Owner Decision 5 → ADR-008 |

### 7.2 Owner inputs: production release gates (owner Decision 6)

These do **not** block architecture review or implementation planning. They **block production release** where applicable. No values are proposed. All attributes (owner category, trigger, acceptance, evidence, failure behavior, and so on) are in the **canonical [gate registry](gate-registry.md)**.

| ID | Input needed | Owner category | Status |
|---|---|---|---|
| OWNER-INPUT-001 | Approved RPO, RTO and API availability target | Product Owner | Blocked, awaiting owner input |
| OWNER-INPUT-002 | Retention periods (all stores) | Privacy Owner | Blocked, awaiting owner input |
| OWNER-INPUT-003 | Restore-rehearsal cadence | Operations Owner | Blocked, awaiting owner input |
| OWNER-INPUT-004 | Two break-glass custodians mapped to distinct humans | Security Owner | Blocked, awaiting owner input |

### 7.3 Release and production gates

The canonical definitions are in [gate-registry.md](gate-registry.md) (N-04): RG-1 … RG-9, PG-DAST, PG-RET, PG-BG, PG-EMAIL, PG-PRIV, and PGM-1 (post-P0 PostgreSQL rehearsal, which carries the A-13 criterion).

- Every gate there lists owner category, trigger point, phase, entry and acceptance criteria, evidence, storage location, approver, failure behavior, revalidation, freshness, dependencies, protected requirements, blocking scope and status.
- **A failed, missing or stale evaluation is FAIL and never defaults to pass.**

## 8. Go-live checklist (P0 exit criteria)

This is for the implementation phase, not this remediation.

- [ ] Every P0 requirement verified per its method (12)
- [ ] Every gate in [gate-registry.md](gate-registry.md) applicable to production is PASSED with evidence
- [ ] Conformance check green on both engines
- [ ] RBAC matrix, guard G1–G12, sensitivity-registry and mass-assignment suites green
- [ ] MFA enrollment-proof, recovery, cooling-off and admin-reset suites green
- [ ] Email-change workflow suite green
- [ ] Security-event prohibited-content and keyed-chain suites green
- [ ] Accessibility AX-01…AX-10 green in both themes
- [ ] Founder bootstrapped with MFA enrolled
- [ ] Runbooks: deploy/migrate, restore, key rotation, break-glass, incident response

## 9. Top risks

| Rank | Risk | Mitigation |
|---|---|---|
| 1 | Broken object-level authorization | 06 §8, §10 |
| 2 | Single-instance recovery without approved objectives | RG-1, OWNER-INPUT-001 |
| 3 | Social engineering of MFA reset or recovery | MFA-013/014/015, dual control, notifications, cooling-off |
| 4 | Audit bypass via bulk or raw SQL | 07 §3 |
| 5 | PostgreSQL gate ignored under business pressure | RG-8, RG-9 |
| 6 | XSS leading to token misuse | X1 |
| 7 | Secrets leaking into logs or events | 05 §9.3 |

## 10. Assumptions register

| ID | Assumption | Status | Validate / replace when |
|---|---|---|---|
| ASM-001 | Staff user base during P0 is small (tens) | Open | Monitoring. Re-evaluated at the PostgreSQL gate. |
| ASM-002 | P0 write concurrency fits SQLite's single writer | Open | RG-4 |
| ASM-003 | Table growth classes (03 §11) are qualitative | Open | 30 days of measured growth |
| ASM-004 | Security-event volumes unknown. Alert, throttle and rate-limit thresholds are initial configuration values. | Open | 30-day review, recorded in ADR-004 |
| ASM-005 | *(Former: Property Type not sent to the public API)* | **Resolved** by owner Decision 4 | — |
| ASM-006 | *(Former: retention default values)* | **Replaced** by OWNER-INPUT-002. No values are asserted (Decision 6). | — |
| ASM-007 | NFR-001 fixture sizes are test fixtures, not forecasts | Open | Measured growth |
| ASM-008 | Cloudflare stays in front of the API | Open | Edge-provider change |
| ASM-009 | SES production access will be granted | Open, production gate PG-EMAIL | SES approval |
| ASM-010 | ≥ 2 GB RAM host suffices for Argon2id | Open | Benchmark |
| ASM-011 | A versioned privacy notice will be published | Open, production gate PG-PRIV | Website implementation |
| ASM-012 | *(Former: AWS region)* | **Resolved** by owner Decision 5 (ap-south-1) | — |
| ASM-013 | One gunicorn process with a thread pool meets NFR-001 at P0 load | Open | RG-4 load test. If missed, move the limiter and idempotency stores to local Redis before adding worker processes. |

## 11. Tracked gates (findings that need evidence beyond architecture)

Full attributes are in the [gate registry](gate-registry.md). Summary:

| ID | Source | Owner category | Phase | Status |
|---|---|---|---|---|
| TG-01 | F-18: verifiable owner approval | Product Owner | Pre-implementation | **Pending: no verifiable owner approval exists** |
| TG-02 | F-13: real KMS blob test | Security Owner | Implementation | Pending |
| TG-03 | F-19: security assessment (via PG-DAST) | Security Owner | Pre-production | Pending |
| TG-04 | F-15: retention values applied (via PG-RET) | Privacy Owner | Pre-production | Blocked, awaiting OWNER-INPUT-002 |
| TG-05 | F-12: runbook rehearsal (via RG-7) | Operations Owner | Pre-production | Pending |
| TG-06 | F-09, F-10: load and revocation evidence (via RG-4) | Operations Owner | Pre-production | Pending |
| TG-07 | Re-review condition: targeted independent verification of this final remediation | Architecture Owner | Pre-implementation (affected stories) | Pending |
| TG-08 | Focused re-review, section 16: explicit owner authorization of implementation | Product Owner | Pre-implementation | Pending: not authorized |
