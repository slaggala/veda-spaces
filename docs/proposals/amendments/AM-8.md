# AM-8: proposed amendment to 05 / 03

> **Status: APPROVED.** Owner decision recorded 2026-09-30 ([decision record](../../implementation/P0-owner-decision-record.md)). Baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`; implementation logic `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`; reviewed tree `3f5920b17d21214b39414d080d34246746c8c40d`; document-level check review/p0-independent-implementation-review @ 093cfa6872c209deb9991910c457afcdb4ad2d04. This proposal lives outside `docs/architecture/`, changes no certified document, and changes no certified document.

| Field | Value |
|---|---|
| Amendment ID | AM-8 |
| Status | **APPROVED** |
| Amends | 05 / 03 |
| Affected requirements | AUTH-008, AUTH-011, USER-007 |
| Related findings | IR-A22 (OI-3) |
| Related deviation | None (documentation) |
| Final targeted check classification (56c20ba, verbatim) | TECHNICALLY SOUND |
| Document-level check classification (093cfa6, verbatim) | TECHNICALLY SOUND |
| Certified behavior | Action tokens are described as random single-use tokens with only a hash stored. |
| Proposed behavior | Document that raw tokens are HMAC(K_action, row id ‖ purpose) so the worker can rebuild links without storing secrets; a K_action compromise together with row ids yields every live link; rotating K_action invalidates all open links. |
| Reason | Documentation of the implemented trade-off. |
| Implementation (provenance) | As described. |
| Security impact | As stated; K_action must differ from every other key (enforced in staging and production, RR-10). |
| Data impact | None. |
| API impact | None. |
| UI impact | None. |
| Compatibility impact | None. |
| Rollback or forward-fix | Not applicable (documentation). |
| Required tests | `api/tests/integration/test_auth.py (token flows)`<br>`api/tests/unit/test_config_environments.py` |
| Staging evidence | None. |
| Production evidence | Key provisioning evidence. |
| Failure behavior | A rotated K_action invalidates every open link (uniform 400). |
| Owner decision required | Accept the documented trade-off. |
| Approval readiness | Ready to submit. |
| Decision owner | Architecture Owner, Security |
| Owner decision recorded | APPROVED (2026-09-30). Conditions: None |
