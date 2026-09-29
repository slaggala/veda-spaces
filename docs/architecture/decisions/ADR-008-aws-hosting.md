# ADR-008: AWS hosting for the backend MVP

- **Status:** Accepted (amended by remediation 01)
- **Date:** 2026-09-29

## Context

The marketing site runs on Cloudflare Pages. The backend needs independent hosting. SQLite imposes a single-writer, local-disk constraint that rules out stateless, horizontally scaled container platforms until PostgreSQL is adopted.

## Decision

- The **backend MVP runs on AWS**. The website stays on **Cloudflare Pages**, and the internal app is also a Cloudflare Pages project.
- SQLite requires a **single active writer and application instance** (OPS-006). No horizontal backend scaling is claimed while SQLite is authoritative.
- SQLite lives on **persistent encrypted storage**: a dedicated KMS-encrypted EBS volume. It is **never only in an ephemeral container layer** (OPS-007).
- **Automated backups** are mandatory: Litestream to S3 and nightly snapshots. So is **automated restoration verification** (OPS-002, OPS-009).
- **Secrets** live in SSM Parameter Store, Secrets Manager or KMS, and never in Git (PLAT-008, SEC-005).
- **Health, readiness, structured logging, metrics and alerting** are mandatory in P0 (LOG-001…006).
- **RPO and RTO** are owner-approved values. They are not invented by this architecture. Mechanisms are provided and measured in rehearsal (OPS-005, OWNER-INPUT-001).
- **Region (owner Decision 5):** the initial backend region is **ap-south-1 (Mumbai)**.
  - The region is a configuration parameter, not hard-coded, and resource ARNs come from configuration.
  - **No infrastructure is provisioned during architecture remediation.**
  - **No multi-region availability is claimed for P0.** Cross-region S3 replication of backups, if enabled, is for durability only. Restoring in another region is a manual rebuild whose duration is not claimed (02 §12.3).
- **Single application process** (OPS-010, F-09): one gunicorn `gthread` worker process, so in-process limiters and caches are authoritative.
- **PostgreSQL migration is a release gate** before procurement, inventory, finance or multi-instance scale goes live (OPS-008).

## Alternatives considered

| Option | Why rejected |
|---|---|
| ECS Fargate or App Runner now | No durable local disk. SQLite on EFS is unsafe. Viable after the gate. |
| Lambda | Same as above |
| PostgreSQL from day one | Stronger, but the owner chose a controlled SQLite MVP with mandatory readiness |
| Non-AWS host | The owner chose AWS |

## Consequences

- Brief restart windows on deploy (no zero-downtime claim).
- Single point of failure accepted for the MVP, with rehearsed recovery.
- The region ap-south-1 (Mumbai) is approved (owner Decision 5). ASM-012 is resolved.
- The production release gates (11 §7) include RG-1 … RG-9 from the independent review.

## Risks

| Risk | Mitigation |
|---|---|
| Business pressure to add modules before the gate | The gate is written into this ADR and ADR-009 |
| Unapproved RPO/RTO at go-live | Go-live checklist item (11 §8) |

## Affected requirement IDs

PLAT-003, PLAT-008, OPS-002, OPS-003, OPS-004, OPS-005, OPS-006, OPS-007, OPS-008, OPS-009, LOG-001, LOG-004, LOG-005, LOG-006, SEC-001, SEC-005, SEC-006, SEC-008, NFR-002

## Affected documents

02 (§1, §8.1, §9, §11.4, §12), 10 (§3.2, §5), 11 (§1, §2, §3, §7, §10), 12 (§4.9)

## Future review triggers

- Any of the PostgreSQL gate conditions
- Sustained `SQLITE_BUSY` or latency breaches
- Owner-approved RPO/RTO that the design can't meet

## Approval record

| Item | Value |
|---|---|
| Approver | Veda Spaces owner (repository owner) |
| Approval | 2026-09-29, `VEDA-SPACES-P0-ARCHITECTURE-SIGNOFF-AND-FREEZE`, decision ADR-008; amended by `VEDA-SPACES-P0-ARCHITECTURE-REMEDIATION-01` Decisions 5 and 6 (ASM-012, OWNER-INPUT-001…004) |
| Evidence | [decision-log.md](decision-log.md). A verifiable owner sign-off (owner approval of the architecture pull request) is tracked gate TG-01 before implementation (F-18). |
