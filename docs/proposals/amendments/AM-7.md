# AM-7: proposed amendment to 08 §12, 05 §4

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It lives outside `docs/architecture/`, does not modify the certified documents, and has no effect until the decision owner approves it. Nothing here claims owner approval or implementation authorization.

| Field | Value |
|---|---|
| Amendment ID | AM-7 |
| Amends | 08 §12, 05 §4 |
| Related findings | IR-23, RR-04 |
| Related deviation | DEV-007 |
| Targeted re-review assessment | Previous text REJECTED AS WRITTEN (OD-1): its security statement was false for MFA holders and reset-email volume. Replaced by this layered proposal. |
| Existing certified behavior | POST /auth/login 5/min per email; POST /auth/password/forgot 3/hour per email (08 §12); per-account throttles of 05 §4. |
| Proposed behavior | Layered limits; none locks an account out, and known and unknown identifiers behave identically. (1) Source network: 10/min per client IP (IPv6 per /64) and 30/min per wide network (IPv4 /24, IPv6 /48) on login; 5/min and 20/min on forgot; 10/min per IP on MFA verify, MFA recovery, enroll confirm, email verify and email cancel. (2) Identifier per network: 5/min login and 3/hour forgot per (HMAC of the normalized email, /24 or /64) — so a third party cannot rate-limit the victim everywhere (IR-23). (3) Account budget across all networks: 10 password failures in 15 minutes → every further attempt for that identifier needs a solved Turnstile challenge, from any network; 20 → attempts are also spaced by an escalating interval (2 s doubling to 30 s, 429 + Retry-After). A correct password is not evaluated without the challenge, which closes the MFA_REQUIRED password oracle. A successful sign-in does not reset the budget; it decays with the window. (4) Aggregate: 200 failures across all identifiers in 5 minutes → challenge for every sign-in until the window drains. (5) MFA: 10 MFA, recovery or enrollment-confirmation failures per account in 15 minutes → MFA throttled 15 minutes (05 §4, unchanged). (6) Recovery (reset emails): at most 3 reset emails per account per hour across all networks; further requests get the identical 202 and send nothing. (7) Certified per-(account, network) throttle and the 5-network global lock for accounts without a factor (05 §4) are unchanged. Client address: CF-Connecting-IP is believed only from configured trusted-proxy peers, each at most /24 (IPv4) or /64 (IPv6); otherwise the TCP peer is the client. State is in-process (one application process, OPS-010) and capped at 50 000 keys per table (expired entries evicted first, then the oldest). Keys and events carry an HMAC of the email, never the address. |
| Reason | Keep IR-23 (no victim lock-out from a third party's network) while restoring a cross-network bound on password guessing for every account, including MFA holders, and on reset-email volume. |
| Code behavior at this commit | Implemented at this commit: api/veda/platform/auth/throttle.py (account budget, aggregate, reset cap, bounded tables), api/veda/kernel/ratelimit.py (wide-network and hashed identifier keys), api/veda/platform/auth/service.py (login and forgot), api/veda/platform/auth/routes.py (endpoint limits), api/veda/config.py (trusted-proxy prefix bound). |
| Security | Correction of the earlier text: per-account throttling did NOT bound guessing for MFA holders — the certified global lock exempts accounts with a factor, and a correct password returned MFA_REQUIRED from any number of networks. Now: distributed guessing against one account is limited to 10 unchallenged attempts per 15 minutes, then one solved challenge per attempt, then at most one attempt per 30 s. Victim-targeted denial of service is bounded to a challenge plus at most 30 s; nobody is locked out except accounts without a factor under the certified 05 §4 lock. Provider failure: if Turnstile verification fails or is unreachable while a challenge is required, sign-in for that identifier fails closed until the window drains (≤ 15 minutes); identifiers not under escalation are unaffected. Residual: an attacker with a human-solvable challenge budget can still make slow guesses; eviction under a flood of fresh identifiers is itself covered by the aggregate tier. |
| Data impact | None (in-process state). |
| API impact | 429 with Retry-After on the delay tier; captcha_required on the challenge tier (AM-3). |
| UI impact | Login already renders the challenge when captcha_required is set. |
| Compatibility | Additive. |
| Rollback | Remove tiers (3), (4) and (6): the MFA-holder guessing gap of RR-04 returns. Not recommended. |
| Tests | `api/tests/integration/test_layered_limiter.py`<br>`api/tests/integration/test_auth_remediation.py::test_IR23_P5_third_party_cannot_rate_limit_the_victim_from_elsewhere`<br>`api/tests/unit/test_config_environments.py (trusted-proxy prefix)` |
| Owner decision requested | Approve the layered design and thresholds, or set different thresholds (OD-1: AM-7 as written rejected). |
| Staging evidence | Real Turnstile keys; proxy CIDR as deployed; load probe of the thresholds. |
| Production evidence | Alarm on ACCOUNT_THROTTLED scope account_* and on aggregate escalation (metric to be added with RG-5). |
| Approval readiness | New text; behaviour matches. Requires the reviewer's confirmation before submission. |
| Decision owner | Architecture Owner, Security |
| Status | **PROPOSED, NOT APPROVED** |
