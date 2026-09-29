# AM-4: proposed amendment to 04 §5.4 vs 08 §8.5; LEAD-027

> **Status: PROPOSED, NOT APPROVED.** Baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`; reviewed implementation `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`; final targeted check review/p0-independent-implementation-review @ 56c20ba992b519daa79aa3802a28343aab8c0b41. This proposal lives outside `docs/architecture/`, changes no certified document, and records no owner decision.

| Field | Value |
|---|---|
| Amendment ID | AM-4 |
| Status | **PROPOSED, NOT APPROVED** |
| Amends | 04 §5.4 vs 08 §8.5; LEAD-027 |
| Affected requirements | LEAD-012, LEAD-027 |
| Related findings | IR-16, RR-12 |
| Related deviation | DEV-004 |
| Final targeted check classification | INCOMPLETE (later-version rule, create-time consent, immutability) — corrected text states the gaps |
| Certified behavior | 04 §5.4: re-consent 'through PATCH of the consent_* fields'; 08 §8.5: consent_* → 422 FIELD_NOT_UPDATABLE. The two conflict. |
| Proposed behavior | PATCH /leads/{id} accepts consent {channel ∈ PHONE_VERBAL\|IN_PERSON\|WHATSAPP\|EMAIL, policy_version, note}; raw consent_* stay FIELD_NOT_UPDATABLE. Target rules (the decision requested): (a) re-consent is accepted only after a withdrawal, when no consent was ever captured, or for a published notice version LATER than the recorded one — an equal or earlier version is refused (422); (b) staff consent recorded at lead creation requires a note and writes the same consent activity as a re-consent; (c) superseded evidence is kept either by an evidence-store guard making the consent activity immutable at database level (option a) or in a dedicated append-only lead_consent_event table (option b). This amendment covers lead consent only; the invitation, MFA-enrollment, partial-account, replay and abandonment behaviour belongs to AM-2. |
| Reason | Resolves the certified conflict and the IR-16 defects without an unapproved schema change. |
| Implementation at the reviewed SHA and after | Partially implemented. Implemented and tested: the consent object on PATCH, the three accepted cases, note required on re-consent, superseded evidence written to a system activity and audit_log. NOT implemented (RR-12, production blocker): (a) any *different* published version is accepted, so alternating between two versions is possible; (b) create-time staff consent needs no note and writes no consent activity; (c) the consent activity is immutable at application level only (no database guard). |
| Security impact | Requires lead.update in scope and If-Match; provenance no longer mixed. Until RR-12 is fixed, consent evidence can churn between published versions. |
| Data impact | Option (a): no schema change, one guard; option (b): a new append-only table. |
| API impact | consent object on PATCH; additive read-only consent_evidence on activities. |
| UI impact | Timeline entry for superseded evidence; the SPA currently renders only subject and note (RR-A20). |
| Compatibility impact | Additive. |
| Rollback or forward-fix | Remove the consent field: re-consent then cannot be recorded (LEAD-027 unmet). |
| Required tests | `api/tests/integration/test_consent_dev004.py` |
| Staging evidence | None required. |
| Production evidence | RR-12 implemented with tests for (a)–(c) on both engines; Data Protection lead sign-off of option (a) or (b). |
| Failure behavior | A re-consent outside the accepted cases is 422; the stored evidence is unchanged. |
| Owner decision required | Choose (a) or (b); approve 'later version only' and the create-time rule. |
| Approval readiness | Not ready for approval as a complete behaviour. The owner may accept the labelled gaps for merge; completion (RR-12) before production. |
| Decision owner | Architecture Owner, Data Protection lead |
