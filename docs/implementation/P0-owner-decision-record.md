# P0 owner decision record

- **Date:** 2026-09-30
- **Source:** Owner instruction VEDA-SPACES-P0-CONSOLIDATED-OWNER-DECISION, recorded by the author on the owner's behalf. Decisions are recorded as stated; nothing is inferred.
- **Recorded at head:** `ca9845c0dd60280fd19cdc9d41843d8567191801` (implementation logic at `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`; technical conditions at `3f5920b17d21214b39414d080d34246746c8c40d`).

## Owner decisions

| ID | Decision | Text |
|---|---|---|
| OD-2 | **APPROVED** | Founder restoration requires two distinct eligible human principals. Requester cannot approve. Target cannot approve. One person cannot approve twice. |
| OD-3 | **APPROVED** | Sensitive operations must revalidate governance class at execution time. Prior approval under a weaker governance class must not execute after promotion into a stronger governance class. |

## Gates

| Gate | Decision | Text | Registry evidence |
|---|---|---|---|
| TG-01 | **APPROVED** | Certified architecture accepted. | Outstanding (owner action) |
| TG-08 | **APPROVED** | Certified implementation accepted. | Outstanding (owner action) |

> The gate registry (docs/architecture/gate-registry.json) names docs/architecture/decisions/decision-log.md as the evidence location and, for TG-01, requires approval from the owner's own account. Both files are in the certified tree, which this workstream was instructed not to change. The certified registry therefore still reads 'Pending'; this record is the owner decision, and the registry evidence entry remains an owner action.

## Amendments

| Amendment | Decision | Conditions |
|---|---|---|
| [AM-1](../proposals/amendments/AM-1.md) | **APPROVED** | None |
| [AM-2](../proposals/amendments/AM-2.md) | **APPROVED WITH CONDITIONS** | Accept the invite-link residual (link holder sets the password before activation). (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-3](../proposals/amendments/AM-3.md) | **APPROVED** | None |
| [AM-4](../proposals/amendments/AM-4.md) | **NOT DECIDED — not included in the consolidated owner decision** | Owner decision still required. For merge: accept the labelled gaps — approval makes the current code (any different version accepted; no create-time note; no withdrawal note in the snapshot; application-level protection only) a tracked deviation from the approved text. Before production: RR-12 implements rules (a)–(d). |
| [AM-5](../proposals/amendments/AM-5.md) | **APPROVED WITH CONDITIONS** | Outbox retention ≥ break-glass window enforced or operationally controlled before production (IR-A10). (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-6](../proposals/amendments/AM-6.md) | **APPROVED WITH CONDITIONS** | RG-7 rollback rehearsal before production. (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-7](../proposals/amendments/AM-7.md) | **APPROVED WITH CONDITIONS** | Accept the disclosed disruption bounds (FC-05 reset-link gap, escalation during a Turnstile outage); staging Turnstile, proxy and alarm evidence. (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-8](../proposals/amendments/AM-8.md) | **APPROVED** | None |
| [AM-9](../proposals/amendments/AM-9.md) | **DEFERRED TO STAGING / PRODUCTION** | Decision deferred to staging/production. Decide before production; recommended option R (target cannot cancel custodian recovery). |
| [AM-10](../proposals/amendments/AM-10.md) | **DEFERRED TO STAGING / PRODUCTION** | Decision deferred to staging/production. Decide before production with the Data Protection lead; RR-13. |
| [AM-11](../proposals/amendments/AM-11.md) | **APPROVED WITH CONDITIONS** | RG-7 before production. (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-12](../proposals/amendments/AM-12.md) | **APPROVED WITH CONDITIONS** | Decide whether reactivation after restore requires credential and MFA resets (FC-A12). (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-13](../proposals/amendments/AM-13.md) | **APPROVED WITH CONDITIONS** | Accept 'blocked, not withdrawn' for role-definition changes (FC-08) and the FC-A09 residual, or require withdrawal. (the owner stated no different conditions; the conditions of the decision package apply) |

## Merge safety

**APPROVED — Option C.** Do not execute. Record only. The plan is not executed.

## Not decided

- **AM-4.** The consolidated decision does not mention it. It stays PROPOSED, NOT APPROVED. The final targeted check lists an AM-4 decision, or explicit owner acceptance of its labelled gaps, as required before merge.

## Unchanged

- Nothing has been merged or deployed.
- Public lead intake is disabled.
- The certified architecture (`docs/architecture/`) is unchanged.
