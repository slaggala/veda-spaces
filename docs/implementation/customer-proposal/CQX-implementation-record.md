# Customer Quotation Experience: implementation record

Instruction: `VEDA-SPACES-CUSTOMER-QUOTATION-EXPERIENCE-END-TO-END` (2026-10-14). One branch
(`feature/customer-quotation-experience`), one umbrella pull request, commits CQX-01 … CQX-15. Decision log entry 35.

## 1. Shape

- **API module** `api/veda/modules/customer_proposal` (grants, projection, journey, references, pricing, selections,
  requests, comparison, acknowledgements, acceptance, events, housekeeping, erasure, policy). It reuses, never
  duplicates: the B4 quotation, its frozen document and digests, its lines, its decision service (split into
  `record_decision`), its variation model and accepted baseline; B1 property locking and lead scope; the estimator's
  customer specification; catalogue V3 public media; the outbox, in-app notifications, audit registry, RBAC registry,
  rate limiter and lead service. No second quotation, pricing, customer, variation or numbering system.
- **App module** `app/src/modules/proposal`: public route `/proposal` (no sign-in, no workspace chrome) and the staff
  "Customer proposal" tab on the commercial page.
- **Migration** `0205_customer_proposal` (after `0202`; `0203` stays free): six tables, five permission codes, one CHECK
  widened (`quotation.decision_method` admits `CUSTOMER_DIGITAL`).
- **Flags** `VEDA_CUSTOMER_PROPOSAL_ENABLED` → `…_INTERACTION_ENABLED` → `VEDA_CUSTOMER_QUOTATION_ACCEPTANCE_ENABLED`
  (each needs the previous; viewing needs `VEDA_MTQ_QUOTATION_ENABLED`); off by default; production refuses all three.

## 2. Data model (each row references one quotation version; no frozen content is copied)

| Table | Purpose |
|---|---|
| `proposal_access_grant` | One secure link: version, recipient kind, token SHA-256, status, expiry, views, revocation, rotation chain |
| `proposal_event` | The proposal's append-only log (ids and codes only) |
| `customer_optional_selection` | Current customer choice per optional line (history: audit + events) |
| `customer_proposal_request` | Questions and change requests, staff answer, resulting version or variation |
| `quotation_acknowledgement` | One recipient's acknowledgement of one section at its digest |
| `quotation_acceptance_evidence` | The evidence of a digital decision (one per version) |

## 3. API

Customer (RBX-009, `auth="public"`, token in `X-Veda-Proposal`): `GET /api/v1/public/proposal`,
`GET …/proposal/comparison` (viewing flag); `POST …/proposal/selections`, `GET|POST …/proposal/requests`,
`POST …/proposal/acknowledgements` (interaction flag); `POST …/proposal/decision` (acceptance flag).

Staff (bearer, lead scope): `POST|GET /api/v1/quotations/<id>/access-grants` (proposal.share),
`POST /api/v1/proposal-access-grants/<id>/rotate` (proposal.share), `…/revoke` (proposal.access.revoke),
`GET /api/v1/quotations/<id>/proposal-preview` and `…/variation-preview` (proposal.preview),
`GET /api/v1/quotations/<id>/customer-activity`, `POST /api/v1/customer-requests/<id>/respond|link`
(proposal.request.review), `GET /api/v1/quotations/<id>/acceptance-evidence` (proposal.acceptance.review).

Permissions: FOUNDER, ADMIN, SALES_MANAGER all at ALL scope; SALES own leads (preview, share, revoke, requests,
evidence); ESTIMATOR preview and requests at ALL scope; DESIGNER and SURVEYOR none. No proposal permission grants a rate,
lineage or pricing view. Measurement-to-proposal traceability for staff stays the B4 lineage walk
(`/quotation-lines/<id>/trace`, `quotation.lineage.read`); customers never receive it.

## 4. Changes to existing modules (all additive)

- B4 `quotations.decide` → `record_decision` (same behaviour for staff; the customer path calls it with
  `CUSTOMER_DIGITAL`). `vocab.DECISION_METHODS` and OI-MTQ-11's allowed methods gain `CUSTOMER_DIGITAL`.
- OI-MTQ-09's terms shape gains optional `service_support`; the document model carries it; template
  `mtq-quotation-html/2` renders it as its own section after warranty (version 1 kept for documents issued with it).
  Two B4 test assertions now expect the current template version; the pinning they test is unchanged.
- `/auth/me` features: `customer_proposal`, `customer_proposal_interaction`, `customer_quotation_acceptance`.
- CORS allows the `X-Veda-Proposal` header; RBX-009 registered; two metrics approved
  (`ProposalIntegrityRefused`, `ProposalDecisionRefused`); lead erasure cascades into CQX; maintenance job
  `customer-proposal-housekeeping`; shared skeleton honours reduced motion.

## 5. Deviations and interpretations (none is an owner decision)

1. **Token in the URL fragment, sent as a header**, rather than a path or query parameter: it never reaches logs,
   proxies or `Referer`.
2. **Link lifetime 1–30 days per link** (CQX-B08): a security bound; the quotation's validity is separate.
3. **Specifications are pinned, not frozen**: the customer specification active at issue, digest-checked on use
   (immutable, versioned records). Media is never part of the frozen document (illustrative, withdrawable).
4. **Customer name excluded** from the projection (link-forwarding risk).
5. **Lead status unchanged on digital acceptance** (CQX-B07), as for B4 staff-recorded acceptance; a lead activity and
   the `quotation.accepted` hand-off event are emitted.
6. **Comparison of packages** lists only issued packages shared with the same recipient kind.
7. **Browser E2E serves SYNTHETIC page models** through Playwright interception: an end-to-end API stack cannot issue a
   quotation outside the test environment (synthetic owner policies are refused there). The API journeys run in the
   API suites on both engines.

## 6. Results

See `evidence/CQX-synthetic-validation-2026-10-14.md` (20 scenarios × 5 configurations, SYNTHETIC_VALIDATED) and the PR
description for the CI matrix.
