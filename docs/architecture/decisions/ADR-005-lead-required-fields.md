# ADR-005: Public lead form fields and intake rules

- **Status:** Accepted (amended by remediation 01)
- **Date:** 2026-09-29

## Context

Lead capture is the P0 business priority. Friction on the public form lowers conversion, while the business still needs contactability, lawful consent and spam protection. The live website form collects name, phone, email, property type, service, location and brief. It hands off to WhatsApp and has no backend.

## Decision

| Field level | Fields |
|---|---|
| **Required** | `name`, `phone`, consent acknowledgement |
| **Optional** | `email`, `city`, `project_type`, `budget_range`, **`property_type`** (owner Decision 4), `message` |

The public API schema is closed to exactly these fields, plus machine-supplied attribution, CAPTCHA token and honeypot.

**Rules:**

| Rule | Design |
|---|---|
| Enrichment | Staff can add or edit optional and enrichment fields later (LEAD-024, 04 §5.3) |
| Consent | Records policy version, server timestamp and source context (channel, form page, IP) (LEAD-012) |
| Phone | Default region India. International numbers with `+<country code>` are accepted. Invalid numbers are rejected. E.164 storage (LEAD-009). |
| Duplicates | Flagged, never silently discarded (LEAD-010) |
| Property type (Decision 4) | Optional. Values: `APARTMENT`, `INDEPENDENT_HOUSE`, `VILLA`, `OFFICE`, `RETAIL`, `OTHER`. "Home Renovation" is **not** a property type; renovation is PROJECT_TYPE `RENOVATION`. Staff can enrich or correct it later. Unknown or future codes on public intake are kept raw in `intake_unmapped` and never reject the enquiry or corrupt records. Lookups are referenced by id, so deactivated values stay valid on old rows (LEAD-030). |
| Idempotency (F-04) | Key plus a request fingerprint (JCS SHA-256), looked up **before** CAPTCHA. Same fingerprint replays the original response. A different one → `422 IDEMPOTENCY_KEY_REUSED`. |
| No silent loss (F-05) | A honeypot hit stores the lead as `spam_status = SUSPECTED` with the same 201 response, for staff review. Every non-2xx except field-level 422 offers the WhatsApp hand-off. Per-IP limits are relaxed for mobile carrier NAT, with Turnstile as the primary control. |
| Consent withdrawal and retention (F-15) | Withdrawal recorded with channel (LEAD-027). Closed-lead anonymization job (LEAD-028, period OWNER-INPUT-002). Erasure requests (LEAD-029). |
| Abuse protection | Cloudflare Turnstile and rate limiting are required. A honeypot is used. Every block is recorded as a security event (LEAD-018). |
| Error state | Accessible: error summary, focus management, inline messages, not color-only (LEAD-026, 09 §4.11) |
| Fallback | The existing WhatsApp hand-off is preserved when the API is unavailable (LEAD-019) |
| Non-disclosure | The public API returns only a random `public_reference` and a message. It never returns the lead id, number, status, assignee, duplicate state or echoed input, and there is no public read endpoint (LEAD-025). |

## Alternatives considered

| Option | Why rejected |
|---|---|
| Make city, project type and budget required | Adds friction. The owner chose to capture them in enrichment. |
| Reject duplicates | Loses genuine repeat enquiries |
| Return `lead_number` to the enquirer | Exposes sequential business volume (ADR-002) |
| Accept any phone string | Uncontactable leads |
| Keep property type staff-only (frozen draft, ASM-005) | Superseded by owner Decision 4: it is now an optional public field |

## Consequences

- The live site's form needs changes when LEAD-001 is implemented (consent checkbox, optional budget, field codes, error states). **The website is not changed by this freeze.**
- `lead.city` and the other optional fields are nullable. A dashboard widget prompts enrichment.

## Risks

| Risk | Mitigation |
|---|---|
| CAPTCHA friction for real users | Accessible CAPTCHA error with a WhatsApp alternative |
| Invalid international numbers accepted as valid | Validity check by region metadata. Staff can correct. |
| Consent policy version mismatch | `UNKNOWN_POLICY_VERSION` error. Versioned notice (ASM-011). |

## Affected requirement IDs

LEAD-001, LEAD-002, LEAD-009, LEAD-010, LEAD-012, LEAD-018, LEAD-019, LEAD-023, LEAD-024, LEAD-025, LEAD-026, SEC-009

## Affected documents

02 (§2.4), 04 (§2, §5, §7, §13), 08 (§8.4, §8.5), 09 (§4.11), 11 (§5.6, §10), 12 (§4.7)

## Future review triggers

- Conversion-rate data after launch
- Adding property type or other fields to the public form
- Launching international marketing

## Approval record

| Item | Value |
|---|---|
| Approver | Veda Spaces owner (repository owner) |
| Approval | 2026-09-29, `VEDA-SPACES-P0-ARCHITECTURE-SIGNOFF-AND-FREEZE`, decision ADR-005; amended by `VEDA-SPACES-P0-ARCHITECTURE-REMEDIATION-01` Decision 4 (F-17, ASM-005), plus architecture fixes for F-04, F-05 and F-15 |
| Evidence | [decision-log.md](decision-log.md). A verifiable owner sign-off (owner approval of the architecture pull request) is tracked gate TG-01 before implementation (F-18). |
