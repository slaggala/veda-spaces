# AM-4: proposed amendment to 04 §5.4 vs 08 §8.5; LEAD-027

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It lives outside `docs/architecture/`, does not modify the certified documents, and has no effect until the decision owner approves it. Nothing here claims owner approval or implementation authorization.

| Field | Value |
|---|---|
| Amendment ID | AM-4 |
| Amends | 04 §5.4 vs 08 §8.5; LEAD-027 |
| Related findings | IR-16, RR-12 |
| Related deviation | DEV-004 |
| Targeted re-review assessment | Technically sound; incomplete: 'new version' must mean later; create-time staff consent; DB-level immutability or a dedicated table. |
| Existing certified behavior | 04 §5.4: re-consent 'through PATCH of the consent_* fields'; 08 §8.5: consent_* → 422 FIELD_NOT_UPDATABLE. The two conflict. |
| Proposed behavior | PATCH /leads/{id} accepts consent {channel ∈ PHONE_VERBAL\|IN_PERSON\|WHATSAPP\|EMAIL, policy_version, note}; raw consent_* stay FIELD_NOT_UPDATABLE. Accepted only after withdrawal, when never captured, or for a notice version published *later* than the recorded one (an older or equal version is refused). Staff consent recorded at lead creation requires the same note and writes the same consent activity as a re-consent. The superseded evidence is first written to a read-only system activity (consent_evidence) and remains in audit_log; the new capture has no web IP or source page. Decision requested: (a) keep the in-row model plus a system activity made immutable at database level by the evidence-store guard, or (b) add a dedicated append-only lead_consent_event table. |
| Reason | Resolves the certified conflict and the IR-16 defects without an unapproved schema change. |
| Code behavior at this commit | Partially implemented. Current behaviour: any different published version is accepted (alternating between versions is possible); create-time staff consent needs no note and writes no consent activity; the consent activity is immutable at application level only. These are the open RR-12 residuals (production blocker); the proposal states the target behaviour. |
| Security | Requires lead.update in scope and If-Match; provenance no longer mixed. Until RR-12 is fixed, consent evidence can churn between published versions. |
| Data impact | Option (a): no schema change, one guard; option (b): a new append-only table. |
| API impact | consent object on PATCH; additive read-only consent_evidence on activities. |
| UI impact | Timeline entry for superseded evidence; the SPA currently renders only subject and note (RR-A20). |
| Compatibility | Additive. |
| Rollback | Remove the consent field: re-consent then cannot be recorded (LEAD-027 unmet). |
| Tests | `api/tests/integration/test_consent_dev004.py` |
| Owner decision requested | Choose (a) or (b); approve 'later version only' and the create-time rule. |
| Staging evidence | None. |
| Production evidence | RR-12 fixed and tested; Data Protection lead sign-off. |
| Approval readiness | Not ready: behaviour does not yet match the proposal (RR-12). |
| Decision owner | Architecture Owner, Data Protection lead |
| Status | **PROPOSED, NOT APPROVED** |
