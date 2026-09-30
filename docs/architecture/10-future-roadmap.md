# 10 — Future Expansion Plan

Governing decisions: [ADR-008](decisions/ADR-008-aws-hosting.md) · [ADR-009](decisions/ADR-009-p0-scope.md)

> **Roadmap only. Not authorized for implementation (ADR-009, PLAT-012).** The P0 architecture freeze covers only authentication, MFA, RBAC, user management, audit logging, security-event logging, lead capture, notes, activities, lead administration, the notification foundation and PostgreSQL migration readiness.
>
> Everything in this document is out of P0 scope. That includes customer, quotation, project, design, vendor, procurement, inventory, employee, onboarding, payroll, portal, warranty, finance, attachments, org units and AI. It shows how those modules *would* attach without schema rewrites. Each needs its own requirements (under the reserved prefixes in 01 §4), design, ADRs and review before any implementation.

## 1. What makes expansion rewrite-free

Every future module plugs into the same six foundation mechanisms. **None of them needs to change** to add a module.

| Mechanism | What a new module does | What stays untouched |
|---|---|---|
| Audit contract (03 §2) | Its tables inherit the nine columns and register an audit policy | Kernel, audit_log |
| GUID ids (UUIDv7, service-generated, ADR-002) | Any table can reference any other without coordination. Imports and syncs get ids from the service layer with no DB sequences. | All existing keys |
| Permission registry + scope (06) | Adds codes under its namespace (`project.*`, `po.*`) and grants them to roles via a migration | RBAC tables, resolver, UI matrix (renders new modules automatically) |
| Lookups (03 §6) | Adds categories (for example `PROJECT_STAGE_TEMPLATE`, `UOM`, `LEAVE_TYPE`) | Lookup tables and API |
| Number sequences | Adds keys (`PROJECT` → `VS-P-2027-000045`, `PO` → `VS-PO-…`) | Sequence table |
| Outbox events | Subscribes to upstream events (`lead.won`) and publishes its own | Outbox table, worker |

## 2. Schema evolution rules

1. **Additive-only in place.** New tables, new nullable columns, new indexes, new lookup values, new permission codes and new enum values (CHECK constraints widened in a migration) are allowed.
2. **Expand → migrate → contract** for anything else. For example, to split `lead.city` into a city reference:
   - Add a `city_id` FK.
   - Backfill it (audited, actor SYSTEM, via MIGRATION).
   - Dual-read for one release.
   - Stop writing the old column.
   - Drop it in a later release.
3. Columns and tables are never renamed. Add new ones and deprecate the old.
4. Every table is created by its owning module's migration chain. Cross-module FKs point only upstream (§3 dependency graph).
5. Polymorphic tables (`audit_log`, `attachment`, `outbox_event`, `notification`) use `(entity_type, entity_id)`, so new entities need no schema change to use them.

## 3. Module roadmap

### 3.1 Dependency graph

```
                                    PLATFORM (identity · RBAC · audit · lookups · sequences · outbox · notifications)
                                                     │
                 ┌───────────────┬───────────────────┼─────────────────────┬─────────────────────┐
                 ▼               ▼                   ▼                     ▼                     ▼
              ORG units       ATT attachments     CRM: LEAD (P0)        HR: EMP              VEND vendors
                 │               │                   │ lead.won            │                     │
                 │               │                   ▼                     ├─► ONB onboarding    │
                 │               │               CUST customer             └─► PAY payroll       │
                 │               │                   │                                           │
                 │               │                   ▼                                           │
                 │               │               QUOTE quotation ◄── (items from INV catalog)    │
                 │               │                   │ quote.accepted                            │
                 │               │                   ▼                                           │
                 │               │               PROJ project ─► DSGN design workflow            │
                 │               │                   │                                           │
                 │               │                   ├─► PROC procurement (PR → PO → GRN) ◄──────┘
                 │               │                   │         │
                 │               │                   │         ▼
                 │               │                   │     INV inventory (stock ledger)
                 │               │                   ▼
                 │               │               FIN invoices & payments ─► PORT customer portal
                 │               │                   │
                 │               │                   ▼
                 │               │               WARR warranty & support tickets
                 └─── TEAM scope for every module ───┘
AI consumes outbox events + read models (no writes except through services with an AI system identity)
```

### 3.2 Suggested sequencing

| Phase | Modules | Why this order |
|---|---|---|
| P0 (authorized, ADR-009) | Platform (auth, MFA, RBAC, users, audit, security events, notifications) + Leads | Revenue: capture and convert enquiries |
| Next candidate (needs separate approval) | Attachments, Customer, Quotation, org units (TEAM scope) | Closes the lead-to-contract loop. MFA is already in P0 (ADR-006). |
| P2 | Project, Design workflow, Vendor | Delivery after signing |
| P3 | Procurement, Inventory, Invoicing/Payments | Material flow and cash. **Blocked by the PostgreSQL release gate** (ADR-008, OPS-008). |
| P4 | Employee, Onboarding, Payroll | Sensitive data. Builds on P0 MFA. Needs field-level permissions and read auditing. |
| P5 | Customer portal, Warranty & Support, AI | External users and intelligence on a mature data set |

### 3.3 Module designs (outline)

All tables below inherit the audit contract and are registered FULL unless stated otherwise.

#### ORG: organization, branches, teams (enables TEAM scope)

| Table | Key columns | Notes |
|---|---|---|
| `org_unit` | `code`, `name`, `unit_type` (COMPANY/BRANCH/TEAM), `parent_id` → org_unit, `path` (materialized) | Hierarchy (Hyderabad branch → Sales team) |
| `user_org_unit` | `user_id`, `org_unit_id`, `is_primary`, validity | Membership |
| Additive columns | `lead.org_unit_id` (nullable, backfilled to the default branch) | Row ownership for TEAM scope |

Once this exists, the resolver's TEAM predicate becomes `row.org_unit_id IN actor's units (and descendants)`. Guard G8 is lifted, and no RBAC table changes.

#### ATT: attachments (floor plans, site photos, quotations, invoices)

| Table | Key columns | Notes |
|---|---|---|
| `attachment` | `entity_type`, `entity_id`, `file_name`, `content_type`, `size_bytes`, `storage_key`, `sha256`, `category_id` → lookup, `visibility` | Polymorphic. Files go to S3 or Cloudflare R2 with pre-signed URLs. Virus scan on upload. |

Permissions follow the parent entity (`lead_attachment.create`, or a generic `attachment.*` evaluated against the parent's scope).

#### CUST: customer management

| Table | Key columns | Notes |
|---|---|---|
| `customer` | `customer_number` (VS-C-…), `display_name`, `customer_type` (INDIVIDUAL/COMPANY), `primary_phone`, `primary_email`, `gstin`, `source_lead_id` → lead, `account_owner_id` → app_user, `org_unit_id` | Created on `lead.won` via the outbox handler, or manually |
| `customer_contact` | `customer_id`, name, phone, email, relationship (spouse, architect…), `is_primary` | |
| `customer_address` | `customer_id`, `address_type` (SITE/BILLING), lines, city, pincode, geo | A site address can later serve many projects |
| Additive column | `lead.converted_customer_id` (nullable) | Blocks WON→NEGOTIATION reopen after conversion |

Leads stay as history. A customer is a new aggregate, so there is no lead-table rewrite.

#### QUOTE: quotations

`quotation` (number, `lead_id` or `customer_id`, version, status DRAFT/SENT/ACCEPTED/REJECTED/EXPIRED, totals, validity) · `quotation_line` (room, item, spec, qty, UOM, rate, tax) · `quotation_revision` (snapshot JSON per sent version).

- `quotation.sent` → lead auto-moves to QUOTATION_SENT and `lead.quoted_amount_minor` is set.
- `quotation.accepted` → project creation.

#### PROJ: project management

`project` (VS-P-…, `customer_id`, `quotation_id`, site address, stage, dates, `project_manager_id`, `org_unit_id`, contract value) · `project_member` (user, role-in-project) · `project_phase` / `project_task` (template-driven from lookups) · `project_milestone` (payment-linked) · `site_log` (daily progress, photos via attachment).

The OWN scope for projects means the actor is a `project_member` of the project. This is added as a new ownership definition in the resolver's per-resource registry, not a schema change.

#### DSGN: design workflow

`design_brief` (per project/room) · `design_revision` (version, status, attachments, client feedback) · `design_approval` (customer sign-off with timestamp and portal user id).

The state machine lives in code like the lead's, with permissions `design.submit`, `design.approve.internal` and `design.publish` (to the portal).

#### VEND: vendor management

`vendor` (VS-V-…, name, category lookups, GSTIN, PAN, bank details **encrypted at column level**, rating, status) · `vendor_contact` · `vendor_rate_card` (item, rate, validity).

Future vendor portal users are `app_user` rows with `user_type = VENDOR` linked through `vendor_user`.

#### PROC: procurement

`purchase_request` (from a project, lines) → `purchase_order` (VS-PO-…, vendor, status, approval chain) → `purchase_order_line` → `goods_receipt` (VS-GRN-…) → `goods_receipt_line`.

- Approvals use a generic `approval_request` (entity_type/entity_id, approver, decision) that can be reused for quotes, discounts and payroll.
- Amount-based approval thresholds come from permissions with limits. This is a P3 addition: a `permission_limit` table (role_id, permission_id, max_amount) on top of the same RBAC.

#### INV: inventory

`item` (SKU, name, UOM lookup, category, is_stocked) · `warehouse` (store or site) · `stock_movement` (**append-only ledger**: item, warehouse, qty ±, movement_type RECEIPT/ISSUE/TRANSFER/ADJUST, reference entity_type/id) · `stock_balance` (derived, rebuilt from the ledger).

The ledger design means stock is never updated in place. That fits the audit philosophy.

#### EMP / ONB: employees and onboarding

`employee` (VS-E-…, `user_id` → app_user **nullable**, since not every employee logs in; legal name, DOB, joining date, designation, department org_unit, manager_id; PII and sensitive fields flagged) · `employee_document` (via attachment) · `onboarding_checklist_template` / `onboarding_task` (lookup-driven).

The platform `app_user` stays the login identity and `employee` is the HR record. They are linked, not merged, so no identity rewrite is needed.

#### PAY: payroll

`salary_structure` · `employee_salary` (effective-dated rows, never updated in place) · `payroll_run` (month, status DRAFT/LOCKED/PAID) · `payslip` · `payslip_line` (component, amount) · `statutory_config` (PF, ESI, PT, TDS via lookups and effective dates).

**Extra controls:**

- `payroll.*` permissions are all sensitive, so MFA and step-up are required.
- Read auditing (ACCESS action) applies to salary data.
- Column-level encryption for bank details.
- Field-level permissions (`employee.salary.read`).
- Payroll runs are locked after approval. Corrections are new adjustment lines, never edits.

#### PORT: customer portal

- Separate Lit app (`portal.vedaspaces.com`) and JWT audience (`veda-portal`).
- `app_user.user_type = CUSTOMER`, linked by `customer_user` (customer_id, user_id).
- A new role, **CUSTOMER_PORTAL**, with permissions like `project.read` (OWN = projects of the linked customer), `design.approve`, `invoice.read` and `ticket.create`.
- Notes with `visibility = CUSTOMER_VISIBLE` (reserved in P0) become visible.
- Login options: email + password, or phone OTP (new `user_action_token.purpose = LOGIN_OTP`, an enum widening).

#### WARR: warranty and support

`warranty` (project, item/category, start and end dates, terms) · `support_ticket` (VS-T-…, customer, project, category, priority, status machine, SLA due) · `ticket_comment` (with visibility) · `ticket_visit` (field visit, reusing the activity pattern).

#### FIN: invoicing and payments

`invoice` (GST-compliant numbering per financial year via `number_sequence` with period `FY`, which is a new enum value) · `invoice_line` · `payment` · `payment_allocation`.

Everything is immutable after issue. Corrections are credit notes.

#### AI features

| Feature | Data source | Pattern |
|---|---|---|
| Lead scoring / next-best-action | lead + activities (read model) | Batch job as the SYSTEM identity `AI_ASSISTANT`. Writes suggestions to a new `ai_suggestion` table (entity_type/entity_id, type, payload, accepted_by). **Never writes business fields directly.** |
| Call and meeting summarization | Activity descriptions | User-triggered. The result is stored as a normal `lead_note` created by the user after review. |
| Semantic search across notes and designs | Embeddings | pgvector on PostgreSQL. Indexed from outbox events. |
| Design ideation / mood boards | Attachments + briefs | External model calls with PII stripped. Logged via audit EXPORT-style rows. |

The AI identity gets permissions like any other principal (`lead.read` ALL, `ai_suggestion.create`), so RBAC and audit cover AI automatically.

## 4. Scope model evolution

| Stage | Scope values in use | Change required |
|---|---|---|
| P0 | ALL, OWN | — |
| P1 (org units) | + TEAM | Service guard lifted. Resolver gets the TEAM predicate. Rows get a nullable `org_unit_id`. |
| P2 (projects) | OWN redefined per resource (membership) | Per-resource ownership registry entry |
| P3 (limits) | + amount limits | New `permission_limit` table (additive) |
| P4 (field-level) | + field permissions | New permission codes plus serializer filtering |
| P5 (portal) | OWN via customer link | Ownership registry entry for CUSTOMER principals |

At no stage do `permission`, `role`, `user_role`, `role_permission` or `user_permission` change shape.

## 5. Platform evolution checkpoints

| Trigger | Platform change | Rewrite? |
|---|---|---|
| **Release gate (ADR-008, OPS-008):** before procurement, inventory or finance goes live, or before running more than one application instance | SQLite → PostgreSQL (RDS). Redis for caches and rate limits. | No: same ORM models and migrations (dual-engine CI). GUID becomes native `uuid` (03 §12). |
| Write contention signals (11 §3.3) | Bring the gate forward | No |
| Reporting needs | Read replica + reporting schema/views, or nightly export to an analytics store | No |
| Portal launch | Separate audience and app. API gateway rules at Cloudflare. | No |
| Very high audit volume | Monthly partitioning of `audit_log` (PG declarative partitioning) | No: same columns |
| Mobile offline site app | Offline drafts use temporary client keys. The sync service assigns UUIDv7 ids (ADR-002) and returns a key→id map. `version` handles conflicts. | No: designed in from P0 |
