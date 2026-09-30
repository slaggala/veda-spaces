# P0 implementation deviations

Baseline `778aa8fdd918da48340319696ada3ff673e9fb8e` · reviewed `9236aa3` · review review/p0-independent-implementation-review @ 1aaf019b6c872a075d13e9b3a2a2e9c16489f6f4 · targeted re-review review/p0-independent-implementation-review @ 15d25a759cfc0342bdca45ba4a9c51550270f305

> **Owner decisions were recorded on 2026-09-30** through the amendments. See [P0-owner-decision-record.md](P0-owner-decision-record.md). DEV-004 (AM-4) is approved with conditions (tracked deviation until RR-12).

| ID | Title | Reviewer decision | Targeted re-review | Amendment | Status |
|---|---|---|---|---|---|
| DEV-001 | MFA factor uniqueness permits the current authenticator and a pending replacement to coexist during controlled re-enrollment | ACCEPTABLE WITH ARCHITECTURE AMENDMENT | ACCEPTABLE WITH ARCHITECTURE AMENDMENT | AM-1 | APPROVED (via AM-1, 2026-09-30) |
| DEV-002 | Invitation acceptance returns an MFA-enrollment step when MFA is required instead of immediate final success | ACCEPTABLE WITH ARCHITECTURE AMENDMENT | ACCEPTABLE WITH ARCHITECTURE AMENDMENT | AM-2 | APPROVED WITH CONDITIONS (via AM-2, 2026-09-30) |
| DEV-003 | Login accepts an optional CAPTCHA token | ACCEPTABLE WITH ARCHITECTURE AMENDMENT | ACCEPTABLE WITH ARCHITECTURE AMENDMENT | AM-3 | APPROVED (via AM-3, 2026-09-30) |
| DEV-004 | Staff lead update accepts a re-consent object | REQUIRES IMPLEMENTATION CHANGE | ACCEPTABLE WITH ARCHITECTURE AMENDMENT | AM-4 | APPROVED WITH CONDITIONS (via AM-4, 2026-09-30) |
| DEV-005 | Break-glass cancel link endpoint and page (06 §7.5 step 5) | n/a (remediation) | ACCEPTABLE WITH ARCHITECTURE AMENDMENT | AM-5 | APPROVED WITH CONDITIONS (via AM-5, 2026-09-30) |
| DEV-006 | mfa_challenge binds enrollment transactions to a factor and a path | n/a (remediation) | ACCEPTABLE WITH ARCHITECTURE AMENDMENT | AM-11 | APPROVED WITH CONDITIONS (via AM-11, 2026-09-30) |
| DEV-007 | Layered sign-in limits: per-(identifier, network) limits plus cross-network account, aggregate and reset-email bounds | n/a (remediation) | REQUIRES IMPLEMENTATION CHANGE | AM-7 | APPROVED WITH CONDITIONS (via AM-7, 2026-09-30) |
| DEV-008 | Readiness accepts a declared newer schema and hides details at the edge | n/a (remediation) | ACCEPTABLE WITH ARCHITECTURE AMENDMENT | AM-6 | APPROVED WITH CONDITIONS (via AM-6, 2026-09-30) |
| DEV-009 | Deleted Founders are restored only through FOUNDER_STATUS_CHANGE status=RESTORE (OD-2) | n/a (OD-2 brief instruction; approved by the owner on 2026-09-30) | n/a | AM-12 | APPROVED WITH CONDITIONS (via AM-12, 2026-09-30) |
| DEV-010 | Pending identity changes are re-validated against the target's current governance class (OD-3) | n/a (OD-3 brief instruction; approved by the owner on 2026-09-30) | n/a | AM-13 | APPROVED WITH CONDITIONS (via AM-13, 2026-09-30) |

## DEV-001: MFA factor uniqueness permits the current authenticator and a pending replacement to coexist during controlled re-enrollment

- **Requirement ids:** MFA-005, MFA-013, MFA-014
- **Adrs:** ADR-006
- **Architecture references:** 03 §5.5 (ux_user_mfa_factor__user_live), 05 §11.3, §11.5, 12 §4.12 TD-E
- **Certified behavior:** 03 §5.5 defines ux_user_mfa_factor__user_live as UNIQUE (user_id, factor_type) WHERE status IN ('PENDING','ACTIVE') AND is_deleted = false, i.e. at most one live factor per user and type.
- **Implemented behavior:** The same index name is keyed on (user_id, factor_type, status) with the same predicate: at most one PENDING and at most one ACTIVE factor per user and type. enroll/start revokes any earlier PENDING factor first; enroll/confirm revokes the ACTIVE factor (REPLACED) and flushes before promoting the PENDING factor.
- **Reason:** The certified index contradicts certified behaviour elsewhere: 05 §11.5 and TD-E require the old factor to stay ACTIVE while a PENDING replacement exists (failed or interrupted re-enrollment must leave the old authenticator working). With the certified key the first enroll/start by an enrolled user fails with a unique violation.
- **Security impact:** None negative. Only one ACTIVE factor can exist, so authentication semantics are unchanged; the PENDING factor is never accepted for login, step-up or recovery. Enrollment still requires the two-proof paths of 05 §11.3.
- **Compatibility impact:** None for clients. PostgreSQL migration: the index is recreated with the same name and predicate.
- **Data model impact:** Index key gains the status column (migration 0004_auth; model veda/platform/auth/models.py). No column or table changes.
- **Api impact:** None.
- **Ui impact:** None.
- **Tests:** tests/integration/test_mfa.py::test_TD_E_failed_reenrollment_commits_nothing_that_grants_access, tests/integration/test_mfa.py::test_MFA_013_recovery_requires_password_and_code, tests/integration/test_mfa.py::test_TD_C_expired_recovery_session, tests/integration/test_mfa.py::test_MFA_005_regenerate_codes_needs_step_up_and_invalidates_old, tests/integration/test_schema.py::test_DATA_011_conformance_passes_on_migrated_schema
- **Rollback:** Restore the certified two-column key in 0004_auth and the model, and change enroll/start to create the PENDING factor only after revoking the ACTIVE one. That reintroduces the TD-E conflict, so it needs an architecture decision first. No data migration: existing rows satisfy both definitions whenever no PENDING factor is open.
- **Reviewer decision:** ACCEPTABLE WITH ARCHITECTURE AMENDMENT
- **Reviewer conditions:** IR-20
- **Conditions resolution:** IR-20 resolved: path C refuses when an ACTIVE factor exists; every confirmation ends other open enrollment links and transactions.
- **Targeted re-review decision:** ACCEPTABLE WITH ARCHITECTURE AMENDMENT
- **Targeted re-review basis:** IR-20 condition met; only one ACTIVE factor; PENDING never authenticates
- **Decision required:** Amend 03 §5.5 to key ux_user_mfa_factor__user_live on (user_id, factor_type, status), or resolve TD-E/05 §11.5 another way.
- **Amendment:** AM-1
- **Status:** APPROVED (via AM-1, 2026-09-30)

## DEV-002: Invitation acceptance returns an MFA-enrollment step when MFA is required instead of immediate final success

- **Requirement ids:** AUTH-011, MFA-014, UI-015
- **Adrs:** ADR-006, ADR-010
- **Architecture references:** 08 §4.5 (POST /auth/invite/accept → 204), 05 §8.4, 05 §11.3 path B
- **Certified behavior:** 08 §4.5 lists POST /api/v1/auth/invite/accept → 204. 05 §8.4 and §11.3 path B require enrollment inside the same flow when policy requires MFA, with the account ACTIVE only after enrollment confirmation, but 08 defines no response carrying the enrollment context.
- **Implemented behavior:** No MFA required: 204 and the user becomes ACTIVE. MFA required: the password is set, the user stays INVITED and the response is 200 {"data": {"status": "MFA_ENROLLMENT_REQUIRED", "invite_context": "<opaque>", "expires_in": 900}}. invite_context is a single-use ENROLLMENT mfa_challenge token (hash stored). POST /auth/mfa/enroll/start {invite_context} and enroll/confirm complete path B, activate the user and issue a FULL session. The INVITE token is consumed at confirmation, so an abandoned acceptance can be restarted with the same link until it expires.
- **Reason:** Path B needs a way to hand the client the enrollment continuation; a 204 cannot carry it.
- **Security impact:** Neutral to positive. Two proofs (emailed invite token + newly set password) precede enrollment; no session exists until confirmation; invite_context is short-lived (15 min), hashed and single-use; an INVITED user cannot sign in with the password alone.
- **Compatibility impact:** Additive within v1 (API-009): clients of the MFA-not-required path still receive 204.
- **Data model impact:** None (uses existing mfa_challenge purpose ENROLLMENT).
- **Api impact:** New 200 response shape on POST /api/v1/auth/invite/accept; POST /auth/mfa/enroll/start accepts invite_context as documented in 08 §4.7.
- **Ui impact:** The accept-invite screen routes to the enrollment screen when it receives MFA_ENROLLMENT_REQUIRED.
- **Tests:** tests/integration/test_mfa.py::test_MFA_014_path_b_invitation_enrollment, tests/integration/test_founder_governance.py::test_AUTH_014_bootstrap_creates_one_invited_founder, tests/integration/test_auth.py::test_AUTH_011_invite_accept_without_mfa_requirement, app/e2e/workspace.e2e.mjs: accept invitation (path B: forced MFA enrollment)
- **Rollback:** None available without an alternative design: the certified 204 cannot carry path B. Alternatives would be (a) emailing a separate enrollment link (path C) after acceptance, or (b) returning the context in a header. Either needs an architecture decision.
- **Reviewer decision:** ACCEPTABLE WITH ARCHITECTURE AMENDMENT
- **Reviewer conditions:** IR-01, IR-21, IR-25
- **Conditions resolution:** IR-01 resolved (transaction binding, AM-11); IR-21 resolved (resend/repeat acceptance supersede contexts; path B requires a live invite); IR-25 resolved (INVITE_ACCEPTED stage password_set).
- **Targeted re-review decision:** ACCEPTABLE WITH ARCHITECTURE AMENDMENT
- **Targeted re-review basis:** Conditions IR-01, IR-21, IR-25 met; AM-2 must state that link replay before activation overwrites the password
- **Decision required:** Amend 08 §4.5 to document the 200 MFA_ENROLLMENT_REQUIRED response, or choose an alternative mechanism for path B.
- **Amendment:** AM-2
- **Status:** APPROVED WITH CONDITIONS (via AM-2, 2026-09-30)

## DEV-003: Login accepts an optional CAPTCHA token

- **Requirement ids:** AUTH-010, SEC-011, MFA-009, UI-001
- **Adrs:** 
- **Architecture references:** 08 §4.1 (login request {email, password}), 05 §4 (next attempt from a throttled pair requires a Turnstile token), 09 §4.1
- **Certified behavior:** 08 §4.1 defines the login body as {email, password}. 05 §4 and 09 §4.1 require a Turnstile challenge after repeated failures from one network, but 08 defines neither the field carrying the token nor the signal telling the client to show it.
- **Implemented behavior:** POST /api/v1/auth/login accepts an optional turnstile_token (≤ 2048 chars). After 5 consecutive failures for an (account, network) pair, the pair needs a valid token; 401 INVALID_CREDENTIALS then carries "captcha_required": true. Unknown emails use the same per-network state keyed by an HMAC of the email, so the signal does not reveal account existence. Related additive field: MFA 401 MFA_CODE_INVALID responses carry attempts_remaining (MFA-009, 09 §4.10).
- **Reason:** 05 §4 cannot be implemented with the closed request schema of 08 §4.1 (unknown fields are rejected with UNKNOWN_FIELD).
- **Security impact:** Implements the certified control. The token is verified server-side; a failed or missing token keeps the uniform 401. The response stays uniform across unknown, invited, disabled and wrong-password cases.
- **Compatibility impact:** Additive (API-009): the field is optional; existing clients are unaffected until a pair is throttled.
- **Data model impact:** None (in-process per-network state, as designed in 05 §4 / OPS-010).
- **Api impact:** Optional request field turnstile_token on POST /api/v1/auth/login; optional response fields captcha_required (401) and attempts_remaining (MFA 401).
- **Ui impact:** The login screen renders the Turnstile widget when captcha_required is true; the MFA screen announces remaining attempts.
- **Tests:** tests/integration/test_auth.py::test_DEV_003_optional_captcha_token_after_network_throttle, tests/integration/test_auth.py::test_AUTH_010_throttle_is_per_account_and_network, tests/integration/test_auth.py::test_AUTH_009_uniform_login_failures, tests/integration/test_mfa.py::test_MFA_001_login_challenge_attempt_limits
- **Rollback:** Remove turnstile_token from LoginIn and the captcha branch in veda/platform/auth/service.py::login; per-network throttling then relies on the escalating delay only. No data migration.
- **Reviewer decision:** ACCEPTABLE WITH ARCHITECTURE AMENDMENT
- **Reviewer conditions:** IR-22, IR-09, IR-02
- **Conditions resolution:** IR-22 resolved (ipaddress-based /24 and /64); IR-09 resolved (dev verifier local/test only; staging validated); IR-02 resolved (siteverify outside the write lock).
- **Targeted re-review decision:** ACCEPTABLE WITH ARCHITECTURE AMENDMENT
- **Targeted re-review basis:** Conditions IR-22, IR-09, IR-02 met
- **Decision required:** Amend 08 §4.1 / §4.7 to document the optional fields.
- **Amendment:** AM-3
- **Status:** APPROVED (via AM-3, 2026-09-30)

## DEV-004: Staff lead update accepts a re-consent object

- **Requirement ids:** LEAD-012, LEAD-024, LEAD-027
- **Adrs:** ADR-005
- **Architecture references:** 04 §5.4 (re-consent recorded through PATCH of the consent_* fields), 08 §8.5 (consent_* → 422 FIELD_NOT_UPDATABLE)
- **Certified behavior:** The certified documents conflict: 04 §5.4 records re-consent 'through PATCH of the consent_* fields, with the channel and policy version', while 08 §8.5 rejects consent_* in PATCH with 422 FIELD_NOT_UPDATABLE.
- **Implemented behavior:** PATCH /api/v1/leads/{lead_id} (lead.update in scope, If-Match) accepts consent: {channel: PHONE_VERBAL|IN_PERSON|WHATSAPP|EMAIL, policy_version, note}. WEBSITE_FORM is refused (also on staff create). Accepted only when consent was withdrawn, never captured, or for a different published notice version (else 409 INVALID_STATE). Before the row changes, a read-only system activity records the superseded evidence (policy version, channel, captured on, source page, whether an IP was recorded, withdrawal time and channel) with the staff note; it is returned as consent_evidence in the timeline. The new capture sets consent_contact, policy version, captured on and channel, clears the withdrawal fields and sets consent_ip_address and consent_source_page to NULL. Raw consent_* fields stay FIELD_NOT_UPDATABLE; the public intake accepts no re-consent object.
- **Reason:** Satisfies 04 §5.4 without contradicting the 08 §8.5 rule that consent_* columns are not mass-assignable.
- **Security impact:** Low. Requires lead.update within scope and optimistic concurrency. Every change is audited (UPDATE row with old and new consent values). Not reachable from the public endpoint.
- **Compatibility impact:** Additive (API-009).
- **Data model impact:** No schema change. Superseded consent evidence is kept append-only in a read-only system activity and in audit_log; the row holds the current consent.
- **Api impact:** Optional consent object on PATCH /api/v1/leads/{lead_id}.
- **Ui impact:** No re-consent control exists in the SPA (09 specifies none); the superseded evidence is visible in the lead timeline. The earlier register text claiming a lead-drawer control was wrong (IR-A25).
- **Tests:** api/tests/integration/test_consent_dev004.py (13 tests)
- **Rollback:** Remove the consent field from LeadPatchIn and the consent branch in veda/modules/crm/leads/service.py::_update. Re-consent then cannot be recorded until 04 §5.4 and 08 §8.5 are reconciled. No data migration.
- **Reviewer decision:** REQUIRES IMPLEMENTATION CHANGE
- **Reviewer conditions:** IR-16
- **Targeted re-review decision:** ACCEPTABLE WITH ARCHITECTURE AMENDMENT
- **Targeted re-review basis:** Corrected behaviour verified on both engines; residuals RR-12
- **Decision required:** AM-4: approve the corrected mechanism and choose in-row + timeline activity (implemented) or a dedicated append-only consent-event table.
- **Amendment:** AM-4
- **Status:** APPROVED WITH CONDITIONS (via AM-4, 2026-09-30)

## DEV-005: Break-glass cancel link endpoint and page (06 §7.5 step 5)

- **Requirement ids:** RBAC-021
- **Adrs:** 
- **Architecture references:** 06 §7.5 step 5, 06 §11 RBX-003, 08 §1, 12 TD-G G12
- **Certified behavior:** The capability is required (06 §7.5, TD-G G12); 08 §1 and the RBX-003 register name no endpoint or page.
- **Implemented behavior:** POST /api/v1/approvals/cancel-link {token} (public, RBX-003) and the SPA page /approvals/cancel (explicit confirmation).
- **Reason:** Makes the certified veto usable (IR-07).
- **Security impact:** Endpoint assessed secure by the reviewer; page scrubs the fragment and needs a click.
- **Compatibility impact:** Additive.
- **Data model impact:** None.
- **Api impact:** One public endpoint.
- **Ui impact:** One public page.
- **Tests:** api/tests/integration/test_founder_governance.py::test_G12_cancel_link_by_notified_party, app/e2e/access.e2e.mjs
- **Rollback:** Remove endpoint and page.
- **Targeted re-review decision:** ACCEPTABLE WITH ARCHITECTURE AMENDMENT
- **Targeted re-review basis:** Endpoint, page, authorization, replay prevention, events, RBX registration verified; OpenAPI status code RR-A09
- **Decision required:** AM-5.
- **Amendment:** AM-5
- **Status:** APPROVED WITH CONDITIONS (via AM-5, 2026-09-30)

## DEV-006: mfa_challenge binds enrollment transactions to a factor and a path

- **Requirement ids:** MFA-011, MFA-012, MFA-014, AUTH-015
- **Adrs:** ADR-006
- **Architecture references:** 03 §5.7, 05 §11.3
- **Certified behavior:** mfa_challenge has no factor or path columns.
- **Implemented behavior:** Nullable factor_id and enrollment_path with CHECKs (migration 0009_mfa_challenge_binding).
- **Reason:** IR-01 remediation.
- **Security impact:** Closes IR-01.
- **Compatibility impact:** Expand-only.
- **Data model impact:** Two nullable columns on mfa_challenge.
- **Api impact:** None.
- **Ui impact:** None.
- **Tests:** api/tests/integration/test_mfa_binding.py, api/tests/integration/test_schema.py
- **Rollback:** N-1 image ignores the columns.
- **Targeted re-review decision:** ACCEPTABLE WITH ARCHITECTURE AMENDMENT
- **Targeted re-review basis:** Expand-only; no schema/authz/replay/migration regression; AM-11 incomplete (rollback reintroduces IR-01; 02 §8.3 placement)
- **Decision required:** AM-11.
- **Amendment:** AM-11
- **Status:** APPROVED WITH CONDITIONS (via AM-11, 2026-09-30)

## DEV-007: Layered sign-in limits: per-(identifier, network) limits plus cross-network account, aggregate and reset-email bounds

- **Requirement ids:** AUTH-010, SEC-011, AUTH-008
- **Adrs:** 
- **Architecture references:** 08 §12, 05 §4
- **Certified behavior:** 08 §12: login 5/min per email, forgot 3/hour per email; 05 §4 per-(account, network) throttle and a 5-network global lock for accounts without a factor.
- **Implemented behavior:** Per-(email HMAC, /24 or /64) limits kept for IR-23 fairness, plus: wide-network limits (IPv4 /24, IPv6 /48); an account budget across networks (10 failures/15 min → Turnstile on every attempt; 20 → escalating spacing up to 30 s, 429); an aggregate bound (200 failures/5 min → Turnstile for every sign-in); at most 3 reset emails per account per hour; endpoint limits on MFA, recovery, enroll confirm and email verify/cancel; trusted-proxy entries at most /24 or /64; bounded in-process state; no raw email in keys or events. Nothing locks out an account except the certified 05 §4 lock for accounts without a factor.
- **Reason:** RR-04: the earlier (email, network) keying removed the only cross-network bound for MFA holders and multiplied reset-email volume.
- **Security impact:** Distributed guessing per account: 10 unchallenged attempts per 15 min, then one solved challenge per attempt, then ≤ 1 per 30 s; the MFA_REQUIRED oracle needs a challenge. Victim DoS bounded to a challenge plus ≤ 30 s. Turnstile failure under escalation fails closed for that identifier (≤ 15 min).
- **Compatibility impact:** Additive: 429 on the delay tier; captcha_required on the challenge tier.
- **Data model impact:** None.
- **Api impact:** 429 RATE_LIMITED with Retry-After from login under the delay tier.
- **Ui impact:** None.
- **Tests:** api/tests/integration/test_layered_limiter.py, api/tests/integration/test_auth_remediation.py::test_IR23_P5_third_party_cannot_rate_limit_the_victim_from_elsewhere
- **Rollback:** Remove the account, aggregate and reset tiers (reintroduces RR-04). Not recommended.
- **Targeted re-review decision:** REQUIRES IMPLEMENTATION CHANGE
- **Targeted re-review basis:** Removes cross-network guessing bound for MFA holders and reset-email cap (RR-04)
- **Decision required:** AM-7 (rewritten; the earlier AM-7 was rejected as written, OD-1).
- **Amendment:** AM-7
- **Status:** APPROVED WITH CONDITIONS (via AM-7, 2026-09-30)

## DEV-008: Readiness accepts a declared newer schema and hides details at the edge

- **Requirement ids:** LOG-005, OPS-004
- **Adrs:** ADR-008
- **Architecture references:** 08 §3, 02 §12.4, LOG-005
- **Certified behavior:** Ready only at head; body with checks returned to every caller.
- **Implemented behavior:** head/behind/ahead/ahead_undeclared; ahead is ready only when declared in VEDA_SCHEMA_AHEAD_ACCEPTED; checks returned only to direct local callers.
- **Reason:** IR-10 (rollback) and IR-A17 (disclosure).
- **Security impact:** Less disclosure.
- **Compatibility impact:** Host deploy gate unchanged.
- **Data model impact:** None.
- **Api impact:** Edge body {status}.
- **Ui impact:** None.
- **Tests:** api/tests/integration/test_ops_remediation.py
- **Rollback:** Strict head equality.
- **Targeted re-review decision:** ACCEPTABLE WITH ARCHITECTURE AMENDMENT
- **Targeted re-review basis:** Safe; no secrets; AM-6 must state that rollback of this release is snapshot restore (RR-17)
- **Decision required:** AM-6.
- **Amendment:** AM-6
- **Status:** APPROVED WITH CONDITIONS (via AM-6, 2026-09-30)

## DEV-009: Deleted Founders are restored only through FOUNDER_STATUS_CHANGE status=RESTORE (OD-2)

- **Requirement ids:** RBAC-020, RBAC-021, USER-001
- **Adrs:** ADR-010
- **Architecture references:** 06 §7.2.2, 06 §7.1 G11, 08 §5.11
- **Certified behavior:** FOUNDER_STATUS_CHANGE statuses DISABLED/ACTIVE/UNLOCK/DELETE; restore of a deleted user through user.restore (USER-001).
- **Implemented behavior:** POST /users/{id}/restore refuses Founders (403 FOUNDER_PROTECTED, FOUNDER_GOVERNANCE_BYPASS_BLOCKED); FOUNDER_STATUS_CHANGE status=RESTORE requested by one eligible Founder and approved in-app by another; refused on both break-glass channels (SECOND_FOUNDER_REQUIRED); re-validated at execution.
- **Reason:** RR-02 and the OD-2 brief instruction (approved by the owner on 2026-09-30).
- **Security impact:** Closes a G11 bypass.
- **Compatibility impact:** Additive status value.
- **Data model impact:** None.
- **Api impact:** status RESTORE; 403 on the generic restore for Founders.
- **Ui impact:** Restore action on the Founder actions page.
- **Tests:** api/tests/integration/test_final_merge_blockers.py::test_RR02_*
- **Rollback:** Remove RESTORE (deleted Founders unrestorable).
- **Reviewer decision:** n/a (OD-2 brief instruction; approved by the owner on 2026-09-30)
- **Reviewer conditions:** 
- **Decision required:** AM-12.
- **Amendment:** AM-12
- **Status:** APPROVED WITH CONDITIONS (via AM-12, 2026-09-30)

## DEV-010: Pending identity changes are re-validated against the target's current governance class (OD-3)

- **Requirement ids:** RBAC-020, USER-007
- **Adrs:** ADR-010
- **Architecture references:** 06 §7.4, 05 §8.6
- **Certified behavior:** G11/G9 re-evaluated when a STANDARD request is decided and executed; email verification completes with no further check.
- **Implemented behavior:** Class escalation (GRANT_FOUNDER, roles, permissions) withdraws weaker-class work in the same transaction; verification recomputes the proposal's authorising class and fails closed when it is weaker than the target's current class or the account is disabled.
- **Reason:** RR-03 (N17) and the OD-3 brief instruction (approved by the owner on 2026-09-30).
- **Security impact:** Closes RR-03.
- **Compatibility impact:** Behavioural tightening.
- **Data model impact:** None.
- **Api impact:** Verification can return EMAIL_TOKEN_INVALID for a live link.
- **Ui impact:** None.
- **Tests:** api/tests/integration/test_final_merge_blockers.py::test_RR03_*
- **Rollback:** Remove the checks (RR-03 returns).
- **Reviewer decision:** n/a (OD-3 brief instruction; approved by the owner on 2026-09-30)
- **Reviewer conditions:** 
- **Decision required:** AM-13.
- **Amendment:** AM-13
- **Status:** APPROVED WITH CONDITIONS (via AM-13, 2026-09-30)
