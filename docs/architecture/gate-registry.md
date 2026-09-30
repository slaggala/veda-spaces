# Gate Registry (canonical)

This is the single source for every owner-input, tracked, release and production gate (N-04). 11 §7 and §11 summarize and point here. Machine-readable: [gate-registry.json](gate-registry.json).

**Rules.**

1. A gate passes only on recorded evidence that meets its acceptance criteria. A missing, stale or failed evaluation is **FAIL** and never defaults to pass.
2. Owners and approvers are **categories** (Product, Security, Operations, Privacy and Architecture Owner). One person may hold several categories, and assigning named individuals is an owner decision outside this architecture.
3. No gate is currently passed. **TG-01 is pending, and the architecture is not owner-approved.**

## Summary

| Gate | Title | Owner | Phase | Status |
|---|---|---|---|---|
| OWNER-INPUT-001 | Recovery objectives and availability target | Product Owner | Pre-production | Blocked — awaiting owner input |
| OWNER-INPUT-002 | Retention periods | Privacy Owner | Pre-production | Blocked — awaiting owner input |
| OWNER-INPUT-003 | Restore-rehearsal cadence | Operations Owner | Pre-production | Blocked — awaiting owner input |
| OWNER-INPUT-004 | Break-glass custodians | Security Owner | Pre-production | Blocked — awaiting owner input |
| TG-01 | Verifiable owner approval of the architecture (F-18) | Product Owner | Pre-implementation | Pending — no verifiable owner approval exists |
| TG-02 | Real KMS blob fits the MFA columns (F-13) | Security Owner | Implementation | Pending |
| TG-03 | Security assessment tracked from F-19 | Security Owner | Pre-production | Pending |
| TG-04 | Retention values applied (F-15) | Privacy Owner | Pre-production | Blocked — awaiting OWNER-INPUT-002 |
| TG-05 | Runbook rehearsal (F-12) | Operations Owner | Pre-production | Pending |
| TG-06 | Single-process performance and revocation under load (F-09, F-10) | Operations Owner | Pre-production | Pending |
| TG-07 | Targeted independent verification of the final minor remediation | Architecture Owner | Pre-implementation | Pending |
| TG-08 | Explicit owner authorization of the implementation workstream | Product Owner | Pre-implementation | Pending — not authorized |
| RG-1 | Recovery objectives met | Operations Owner | Pre-production | Pending |
| RG-2 | Restore verification green | Operations Owner | Pre-production | Pending |
| RG-3 | Single instance and process enforced | Operations Owner | Pre-production | Pending |
| RG-4 | Load and contention | Operations Owner | Pre-production | Pending |
| RG-5 | Backup and disk alerts | Operations Owner | Pre-production | Pending |
| RG-6 | Encrypted persistent volume | Operations Owner | Pre-production | Pending |
| RG-7 | Migration runbook rehearsal | Operations Owner | Pre-production | Pending |
| RG-8 | PostgreSQL gate recorded | Architecture Owner | Pre-production | Pending |
| RG-9 | No SQLite-incompatible usage | Architecture Owner | Pre-production | Pending |
| PG-DAST | Security assessment | Security Owner | Pre-production | Pending |
| PG-RET | Retention values applied | Privacy Owner | Pre-production | Blocked — awaiting OWNER-INPUT-002 |
| PG-BG | Break-glass readiness | Security Owner | Pre-production | Blocked — awaiting OWNER-INPUT-004 |
| PG-EMAIL | Production email readiness | Operations Owner | Pre-production | Pending |
| PG-PRIV | Privacy notice and consent | Privacy Owner | Pre-production | Pending |
| PGM-1 | PostgreSQL migration rehearsal (includes A-13 criterion) | Architecture Owner | Post-P0 migration | Not applicable until post-P0 |

## Gate definitions

### OWNER-INPUT-001

| Attribute | Value |
|---|---|
| Title | Recovery objectives and availability target |
| Purpose | Obtain owner-approved RPO, RTO and API availability target (owner Decision 6) |
| Owner | Product Owner |
| Trigger point | Before production readiness sign-off |
| Applies to phase | Pre-production |
| Entry criteria | Rebuild/restore mechanisms designed (02 §12.3) |
| Acceptance criteria | Numeric RPO, RTO and monthly availability target approved and recorded; no value proposed by the architecture |
| Evidence required | Signed or PR-approved decision-log entry with the values |
| Evidence storage location | `docs/architecture/decisions/decision-log.md` (new dated entry referencing the approval) |
| Approver | Product Owner |
| Failure behavior | Production release is blocked. A failed or missing evaluation is recorded as FAIL, never as pass. A remediation item is opened with the gate owner. NFR-002 and OPS-005 remain 'Not testable'. |
| Retry / revalidation | Re-approval required if ADR-008 topology changes |
| Expiry / freshness | Valid until changed by a new decision-log entry |
| Dependencies | — |
| Requirements protected | OPS-005, NFR-002, OPS-009 |
| Blocking scope | Production release; RG-1 |
| Status | Blocked — awaiting owner input |

### OWNER-INPUT-002

| Attribute | Value |
|---|---|
| Title | Retention periods |
| Purpose | Obtain approved retention periods for audit, security events, sessions, tokens, outbox, notifications, closed leads and application logs |
| Owner | Privacy Owner |
| Trigger point | Before enabling any purge, archival or anonymization job |
| Applies to phase | Pre-production |
| Entry criteria | Retention mechanisms designed (03 §2.10, 04 §14, 05 §9.4, 07 §8) |
| Acceptance criteria | Every retention setting has an approved value recorded; legal basis noted |
| Evidence required | Decision-log entry + configuration record listing each value |
| Evidence storage location | `docs/architecture/decisions/decision-log.md` (new dated entry referencing the approval) |
| Approver | Privacy Owner |
| Failure behavior | Retention, archival and anonymization jobs refuse to run (nothing is deleted); PG-RET fails; production release blocked where retention is required. |
| Retry / revalidation | Re-approval on any legal or policy change |
| Expiry / freshness | Reviewed at least at each DPDP policy change |
| Dependencies | — |
| Requirements protected | SEVT-004, LEAD-028, DATA-017, AUDIT-009, SEC-009 |
| Blocking scope | Enabling retention jobs; PG-RET |
| Status | Blocked — awaiting owner input |

### OWNER-INPUT-003

| Attribute | Value |
|---|---|
| Title | Restore-rehearsal cadence |
| Purpose | Set how often full restore rehearsals repeat |
| Owner | Operations Owner |
| Trigger point | Before production readiness sign-off |
| Applies to phase | Pre-production |
| Entry criteria | RG-2 mechanism exists |
| Acceptance criteria | Cadence approved and recorded |
| Evidence required | Decision-log entry |
| Evidence storage location | `docs/architecture/decisions/decision-log.md` (new dated entry referencing the approval) |
| Approver | Product Owner |
| Failure behavior | Production release is blocked. A failed or missing evaluation is recorded as FAIL, never as pass. A remediation item is opened with the gate owner. |
| Retry / revalidation | Re-approval on topology change |
| Expiry / freshness | Valid until changed |
| Dependencies | — |
| Requirements protected | OPS-009, SEC-008 |
| Blocking scope | Production release; RG-2 schedule |
| Status | Blocked — awaiting owner input |

### OWNER-INPUT-004

| Attribute | Value |
|---|---|
| Title | Break-glass custodians |
| Purpose | Designate two break-glass custodians (IAM principals mapped to distinct humans) — 06 §7.5 |
| Owner | Security Owner |
| Trigger point | Before production readiness sign-off |
| Applies to phase | Pre-production |
| Entry criteria | Break-glass design (06 §7.5) |
| Acceptance criteria | Two IAM principals in the break-glass group, AWS MFA enforced, each mapped to exactly one distinct human in the custodian register; neither maps to the same human |
| Evidence required | Decision-log entry + IAM group membership export + custodian register (hashes) |
| Evidence storage location | `docs/architecture/decisions/decision-log.md` (new dated entry referencing the approval); Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Product Owner |
| Failure behavior | Production release blocked; single-Founder mode and Founder recovery are unavailable (Founder-level actions cannot execute). |
| Retry / revalidation | Revalidate on any personnel change or IAM change |
| Expiry / freshness | Revalidated at least on every custodian change; PG-BG drill evidence ≤ one release old |
| Dependencies | — |
| Requirements protected | RBAC-021, MFA-015, RBAC-020 |
| Blocking scope | Production release; PG-BG |
| Status | Blocked — awaiting owner input |

### TG-01

| Attribute | Value |
|---|---|
| Title | Verifiable owner approval of the architecture (F-18) |
| Purpose | Provide verifiable evidence that the owner accepts the architecture decisions |
| Owner | Product Owner |
| Trigger point | Before any implementation begins |
| Applies to phase | Pre-implementation |
| Entry criteria | Architecture at the reviewed SHA; decision log present |
| Acceptance criteria | The owner approves the architecture pull request (or signs the decision log) from the owner's own account |
| Evidence required | Link to the PR approval (or signed log) recorded in the decision log |
| Evidence storage location | `docs/architecture/decisions/decision-log.md` (new dated entry referencing the approval) |
| Approver | Product Owner (self-evidencing) |
| Failure behavior | The affected implementation work must not start, or must not be marked Done. A failed or missing evaluation is FAIL, never pass. The architecture must not be described as owner-approved. |
| Retry / revalidation | Re-approval required for any later architecture commit that changes an ADR |
| Expiry / freshness | Tied to the approved SHA; stale when a later ADR-changing commit lands |
| Dependencies | — |
| Requirements protected | PLAT-006 |
| Blocking scope | All implementation |
| Status | Pending — no verifiable owner approval exists |

### TG-02

| Attribute | Value |
|---|---|
| Title | Real KMS blob fits the MFA columns (F-13) |
| Purpose | Prove `wrapped_data_key`/`kms_key_arn` store real KMS output |
| Owner | Security Owner |
| Trigger point | During the MFA implementation story, before it is Done |
| Applies to phase | Implementation |
| Entry criteria | Prerequisite: TG-01 and TG-08 passed; staging KMS key available |
| Acceptance criteria | 12 §4.5 'KMS blob size' test passes on both engines with a real GenerateDataKey blob and a maximum-length ARN |
| Evidence required | CI test report |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Security Owner |
| Failure behavior | The affected implementation work must not start, or must not be marked Done. A failed or missing evaluation is FAIL, never pass. |
| Retry / revalidation | Re-run on KMS key or schema change |
| Expiry / freshness | Latest CI run on the release commit |
| Dependencies | TG-01, TG-08 |
| Requirements protected | MFA-010, MFA-001 |
| Blocking scope | MFA story Done |
| Status | Pending |

### TG-03

| Attribute | Value |
|---|---|
| Title | Security assessment tracked from F-19 |
| Purpose | Track F-19's DAST/penetration deficiency to PG-DAST |
| Owner | Security Owner |
| Trigger point | Before production readiness sign-off |
| Applies to phase | Pre-production |
| Entry criteria | Staging deployed at the release candidate |
| Acceptance criteria | PG-DAST passed |
| Evidence required | PG-DAST evidence |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Security Owner |
| Failure behavior | Production release is blocked. A failed or missing evaluation is recorded as FAIL, never as pass. A remediation item is opened with the gate owner. |
| Retry / revalidation | As PG-DAST |
| Expiry / freshness | As PG-DAST |
| Dependencies | PG-DAST |
| Requirements protected | SEC-010, SEC-002, SEC-003 |
| Blocking scope | Production release |
| Status | Pending |

### TG-04

| Attribute | Value |
|---|---|
| Title | Retention values applied (F-15) |
| Purpose | Ensure retention jobs run only with approved values |
| Owner | Privacy Owner |
| Trigger point | Before enabling retention jobs in production |
| Applies to phase | Pre-production |
| Entry criteria | OWNER-INPUT-002 approved |
| Acceptance criteria | PG-RET passed |
| Evidence required | PG-RET evidence |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Privacy Owner |
| Failure behavior | Retention jobs stay disabled; production release blocked where retention is required. |
| Retry / revalidation | As PG-RET |
| Expiry / freshness | As PG-RET |
| Dependencies | OWNER-INPUT-002, PG-RET |
| Requirements protected | LEAD-028, SEVT-004 |
| Blocking scope | Retention enablement |
| Status | Blocked — awaiting OWNER-INPUT-002 |

### TG-05

| Attribute | Value |
|---|---|
| Title | Runbook rehearsal (F-12) |
| Purpose | Track F-12's rehearsal to RG-7 |
| Owner | Operations Owner |
| Trigger point | Before production readiness sign-off |
| Applies to phase | Pre-production |
| Entry criteria | Staging environment |
| Acceptance criteria | RG-7 passed |
| Evidence required | RG-7 evidence |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Operations Owner |
| Failure behavior | Production release is blocked. A failed or missing evaluation is recorded as FAIL, never as pass. A remediation item is opened with the gate owner. |
| Retry / revalidation | As RG-7 |
| Expiry / freshness | As RG-7 |
| Dependencies | RG-7 |
| Requirements protected | OPS-004 |
| Blocking scope | Production release |
| Status | Pending |

### TG-06

| Attribute | Value |
|---|---|
| Title | Single-process performance and revocation under load (F-09, F-10) |
| Purpose | Track ASM-013 and uncached-session costs to RG-4 |
| Owner | Operations Owner |
| Trigger point | Before production readiness sign-off |
| Applies to phase | Pre-production |
| Entry criteria | Staging at release candidate |
| Acceptance criteria | RG-4 passed and 12 §4.5 revocation tests green |
| Evidence required | RG-4 evidence + CI report |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Operations Owner |
| Failure behavior | Production release is blocked. A failed or missing evaluation is recorded as FAIL, never as pass. A remediation item is opened with the gate owner. |
| Retry / revalidation | As RG-4 |
| Expiry / freshness | As RG-4 |
| Dependencies | RG-4 |
| Requirements protected | OPS-010, AUTH-006, NFR-001 |
| Blocking scope | Production release |
| Status | Pending |

### TG-07

| Attribute | Value |
|---|---|
| Title | Targeted independent verification of the final minor remediation |
| Purpose | Independent confirmation that N-01…N-04 and F-19 are corrected |
| Owner | Architecture Owner |
| Trigger point | Before implementing the Founder workflow, approvals, conformance check, recovery, RBAC resolver, duplicate-detection or concurrency stories |
| Applies to phase | Pre-implementation |
| Entry criteria | This remediation committed and pushed |
| Acceptance criteria | An independent reviewer (not the author) confirms N-01…N-04 and F-19 resolved at the new SHA |
| Evidence required | Review artifact on the review branch |
| Evidence storage location | `review/p0-foundation-independent-review` branch |
| Approver | Architecture Owner (acceptance of the independent verdict) |
| Failure behavior | The affected implementation work must not start, or must not be marked Done. A failed or missing evaluation is FAIL, never pass. Affected stories: RBAC-021, MFA-015, DATA-011, DATA-014, MFA-013, RBAC-006, LEAD-010, API-006. |
| Retry / revalidation | Re-verification after any change to 06 §7.2, 03 §2.11 or 12 §4.12 |
| Expiry / freshness | Tied to the verified SHA |
| Dependencies | — |
| Requirements protected | RBAC-021, MFA-015, DATA-011, DATA-014, MFA-013, RBAC-006, LEAD-010, API-006 |
| Blocking scope | Listed implementation stories |
| Status | Pending |

### TG-08

| Attribute | Value |
|---|---|
| Title | Explicit owner authorization of the implementation workstream |
| Purpose | Implementation needs separate explicit owner authorization (focused re-review, section 16) |
| Owner | Product Owner |
| Trigger point | Before any implementation begins |
| Applies to phase | Pre-implementation |
| Entry criteria | Prerequisite: TG-01 passed |
| Acceptance criteria | Explicit written authorization naming the implementation scope |
| Evidence required | Decision-log entry referencing the authorization |
| Evidence storage location | `docs/architecture/decisions/decision-log.md` (new dated entry referencing the approval) |
| Approver | Product Owner |
| Failure behavior | The affected implementation work must not start, or must not be marked Done. A failed or missing evaluation is FAIL, never pass. |
| Retry / revalidation | New authorization for scope changes |
| Expiry / freshness | Per authorized scope |
| Dependencies | TG-01 |
| Requirements protected | PLAT-012 |
| Blocking scope | All implementation |
| Status | Pending — not authorized |

### RG-1

| Attribute | Value |
|---|---|
| Title | Recovery objectives met |
| Purpose | Prove the owner's RPO/RTO are achievable |
| Owner | Operations Owner |
| Trigger point | Before production readiness sign-off (and re-run before each production release that changes infrastructure) |
| Applies to phase | Pre-production |
| Entry criteria | Release candidate deployed to staging; dependencies met |
| Acceptance criteria | Full rebuild-and-restore rehearsal on staging measures RPO and RTO that meet OWNER-INPUT-001 |
| Evidence required | Rehearsal report with timestamps, restored row counts, measured RPO/RTO |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Operations Owner |
| Failure behavior | Production release is blocked. A failed or missing evaluation is recorded as FAIL, never as pass. A remediation item is opened with the gate owner. |
| Retry / revalidation | Fix and re-run the full gate; partial re-runs are not accepted |
| Expiry / freshness | Evidence older than the current release candidate is stale |
| Dependencies | OWNER-INPUT-001 |
| Requirements protected | OPS-005, OPS-009, NFR-002 |
| Blocking scope | Production release |
| Status | Pending |

### RG-2

| Attribute | Value |
|---|---|
| Title | Restore verification green |
| Purpose | Prove backups restore |
| Owner | Operations Owner |
| Trigger point | Before production readiness sign-off (and re-run before each production release that changes infrastructure) |
| Applies to phase | Pre-production |
| Entry criteria | Release candidate deployed to staging; dependencies met |
| Acceptance criteria | Automated restore verification (OPS-009) passed on consecutive scheduled runs covering at least the owner-approved cadence window, and its failure alert was test-fired |
| Evidence required | Job run history + alert test-fire record |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Operations Owner |
| Failure behavior | Production release is blocked. A failed or missing evaluation is recorded as FAIL, never as pass. A remediation item is opened with the gate owner. |
| Retry / revalidation | Fix and re-run the full gate; partial re-runs are not accepted |
| Expiry / freshness | Evidence older than the current release candidate is stale |
| Dependencies | OWNER-INPUT-003 |
| Requirements protected | OPS-009, SEC-008, OPS-002 |
| Blocking scope | Production release |
| Status | Pending |

### RG-3

| Attribute | Value |
|---|---|
| Title | Single instance and process enforced |
| Purpose | Enforce SQLite single-writer topology |
| Owner | Operations Owner |
| Trigger point | Before production readiness sign-off (and re-run before each production release that changes infrastructure) |
| Applies to phase | Pre-production |
| Entry criteria | Release candidate deployed to staging; dependencies met |
| Acceptance criteria | Deployment config and a CI/OP check prove exactly one instance, one gunicorn worker process and one Litestream replicator |
| Evidence required | Config export + check output |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Operations Owner |
| Failure behavior | Production release is blocked. A failed or missing evaluation is recorded as FAIL, never as pass. A remediation item is opened with the gate owner. |
| Retry / revalidation | Fix and re-run the full gate; partial re-runs are not accepted |
| Expiry / freshness | Evidence older than the current release candidate is stale |
| Dependencies | — |
| Requirements protected | OPS-006, OPS-010 |
| Blocking scope | Production release |
| Status | Pending |

### RG-4

| Attribute | Value |
|---|---|
| Title | Load and contention |
| Purpose | Prove performance targets with one process |
| Owner | Operations Owner |
| Trigger point | Before production readiness sign-off (and re-run before each production release that changes infrastructure) |
| Applies to phase | Pre-production |
| Entry criteria | Release candidate deployed to staging; dependencies met |
| Acceptance criteria | Load test at ASM-007 fixture sizes meets NFR-001 and NFR-003; no SQLITE_BUSY surfaced to clients; chain-append latency recorded |
| Evidence required | Load-test report |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Operations Owner |
| Failure behavior | Production release is blocked. A failed or missing evaluation is recorded as FAIL, never as pass. A remediation item is opened with the gate owner. |
| Retry / revalidation | Fix and re-run the full gate; partial re-runs are not accepted |
| Expiry / freshness | Evidence older than the current release candidate is stale |
| Dependencies | — |
| Requirements protected | NFR-001, NFR-003, OPS-010, SEVT-006 |
| Blocking scope | Production release |
| Status | Pending |

### RG-5

| Attribute | Value |
|---|---|
| Title | Backup and disk alerts |
| Purpose | Prove operators are warned |
| Owner | Operations Owner |
| Trigger point | Before production readiness sign-off (and re-run before each production release that changes infrastructure) |
| Applies to phase | Pre-production |
| Entry criteria | Release candidate deployed to staging; dependencies met |
| Acceptance criteria | Litestream lag, snapshot-missing and disk alerts wired and each test-fired to its destination |
| Evidence required | Alert test-fire records |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Operations Owner |
| Failure behavior | Production release is blocked. A failed or missing evaluation is recorded as FAIL, never as pass. A remediation item is opened with the gate owner. |
| Retry / revalidation | Fix and re-run the full gate; partial re-runs are not accepted |
| Expiry / freshness | Evidence older than the current release candidate is stale |
| Dependencies | — |
| Requirements protected | OPS-002, LOG-006 |
| Blocking scope | Production release |
| Status | Pending |

### RG-6

| Attribute | Value |
|---|---|
| Title | Encrypted persistent volume |
| Purpose | Prove data is not in the container layer |
| Owner | Operations Owner |
| Trigger point | Before production readiness sign-off (and re-run before each production release that changes infrastructure) |
| Applies to phase | Pre-production |
| Entry criteria | Release candidate deployed to staging; dependencies met |
| Acceptance criteria | DB path on the dedicated KMS-encrypted volume; DeleteOnTermination=false verified |
| Evidence required | Instance/volume description export |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Operations Owner |
| Failure behavior | Production release is blocked. A failed or missing evaluation is recorded as FAIL, never as pass. A remediation item is opened with the gate owner. |
| Retry / revalidation | Fix and re-run the full gate; partial re-runs are not accepted |
| Expiry / freshness | Evidence older than the current release candidate is stale |
| Dependencies | — |
| Requirements protected | OPS-007 |
| Blocking scope | Production release |
| Status | Pending |

### RG-7

| Attribute | Value |
|---|---|
| Title | Migration runbook rehearsal |
| Purpose | Prove deploy and both rollback paths |
| Owner | Operations Owner |
| Trigger point | Before production readiness sign-off (and re-run before each production release that changes infrastructure) |
| Applies to phase | Pre-production |
| Entry criteria | Release candidate deployed to staging; dependencies met |
| Acceptance criteria | 02 §12.4 rehearsed on staging including N-1 rollback and snapshot-restore rollback with the data-loss window reported |
| Evidence required | Rehearsal record |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Operations Owner |
| Failure behavior | Production release is blocked. A failed or missing evaluation is recorded as FAIL, never as pass. A remediation item is opened with the gate owner. |
| Retry / revalidation | Fix and re-run the full gate; partial re-runs are not accepted |
| Expiry / freshness | Evidence older than the current release candidate is stale |
| Dependencies | — |
| Requirements protected | OPS-004 |
| Blocking scope | Production release |
| Status | Pending |

### RG-8

| Attribute | Value |
|---|---|
| Title | PostgreSQL gate recorded |
| Purpose | Keep gated modules off SQLite |
| Owner | Architecture Owner |
| Trigger point | Before production readiness sign-off (and re-run before each production release that changes infrastructure) |
| Applies to phase | Pre-production |
| Entry criteria | Release candidate deployed to staging; dependencies met |
| Acceptance criteria | Release checklist confirms no procurement, inventory, finance or multi-instance feature is enabled while SQLite is authoritative |
| Evidence required | Signed release checklist |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Architecture Owner |
| Failure behavior | Production release is blocked. A failed or missing evaluation is recorded as FAIL, never as pass. A remediation item is opened with the gate owner. |
| Retry / revalidation | Fix and re-run the full gate; partial re-runs are not accepted |
| Expiry / freshness | Evidence older than the current release candidate is stale |
| Dependencies | — |
| Requirements protected | OPS-008, PLAT-012 |
| Blocking scope | Production release |
| Status | Pending |

### RG-9

| Attribute | Value |
|---|---|
| Title | No SQLite-incompatible usage |
| Purpose | Prevent unsafe scale or BI access |
| Owner | Architecture Owner |
| Trigger point | Before production readiness sign-off (and re-run before each production release that changes infrastructure) |
| Applies to phase | Pre-production |
| Entry criteria | Release candidate deployed to staging; dependencies met |
| Acceptance criteria | No second instance, gated module or direct BI DB access configured |
| Evidence required | Config and access review record |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Architecture Owner |
| Failure behavior | Production release is blocked. A failed or missing evaluation is recorded as FAIL, never as pass. A remediation item is opened with the gate owner. |
| Retry / revalidation | Fix and re-run the full gate; partial re-runs are not accepted |
| Expiry / freshness | Evidence older than the current release candidate is stale |
| Dependencies | — |
| Requirements protected | OPS-006, OPS-008 |
| Blocking scope | Production release |
| Status | Pending |

### PG-DAST

| Attribute | Value |
|---|---|
| Title | Security assessment |
| Purpose | Independent security testing of auth, MFA recovery, account control and public intake |
| Owner | Security Owner |
| Trigger point | Before production readiness sign-off |
| Applies to phase | Pre-production |
| Entry criteria | Release candidate on staging; test accounts provisioned; scope letter agreed |
| Acceptance criteria | An assessment (automated DAST baseline + authenticated scan + manual penetration test of the listed surfaces) is complete; the report states its methodology and severity scale; **no finding the assessor rates at the report's two highest severities remains open** — each is fixed and verified by retest, or formally risk-accepted by the Security Owner and Product Owner with rationale; all remaining findings are triaged with an owner |
| Evidence required | Assessment report, retest evidence, risk-acceptance records |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Security Owner |
| Failure behavior | Production release is blocked. A failed or missing evaluation is recorded as FAIL, never as pass. A remediation item is opened with the gate owner. |
| Retry / revalidation | Retest affected areas after fixes; full re-assessment if auth/MFA/account-control code changes materially |
| Expiry / freshness | Assessment must be against the release candidate or a build with no security-relevant changes since |
| Dependencies | TG-03 |
| Requirements protected | SEC-010, SEC-002, SEC-003, SEC-004, AUTH-005, MFA-013, USER-007, LEAD-018 |
| Blocking scope | Production release |
| Status | Pending |

### PG-RET

| Attribute | Value |
|---|---|
| Title | Retention values applied |
| Purpose | Retention jobs use approved values |
| Owner | Privacy Owner |
| Trigger point | Before enabling any retention/archival/anonymization job |
| Applies to phase | Pre-production |
| Entry criteria | OWNER-INPUT-002 approved |
| Acceptance criteria | Configured values equal the approved values; staging run of each job succeeds with those values; archival verifies checksums before deletion |
| Evidence required | Config diff vs decision log + job run evidence |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Privacy Owner |
| Failure behavior | Jobs remain disabled; nothing is deleted; production release blocked where retention is legally required. |
| Retry / revalidation | Re-run after any value change |
| Expiry / freshness | Evidence per configuration version |
| Dependencies | OWNER-INPUT-002 |
| Requirements protected | LEAD-028, SEVT-004, DATA-017, SEC-009 |
| Blocking scope | Retention enablement; production |
| Status | Blocked — awaiting OWNER-INPUT-002 |

### PG-BG

| Attribute | Value |
|---|---|
| Title | Break-glass readiness |
| Purpose | Founder recovery must work before production |
| Owner | Security Owner |
| Trigger point | Before production readiness sign-off |
| Applies to phase | Pre-production |
| Entry criteria | OWNER-INPUT-004 approved |
| Acceptance criteria | Custodians identified per OWNER-INPUT-004; a staging drill executes single-Founder-mode approval and full break-glass: same-human refusal observed, cooling-off respected, cancel link works, all events and notifications recorded |
| Evidence required | Drill record + event export (no secrets) |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Security Owner |
| Failure behavior | Production release is blocked. A failed or missing evaluation is recorded as FAIL, never as pass. A remediation item is opened with the gate owner. Founder-level actions cannot execute in production. |
| Retry / revalidation | Re-drill on custodian change |
| Expiry / freshness | Drill evidence must be from the current release line |
| Dependencies | OWNER-INPUT-004 |
| Requirements protected | RBAC-021, MFA-015 |
| Blocking scope | Production release |
| Status | Blocked — awaiting OWNER-INPUT-004 |

### PG-EMAIL

| Attribute | Value |
|---|---|
| Title | Production email readiness |
| Purpose | Security flows depend on outbound email |
| Owner | Operations Owner |
| Trigger point | Before production readiness sign-off |
| Applies to phase | Pre-production |
| Entry criteria | SES production access requested |
| Acceptance criteria | SES production access granted; SPF, DKIM and DMARC pass; reset, invite, enrollment-link, recovery-notification and email-change messages delivered to test inboxes; forced provider failure leaves leads persisted and outbox rows FAILED/DEAD with an alert (NOTIF-008) |
| Evidence required | Delivery evidence + DNS check output + failure-drill record |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Operations Owner |
| Failure behavior | Production release is blocked. A failed or missing evaluation is recorded as FAIL, never as pass. A remediation item is opened with the gate owner. Unless the Product Owner explicitly records acceptance of go-live without outbound email (security flows would then be unavailable). |
| Retry / revalidation | Re-verify after DNS or provider change |
| Expiry / freshness | Current release line |
| Dependencies | — |
| Requirements protected | NOTIF-002, NOTIF-008, NOTIF-009, AUTH-008, MFA-014, USER-007 |
| Blocking scope | Production release |
| Status | Pending |

### PG-PRIV

| Attribute | Value |
|---|---|
| Title | Privacy notice and consent |
| Purpose | Public intake must be lawful |
| Owner | Privacy Owner |
| Trigger point | Before public intake goes live |
| Applies to phase | Pre-production |
| Entry criteria | Privacy text drafted |
| Acceptance criteria | Versioned privacy notice approved by the Privacy Owner and published; its version id equals `consent.policy_version` sent by the form; consent checkbox unchecked by default; withdrawal process published |
| Evidence required | Approved notice + form E2E evidence |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Privacy Owner |
| Failure behavior | Public intake (LEAD-001) must not go live; the website keeps the WhatsApp-only flow. |
| Retry / revalidation | Re-approve on notice change (new version id) |
| Expiry / freshness | Per notice version |
| Dependencies | — |
| Requirements protected | LEAD-012, LEAD-027, SEC-009 |
| Blocking scope | Public intake go-live |
| Status | Pending |

### PGM-1

| Attribute | Value |
|---|---|
| Title | PostgreSQL migration rehearsal (includes A-13 criterion) |
| Purpose | Validate migration and the advisory-lock cost of security-event chaining |
| Owner | Architecture Owner |
| Trigger point | Before PostgreSQL cutover (post-P0) |
| Applies to phase | Post-P0 migration |
| Entry criteria | PostgreSQL release gate triggered (OPS-008) |
| Acceptance criteria | Rehearsal per 11 §3.4 passes (row counts, checksums, keyed-chain recomputation); **NFR-001 p95 is met on PostgreSQL with security-event chain appends enabled under the advisory lock** (A-13) |
| Evidence required | Rehearsal report |
| Evidence storage location | Release evidence register `docs/release-evidence/<gate-id>/` (summary, links and SHA-256 of artifacts; no secrets or personal data), with raw artifacts in the restricted evidence bucket referenced by hash |
| Approver | Architecture Owner |
| Failure behavior | Cutover must not proceed; stay on SQLite; if A-13 fails, implement deferred chaining (sequence + asynchronous chaining) and re-run. |
| Retry / revalidation | Full re-rehearsal after fixes |
| Expiry / freshness | Current migration candidate |
| Dependencies | RG-8 |
| Requirements protected | OPS-008, SEVT-006, NFR-001 |
| Blocking scope | PostgreSQL cutover |
| Status | Not applicable until post-P0 |

