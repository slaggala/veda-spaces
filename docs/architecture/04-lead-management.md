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

> Traces: LEAD-002, LEAD-004, LEAD-006, LEAD-007, LEAD-008, LEAD-010, LEAD-015

The nine audit-contract columns and their actor FKs to `app_user.id` (03 §2) come first.

**Field requirement levels (ADR-005, LEAD-023):**

| Level | Fields |
|---|---|
| **Required on the public form** | `name`, `phone`, consent acknowledgement |
| **Optional on the public form** | `email`, `city`, `project_type`, `budget_range`, `message` |
| **Staff-only enrichment** | Everything else (`locality`, `property_type`, `priority`, `expected_close_on`, …) |

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
| `property_type_id` | GUID | NULL | — | Staff enrichment. FK → `lookup_value` (PROPERTY_TYPE). |
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

### Foreign keys and audit

- **Foreign keys:** `assigned_to` → `app_user.id`; lookup FKs → `lookup_value.id`; `duplicate_of_lead_id` → `lead.id`; plus the contract actor FKs. All use the GUID type (DATA-012).
- **Lookup-category guard:** the service verifies that each lookup value belongs to the correct category.
- **Audit:** FULL. Diffs exclude `next_follow_up_on` and `last_activity_on`. The PII fields for anonymization are `name`, `phone`, `phone_raw`, `email`, `email_normalized`, `message`, `locality`, `consent_ip_address`.

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
| NEGOTIATION / QUOTATION_SENT → WON | Yes | `lead.status.change` | `won_on` (default now) | Outbox `lead.won` |
| NEW / CONTACTED / SITE_VISIT → WON | Yes | `lead.status.change` | Comment required | Same |
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

### 5.1 Public intake (LEAD-001, LEAD-012, LEAD-018, LEAD-019, LEAD-023, LEAD-025)

```
Browser (www) ── POST /api/v1/public/leads ─────────────────────────────────────────────────► API
  headers: Idempotency-Key            body: approved fields + consent + attribution + turnstile_token + honeypot
  1 Cloudflare edge rate limit + WAF (LEAD-018)
  2 body ≤ 16 KB · schema allows ONLY the approved public fields (unknown field → 422)
  3 honeypot non-empty → security event PUBLIC_INTAKE_BLOCKED (reason HONEYPOT); 202 generic body; no lead
  4 Turnstile verification server-to-server → failure: security event PUBLIC_INTAKE_BLOCKED (CAPTCHA_FAILED); 422
  5 app rate limit per IP → 429 + security event PUBLIC_INTAKE_BLOCKED (RATE_LIMITED)
  6 idempotency: intake_idempotency_key already stored → return the ORIGINAL 201 body (no new lead)
  7 validate: name, phone (LEAD-009), consent_acknowledged = true, policy version known
  8 normalize; map optional codes; source = WEBSITE; consent_channel = WEBSITE_FORM; consent context captured
  9 duplicate check (§7) → duplicate_status flag — the submission is ALWAYS stored (LEAD-010)
 10 actor = WEB_INTAKE, via = PUBLIC_FORM; lead_number + public_reference; insert lead;
    system activity "Enquiry received via website"; audit_log CREATE; outbox lead.created   (one transaction)
 11 commit → 201 { reference: public_reference, message }  — nothing else (LEAD-025)
```

**Latency target (NFR-003).** p95 < 800 ms end to end, including Turnstile verification. Email is not on the request path.

**Public response contract (LEAD-025).** The response contains only `reference` (the random `public_reference`) and a static `message`.

- It never contains the lead `id`, `lead_number`, status, assignee, duplicate state, timestamps or any echo of input.
- Error responses contain field-level validation codes only.
- There is no public read endpoint for leads.

**Honeypot and CAPTCHA rejections** are bot-traffic controls, not duplicate handling. Every rejection is recorded as a `PUBLIC_INTAKE_BLOCKED` security event with reason and IP (SEVT-002), so blocked traffic is observable and never silently lost. Real enquirers who fail CAPTCHA see an accessible error and the WhatsApp alternative (09 §4.11).

**Website form mapping.** This is implemented when LEAD-001 is built. It is not a change to the live site in this freeze.

| Website field (live today) | Public API field | Lead column | Level |
|---|---|---|---|
| Full Name | `name` | `name` | Required |
| Phone Number | `phone` | `phone_raw` → `phone` | Required |
| *(new)* Consent checkbox + privacy notice link | `consent.acknowledged`, `consent.policy_version` | `consent_*` | Required |
| Email Address | `email` | `email` | Optional |
| Project Location | `city` | `city` (free text) | Optional |
| Service Required | `project_type_code` | `project_type_id` | Optional |
| *(new)* Budget select | `budget_range_code` | `budget_range_id` | Optional |
| Brief Description | `message` | `message` | Optional |
| Property Type | *not accepted by the public API* | Staff enrichment into `property_type_id` | See ASM-005 |
| URL `utm_*`, page path, `document.referrer` | `attribution` (metadata, not user-entered) | Attribution columns and `consent_source_page` | Captured automatically |

**Fallback (LEAD-019).** On a network error, a timeout (8 s) or a 5xx, the website runs the existing WhatsApp hand-off with the same prefilled text. The live WhatsApp behavior is preserved unchanged.

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
- **Resolution** needs `lead.update`: CONFIRMED (typically then LOST with reason DUPLICATE) or NOT_DUPLICATE.
- **Privacy.** Public intake never reveals duplicate status (LEAD-025). Staff see only matches within their scope.

## 8. Follow-ups (LEAD-015)

- A follow-up is a PLANNED `lead_activity` with `scheduled_on`.
- `lead.next_follow_up_on` = min(`scheduled_on`) over PLANNED, non-deleted activities. It is recomputed on every activity change within the same transaction.
- Overdue means `next_follow_up_on < now`.
- WON or LOST cancels all PLANNED activities.
- Reminders and the daily digest are P1 (NOTIF-006).

## 9. Entity: `lead_note` (NOTE-*)

> Traces: NOTE-001, NOTE-002

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
- **Authorization:**
  - Read requires `lead_note.read` and a visible parent lead.
  - Update and delete with OWN scope are limited to notes the actor authored.

## 10. Entity: `lead_activity` (ACT-*)

> Traces: ACT-001, ACT-002, ACT-003, ACT-004

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

> Traces: LEAD-016

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
| `lead_note.*`, `lead_activity.*` (scope) | Notes, activities |

## 13. Validation rules

> Traces: LEAD-009

| Field | Rule | Error code |
|---|---|---|
| name | Required. 2–150 chars after trim. At least one letter. | `REQUIRED`, `INVALID_NAME` |
| phone | Required. Parsed with libphonenumber, **default region IN** when no `+` country code is given (a 10-digit Indian mobile such as `98765 43210` becomes `+919876543210`). Numbers with an explicit `+<country code>` are accepted for any region. Must be valid for its region (`is_valid_number`). Stored as E.164 (max 15 digits). | `REQUIRED`, `INVALID_PHONE` |
| consent (public) | `acknowledged` must be true. `policy_version` must match a published version. | `CONSENT_REQUIRED`, `UNKNOWN_POLICY_VERSION` |
| email | Optional. RFC 5322 practical subset. ≤ 254. | `INVALID_EMAIL` |
| city | Optional. ≤ 100. | `TOO_LONG` |
| project_type / budget_range / source / lost_reason / property_type | Active code in the correct category | `INVALID_LOOKUP` |
| message | Optional. ≤ 4,000. Control characters stripped. | `TOO_LONG` |
| quoted_amount (P1) | ≥ 0 | `OUT_OF_RANGE` |
| assigned_to | Active HUMAN user holding `lead.read`. Canonical GUID. | `INVALID_ASSIGNEE`, `INVALID_ID` |
