# AM-4: proposed amendment to 04 §5.4 vs 08 §8.5; LEAD-027

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It does not modify the certified documents and has no effect until the decision owner approves it.

| Field | Value |
|---|---|
| Amendment ID | AM-4 |
| Related finding | IR-16 |
| Related deviation | DEV-004 |
| Amends | 04 §5.4 vs 08 §8.5; LEAD-027 |
| Existing certified behavior | 04 §5.4: re-consent 'through PATCH of the consent_* fields'; 08 §8.5: consent_* → 422 FIELD_NOT_UPDATABLE. The two conflict. |
| Proposed behavior | PATCH /leads/{id} accepts consent {channel ∈ PHONE_VERBAL\|IN_PERSON\|WHATSAPP\|EMAIL, policy_version, note}; raw consent_* stay FIELD_NOT_UPDATABLE. Accepted only after withdrawal, when never captured, or for a new published notice version. The superseded evidence is first written to a read-only system activity (consent_evidence, visible in the lead timeline) and remains in audit_log; the new capture has no web IP or source page. Decision requested: keep this in-row + timeline model, or add a dedicated append-only lead_consent_event table. |
| Reason | Resolves the certified conflict and the IR-16 defects without an unapproved schema change. |
| Security impact | Requires lead.update in scope and If-Match; provenance no longer mixed. |
| Data impact | No schema change; one system activity per re-consent. |
| API impact | consent object on PATCH; additive read-only consent_evidence on activities. |
| UI impact | Timeline shows the superseded evidence; no re-consent control in P0 (09 specifies none). |
| Compatibility impact | Additive. |
| Tests | `api/tests/integration/test_consent_dev004.py` |
| Rollback | Remove the consent field; re-consent then cannot be recorded. |
| Decision owner | Architecture Owner, Data Protection lead |
| Status | **PROPOSED, NOT APPROVED** |
