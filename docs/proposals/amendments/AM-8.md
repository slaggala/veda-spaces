# AM-8: proposed amendment to 05 / 03

> **Status: PROPOSED, NOT APPROVED.** Baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`; reviewed implementation `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`; final targeted check review/p0-independent-implementation-review @ 56c20ba992b519daa79aa3802a28343aab8c0b41. This proposal lives outside `docs/architecture/`, changes no certified document, and records no owner decision.

| Field | Value |
|---|---|
| Amendment ID | AM-8 |
| Status | **PROPOSED, NOT APPROVED** |
| Amends | 05 / 03 |
| Affected requirements | AUTH-008, AUTH-011, USER-007 |
| Related findings | IR-A22 (OI-3) |
| Related deviation | None (documentation) |
| Final targeted check classification | TECHNICALLY SOUND |
| Certified behavior | Action tokens are described as random single-use tokens with only a hash stored. |
| Proposed behavior | Document that raw tokens are HMAC(K_action, row id ‖ purpose) so the worker can rebuild links without storing secrets; a K_action compromise together with row ids yields every live link; rotating K_action invalidates all open links. |
| Reason | Documentation of the implemented trade-off. |
| Implementation at the reviewed SHA and after | As described. |
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
