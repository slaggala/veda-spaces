# P0 owner decision package

> **Nothing in this package is decided, and nothing in it implies a decision.**
> - The dispositions are the author's proposals for the owner to accept, change or reject.
> - Every amendment is **PROPOSED, NOT APPROVED**.
> - OD-2 and OD-3 are brief instructions that **await formal owner confirmation**.
> - TG-01, TG-08, the merge-safety decision and production deployment approval are all **PENDING**.

## References

| Item | Value |
|---|---|
| Reviewed tree (document-level check target) | `3f5920b17d21214b39414d080d34246746c8c40d` |
| Implementation provenance | The merge-blocker fixes (RR items) were committed at `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`. `3f5920b` added the FC-02, FC-04, FC-06, FC-11 and FC-12 code changes. The document-conditions commit changes only documents, tests and CI checkout depth. |
| Final targeted check | review/p0-independent-implementation-review @ 56c20ba992b519daa79aa3802a28343aab8c0b41. Verdict: **CERTIFIED WITH TECHNICAL CONDITIONS**. It authorizes no merge or deployment. |
| Document-level check | review/p0-independent-implementation-review @ 093cfa6872c209deb9991910c457afcdb4ad2d04. Verdict: **READY WITH DOCUMENT CONDITIONS**. It authorizes no merge or deployment. |
| SHA correction (FC-A01) | The brief quoted `6ec2e76f156e963c7363c4ad9ce93d0bc0b11f41`, which does not exist. The implementation commit is `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`. |
| This document-conditions commit | Its SHA is reported in the final report and CI. A commit cannot contain its own hash. |

## Amendments

Classifications are quoted verbatim from each reviewer.

| ID | Amends | Final targeted check (verbatim) | Document-level check (verbatim) | Decision before | Author-proposed disposition |
|---|---|---|---|---|---|
| [AM-1](../proposals/amendments/AM-1.md) | 03 §5.5 | TECHNICALLY SOUND | TECHNICALLY SOUND | Merge | APPROVE |
| [AM-2](../proposals/amendments/AM-2.md) | 08 §4.5, 05 §11.3 | TECHNICALLY SOUND WITH OWNER CONDITIONS (accept invite-link password-overwrite residual) | TECHNICALLY SOUND WITH OWNER CONDITIONS | Merge | APPROVE WITH CONDITIONS |
| [AM-3](../proposals/amendments/AM-3.md) | 08 §4.1, §4.7 | TECHNICALLY SOUND | TECHNICALLY SOUND | Merge | APPROVE WITH CONDITIONS |
| [AM-4](../proposals/amendments/AM-4.md) | 04 §5.4 vs 08 §8.5; LEAD-027 | INCOMPLETE (gaps honestly labelled: later-version rule, create-time consent, immutability) | INCOMPLETE — states 422 where code/tests return 409; 'later version' has no ordering rule; the immutability option conflicts with erasure rewriting consent notes (DC-02) | Merge (owner may accept labelled gaps) / completion before production | APPROVE WITH CONDITIONS |
| [AM-5](../proposals/amendments/AM-5.md) | 08 §1, 06 §11 (RBX-003), 06 §7.5, 09 | TECHNICALLY SOUND WITH OWNER CONDITIONS (outbox retention bound not enforced) | TECHNICALLY SOUND WITH OWNER CONDITIONS | Merge; retention enforcement before production | APPROVE WITH CONDITIONS |
| [AM-6](../proposals/amendments/AM-6.md) | LOG-005, 08 §3, 02 §12.4 | TECHNICALLY SOUND WITH OWNER CONDITIONS (resolve FC-12 release floor) | TECHNICALLY SOUND WITH OWNER CONDITIONS | Merge | APPROVE WITH CONDITIONS |
| [AM-7](../proposals/amendments/AM-7.md) | 08 §12, 05 §4 | INCOMPLETE (FC-05 reset-link disclosure; FC-A06 outage bound) | TECHNICALLY SOUND WITH OWNER CONDITIONS — upgraded from INCOMPLETE: every claim verified against kernel/ratelimit.py, auth/throttle.py, auth/service.py; discloses reset-link suppression and that a Turnstile outage is fail-closed with unbounded availability impact under attack; makes none of the forbidden claims | Merge — correct text before approval; real-Turnstile staging evidence | APPROVE WITH CONDITIONS |
| [AM-8](../proposals/amendments/AM-8.md) | 05 / 03 | TECHNICALLY SOUND | TECHNICALLY SOUND | Production | APPROVE |
| [AM-9](../proposals/amendments/AM-9.md) | 06 §7.5 | INCOMPLETE (no decision; not implemented) | INCOMPLETE — owner decision not yet taken; repository/staging/production/provider/owner evidence are separated, but the policy itself is undecided | Production | DEFER |
| [AM-10](../proposals/amendments/AM-10.md) | 07 §2, 04 §14 | INCOMPLETE (honestly labelled) | INCOMPLETE — omits PII entering outbox_event.last_error from SQL and handler exception text (DC-03) | Production | DEFER |
| [AM-11](../proposals/amendments/AM-11.md) | 03 §5.7 (mfa_challenge), 05 §11.3, 05 §6.1, 02 §8.3 | TECHNICALLY SOUND WITH OWNER CONDITIONS (refresh rule wording FC-A08; N-1 wording FC-12) | TECHNICALLY SOUND WITH OWNER CONDITIONS | Merge; RG-7 before production | APPROVE WITH CONDITIONS |
| [AM-12](../proposals/amendments/AM-12.md) | 06 §7.2.2, 06 §7.1 (G11), 08 §5.11 | TECHNICALLY SOUND WITH OWNER CONDITIONS (FC-A10, FC-A12 wording) | TECHNICALLY SOUND WITH OWNER CONDITIONS | Merge | APPROVE WITH CONDITIONS |
| [AM-13](../proposals/amendments/AM-13.md) | 06 §7.4, 05 §8.6 | TECHNICALLY SOUND WITH OWNER CONDITIONS (correct withdrawal over-claim FC-08, FC-A09) | TECHNICALLY SOUND WITH OWNER CONDITIONS | Merge | APPROVE WITH CONDITIONS |

### AM-1

| Field | Value |
|---|---|
| Owner decision required | Approve the three-column key (OD-1). |
| Implementation behavior (provenance) | Implemented in migration 0004_auth and mfa.py exactly as proposed; unchanged by this workstream. |
| Risks | None identified. |
| Conditions | None. |
| Staging dependency | Migration upgrade-with-data on SQLite, PostgreSQL 16 and 18 (CI and local evidence); no staging host run yet. |
| Production dependency | Not applicable beyond the release gates. |
| Author recommendation | Matches the implementation; removes a certified contradiction. |
| Author-proposed disposition | APPROVE |
| Owner decision recorded | NONE |
| Status | PROPOSED, NOT APPROVED |

### AM-2

| Field | Value |
|---|---|
| Owner decision required | Approve the response shape and accept the stated link-possession residual, or require an additional proof before activation. |
| Implementation behavior (provenance) | Implemented as proposed (service.accept_invite, mfa.enroll_start/confirm with PATH_B binding). Replay behaviour described above is the current code: api/veda/platform/auth/service.py accept_invite accepts the live INVITE token again while the user is INVITED. |
| Risks | Invitation-link possession sets the password before activation. |
| Conditions | Accept the invite-link residual (link holder sets the password before activation). |
| Staging dependency | None. |
| Production dependency | Invitation email delivery through SES in staging before production. |
| Author recommendation | The certified 204 cannot express path B. |
| Author-proposed disposition | APPROVE WITH CONDITIONS |
| Owner decision recorded | NONE |
| Status | PROPOSED, NOT APPROVED |

### AM-3

| Field | Value |
|---|---|
| Owner decision required | Approve. |
| Implementation behavior (provenance) | Implemented as proposed. |
| Risks | None beyond Turnstile availability (AM-7). |
| Conditions | Real Turnstile keys verified in staging (IR-18). |
| Staging dependency | Real Turnstile keys in staging (IR-18) before production. |
| Production dependency | Turnstile production secret provisioned. |
| Author recommendation | Implements the certified 05 §4 control. |
| Author-proposed disposition | APPROVE WITH CONDITIONS |
| Owner decision recorded | NONE |
| Status | PROPOSED, NOT APPROVED |

### AM-4

| Field | Value |
|---|---|
| Owner decision required | Accept the labelled gaps for merge (approval then records the current code as a tracked deviation), approve the ordering rule (a), the create-time rule (b), the withdrawal-note rule (c), and choose option (a) or (b) for (d) with the erasure exemption. |
| Implementation behavior (provenance) | Implemented at 6ec2e76 (unchanged at 3f5920b): the consent object on PATCH; the three accepted cases with 'different version' semantics; 409 INVALID_STATE otherwise and 422 for an unknown version; note required on re-consent; superseded evidence in a system activity (without the withdrawal note) and in audit_log; application-level read-only activity. NOT implemented (RR-12, production blocker): target rules (a) ordering, (b) create-time note and activity, (c) withdrawal note in the snapshot, (d) database-level protection. Approving this amendment would make the current code a tracked deviation from the approved text until RR-12 lands. |
| Risks | Consent evidence churn between published versions until RR-12. |
| Conditions | For merge: accept the labelled gaps — approval makes the current code (any different version accepted; no create-time note; no withdrawal note in the snapshot; application-level protection only) a tracked deviation from the approved text. Before production: RR-12 implements rules (a)–(d). |
| Staging dependency | None required. |
| Production dependency | RR-12 implemented with tests for (a)–(c) on both engines; Data Protection lead sign-off of option (a) or (b). |
| Author recommendation | Resolves the certified 04/08 conflict; completion is tracked. |
| Author-proposed disposition | APPROVE WITH CONDITIONS |
| Owner decision recorded | NONE |
| Status | PROPOSED, NOT APPROVED |

### AM-5

| Field | Value |
|---|---|
| Owner decision required | Approve the endpoint, the veto semantics and the retention condition. |
| Implementation behavior (provenance) | Endpoint, page, token binding and events implemented; OpenAPI now documents 204 (RR-A09 fixed). The outbox retention condition is not enforced by code (IR-A10, staging gate). |
| Risks | A link may fail to bind if outbox rows are purged before the window ends. |
| Conditions | Outbox retention ≥ break-glass window enforced or operationally controlled before production (IR-A10). |
| Staging dependency | Staging check that outbox retention ≥ break-glass window (IR-A10). |
| Production dependency | Retention configuration evidence. |
| Author recommendation | Makes the certified veto usable. |
| Author-proposed disposition | APPROVE WITH CONDITIONS |
| Owner decision recorded | NONE |
| Status | PROPOSED, NOT APPROVED |

### AM-6

| Field | Value |
|---|---|
| Owner decision required | Approve the readiness states, the rollback floor mechanism and the statement that this release rolls back only by forward fix or snapshot restore (OD-1). |
| Implementation behavior (provenance) | Readiness states implemented (health.py). deploy.sh reads revision, release and readiness inside the target image's container; RELEASE_FLOOR=3 and ROLLBACK_FLOOR=0009_mfa_challenge_binding are enforced in every mode (FC-12); images too old to report (9236aa3, 2f6b59a) are refused. The release floor (FC-12) was added at 3f5920b. |
| Risks | Rollback unrehearsed (RG-7). |
| Conditions | RG-7 rollback rehearsal before production. |
| Staging dependency | RG-7 rollback rehearsal (not performed). |
| Production dependency | RG-7 evidence. |
| Author recommendation | Release and schema floors now enforced in every deploy mode (FC-12). |
| Author-proposed disposition | APPROVE WITH CONDITIONS |
| Owner decision recorded | NONE |
| Status | PROPOSED, NOT APPROVED |

### AM-7

| Field | Value |
|---|---|
| Owner decision required | Approve the layered design and thresholds, accept the disclosed victim-disruption and outage behaviour, or require changes (for example per-requester-network reset caps or a victim-initiated bypass, FC-05). |
| Implementation behavior (provenance) | Implemented at 6ec2e76 (unchanged at 3f5920b): api/veda/platform/auth/throttle.py (account budget, aggregate, reset cap, bounded tables), api/veda/kernel/ratelimit.py (wide-network and hashed identifier keys), api/veda/platform/auth/service.py (login and forgot), api/veda/platform/auth/routes.py (endpoint limits), api/veda/config.py (trusted-proxy prefix bound). |
| Risks | Victim reset-link gap (~half of each hour under attack); escalated identifiers cannot sign in during a Turnstile outage while attacked; slow guessing by a challenge-solving attacker. |
| Conditions | Accept the disclosed disruption bounds (FC-05 reset-link gap, escalation during a Turnstile outage); staging Turnstile, proxy and alarm evidence. |
| Staging dependency | Real Turnstile keys (success, failure, outage simulated by a blocked siteverify); deployed trusted-proxy CIDR; load probe of the thresholds; alarm on ACCOUNT_THROTTLED account_* and aggregate escalation. |
| Production dependency | Alarms configured and test-fired (RG-5); owner acceptance of the disclosed disruption bounds. |
| Author recommendation | Replaces the rejected text; restores a cross-network bound for all accounts. |
| Author-proposed disposition | APPROVE WITH CONDITIONS |
| Owner decision recorded | NONE |
| Status | PROPOSED, NOT APPROVED |

### AM-8

| Field | Value |
|---|---|
| Owner decision required | Accept the documented trade-off. |
| Implementation behavior (provenance) | As described. |
| Risks | K_action compromise plus row ids yields live links. |
| Conditions | Key provisioning evidence before production. |
| Staging dependency | None. |
| Production dependency | Key provisioning evidence. |
| Author recommendation | Documentation of an implemented trade-off. |
| Author-proposed disposition | APPROVE |
| Owner decision recorded | NONE |
| Status | PROPOSED, NOT APPROVED |

### AM-9

| Field | Value |
|---|---|
| Owner decision required | Choose R, (a) or (b), and accept the IR-05 residual. |
| Implementation behavior (provenance) | Repository-tested behaviour today: every notified party, including the target, can cancel through the link (test_founder_governance.py::test_G12_cancel_link_by_notified_party); custodian requests are refused while a Founder is eligible (test_governance_remediation.py::test_IR05_*). Option R is NOT implemented. |
| Risks | Hostile target can block custodial recovery until decided. |
| Conditions | Decide before production; recommended option R (target cannot cancel custodian recovery). |
| Staging dependency | Staging-required: custodian identity rehearsal with two principals and CloudTrail (RR-09, PG-BG), including a cancellation by a notified Founder; if R is chosen, a refused cancellation by the target. |
| Production dependency | Production-required: custodians named (OWNER-INPUT-004), PG-BG passed, the chosen option implemented and tested. |
| Author recommendation | Not implemented; no merge dependency. |
| Author-proposed disposition | DEFER |
| Owner decision recorded | NONE |
| Status | PROPOSED, NOT APPROVED |

### AM-10

| Field | Value |
|---|---|
| Owner decision required | Choose the field list and the IP/user-agent retention option. |
| Implementation behavior (provenance) | Repository today: the certified pii_fields only; outbox_event.last_error is not redacted; Sentry transactions carry query strings (RR-13). No real infrastructure has been tested. |
| Risks | PII survives erasure in listed fields until decided. |
| Conditions | Decide before production with the Data Protection lead; RR-13. |
| Staging dependency | Staging-required: an erasure run on a staging copy showing every listed field rewritten; a provider-error outbox row showing last_error redacted; a Sentry test project receiving a transaction without query strings or addresses. |
| Production dependency | Production-required: implementation with tests on both engines, the staging evidence above, Data Protection lead sign-off, and the erasure-audit job (erasure-audit) reporting 0 residual fields. |
| Author recommendation | Not implemented; no merge dependency. |
| Author-proposed disposition | DEFER |
| Owner decision recorded | NONE |
| Status | PROPOSED, NOT APPROVED |

### AM-11

| Field | Value |
|---|---|
| Owner decision required | Approve the columns, binding and refresh rules, the 02 §8.3 placement rule and the rollback floor (OD-1). |
| Implementation behavior (provenance) | Implemented; refresh successor linking added at 6ec2e76 (unchanged at 3f5920b) (auth.service.rotate_session_refresh used by path-A confirm and change_password); rollback floor enforced by deploy.sh. |
| Risks | None beyond RG-7. |
| Conditions | RG-7 before production. |
| Staging dependency | Migration on the staging copy; RG-7 rehearsal (not performed). |
| Production dependency | RG-7 evidence. |
| Author recommendation | IR-01 fix; wording corrected (FC-A08, FC-12). |
| Author-proposed disposition | APPROVE WITH CONDITIONS |
| Owner decision recorded | NONE |
| Status | PROPOSED, NOT APPROVED |

### AM-12

| Field | Value |
|---|---|
| Owner decision required | Confirm OD-2 formally, then decide this amendment (06 §7.2.2), including whether reactivation after restore requires credential and MFA resets (FC-A12). |
| Implementation behavior (provenance) | Implemented at 6ec2e76 (unchanged at 3f5920b) (rbac/governance.py, rbac/users.py, rbac/routes.py; SPA Founder actions page). |
| Risks | Restored Founder keeps pre-deletion credentials. |
| Conditions | Decide whether reactivation after restore requires credential and MFA resets (FC-A12). |
| Staging dependency | None. |
| Production dependency | None beyond the release gates. |
| Author recommendation | Implements OD-2. |
| Author-proposed disposition | APPROVE WITH CONDITIONS |
| Owner decision recorded | NONE |
| Status | PROPOSED, NOT APPROVED |

### AM-13

| Field | Value |
|---|---|
| Owner decision required | Confirm OD-3 formally, then decide this amendment (06 §7.4 / 05 §8.6), including the 'blocked, not withdrawn' behaviour for role-definition changes (FC-08) and the FC-A09 residual. |
| Implementation behavior (provenance) | Implemented at 6ec2e76 (unchanged at 3f5920b) (rbac/governance.py governance_class, revalidate_after_escalation, proposal_still_authorised; auth/service.py verify_email_change; rbac/users.py role and permission paths). |
| Risks | Pending proposals survive role-definition escalation (blocked only); admin-issued links survive promotion. |
| Conditions | Accept 'blocked, not withdrawn' for role-definition changes (FC-08) and the FC-A09 residual, or require withdrawal. |
| Staging dependency | None. |
| Production dependency | None beyond the release gates. |
| Author recommendation | Implements OD-3. |
| Author-proposed disposition | APPROVE WITH CONDITIONS |
| Owner decision recorded | NONE |
| Status | PROPOSED, NOT APPROVED |

## Owner confirmations required

### OD-2: Founder restoration requires two distinct eligible human principals

- **Implementation:** Code at 6ec2e76 (unchanged at 3f5920b) follows this brief instruction (RR-02, AM-12).
- **Record status:** AWAITING FORMAL OWNER CONFIRMATION — a brief instruction to the author, not a recorded owner decision; no decision-log entry exists (FC-A02).

### OD-3: Sensitive operations revalidate the current governance class at execution

- **Implementation:** Code at 6ec2e76 (unchanged at 3f5920b) follows this brief instruction (RR-03, AM-13), within the FC-08 and FC-A09 limits stated in AM-13.
- **Record status:** AWAITING FORMAL OWNER CONFIRMATION — a brief instruction to the author, not a recorded owner decision; no decision-log entry exists (FC-A02).

## Gates and approvals

| Item | Status |
|---|---|
| TG-01 | **PENDING** |
| TG-08 | **PENDING** |
| Merge-safety decision | **PENDING** |
| Production deployment approval | **PENDING** |

## Owner decisions the final check lists as required for merge

- AM-1..AM-7, AM-11..AM-13 decisions
- Confirm OD-2/OD-3 in a decision record
- TG-01
- TG-08
- Site production deployment on merge

The merge-safety options are in [P0-merge-safety-plan.md](P0-merge-safety-plan.md). None has been executed.
