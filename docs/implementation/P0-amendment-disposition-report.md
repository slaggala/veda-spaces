# P0 amendment disposition report

Owner decisions recorded on 2026-09-30. Canonical: [P0-owner-decision-record.md](P0-owner-decision-record.md).

| Disposition | Amendments |
|---|---|
| APPROVED | AM-1, AM-3, AM-8 |
| APPROVED WITH CONDITIONS | AM-2, AM-4, AM-5, AM-6, AM-7, AM-11, AM-12, AM-13 |
| DEFERRED TO STAGING / PRODUCTION | AM-9, AM-10 |
| NOT DECIDED | None |

| ID | Amends | Owner decision | Conditions | Staging dependency | Production dependency |
|---|---|---|---|---|---|
| AM-1 | 03 §5.5 | **APPROVED** | None | Migration upgrade-with-data on SQLite, PostgreSQL 16 and 18 (CI and local evidence); no staging host run yet. | Not applicable beyond the release gates. |
| AM-2 | 08 §4.5, 05 §11.3 | **APPROVED WITH CONDITIONS** | Accept the invite-link residual (link holder sets the password before activation). (the owner stated no different conditions; the conditions of the decision package apply) | None. | Invitation email delivery through SES in staging before production. |
| AM-3 | 08 §4.1, §4.7 | **APPROVED** | None | Real Turnstile keys in staging (IR-18) before production. | Turnstile production secret provisioned. |
| AM-4 | 04 §5.4 vs 08 §8.5; LEAD-027 | **APPROVED WITH CONDITIONS** | For merge: the labelled gaps are accepted — the current code (any different version accepted; no create-time note; no withdrawal note in the snapshot; application-level protection only) is a tracked deviation from the approved text. Before production: RR-12 implements rules (a)–(d), including the choice of option (a) or (b) for (d). (the owner stated no different conditions; the conditions of the decision package apply) | None required. | RR-12 implemented with tests for (a)–(c) on both engines; Data Protection lead sign-off of option (a) or (b). |
| AM-5 | 08 §1, 06 §11 (RBX-003), 06 §7.5, 09 | **APPROVED WITH CONDITIONS** | Outbox retention ≥ break-glass window enforced or operationally controlled before production (IR-A10). (the owner stated no different conditions; the conditions of the decision package apply) | Staging check that outbox retention ≥ break-glass window (IR-A10). | Retention configuration evidence. |
| AM-6 | LOG-005, 08 §3, 02 §12.4 | **APPROVED WITH CONDITIONS** | RG-7 rollback rehearsal before production. (the owner stated no different conditions; the conditions of the decision package apply) | RG-7 rollback rehearsal (not performed). | RG-7 evidence. |
| AM-7 | 08 §12, 05 §4 | **APPROVED WITH CONDITIONS** | Accept the disclosed disruption bounds (FC-05 reset-link gap, escalation during a Turnstile outage); staging Turnstile, proxy and alarm evidence. (the owner stated no different conditions; the conditions of the decision package apply) | Real Turnstile keys (success, failure, outage simulated by a blocked siteverify); deployed trusted-proxy CIDR; load probe of the thresholds; alarm on ACCOUNT_THROTTLED account_* and aggregate escalation. | Alarms configured and test-fired (RG-5); owner acceptance of the disclosed disruption bounds. |
| AM-8 | 05 / 03 | **APPROVED** | None | None. | Key provisioning evidence. |
| AM-9 | 06 §7.5 | **DEFERRED TO STAGING / PRODUCTION** | Decision deferred to staging/production. Decide before production; recommended option R (target cannot cancel custodian recovery). | Staging-required: custodian identity rehearsal with two principals and CloudTrail (RR-09, PG-BG), including a cancellation by a notified Founder; if R is chosen, a refused cancellation by the target. | Production-required: custodians named (OWNER-INPUT-004), PG-BG passed, the chosen option implemented and tested. |
| AM-10 | 07 §2, 04 §14 | **DEFERRED TO STAGING / PRODUCTION** | Decision deferred to staging/production. Decide before production with the Data Protection lead; RR-13. | Staging-required: an erasure run on a staging copy showing every listed field rewritten; a provider-error outbox row showing last_error redacted; a Sentry test project receiving a transaction without query strings or addresses. | Production-required: implementation with tests on both engines, the staging evidence above, Data Protection lead sign-off, and the erasure-audit job (erasure-audit) reporting 0 residual fields. |
| AM-11 | 03 §5.7 (mfa_challenge), 05 §11.3, 05 §6.1, 02 §8.3 | **APPROVED WITH CONDITIONS** | RG-7 before production. (the owner stated no different conditions; the conditions of the decision package apply) | Migration on the staging copy; RG-7 rehearsal (not performed). | RG-7 evidence. |
| AM-12 | 06 §7.2.2, 06 §7.1 (G11), 08 §5.11 | **APPROVED WITH CONDITIONS** | Decide whether reactivation after restore requires credential and MFA resets (FC-A12). (the owner stated no different conditions; the conditions of the decision package apply) | None. | None beyond the release gates. |
| AM-13 | 06 §7.4, 05 §8.6 | **APPROVED WITH CONDITIONS** | Accept 'blocked, not withdrawn' for role-definition changes (FC-08) and the FC-A09 residual, or require withdrawal. (the owner stated no different conditions; the conditions of the decision package apply) | None. | None beyond the release gates. |

The deviation register shows the matching status for each deviation (DEV-001…DEV-010). DEV-004 follows AM-4 and is approved with conditions as a tracked deviation until RR-12 lands.
