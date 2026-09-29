# ADR-005: Public lead form fields and intake rules

- **Status:** Accepted
- **Date:** 2026-09-29

## Context

Lead capture is the P0 business priority. Friction on the public form lowers conversion, while the business still needs contactability, lawful consent and spam protection. The live website form collects name, phone, email, property type, service, location and brief. It hands off to WhatsApp and has no backend.

## Decision

| Field level | Fields |
|---|---|
| **Required** | `name`, `phone`, consent acknowledgement |
| **Optional** | `email`, `city`, `project_type`, `budget_range`, `message` |

The public API schema is closed to exactly these fields, plus machine-supplied attribution, CAPTCHA token and honeypot.

**Rules:**

| Rule | Design |
|---|---|
| Enrichment | Staff can add or edit optional and enrichment fields later (LEAD-024, 04 §5.3) |
| Consent | Records policy version, server timestamp and source context (channel, form page, IP) (LEAD-012) |
| Phone | Default region India. International numbers with `+<country code>` are accepted. Invalid numbers are rejected. E.164 storage (LEAD-009). |
| Duplicates | Flagged, never silently discarded (LEAD-010) |
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
| Allow the website's "Property Type" as an extra optional field | Not in the approved list. Captured by staff instead (ASM-005). The owner may amend. |

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
