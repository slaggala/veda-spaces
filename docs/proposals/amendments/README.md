# Architecture amendments

> Owner decisions recorded on 2026-09-30: see [the decision record](../../implementation/P0-owner-decision-record.md). The certified documents in `docs/architecture/` are unchanged; approved amendments take effect alongside them. AM-4 is approved with conditions.

| ID | Amends | Owner decision | Conditions |
|---|---|---|---|
| [AM-1](AM-1.md) | 03 §5.5 | **APPROVED** | None |
| [AM-2](AM-2.md) | 08 §4.5, 05 §11.3 | **APPROVED WITH CONDITIONS** | Accept the invite-link residual (link holder sets the password before activation). (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-3](AM-3.md) | 08 §4.1, §4.7 | **APPROVED** | None |
| [AM-4](AM-4.md) | 04 §5.4 vs 08 §8.5; LEAD-027 | **APPROVED WITH CONDITIONS** | For merge: the labelled gaps are accepted — the current code (any different version accepted; no create-time note; no withdrawal note in the snapshot; application-level protection only) is a tracked deviation from the approved text. Before production: RR-12 implements rules (a)–(d), including the choice of option (a) or (b) for (d). (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-5](AM-5.md) | 08 §1, 06 §11 (RBX-003), 06 §7.5, 09 | **APPROVED WITH CONDITIONS** | Outbox retention ≥ break-glass window enforced or operationally controlled before production (IR-A10). (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-6](AM-6.md) | LOG-005, 08 §3, 02 §12.4 | **APPROVED WITH CONDITIONS** | RG-7 rollback rehearsal before production. (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-7](AM-7.md) | 08 §12, 05 §4 | **APPROVED WITH CONDITIONS** | Accept the disclosed disruption bounds (FC-05 reset-link gap, escalation during a Turnstile outage); staging Turnstile, proxy and alarm evidence. (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-8](AM-8.md) | 05 / 03 | **APPROVED** | None |
| [AM-9](AM-9.md) | 06 §7.5 | **DEFERRED TO STAGING / PRODUCTION** | Decision deferred to staging/production. Decide before production; recommended option R (target cannot cancel custodian recovery). |
| [AM-10](AM-10.md) | 07 §2, 04 §14 | **DEFERRED TO STAGING / PRODUCTION** | Decision deferred to staging/production. Decide before production with the Data Protection lead; RR-13. |
| [AM-11](AM-11.md) | 03 §5.7 (mfa_challenge), 05 §11.3, 05 §6.1, 02 §8.3 | **APPROVED WITH CONDITIONS** | RG-7 before production. (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-12](AM-12.md) | 06 §7.2.2, 06 §7.1 (G11), 08 §5.11 | **APPROVED WITH CONDITIONS** | Decide whether reactivation after restore requires credential and MFA resets (FC-A12). (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-13](AM-13.md) | 06 §7.4, 05 §8.6 | **APPROVED WITH CONDITIONS** | Accept 'blocked, not withdrawn' for role-definition changes (FC-08) and the FC-A09 residual, or require withdrawal. (the owner stated no different conditions; the conditions of the decision package apply) |
