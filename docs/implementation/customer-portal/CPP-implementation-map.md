# Customer Project Portal: implementation map (discovery, 2026-10-16)

Baseline: main `24f705d` (PR #101 and PR #103 merged; deployed to staging; Project Lifecycle off; PLB-OD-01…13 null).

The portal is a **customer-authorised projection** over existing sources of truth. It adds one thing the repository
does not have: an authenticated customer identity. Everything it shows is read from the modules that own it, through
the same customer-safe projections the Customer Quotation Experience (CQX) already uses.

## Existing capability → source of truth → how the portal consumes it

| Capability | Source of truth | Portal use |
|---|---|---|
| Staff authentication | `platform/auth` (JWT `at+jwt`, `user_session`, refuses any `user_type` other than HUMAN) | Untouched. Customers never hold a staff token, and a portal session is never accepted by a staff route. |
| Customer identity | none (CQX gives customers a per-version link, not an identity) | **New**: `portal_account` + `portal_access` (account ↔ lead), passwordless email sign-in, `portal_session`. See "Identity decision". |
| Customer record | `lead` (CRM), `lead.assigned_to` | Access is granted per lead by staff. The lead's assigned consultant is shown by name only. |
| Properties | `property` (`lead_id`) | Listed per accessible lead (reference, configuration, city). |
| Site measurement | `site_visit`, `measurement_set` (MTQ B1) | Journey step "Site measurement" (scheduled date, completed, verified); no measurements are shown. |
| Scope / BOQ / estimate | MTQ B2-B4 | Never read by the portal (internal economics). The customer sees only the issued quotation. |
| Quotation | `quotation` frozen snapshot (B4) + CQX `projection.build` (customer-safe, digest-verified) + `grants.proposal_state` | The issued versions of the customer's quotations, rendered with the CQX `vs-proposal-view` (read-only). Drafts, internal review and approvals are never shown. |
| Quotation acceptance | CQX `acceptance.decide` (bound to a secure-link grant and its evidence) | Not re-implemented. An open quotation is an "Action required" item that points the customer to the secure link they were sent (see Limitations). |
| Customer Promise | the information pack frozen in each issued quotation (`projection.information`) | "What Veda Spaces has committed to" and "Your responsibilities", from the latest issued quotation. |
| Contacts | frozen `information.contacts` (business channels approved for customers) | "Your Veda Spaces contact". Falls back to the assigned consultant's name only, without a contact channel. |
| Project lifecycle | `project` module (flag `VEDA_PROJECT_LIFECYCLE_ENABLED`, off) + `classification.py` allow-list | Journey stages after approval and customer actions only while that flag is on and a project exists; otherwise "Not yet available". The portal never reads or changes the flag. |
| Documents | issued quotation versions; `attachment` has no customer-visible class (`STANDARD`/`INTERNAL` site evidence) | Documents = the issued quotation versions. No attachment is exposed. |
| Notifications | outbox + email handlers + templates | Sign-in and invitation emails through the outbox (`portal.sign_in_link`). |
| Tokens | `derive_action_token` (HMAC of id + purpose; nothing secret stored), `new_opaque_token` + SHA-256 | Sign-in links derive from the row id; session tokens are opaque, stored as SHA-256. |
| Rate limits | `kernel/ratelimit` (Flask-Limiter keys) | Per IP and per email on sign-in; per IP on reads. |
| RBAC exceptions | 06 §11 RBX register, `app.RBX_REGISTER` | New RBX-010 for the portal's public routes. |
| Feature flags | `config.Settings`, `validate_environment` (production refusals), `/auth/me` features | New `VEDA_CUSTOMER_PORTAL_ENABLED`, off, refused in production. |
| Audit / timeline | `AuditedBase` + audit registry; `ms.create_immutability_guards` | `portal_event` (immutable, codes and ids only); all tables audited FULL. |
| Erasure | `crm/leads/erasure.py` CASCADES | Lead erasure revokes its portal access; an account left with no access has its email erased. |
| Staff UI | lead page (`app/src/modules/leads`) | A "Customer portal" card: invite, list, revoke. |
| Customer UI | `/proposal` (public route, no workspace shell), design system | New `/portal` routes in the same SPA, public shell, mobile first. |

## Identity decision

The roadmap (10 §PORT) sketches `app_user.user_type = CUSTOMER`. This workstream uses separate tables instead:

- staff authentication explicitly refuses non-HUMAN users today, and keeping customers out of `app_user` keeps them
  out of every staff list, assignment picker, permission resolver and MFA policy by construction;
- widening the `app_user.user_type` CHECK on SQLite rebuilds the most referenced table in the schema;
- a customer principal needs none of the staff machinery (roles, MFA, step-up, recovery).

Customer actions are recorded with the anonymous actor (as CQX does) and the portal account in the event detail.

## Limitations by design

- Quotation decisions stay on the CQX secure-link journey, whose acceptance evidence is bound to the link. A portal
  decision channel needs an evidence change and owner decisions; it is listed as a follow-up.
- Execution, quality and handover progress need the Project Lifecycle, which is off. The portal shows them as not yet
  available rather than inferring them.
- No attachment is customer-visible until an owner-approved visibility class exists.
