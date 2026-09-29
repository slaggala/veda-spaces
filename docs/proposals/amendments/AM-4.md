# AM-4: proposed amendment to 04 §5.4 vs 08 §8.5; LEAD-027

> **Status: PROPOSED, NOT APPROVED.** Baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`; implementation logic `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`; reviewed tree `3f5920b17d21214b39414d080d34246746c8c40d`; document-level check review/p0-independent-implementation-review @ 093cfa6872c209deb9991910c457afcdb4ad2d04. This proposal lives outside `docs/architecture/`, changes no certified document, and records no owner decision.

| Field | Value |
|---|---|
| Amendment ID | AM-4 |
| Status | **PROPOSED, NOT APPROVED** |
| Amends | 04 §5.4 vs 08 §8.5; LEAD-027 |
| Affected requirements | LEAD-012, LEAD-027 |
| Related findings | IR-16, RR-12 |
| Related deviation | DEV-004 |
| Final targeted check classification (56c20ba, verbatim) | INCOMPLETE (gaps honestly labelled: later-version rule, create-time consent, immutability) |
| Document-level check classification (093cfa6, verbatim) | INCOMPLETE — states 422 where code/tests return 409; 'later version' has no ordering rule; the immutability option conflicts with erasure rewriting consent notes (DC-02) |
| Certified behavior | 04 §5.4: re-consent 'through PATCH of the consent_* fields'; 08 §8.5: consent_* → 422 FIELD_NOT_UPDATABLE. The two conflict. |
| Proposed behavior | PATCH /leads/{id} accepts consent {channel ∈ PHONE_VERBAL\|IN_PERSON\|WHATSAPP\|EMAIL, policy_version, note}; raw consent_* stay FIELD_NOT_UPDATABLE. Current, tested behaviour (the code at 6ec2e76): an unknown policy_version is 422 UNKNOWN_POLICY_VERSION; a re-consent is accepted after a withdrawal, when consent was never captured, or for any published version DIFFERENT from the recorded one; otherwise 409 INVALID_STATE ("Consent is already recorded for this privacy notice version"). The superseded evidence (policy version, channel, captured_on, source page, whether an IP was recorded, withdrawn_on, withdrawal channel) is written to a read-only system activity before the lead row is overwritten; the full prior row stays in audit_log. Target rules for the owner's decision (not implemented, RR-12): (a) ordering — a version is LATER when it appears after the recorded one in VEDA_PUBLISHED_POLICY_VERSIONS, which lists published notices in publication order (oldest first); a recorded version no longer listed counts as earliest; an equal or earlier version is refused with the same 409 INVALID_STATE; (b) staff consent recorded at lead creation requires a note and writes the same consent activity; (c) the superseded snapshot also records consent_withdrawal_note; (d) superseded evidence is protected either by a database guard on the consent activity (option a) or by a dedicated append-only lead_consent_event table (option b). Under either option erasure stays possible: anonymize() rewrites the consent note and other personal text (AM-10 lists consent notes as PII), so the guard of option (a) must exempt the erasure rewrite, and option (b) must allow the same rewrite of its note columns. This amendment covers lead consent only; invitation and enrollment behaviour is AM-2. |
| Reason | Resolves the certified conflict and the IR-16 defects without an unapproved schema change. |
| Implementation (provenance) | Implemented at 6ec2e76 (unchanged at 3f5920b): the consent object on PATCH; the three accepted cases with 'different version' semantics; 409 INVALID_STATE otherwise and 422 for an unknown version; note required on re-consent; superseded evidence in a system activity (without the withdrawal note) and in audit_log; application-level read-only activity. NOT implemented (RR-12, production blocker): target rules (a) ordering, (b) create-time note and activity, (c) withdrawal note in the snapshot, (d) database-level protection. Approving this amendment would make the current code a tracked deviation from the approved text until RR-12 lands. |
| Security impact | Requires lead.update in scope and If-Match; provenance no longer mixed. Until RR-12 is fixed, consent evidence can churn between published versions. |
| Data impact | Option (a): no schema change, one guard; option (b): a new append-only table. |
| API impact | consent object on PATCH; additive read-only consent_evidence on activities. |
| UI impact | Timeline entry for superseded evidence; the SPA currently renders only subject and note (RR-A20). |
| Compatibility impact | Additive. |
| Rollback or forward-fix | Remove the consent field: re-consent then cannot be recorded (LEAD-027 unmet). |
| Required tests | `api/tests/integration/test_consent_dev004.py (reconsent_without_withdrawal_or_new_version_is_refused expects 409)` |
| Staging evidence | None required. |
| Production evidence | RR-12 implemented with tests for (a)–(c) on both engines; Data Protection lead sign-off of option (a) or (b). |
| Failure behavior | Unknown policy version: 422 UNKNOWN_POLICY_VERSION. Re-consent outside the accepted cases: 409 INVALID_STATE. Missing note: 422. In every case the stored evidence is unchanged. |
| Owner decision required | Accept the labelled gaps for merge (approval then records the current code as a tracked deviation), approve the ordering rule (a), the create-time rule (b), the withdrawal-note rule (c), and choose option (a) or (b) for (d) with the erasure exemption. |
| Approval readiness | Not ready for approval as a complete behaviour. The owner may accept the labelled gaps for merge; completion (RR-12) before production. |
| Decision owner | Architecture Owner, Data Protection lead |
