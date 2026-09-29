# 04 — Lead Management MVP Design

Governing decisions: [ADR-005](decisions/ADR-005-lead-required-fields.md) · [ADR-009](decisions/ADR-009-p0-scope.md)

## 1. Scope

**In P0 (ADR-009):**

- Capture leads from the public website and manually.
- Enrich leads with staff data.
- Pipeline status.
- Assignment.
- Notes, activities and follow-ups.
- Dashboard.
- Soft delete and restore.
- Full audit.

**Deferred (designed, not in P0):**

| Item | Deferred to |
|---|---|
| CSV export (LEAD-017) | P1 |
| Quoted amount capture (LEAD-021) | P1 |
| Auto-assignment (LEAD-022) | P2 |
| Lead merge | Roadmap |

**Out of scope (roadmap only, 10):** quotation documents, customer conversion, attachments, WhatsApp API.

### Domain vocabulary

| Term | Meaning |
|---|---|
| Lead | A prospective client enquiry, before it becomes a customer or project |
| Pipeline | Ordered statuses NEW → … → WON/LOST |
| Owner / assignee | `lead.assigned_to` |
| Enrichment | Staff adding optional or extra data after capture (LEAD-024) |
| Public reference | A random, non-sequential code shown to the enquirer (LEAD-025) |
| Activity | A dated interaction (planned or completed) |
| Note | Internal free-text knowledge |
| Follow-up | A PLANNED activity with a `scheduled_on` |

## 2. Entity: `lead`

The nine audit-contract columns and their actor FKs to `app_user.id` (03 §2) come first.

**Field requirement levels (ADR-005, LEAD-023):**

| Level | Fields |
|---|---|
| **Required on the public form** | `name`, `phone`, consent acknowledgement |
| **Optional on the public form** | `email`, `city`, `project_type`, `budget_range`, `property_type`, `message` (owner Decision 4 added `property_type`) |
| **Staff-only enrichment** | Everything else (`locality`, `priority`, `expected_close_on`, …) |

All optional fields can be added or edited later by staff with `lead.update` (LEAD-024).

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `lead_number` | VARCHAR(20) | NOT NULL | sequence | `VS-L-2026-000123`. **Internal staff display only.** Never in public responses, never an API identifier (ADR-002). |
| `public_reference` | CHAR(9) | NOT NULL | random | `K7M3-Q9TD` style: 8 random Crockford base32 characters, formatted with a hyphen (40 bits). This is the only reference given to the enquirer (LEAD-025). |
| `name` | VARCHAR(150) | NOT NULL | — | **Required** |
| `phone` | VARCHAR(16) | NOT NULL | — | **Required.** Valid E.164 (LEAD-009). |
| `phone_raw` | VARCHAR(30) | NOT NULL | — | As typed |
| `email` | VARCHAR(254) | NULL | — | Optional |
| `email_normalized` | VARCHAR(254) | NULL | — | For duplicate detection |
| `city` | VARCHAR(100) | NULL | — | Optional. Free text from the public form. Staff may normalize it. |
| `locality` | VARCHAR(150) | NULL | — | Staff enrichment |
| `project_type_id` | GUID | NULL | — | Optional. FK → `lookup_value` (PROJECT_TYPE). |
| `property_type_id` | GUID | NULL | — | Optional on the public form. Enrichable by staff. FK → `lookup_value` (PROPERTY_TYPE: APARTMENT, INDEPENDENT_HOUSE, VILLA, OFFICE, RETAIL, OTHER). |
| `budget_range_id` | GUID | NULL | — | Optional. FK → `lookup_value` (BUDGET_RANGE). |
| `message` | TEXT | NULL | — | Optional. Max 4,000 chars, plain text. |
| `status` | CODE(20) | NOT NULL | `'NEW'` | §3 |
| `status_changed_on` | UTCDATETIME | NOT NULL | tx time | |
| `priority` | CODE(10) | NOT NULL | `'MEDIUM'` | `HIGH`, `MEDIUM`, `LOW` |
| `source_id` | GUID | NOT NULL | — | FK → `lookup_value` (LEAD_SOURCE). WEBSITE for public intake. |
| `source_detail` | VARCHAR(200) | NULL | — | |
| `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content` | VARCHAR(100) each | NULL | — | LEAD-011 |
| `landing_page` | VARCHAR(500) | NULL | — | Path + query, PII-stripped |
| `referrer_url` | VARCHAR(500) | NULL | — | |
| `assigned_to` | GUID | NULL | — | FK → `app_user.id` |
| `assigned_on` | UTCDATETIME | NULL | — | |
| `next_follow_up_on` | UTCDATETIME | NULL | — | Derived (§8) |
| `last_activity_on` | UTCDATETIME | NULL | — | Derived |
| `expected_close_on` | DATE | NULL | — | |
| `quoted_amount_minor` | MONEY_MINOR | NULL | — | LEAD-021 (P1). Paise. |
| `currency` | CHAR(3) | NOT NULL | `'INR'` | |
| `won_on` | UTCDATETIME | NULL | — | |
| `lost_on` | UTCDATETIME | NULL | — | |
| `lost_reason_id` | GUID | NULL | — | FK → `lookup_value` (LOST_REASON) |
| `lost_reason_note` | VARCHAR(1000) | NULL | — | |
| `duplicate_status` | CODE(15) | NOT NULL | `'NONE'` | `NONE`, `SUSPECTED`, `CONFIRMED`, `NOT_DUPLICATE` |
| `duplicate_of_lead_id` | GUID | NULL | — | FK → `lead.id` |
| `consent_contact` | BOOL | NOT NULL | false | Consent to be contacted (LEAD-012) |
| `consent_policy_version` | VARCHAR(20) | NULL | — | Privacy notice version acknowledged, for example `2026-09-v1` |
| `consent_captured_on` | UTCDATETIME | NULL | — | Server time of capture |
| `consent_channel` | CODE(20) | NULL | — | Source context: `WEBSITE_FORM`, `PHONE_VERBAL`, `IN_PERSON`, `WHATSAPP`, `EMAIL` |
| `consent_source_page` | VARCHAR(500) | NULL | — | Source context: page path the form was submitted from (website) |
| `consent_ip_address` | VARCHAR(45) | NULL | — | Source context: submitting IP (website) |
| `intake_idempotency_key` | VARCHAR(64) | NULL | — | Client-supplied `Idempotency-Key` (API-007). An opaque key, **not** an entity ID. |
| `intake_request_fingerprint` | CHAR(64) | NULL | — | SHA-256 of the JCS-canonical public request body, excluding `turnstile_token` and the honeypot field (F-04) |
| `intake_unmapped` | JSON | NULL | — | Raw values of optional lookup fields the API could not map (unknown or inactive codes), kept for staff review. The enquiry is never rejected for them (LEAD-030). |
| `spam_status` | CODE(15) | NOT NULL | `'NONE'` | `NONE`, `SUSPECTED` (honeypot hit), `CONFIRMED_SPAM`, `NOT_SPAM` (F-05) |
| `consent_withdrawn_on` | UTCDATETIME | NULL | — | LEAD-027 |
| `consent_withdrawal_channel` | CODE(20) | NULL | — | `PHONE_VERBAL`, `IN_PERSON`, `WHATSAPP`, `EMAIL`, `WEBSITE` |
| `consent_withdrawal_note` | VARCHAR(500) | NULL | — | |
| `search_text` | TEXT | NOT NULL | '' | Application-maintained, casefolded (Unicode `casefold()` + NFKC) concatenation of name, email, phone digits, lead number, public reference, city and locality. Engine-independent search (A-03). |
| `anonymized_on` | UTCDATETIME | NULL | — | Set by erasure or retention anonymization (LEAD-028, LEAD-029) |

### Constraints

| Name | Rule |
|---|---|
| `ck_lead__status` | `status IN ('NEW','CONTACTED','SITE_VISIT','QUOTATION_SENT','NEGOTIATION','WON','LOST')` |
| `ck_lead__priority` / `ck_lead__duplicate_status` / `ck_lead__consent_channel` | Enumerations |
| `ck_lead__won_consistency` | `(status = 'WON') = (won_on IS NOT NULL)` |
| `ck_lead__lost_consistency` | `(status = 'LOST') = (lost_on IS NOT NULL AND lost_reason_id IS NOT NULL)` |
| `ck_lead__assigned_consistency` | `(assigned_to IS NULL) = (assigned_on IS NULL)` |
| `ck_lead__consent_complete` | `consent_contact = false OR (consent_policy_version IS NOT NULL AND consent_captured_on IS NOT NULL AND consent_channel IS NOT NULL)` |
| `ck_lead__quoted_amount` | `quoted_amount_minor IS NULL OR quoted_amount_minor >= 0` |
| `ck_lead__not_self_duplicate` | `duplicate_of_lead_id IS NULL OR duplicate_of_lead_id <> id` |
| `ck_lead__spam_status` | Enumeration |
| `ck_lead__withdrawal_consistency` | `consent_withdrawn_on IS NULL OR (consent_contact = false AND consent_withdrawal_channel IS NOT NULL)` |

### Indexes

| Name | Columns | Predicate | Serves |
|---|---|---|---|
| `ux_lead__lead_number` | `lead_number` | `is_deleted = false` | Staff lookup |
| `ux_lead__public_reference` | `public_reference` | — | Enquirer call-back lookup by staff |
| `ux_lead__intake_idempotency_key` | `intake_idempotency_key` | `intake_idempotency_key IS NOT NULL` | Idempotent intake |
| `ix_lead__status_created` | `status, created_on DESC` | `is_deleted = false` | Pipeline lists |
| `ix_lead__assigned_status` | `assigned_to, status, created_on DESC` | `is_deleted = false` | OWN scope |
| `ix_lead__created_by` | `created_by` | `is_deleted = false` | OWN scope (creator) |
| `ix_lead__phone` | `phone` | `is_deleted = false` | Duplicates, search |
| `ix_lead__email_normalized` | `email_normalized` | `email_normalized IS NOT NULL AND is_deleted = false` | Duplicates |
| `ix_lead__next_follow_up` | `next_follow_up_on` | `status NOT IN ('WON','LOST') AND is_deleted = false` | Due/overdue |
| `ix_lead__created_on` | `created_on DESC` | — | Dashboard |
| `ix_lead__source` | `source_id, created_on DESC` | `is_deleted = false` | Source analytics |
| `ix_lead__spam_queue` | `spam_status, created_on DESC` | `spam_status = 'SUSPECTED' AND is_deleted = false` | Spam review queue |
| `ix_lead__retention` | `status, status_changed_on` | `status IN ('WON','LOST') AND anonymized_on IS NULL` | Retention job (LEAD-028) |

### Foreign keys and audit

- **Foreign keys:** `assigned_to` → `app_user.id`; lookup FKs → `lookup_value.id`; `duplicate_of_lead_id` → `lead.id`; plus the contract actor FKs. All use the GUID type (DATA-012).
- **Lookup-category guard:** the service verifies that each lookup value belongs to the correct category.
- **Audit:** FULL. Diffs exclude `next_follow_up_on`, `last_activity_on` and `search_text`. The PII fields for anonymization are `name`, `phone`, `phone_raw`, `email`, `email_normalized`, `message`, `locality`, `city`, `consent_ip_address`, `consent_source_page`, `intake_unmapped` and `search_text`.
- **Default visibility:** lists and the dashboard exclude `spam_status IN ('SUSPECTED','CONFIRMED_SPAM')` unless the `spam_status` filter is given (08 §8.2).

## 3. Status state machine (LEAD-004, LEAD-005, LEAD-006)

```
          ┌───────────────────────────────────────────────────────────────────┐
          │                       (any open status) ── lead.status.change ──► LOST
  NEW ──► CONTACTED ──► SITE_VISIT ──► QUOTATION_SENT ──► NEGOTIATION ──► WON │
   │          │              │  ▲            │  ▲              │              │
   │          └──────────────┼──┼────────────┘  │              │              │
   │                         │  └── back one step (lead.status.change) ◄──────┘
   └── skip forward allowed
                                                        LOST ── lead.reopen ──► CONTACTED
                                                        WON  ── lead.reopen ──► NEGOTIATION
```

"Open" means NEW, CONTACTED, SITE_VISIT, QUOTATION_SENT, NEGOTIATION.

| From → To | Allowed | Permission | Required input | Side effects |
|---|---|---|---|---|
| Open → later open status (forward, skipping allowed) | Yes | `lead.status.change` | Optional comment | STATUS_CHANGE activity · `status_changed_on` |
| Open → immediately previous status | Yes | `lead.status.change` | Comment **required** | Same |
| Open → earlier status, more than one step back | No | — | — | 422 `INVALID_STATUS_TRANSITION` |
| NEGOTIATION / QUOTATION_SENT → WON | Yes | `lead.status.change` | `won_on` (default now) | Outbox `lead.won`. Cancels PLANNED activities and clears `next_follow_up_on` (§8). |
| NEW / CONTACTED / SITE_VISIT → WON | Yes | `lead.status.change` | Comment required | Same as the row above, including cancellation of PLANNED activities |
| Open → LOST | Yes | `lead.status.change` | `lost_reason_code` required. Note required when the reason is OTHER. | `lost_on`, cancels PLANNED activities, clears `next_follow_up_on` |
| LOST → CONTACTED | Yes | `lead.reopen` | Comment required | Clears lost fields, outbox `lead.reopened` |
| WON → NEGOTIATION | Yes | `lead.reopen` | Comment required | Clears `won_on` |
| WON ↔ LOST directly | No | — | — | Reopen first |
| Same status | No | — | — | 422 `NO_OP_TRANSITION` |

Status changes **only** through `POST /leads/{id}/status` (08 §8.6).

## 4. Lead lifecycle overview

```
 Website form ─┐                    ┌──────────── Sales workflow ────────────┐
 Phone/walk-in ├─► intake ─► NEW ─► assign ─► CONTACTED ─► SITE_VISIT ─► QUOTATION_SENT ─► NEGOTIATION ─► WON
 Referral ─────┘      │                 │                                                                   └► LOST
                      │                 └─ enrichment · activities · notes · follow-ups at every stage
                      └─ validation · consent · duplicate flag · public reference · outbox lead.created
```

## 5. Intake

### 5.1 Public intake (LEAD-001, LEAD-012, LEAD-018, LEAD-019, LEAD-023, LEAD-025, LEAD-030)

Processing order. Cheap checks come first, and idempotency is checked before the single-use CAPTCHA token (F-04, A-09).

```
Browser (www) ── POST /api/v1/public/leads ── headers: Idempotency-Key ── body: approved fields + consent + attribution
                                                                               + turnstile_token + honeypot field
  1 Cloudflare edge rate limit + WAF
  2 body ≤ 16 KB; JSON parse; CLOSED schema (unknown field → 422 UNKNOWN_FIELD)
  3 application rate limit per IP (single-process limiter, OPS-010)          → 429 + PUBLIC_INTAKE_BLOCKED
  4 IDEMPOTENCY (before CAPTCHA):
       fingerprint = SHA-256(JCS(body minus turnstile_token and honeypot))
       key found ∧ fingerprint equal     → return the ORIGINAL 201 body; nothing else runs (no CAPTCHA re-check)
       key found ∧ fingerprint differs   → 422 IDEMPOTENCY_KEY_REUSED
  5 Turnstile verification (server-to-server)                                 → 422 CAPTCHA_FAILED + PUBLIC_INTAKE_BLOCKED
  6 validation: name, phone (LEAD-009), consent.acknowledged = true, known policy_version
       optional lookup codes (project_type, budget_range, property_type): unknown or inactive → field stored NULL,
       raw value kept in intake_unmapped (LEAD-030); the enquiry is NOT rejected
  7 honeypot non-empty → spam_status = SUSPECTED (the lead IS stored, in the spam review queue); the response is identical
  8 normalize; source = WEBSITE; consent context captured; search_text built
  9 duplicate check (§7) → duplicate_status flag (never rejects)
 10 actor WEB_INTAKE, via PUBLIC_FORM; lead_number + public_reference; insert lead with intake_idempotency_key and
    intake_request_fingerprint; system activity; audit_log CREATE; outbox lead.created (not for SUSPECTED spam)
    — all in ONE transaction
 11 commit → 201 { reference: public_reference, message }
```

**Latency target (NFR-003).** p95 < 800 ms end to end, including Turnstile verification. Email is not on the request path.

**Public response contract (LEAD-025).** Every accepted submission, including a suspected-spam one, gets the **same** `201 {reference, message}` shape with a real random reference. So:

- there is no silent drop (F-05);
- bots cannot distinguish the honeypot (A-14);
- no lead id, `lead_number`, status, assignee, duplicate or spam state, timestamps or echoed input is ever returned;
- there is no public read endpoint.

**Honeypot markup (F-05).** The trap field is:

- named `company_website_url`, a name that password managers and autofill don't target;
- given `autocomplete="off"`, `tabindex="-1"` and `aria-hidden="true"`;
- positioned off-screen with CSS rather than `display:none`;
- excluded from the accessible form summary.

Because a hit only quarantines, a false positive from autofill loses nothing: staff review the Spam queue (09 §4.3) and mark `NOT_SPAM`, which releases the lead into the normal pipeline and triggers `lead.created` notifications.

**Non-success responses and the website (F-05, LEAD-019).**

| Response | Website behavior |
|---|---|
| 201 | Confirmation panel showing the reference |
| 422 with field errors (`VALIDATION_FAILED`, `CONSENT_REQUIRED`) | Inline accessible errors. The user can correct and resubmit. |
| Every other non-2xx (422 `CAPTCHA_FAILED`, 428, 413, 429, 5xx), a network error, or an 8-second timeout | The WhatsApp hand-off is offered **prominently** with the prefilled text, together with the specific message (09 §4.11). No path ends without either a stored lead or a WhatsApp route. |

**Website form mapping.** This is implemented with LEAD-001. It is not a change to the live site in this remediation.

| Website field | Public API field | Lead column | Level |
|---|---|---|---|
| Full Name | `name` | `name` | Required |
| Phone Number | `phone` | `phone_raw` → `phone` | Required |
| *(new)* Consent checkbox and privacy notice link | `consent.acknowledged`, `consent.policy_version` | `consent_*` | Required |
| Email Address | `email` | `email` | Optional |
| Project Location | `city` | `city` (free text) | Optional |
| Property Type (select; **becomes optional**) | `property_type_code` | `property_type_id` | Optional |
| Service Required (select; becomes optional) | `project_type_code` | `project_type_id` | Optional |
| *(new)* Budget select | `budget_range_code` | `budget_range_id` | Optional |
| Brief Description | `message` | `message` | Optional |
| URL `utm_*`, page, `document.referrer` | `attribution` | Attribution and `consent_source_page` | Automatic |

**Live-option reconciliation (owner Decision 4).**

| Live option | New code |
|---|---|
| Property Type "Apartment / Flat" | `APARTMENT` |
| Property Type "Independent House / Villa" | Split into two options: `INDEPENDENT_HOUSE` and `VILLA` |
| Property Type "Home Renovation" | **Removed** from Property Type. It moves to Service Required as PROJECT_TYPE `RENOVATION`. |
| Property Type "Other" | `OTHER` |
| *(new)* | `OFFICE`, `RETAIL` |

**Fallback (LEAD-019).** The existing WhatsApp hand-off is preserved unchanged.

### 5.2 Manual intake (LEAD-003)

- Requires `lead.create`. Source is required and can't be WEBSITE.
- `name` and `phone` are required. Other fields are optional.
- Consent is optional. When recorded, the channel (`PHONE_VERBAL`, `IN_PERSON`, …) and policy version are required by `ck_lead__consent_complete`.
- If the actor's `lead.read` scope is OWN, `assigned_to` defaults to the actor.
- The UI runs the duplicate check before save and shows matches within the actor's scope.

### 5.3 Enrichment (LEAD-024)

- Staff with `lead.update` (in scope) can fill or correct any optional or enrichment field at any stage through `PATCH /leads/{id}` (08 §8.5).
- The lead detail view highlights empty optional fields ("Add budget", "Add project type") to prompt enrichment after the first call.
- Every change is audited.

### 5.4 Consent withdrawal (LEAD-027)

- `POST /leads/{id}/consent/withdraw {channel, note}` requires `lead.update` in scope and `If-Match`.
- Effect, in one transaction:
  - `consent_contact = false`, `consent_withdrawn_on = now`, and the channel and note are recorded;
  - PLANNED contact activities (CALL, WHATSAPP, EMAIL, MEETING, SITE_VISIT, FOLLOW_UP) are cancelled with the reason `CONSENT_WITHDRAWN`;
  - `next_follow_up_on` is cleared;
  - a system activity is written, plus an audit UPDATE.
- **After withdrawal:**
  - The UI shows a **Do not contact** banner, and the Call and WhatsApp buttons require an explicit acknowledgment.
  - Planning new contact activities returns `422 CONSENT_WITHDRAWN`.
  - Outbound marketing is never sent.
- The original consent record (`consent_policy_version`, `consent_captured_on`, context) is kept as evidence.
- Re-consent is recorded as a new consent capture through `PATCH` of the `consent_*` fields, with the channel and policy version. It is audited.

### 5.5 Spam review (LEAD-018, F-05)

- `GET /leads?spam_status=SUSPECTED` (`lead.read`, scope ALL in practice) lists quarantined leads.
- `POST /leads/{id}/spam-resolution {resolution: NOT_SPAM | CONFIRMED_SPAM}` (`lead.update`, `If-Match`):
  - **NOT_SPAM** releases the lead and emits `lead.created`.
  - **CONFIRMED_SPAM** keeps the lead hidden. It can be soft-deleted, and becomes eligible for purge by retention (§14).
- **Ageing (N-A3).** A daily scheduled job sends holders of `lead.update` at scope ALL an in-app notification and an email summarizing SUSPECTED leads. Any SUSPECTED lead older than the configured review age (initial default 1 working day) raises an operational alert, so a false positive is never silently parked.

## 6. Assignment (LEAD-007, LEAD-022)

| Rule | Detail |
|---|---|
| Permission | `lead.assign` |
| Eligible assignees | Active HUMAN users holding `lead.read`, resolved by permission |
| Effects | Sets `assigned_to` and `assigned_on` · ASSIGNMENT activity · outbox `lead.assigned` → notify the assignee |
| Unassign | Allowed with the same permission |
| Disabled assignee | Their open leads appear in the dashboard's "Needs reassignment" widget |
| Auto-assign | P2 (deferred) |

## 7. Duplicate detection (LEAD-010)

- **Match rule.** Another live lead with the same `phone`, or the same `email_normalized`, created within the last 180 days.
- **Outcome.** The new lead is **always stored**, with `duplicate_status = SUSPECTED` and `duplicate_of_lead_id` set. Submissions are never rejected or silently discarded for being duplicates.
- **Resolution** needs `lead.update`: CONFIRMED (typically then LOST with reason DUPLICATE) or NOT_DUPLICATE. A client-supplied `duplicate_of_lead_id` is loaded through the scoped repository. If it is outside the actor's scope, the response is `404 NOT_FOUND`, identical to a non-existent lead (A-07).
- **Privacy.** Public intake never reveals duplicate status (LEAD-025). Staff see only matches within their scope.

## 8. Follow-ups (LEAD-015)

- A follow-up is a PLANNED `lead_activity` with `scheduled_on`.
- `lead.next_follow_up_on` = min(`scheduled_on`) over PLANNED, non-deleted activities. It is recomputed on every activity change within the same transaction.
- Overdue means `next_follow_up_on < now`.
- WON or LOST cancels all PLANNED activities.
- Reminders and the daily digest are P1 (NOTIF-006).

## 9. Entity: `lead_note` (NOTE-*)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `lead_id` | GUID | NOT NULL | — | FK → `lead.id` |
| `body` | TEXT | NOT NULL | — | 1–10,000 chars, plain text |
| `is_pinned` | BOOL | NOT NULL | false | NOTE-003 (P1 UI) |
| `visibility` | CODE(20) | NOT NULL | `'INTERNAL'` | `INTERNAL`. `CUSTOMER_VISIBLE` is reserved and rejected in P0 (NOTE-004). |

- **Checks:** `visibility IN ('INTERNAL','CUSTOMER_VISIBLE')`
- **Indexes:**
  - `ix_lead_note__lead_created` (`lead_id`, `is_pinned` DESC, `created_on` DESC) WHERE `is_deleted = false`
  - `ix_lead_note__created_by` (`created_by`) WHERE `is_deleted = false`
- **Foreign keys:** `lead_id` → `lead.id`, plus contract actor FKs.
- **Audit:** FULL, with parent (`lead`, `lead_id`).
- **Deleted parent:** creating, editing or listing notes on a soft-deleted lead returns `404 NOT_FOUND`.
- **Deletion:** note deletion is a confirmed soft delete. There is **no Undo** in P0 and no note-restore endpoint (F-20).
- **Authorization:**
  - Read requires `lead_note.read` and a visible parent lead.
  - Update and delete with OWN scope are limited to notes the actor authored.

## 10. Entity: `lead_activity` (ACT-*)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `lead_id` | GUID | NOT NULL | — | FK → `lead.id` |
| `activity_type` | CODE(20) | NOT NULL | — | `CALL`, `WHATSAPP`, `EMAIL`, `MEETING`, `SITE_VISIT`, `QUOTATION`, `FOLLOW_UP`, `STATUS_CHANGE`, `ASSIGNMENT`, `SYSTEM` |
| `is_system_generated` | BOOL | NOT NULL | false | Read-only in the API |
| `activity_status` | CODE(12) | NOT NULL | `'COMPLETED'` | `PLANNED`, `COMPLETED`, `CANCELLED` |
| `subject` | VARCHAR(200) | NOT NULL | — | |
| `description` | TEXT | NULL | — | Max 4,000 |
| `direction` | CODE(10) | NULL | — | `INBOUND`, `OUTBOUND` |
| `scheduled_on` | UTCDATETIME | NULL | — | Required when PLANNED |
| `completed_on` | UTCDATETIME | NULL | — | Required when COMPLETED |
| `duration_minutes` | INTEGER | NULL | — | 0–1440 |
| `outcome_id` | GUID | NULL | — | FK → `lookup_value` (ACTIVITY_OUTCOME) |
| `owner_user_id` | GUID | NOT NULL | actor | FK → `app_user.id` |
| `location` | VARCHAR(300) | NULL | — | |
| `from_status` | CODE(20) | NULL | — | STATUS_CHANGE only |
| `to_status` | CODE(20) | NULL | — | STATUS_CHANGE only |
| `cancelled_reason` | VARCHAR(300) | NULL | — | |
| `metadata` | JSON | NULL | — | |

### Constraints

| Name | Rule |
|---|---|
| `ck_lead_activity__type` / `ck_lead_activity__status` | Enumerations |
| `ck_lead_activity__planned_has_schedule` | `activity_status <> 'PLANNED' OR scheduled_on IS NOT NULL` |
| `ck_lead_activity__completed_has_time` | `activity_status <> 'COMPLETED' OR completed_on IS NOT NULL` |
| `ck_lead_activity__status_change_fields` | `activity_type <> 'STATUS_CHANGE' OR (from_status IS NOT NULL AND to_status IS NOT NULL)` |
| `ck_lead_activity__duration` | `duration_minutes IS NULL OR duration_minutes BETWEEN 0 AND 1440` |

### Indexes

| Name | Columns | Predicate |
|---|---|---|
| `ix_lead_activity__lead_timeline` | `lead_id, created_on DESC` | `is_deleted = false` |
| `ix_lead_activity__owner_planned` | `owner_user_id, scheduled_on` | `activity_status = 'PLANNED' AND is_deleted = false` |
| `ix_lead_activity__lead_planned` | `lead_id, scheduled_on` | `activity_status = 'PLANNED' AND is_deleted = false` |

### Foreign keys, audit and rules

- **Foreign keys:** `lead_id`, `owner_user_id` → `app_user.id`, `outcome_id`, plus contract actor FKs.
- **Deleted parent:** any activity operation on a soft-deleted lead returns `404 NOT_FOUND`.
- **Audit:** FULL, with parent (`lead`, `lead_id`).
- **Lifecycle:**
  - PLANNED → COMPLETED or CANCELLED.
  - COMPLETED → PLANNED isn't allowed.
  - System-generated rows are immutable through the API.
- **Contact buttons (ACT-005, P1).** Call and WhatsApp buttons prompt a prefilled quick-log.

## 11. Dashboard metrics (LEAD-014)

All metrics respect the viewer's `lead.read` scope.

| Widget | Definition |
|---|---|
| Pipeline by status | Count of live leads per open status + WON/LOST closed in period |
| New leads | Created in period vs previous period |
| Unassigned | Open leads with `assigned_to IS NULL` |
| Follow-ups due today / overdue | PLANNED activities by window |
| Conversion rate | WON ÷ (WON + LOST) closed in period |
| Median time to first contact | created_on → first completed CALL/WHATSAPP/MEETING |
| Leads by source | Count by `source_id` |
| Needs enrichment | Open leads missing `project_type_id` or `budget_range_id` (LEAD-024) |

## 12. Lead permissions summary

The full catalog is in 06 §6.3.

| Permission | Guards |
|---|---|
| `lead.create` | Manual create |
| `lead.read` (scope) | List, detail, dashboard, duplicates |
| `lead.update` (scope) | Enrichment and edits, duplicate resolution |
| `lead.status.change` (scope) | Transitions, WON/LOST |
| `lead.reopen` (scope) | Reopen |
| `lead.assign` (scope) | Assign or unassign |
| `lead.delete` (scope) | Soft delete |
| `lead.restore` | Restore, view deleted |
| `lead.export` | CSV export (P1) |
| `lead.erase` | Execute an erasure request (§14) |
| `lead_note.*`, `lead_activity.*` (scope) | Notes, activities |

## 13. Validation rules

| Field | Rule | Error code |
|---|---|---|
| name | Required. 2–150 chars after trim. At least one letter. | `REQUIRED`, `INVALID_NAME` |
| phone | Required. Parsed with libphonenumber, **default region IN** when no `+` country code is given (a 10-digit Indian mobile such as `98765 43210` becomes `+919876543210`). Numbers with an explicit `+<country code>` are accepted for any region. Must be valid for its region (`is_valid_number`). Stored as E.164 (max 15 digits). | `REQUIRED`, `INVALID_PHONE` |
| consent (public) | `acknowledged` must be true. `policy_version` must match a published version. | `CONSENT_REQUIRED`, `UNKNOWN_POLICY_VERSION` |
| email | Optional. RFC 5322 practical subset. ≤ 254. | `INVALID_EMAIL` |
| city | Optional. ≤ 100. | `TOO_LONG` |
| source / lost_reason (staff API) | Active code in the correct category | `INVALID_LOOKUP` |
| project_type / budget_range / property_type (staff API) | Active code in the correct category | `INVALID_LOOKUP` |
| project_type / budget_range / property_type (**public API**) | Unknown or inactive → stored NULL, raw value kept in `intake_unmapped`. Never rejects the enquiry (LEAD-030). | — |
| message | Optional. ≤ 4,000. Control characters stripped. | `TOO_LONG` |
| quoted_amount (P1) | ≥ 0 | `OUT_OF_RANGE` |
| assigned_to | Active HUMAN user holding `lead.read`. Canonical GUID. | `INVALID_ASSIGNEE`, `INVALID_ID` |

## 14. Retention, erasure and anonymization (LEAD-028, LEAD-029, AUDIT-011)

### 14.1 Closed-lead retention job (LEAD-028)

| Item | Design |
|---|---|
| Scope | Leads with status WON or LOST (or `CONFIRMED_SPAM`) whose `status_changed_on` is older than `LEAD_RETENTION_DAYS`, and that are not linked to a customer (a future module) |
| Action | Anonymize: PII fields (§2 Audit) are replaced by placeholders (`name = "Anonymized lead"`, other PII NULL or empty) through the ORM. `anonymized_on` is set. Related `lead_note.body` and `lead_activity.description` and `location` are replaced with `"[anonymized]"`. Audit payloads for the lead and its children are anonymized by the 07 §8.2 procedure. An ANONYMIZE audit row is written. |
| Configuration | `LEAD_RETENTION_DAYS` and `LEAD_RETENTION_ENABLED`. **The period is owner input OWNER-INPUT-002.** The job ships **disabled** and cannot be enabled in production without an approved value. It is testable with test configuration. |
| Run | Daily, as SYSTEM, from the maintenance CLI, in batches, with a summary security event |

### 14.2 Erasure request (LEAD-029)

| Step | Design |
|---|---|
| Intake | A data principal's request arrives through the published privacy contact. Staff record it as a note with the request reference. |
| Execute | `POST /leads/{id}/erasure {request_ref, legal_basis, reason}` requires `lead.erase` (sensitive, DESTRUCTIVE), step-up (G10) and `If-Match`. In the request transaction, the live lead and child fields are anonymized. An outbox job then has the maintenance CLI anonymize the historical audit payloads (07 §8.2 steps 2, 5 and 6). The lead shows `erasure.audit_status` = `PENDING` until the job completes (`COMPLETED`), and failures alert. |
| Refusal | When a legal hold or legitimate retention need applies, the request is recorded and refused with a reason. `422 ERASURE_BLOCKED` with the basis. |
| Evidence | ANONYMIZE audit row with `legal_basis` and `request_ref`, and a `SENSITIVE_ACTION` security event. Security events never contained lead PII (SEVT-003). |
| Irreversibility | Not undoable. The UI requires typing the lead number to confirm. |
