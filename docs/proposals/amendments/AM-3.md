# AM-3: proposed amendment to 08 §4.1, §4.7

> **Status: APPROVED.** Owner decision recorded 2026-09-30 ([decision record](../../implementation/P0-owner-decision-record.md)). Baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`; implementation logic `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`; reviewed tree `3f5920b17d21214b39414d080d34246746c8c40d`; document-level check review/p0-independent-implementation-review @ 093cfa6872c209deb9991910c457afcdb4ad2d04. This proposal lives outside `docs/architecture/`, changes no certified document, and changes no certified document.

| Field | Value |
|---|---|
| Amendment ID | AM-3 |
| Status | **APPROVED** |
| Amends | 08 §4.1, §4.7 |
| Affected requirements | AUTH-001, AUTH-010 |
| Related findings | DEV-003 (conditions IR-22, IR-09, IR-02) |
| Related deviation | DEV-003 |
| Final targeted check classification (56c20ba, verbatim) | TECHNICALLY SOUND |
| Document-level check classification (093cfa6, verbatim) | TECHNICALLY SOUND |
| Certified behavior | Login body {email, password}; no CAPTCHA field or signal. |
| Proposed behavior | Optional turnstile_token (≤ 2048) on login; 401 INVALID_CREDENTIALS carries captcha_required; MFA 401s carry attempts_remaining. Verification runs outside the write lock (IR-02); networks are parsed /24 and /64 (IR-22); the development verifier exists only in local and test (IR-09). The same field carries the challenge escalation of AM-7. |
| Reason | 05 §4 cannot be implemented with the closed 08 §4.1 schema. |
| Implementation (provenance) | Implemented as proposed. |
| Security impact | Implements the certified control; responses stay uniform for known and unknown accounts. |
| Data impact | None. |
| API impact | Optional fields. |
| UI impact | Login shows the widget when required. |
| Compatibility impact | Additive. |
| Rollback or forward-fix | Remove the field; throttling falls back to delays only and AM-7's challenge tier is lost. |
| Required tests | `api/tests/integration/test_auth.py::test_DEV_003_optional_captcha_token_after_network_throttle`<br>`api/tests/integration/test_intake_lock.py`<br>`api/tests/integration/test_auth_remediation.py::test_IR22_*` |
| Staging evidence | Real Turnstile keys in staging (IR-18) before production. |
| Production evidence | Turnstile production secret provisioned. |
| Failure behavior | A required but missing or failed challenge is INVALID_CREDENTIALS with captcha_required; the password is not evaluated. |
| Owner decision required | Approve. |
| Approval readiness | Ready to submit. |
| Decision owner | Architecture Owner |
| Owner decision recorded | APPROVED (2026-09-30). Conditions: None |
