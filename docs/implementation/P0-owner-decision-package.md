# P0 owner decision package

> **Owner decisions were recorded on 2026-09-30.** See [P0-owner-decision-record.md](P0-owner-decision-record.md), the canonical record.
> - OD-2 and OD-3 are APPROVED.
> - TG-01 and TG-08 are APPROVED; the owner waived the decision-log and PR evidence for merge readiness (the certified registry is unchanged).
> - Merge-safety option C is APPROVED but not executed.
> - Production deployment approval is PENDING.
> - **AM-4 is APPROVED WITH CONDITIONS** (labelled gaps accepted for merge; RR-12 before production).

## References

| Item | Value |
|---|---|
| Recorded at head | `ca9845c0dd60280fd19cdc9d41843d8567191801` |
| Implementation logic | `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41` |
| Technical conditions | `3f5920b17d21214b39414d080d34246746c8c40d` |
| Final targeted check | review/p0-independent-implementation-review @ 56c20ba992b519daa79aa3802a28343aab8c0b41 (CERTIFIED WITH TECHNICAL CONDITIONS) |
| Document-level check | review/p0-independent-implementation-review @ 093cfa6872c209deb9991910c457afcdb4ad2d04 (READY WITH DOCUMENT CONDITIONS) |
| SHA correction (FC-A01) | `6ec2e76f156e963c7363c4ad9ce93d0bc0b11f41` does not exist; the implementation commit is `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`. |

## Amendments

| ID | Final targeted check (verbatim) | Document-level check (verbatim) | Author proposal | Owner decision | Conditions |
|---|---|---|---|---|---|
| [AM-1](../proposals/amendments/AM-1.md) | TECHNICALLY SOUND | TECHNICALLY SOUND | APPROVE | **APPROVED** | None |
| [AM-2](../proposals/amendments/AM-2.md) | TECHNICALLY SOUND WITH OWNER CONDITIONS (accept invite-link password-overwrite residual) | TECHNICALLY SOUND WITH OWNER CONDITIONS | APPROVE WITH CONDITIONS | **APPROVED WITH CONDITIONS** | Accept the invite-link residual (link holder sets the password before activation). (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-3](../proposals/amendments/AM-3.md) | TECHNICALLY SOUND | TECHNICALLY SOUND | APPROVE WITH CONDITIONS | **APPROVED** | None |
| [AM-4](../proposals/amendments/AM-4.md) | INCOMPLETE (gaps honestly labelled: later-version rule, create-time consent, immutability) | INCOMPLETE — states 422 where code/tests return 409; 'later version' has no ordering rule; the immutability option conflicts with erasure rewriting consent notes (DC-02) | APPROVE WITH CONDITIONS | **APPROVED WITH CONDITIONS** | For merge: the labelled gaps are accepted — the current code (any different version accepted; no create-time note; no withdrawal note in the snapshot; application-level protection only) is a tracked deviation from the approved text. Before production: RR-12 implements rules (a)–(d), including the choice of option (a) or (b) for (d). (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-5](../proposals/amendments/AM-5.md) | TECHNICALLY SOUND WITH OWNER CONDITIONS (outbox retention bound not enforced) | TECHNICALLY SOUND WITH OWNER CONDITIONS | APPROVE WITH CONDITIONS | **APPROVED WITH CONDITIONS** | Outbox retention ≥ break-glass window enforced or operationally controlled before production (IR-A10). (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-6](../proposals/amendments/AM-6.md) | TECHNICALLY SOUND WITH OWNER CONDITIONS (resolve FC-12 release floor) | TECHNICALLY SOUND WITH OWNER CONDITIONS | APPROVE WITH CONDITIONS | **APPROVED WITH CONDITIONS** | RG-7 rollback rehearsal before production. (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-7](../proposals/amendments/AM-7.md) | INCOMPLETE (FC-05 reset-link disclosure; FC-A06 outage bound) | TECHNICALLY SOUND WITH OWNER CONDITIONS — upgraded from INCOMPLETE: every claim verified against kernel/ratelimit.py, auth/throttle.py, auth/service.py; discloses reset-link suppression and that a Turnstile outage is fail-closed with unbounded availability impact under attack; makes none of the forbidden claims | APPROVE WITH CONDITIONS | **APPROVED WITH CONDITIONS** | Accept the disclosed disruption bounds (FC-05 reset-link gap, escalation during a Turnstile outage); staging Turnstile, proxy and alarm evidence. (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-8](../proposals/amendments/AM-8.md) | TECHNICALLY SOUND | TECHNICALLY SOUND | APPROVE | **APPROVED** | None |
| [AM-9](../proposals/amendments/AM-9.md) | INCOMPLETE (no decision; not implemented) | INCOMPLETE — owner decision not yet taken; repository/staging/production/provider/owner evidence are separated, but the policy itself is undecided | DEFER | **DEFERRED TO STAGING / PRODUCTION** | Decision deferred to staging/production. Decide before production; recommended option R (target cannot cancel custodian recovery). |
| [AM-10](../proposals/amendments/AM-10.md) | INCOMPLETE (honestly labelled) | INCOMPLETE — omits PII entering outbox_event.last_error from SQL and handler exception text (DC-03) | DEFER | **DEFERRED TO STAGING / PRODUCTION** | Decision deferred to staging/production. Decide before production with the Data Protection lead; RR-13. |
| [AM-11](../proposals/amendments/AM-11.md) | TECHNICALLY SOUND WITH OWNER CONDITIONS (refresh rule wording FC-A08; N-1 wording FC-12) | TECHNICALLY SOUND WITH OWNER CONDITIONS | APPROVE WITH CONDITIONS | **APPROVED WITH CONDITIONS** | RG-7 before production. (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-12](../proposals/amendments/AM-12.md) | TECHNICALLY SOUND WITH OWNER CONDITIONS (FC-A10, FC-A12 wording) | TECHNICALLY SOUND WITH OWNER CONDITIONS | APPROVE WITH CONDITIONS | **APPROVED WITH CONDITIONS** | Decide whether reactivation after restore requires credential and MFA resets (FC-A12). (the owner stated no different conditions; the conditions of the decision package apply) |
| [AM-13](../proposals/amendments/AM-13.md) | TECHNICALLY SOUND WITH OWNER CONDITIONS (correct withdrawal over-claim FC-08, FC-A09) | TECHNICALLY SOUND WITH OWNER CONDITIONS | APPROVE WITH CONDITIONS | **APPROVED WITH CONDITIONS** | Accept 'blocked, not withdrawn' for role-definition changes (FC-08) and the FC-A09 residual, or require withdrawal. (the owner stated no different conditions; the conditions of the decision package apply) |

## Owner decisions

- **OD-2**: Founder restoration requires two distinct eligible human principals. APPROVED by the owner on 2026-09-30 (decision record).
- **OD-3**: Sensitive operations revalidate the current governance class at execution. APPROVED by the owner on 2026-09-30 (decision record).

## Gates and approvals

| Item | Status |
|---|---|
| TG-01 | **APPROVED** (registry evidence entry waived by the owner for merge readiness) |
| TG-08 | **APPROVED** (registry evidence entry waived by the owner for merge readiness) |
| Merge-safety decision | **APPROVED — Option C (not executed)** |
| Production deployment approval | **PENDING** |
