# Catalog-driven estimator (V3): independent-review package (remediated)

- **Instructions:** VEDA-SPACES-CATALOG-DRIVEN-ESTIMATOR-V3, then VEDA-SPACES-CATALOG-ESTIMATOR-V3-REMEDIATION.
- **Decision record:** [ADR-013](../../architecture/decisions/ADR-013-catalog-driven-estimator.md).
- **Companions:**
  - [media infrastructure design](CATALOG-V3-media-infrastructure.md), prepared, not active;
  - [owner decisions](CATALOG-V3-owner-decisions.md), proposed, not approved.
- **Branch:** `feature/catalog-estimator-v3` (PR #66), from `main` at `18dcf0a`.
- **State:** every V3 switch is off by default, and production refuses each one.

Nothing here activates V3, changes V1 or V2, enables public intake, or changes production behaviour.

## Canonical customer-copy closure (follow-up to PR #68)

### Current status

| Item | Status |
|---|---|
| V3 | **Off** in every environment. Every switch defaults off, and production refuses each one. |
| Protected staging | **Uncertified.** |
| Protected-staging infrastructure (bucket, KMS, malware scanner, CDN, CSP for media) | **Not started.** |
| Public intake | **Disabled.** |
| Real media and 3D | **Disabled.** No real media or 3D asset is uploaded. |
| Production V3 | **Prohibited.** |

### Corrections to the customer-safety closure

1. **This statement is withdrawn:** "Every customer-visible text path is inventoried and is either factual,
   controlled-copy governed, or promise-matrix governed."
   - It covered catalog records only.
   - Estimate response text and the customer text kept in the pricing card were outside that inventory and its
     checks.
   - The independent reviewer reproduced two defects on `main` at `006c203`:
     - estimate and card text bypassed the inventory;
     - claims and rates passed when written with invisible characters, fullwidth forms, Cyrillic lookalikes,
       separators or informal pricing (10 of 13 variants).
2. **Governance is claimed only as far as the final-payload tests prove it.** A field counts as governed when:
   - it is a field of a strict public DTO;
   - its classification is in `PUBLIC_FIELD_CLASSES`;
   - its strings pass the one canonical checker in release validation and in its serialiser.

   Record approval alone is not evidence.
3. **Earlier journey counts were stale.** The "34/34" counts below are historical. The V3 browser journey now has
   **86 checks**.

### The distinct inventories

| Inventory | What it covers | How it is governed | Evidence |
|---|---|---|---|
| **Catalog inventory** | 151 string-bearing fields of the catalog record models (authoring) | `text.FIELD_CLASSES`: factual, statement, staff or identifier. Text checks run at authoring, submission and release. | `test_catalog_text_inventory.py`, `test_catalog_claims.py` |
| **Public catalog payload** | Every field of `PublicCatalog` and its nested DTOs | Eight classes. `check_payload` runs at release validation and in `configure.public_catalog`, which fails closed with 503. | `test_catalog_canonical_copy.py`, `test_catalog_public_payload.py` |
| **Estimate and pricing inventory** | Every field of `PublicEstimate`. The pricing card's customer-visible text: exclusions, client scope, timeline labels, site-package labels and inclusions, product and input labels. | Estimate text is PROMISE_GOVERNED_COPY: the V2 promise matrix scope, with no rate, amount, contact or marketing claim. It is checked in representative estimates at release, in `create_public`, and on replay. Card text is checked at release although the card is staff-only. | `test_catalog_public_payload.py` |
| **Controlled claims** | Copy records with claim governance | The declared categories must equal those detected in canonical form. The record needs source, evidence reference and period, owner, backup owner, an approver who is not the owner, an effective date, a review date or an explicit non-expiring policy, environments, and the canonical digest. Placeholders, self-approval, an expired claim, a claim not allowed in this environment, and an ownerless or unapproved claim all fail closed. | `test_catalog_canonical_copy.py`, `test_catalog_claims.py` |
| **Promise-matrix content** | Warranty, quality-proofing, service and delivery wording: lifetime warranty, guaranteed, certified, waterproof, termite or scratch proof, maintenance free, guaranteed or on-time delivery, one-day callback, free service or consultation | Only a promise copy record linked to its confirmed matrix row (ESSENTIAL-1.1), or estimator text within the V2 matrix scope | `test_catalog_canonical_copy.py`, `test_catalog_closure.py` |
| **Public totals (allowed)** | The range, GST, rounded room subtotals, site-package amount, allowance band | PRICE_OR_RATE_COPY: integers computed by the engine, never text | `test_public_totals_are_numbers_not_text` |
| **Prohibited rates** | Unit rates, line amounts, margins, markups, procurement, supplier, dealer or cost prices, price ceilings, discounts | In no public DTO, and refused in every customer string in every format, including `₹1200`, `Rs 1200`, `INR 1200`, `1200/-`, `1,200`, `1,20,000`, `/sqft`, `per sq ft`, `12k per sqft`, `12K/sft`, `psf`, `rft`, `per running foot`, `per unit`, `/pc`, `% off`, `percent off`, fullwidth digits, the fraction slash and zero-width splits | `test_rates_and_prices_are_refused_everywhere` (34 formats); `test_sizes_counts_and_timelines_are_not_rates` (negatives) |

### Canonical normalisation

`veda.modules.catalog.text` decodes once and builds the canonical form. Every check compares in that form. The steps:

1. NFKC.
2. Remove invisible and format characters: Cf, Cc, Co, Cs, Cn, variation selectors, Mongolian free variation
   selectors and U+034F.
3. Casefold.
4. Map a narrow Cyrillic, Greek and Latin lookalike set to Latin.
5. Make every Unicode space a space.
6. Make every dash and the separators `_ - / \ . : |` and punctuation a single space.
7. Remove apostrophes and join letter-spaced runs, so "b e s t" becomes "best".
8. Drop a short list of factual compounds: free-standing, hands-free, top-hung, top-mounted, best-fit hinge, leading
   edge.

Detection matches whole words and phrases in this form, never substrings.

Normalisation is comparison only:
- Stored display text is never rewritten (`test_rows_are_never_rewritten_by_normalisation`).
- New text containing invisible or format characters is refused at authoring.
- Every record event (created, updated, approved) audits both the display digest and the canonical digest of each
  customer-visible field.
- Normalising text never authorises it.

### Release-wide payload validation

`validation._public_payload` builds the complete resolved public catalog payload and the representative estimate
payloads:
- each home under each online package and project kind;
- then each customer extra added to, and each other customer variant chosen in, a default room.

It also checks the card's customer text. Every string goes through the same `check_text`.

The digest of the payloads (`public_payload_sha256`) has the release identifiers neutralised. It is:
- recorded at preview approval and at release approval;
- compared at release approval and again at activation.

A change to pricing, specification, copy or catalog after approval refuses activation, and approval must be given
again (`test_a_payload_change_after_approval_refuses_activation`). A rollback carries the digest its target was
activated with, so a restore of what customers saw is allowed and anything else is refused.

### Reviewer-reproduced bypasses and their closure

| Reproduced on `006c203` | Closure evidence |
|---|---|
| Estimate and card text outside the inventory | `PublicEstimate` and `card_texts` are classified and checked: `test_estimator_text_with_a_claim_blocks_the_release`, `test_customer_text_in_the_staff_only_card_is_governed`, `test_the_serialiser_refuses_a_stored_estimate_whose_text_fails` |
| Zero-width split `B\u200best seller` | `test_reproduced_bypasses_are_detected`, `test_invisible_and_format_characters_are_reported` |
| Fullwidth `Ｂｅｓｔ ｓｅｌｌｅｒ` | `test_reproduced_bypasses_are_detected` |
| Cyrillic `Bеst seller`, `Тop rated` | `test_reproduced_bypasses_are_detected` |
| Underscore, en and em dash, slash, backslash, colon, pipe, NBSP, spaced dots, letter spacing, repeated punctuation | `test_reproduced_bypasses_are_detected` (27 variants) |
| `1200/sqft`, `12k per sft`, `1,20,000`, `20% off` | `test_rates_and_prices_are_refused_everywhere` |
| A string unclassified or weakly typed | `test_no_public_dto_has_a_weak_type`, `test_every_public_field_is_classified_and_the_registry_has_no_stale_entries`, `test_an_unclassified_or_weak_public_field_fails_closed` |

### Other closures in this round

- **Idempotency.**
  - The key is required, with at least 128 bits.
  - It is stored only as a SHA-256 scoped to the browser's `X-Veda-Client` token, so no other browser can replay it.
  - It expires after 24 hours (`409 IDEMPOTENCY_KEY_EXPIRED`).
  - Concurrency, timeout-then-retry, original-response recovery and 409 key replacement are tested.
  - See [CATALOG-V3-idempotency.md](CATALOG-V3-idempotency.md).
- **Turnstile.**
  - Mocked Cloudflare siteverify covers rejected, used (`timeout-or-duplicate`), wrong-hostname, unreachable, empty
    and oversized tokens (`test_catalog_turnstile.py`).
  - The browser journey adds a callback error, an empty token, a token past its accepted age, a mismatched token, a
    redelivered used token, a server used-token rejection, and waiting and submitting double clicks.
  - Customer messages are mapped by what happened:

    | Situation | Message |
    |---|---|
    | 422 | "Please review the highlighted information." |
    | 409 | "This request conflicts with an earlier submission. Please refresh and try again." |
    | 429 | "Too many attempts. Please wait before trying again." |
    | Anti-bot refusal only | "The security check could not be completed. Please retry." |

    A 500 or 503 is never labelled an anti-bot failure.
- **Accessibility.**
  - Images are checked as really decoded from hashed delivery paths with alt text, and really failing to text with
    no broken image left.
  - The focus walk covers radios, checkboxes, buttons, links, panels and the gallery dialog, which returns focus on
    Escape.
  - The keyboard run selects a style and an extra and verifies them in the request.
  - Overflow is checked on the initial page, an expanded panel, the gallery, the result, the error summary and the
    longest text.
  - **Defect found and fixed:** choosing a style re-rendered the room and dropped keyboard focus to the page body.
    Focus now stays on the chosen option.
- **Real-card evidence.**
  - An owner-run procedure and tool exist. **It has not been run on the real card**, and no real-card artifact
    exists.
  - Real-card equivalence is therefore not claimed as verified for this head.
  - See [CATALOG-V3-real-card-evidence.md](CATALOG-V3-real-card-evidence.md).
- **V3 estimate response.**
  - It is now the strict `PublicEstimate`.
  - The V2-only blocks are no longer sent to V3: `v2_copy`, `room_details`, `warranty`, `subject_to`,
    `optional_items_minor`, `rate_card_version`, the preparation note and component codes.
  - The V3 page never rendered them. V1 and V2 responses are unchanged.

### Closure validation (local; CI is reported in the PR)

| Check | Result |
|---|---|
| API on SQLite and PostgreSQL | 2740 tests: 1 failure, since fixed (a docs registry entry for the cited `006c203`), 0 errors, 14 skipped. The skips are the same 11 engine-specific ones and 3 local-only real-card tests as in §18. |
| Canonical-copy, payload, claims, idempotency and Cloudflare-path suites | Pass |
| mypy ratchet | 157 (baseline 157) |
| ruff, format, OpenAPI snapshot, bandit, secret scan, deploy-check | Pass. pip-audit runs in CI; no dependency changed. |
| Workspace on Node 22.23.3: lint, typecheck, tokens, contrast, unit, staging build, build | Pass |
| V3 browser journey | 86/86 |
| Real-card equivalence | **Not run on the real card for this head.** The procedure was dry-run end to end on the synthetic card (both engines: PASS, artifact intact). That proves the tool, not the real card. |

## Post-merge status and corrections (pre-activation closure)

PR #66 was re-certified **for merge with pre-activation conditions** and merged. Four claims in this package were
inaccurate when it was written and are corrected here:

1. **"Every customer-visible string is promise checked" is withdrawn.**
   - `Package.badge` was free-form text that did not pass the promise-governance controls.
   - Other short-text fields are inventoried in the pre-activation closure.
   - R2/R3 stay open until every customer-visible text path is governed.
2. **"R9 is fully resolved" is withdrawn.**
   - Rollback restores a manifest as a new release, but its target came from `previous_release_id`, which is fixed
     when the release is drafted and can be stale.
   - Rollback-target selection is subject to remediation.
3. **R12 is open** until GLB upload and delivery are safely disabled or fully sanitised.
4. **Soft-close storage is blocked by release-gate validation and the promise-matrix status.**
   - Its matrix row `spec.soft_close` is BLOCKED, so promise validation fails.
   - Its option group is absent from the TV unit, so reference validation fails.
   - `BLOCKED_FROM_RELEASE` in `seed.py` is a test and local-tool helper that keeps those records out of test
     releases. It is **not** the production enforcement mechanism.

Also stated plainly:
- Protected staging is **not certified**.
- Media infrastructure (bucket, scanner, media host) **remains unavailable**.
- Full-catalog expansion is **not approved**.
- Production V3 **remains prohibited**.

## Pre-activation closure (follow-up to PR #66)

### R2/R3: badges and the first short-text inventory (superseded by the customer-safety closure below)

- **Badges:** `Package.badge` is a key to a `badge` copy record, never free text.
  - Badge copy (30 characters at most) refuses promise wording and marketing claims, such as premium, best, lowest,
    cheapest, number one, offers, discounts, free, guaranteed and quality, unless it is a promise linked to a
    confirmed promise-matrix row with governance.
  - A badge that is not a badge copy record in the release fails validation, and so does an unconfirmed promise badge.
  - The public payload carries only copy approved in the active release.
- **Inventory of short-text fields that reach customers:**

  | Field | Control |
  |---|---|
  | Names, descriptions, "What is this?", "Typically used for" of homes, rooms, families, products, variants, choices, extras, packages, materials; material finish, colour family, texture | Promise check |
  | Option-group names and descriptions; measurement labels and hints | Promise check |
  | Media title, alternate text, caption, attribution, **and the rights owner shown when there is no attribution** | Promise check (rights owner new) |
  | 3D hotspot and camera labels | Promise check (new). 3D is disabled anyway |
  | Badges | Badge copy, claims check, matrix governance (new) |
  | Package subtitles (`public_summary`), rule messages, disclaimers, labels | Copy records: promise check, or matrix governance for promises |
  | Media `label` | A fixed choice: "Design reference" or "Illustrative example" |
  | Ribbons, recommendation labels, promotional labels | No such catalog field exists. `Package.recommended` is a boolean the page does not render as text |
  | Grades, thicknesses, brands, load capacity, soft-close capability | Never sent to customers |

- **Guard test:** walks the entire public catalog payload. Every string is a key, code, hash, path or date, a
  matrix-governed promise statement, or free of promise wording.
- **Outside the catalog:**
  - the V3 page's fixed headings, such as "Exclusions" and "What you supply";
  - the estimate's engine text (assumptions, exclusions, client scope, package inclusions), governed by the V2
    customer copy and the ESSENTIAL-1.1 matrix like V2.

  Neither is catalog content.

### R9: rollback target selection, closed

- What a release replaced is recorded when it is **activated**, in its immutable activation event. Drafts record
  nothing.
- Rollback runs at execution time:
  - it reads the active release's single activation event;
  - it proves the predecessor (RETIRED, retired at the instant the active release went live, matching the row);
  - it restores that exact manifest as a new release.
- Missing, duplicate or inconsistent history fails closed.
- The caller names the release they mean to roll back; a different active release is refused. Activation and rollback
  lock the active release; the one-ACTIVE index backs that up.
- **Tests:**
  - A→B→C, then rollback C restores B;
  - a stale draft (C drafted under B, D activated, then C), then rollback C restores D;
  - rolling back a rollback restores the release that immediately preceded the rollback release (undo, see below);
  - a concurrent change is refused;
  - four kinds of corrupted history are refused.

### R12: closed by safe disablement

**GLB is planned but disabled. glTF and USDZ are not supported. No real 3D customer asset is active.**
- **Upload:** a GLB is refused until approved private storage, the malware scanner, approved media delivery and the
  3D switch all exist. Today that means everywhere, including local and test.
- **Releases:** no release may contain a 3D media record.
- **Delivery:** images only. A known hash never fetches a model, even one written around every other control.
- **Customers:** see the gallery only. The slice has no model.
- **Planned code:** the GLB sanitiser is kept, and tested, for when 3D is approved. It is not reachable today.

### Market-condition rules

- The engine has no market context. Market or city conditions, and market availability, are refused when saved,
  rather than evaluated as "never matches". That evaluation would hide nothing under `hidden_when` and never trigger
  `requires_consultation` or `unavailable_online`.
- Conditions with no criteria, unknown fields (for example `city`), wrong operand types, empty or misspelled markets,
  and conflicting market rules are all refused.
- Market content written around validation into a live release makes V3 unavailable (503); nothing is shown or
  priced.

### Soft-close enforcement

Soft-close storage is blocked by **release-gate validation and promise-matrix status**. Tests make every other
condition hold:
- an option and a visible extra exist;
- the copy's own governance is confirmed;
- nothing is held back by the test helper.

The release still fails promises validation because the matrix row `spec.soft_close` is BLOCKED, with its owner
UNASSIGNED. It therefore cannot activate, reach the public payload, be priced, or appear in an estimate or snapshot.
`BLOCKED_FROM_RELEASE` is only a test and local-tool helper.

### Closure validation (local; CI is reported in the PR)

| Check | Result |
|---|---|
| API on SQLite and PostgreSQL | 2424 tests, 0 failures, 0 errors, 14 skipped: the same 11 engine-specific skips and 3 local-only real-card tests listed in §18 |
| Real draft-4 equivalence | Run locally on both engines: pass |
| mypy ratchet | 157 (baseline 157) |
| ruff, OpenAPI, bandit, pip-audit, secret scan, deploy-check | Pass |
| Workspace on Node 22.23.3: lint, typecheck, tokens, contrast, unit, staging build, build | Pass |
| V3 browser journey | 34/34, three consecutive runs (historical: the journey had 34 checks then; it now has 86) |

A keyboard-speed race found in this round, an estimate sent before the Turnstile widget rendered, is fixed: the page
now awaits the widget.

## Customer-safety closure (follow-up to PR #67)

**Customer text.** Every customer-visible text path is inventoried and is either factual, controlled-copy governed,
or promise-matrix governed.
- The registry `veda.modules.catalog.text.FIELD_CLASSES` classifies all 151 string-bearing fields of the catalog
  models as factual, statement, staff or identifier.
- A test enumerates the fields by type and fails CI on any unclassified field.
- The [customer-text inventory](CATALOG-V3-customer-text-inventory.md) is generated from the registry and checked to
  be current.

**Marketing claims.** These rules apply to every factual field (names, descriptions, option and measurement labels,
captions, 3D labels, the rights owner):
- A factual field may make no claim, matched as words and phrases, not substrings. "Premium" and "Luxury" name package
  tiers; "premium pick" and "luxury choice" are claims.
- A claim is made only by a copy record with claim governance: category, approval status, supporting source,
  responsible owner, effective date, review date and what it applies to.
- Absolute claims (best, number one, cheapest, lowest, guaranteed) also need independent substantiation. Pricing
  wording is never customer text.
- The release gate refuses unapproved, unowned, expired or unsubstantiated claims, and re-checks every string under
  the current rules.
- Released content loads by schema only, so historical releases and estimate snapshots are not re-judged.

**Anti-bot readiness.** A token counts only when Turnstile's callback delivers it, and submission is refused without
one.
- Each widget runs a state machine: NOT_LOADED, LOADING, READY_NO_TOKEN, TOKEN_AVAILABLE, SUBMITTING, SUCCEEDED,
  FAILED, EXPIRED.
- The live token is read at submission; an empty, stale, expired or used token is never sent.
- One request is in flight at a time.
- Each estimate carries an `Idempotency-Key`. The server (migration 0104, additive) returns the same estimate for a
  repeat; refuses the same key with other choices (409); and replays before the anti-bot check, because a real token
  is single-use.
- Failures (refused token, script not loading, lost response, expiry) are announced, keep the customer's choices,
  and offer a safe retry, never a bypass.
- The browser journey uses an asynchronous Turnstile stand-in; no scenario relies on an instant token.

**Rollback semantics.** Rolling back a rollback restores the release that immediately preceded the rollback
release. It behaves like undo, not like navigation through an arbitrary multi-step history.

**Status (unchanged by this closure):**
- V3 remains inactive.
- Protected staging remains uncertified.
- Media infrastructure remains unavailable.
- Real 3D remains disabled.
- Full-catalog expansion remains unapproved.
- Production V3 remains prohibited.

## Merge versus activation boundaries

| Boundary | What it allows | Status |
|---|---|---|
| **Merge** | The code on `main` with every switch off: public V3 routes return 404, the staff catalog API returns 404, no media is served, and the V3 page is not in staging builds | Merged after re-certification with pre-activation conditions |
| **Protected-staging review** | V3 on staging behind Cloudflare Access with `VEDA_CATALOG_ADMIN_ENABLED`, then `VEDA_CATALOG_ESTIMATOR_ENABLED` | **Not certified.** Blocked: §25 and the pre-activation conditions |
| **Public intake** | Customers using V3 | Blocked: §26 |
| **Production** | Any V3 switch in production | Refused by configuration validation: §27 |

## Remediation record

**M1, the merge blocker:** required CI failed, so the API jobs never ran their tests. The cause was 43 new mypy
errors. All 43 are fixed with typed catalog accessors and precise narrowing. The ratchet baseline is unchanged, and
there is no suppression or broad `Any`. Typing also exposed real defects, each now handled (A1).

**R1–R15:**

| Finding | Resolution | Evidence |
|---|---|---|
| R1 four-eyes | Each record version keeps an append-only contributor set: creator, every editor and the submitter. Approval reads that set together with the creator and submitter fields and the create/edit/submit events, so clearing one source never opens approval. Release approval is refused to anyone who contributed to a record the release adds or changes (pricing, copy, rules, media mappings). An edit clears an earlier review | `test_catalog_lifecycle.py`: self-approval; editor cannot approve; uninvolved approves; contributor removal; stale review; release approver |
| R2, R3 promise wording (**open**: `Package.badge` and the short-text inventory) | Promise-like wording is refused in descriptive strings (names, descriptions, explanations, option and measurement labels, media text) and in non-promise copy, with no exemptions: warranty, guarantee, certification, free, included, excluded, installation, delivery, timelines, grades, brands, service, soft-close. A promise is a copy record that names its matrix row and the products, rooms or packages it applies to. It must be registered text of a confirmed ESSENTIAL-1.1 row with named owners | `test_catalog_promises.py`: 18 phrases × 4 places; matrix linkage cases |
| R4 staff-only visibility | Staff-only products, variants, choices, extras, rooms, packages, homes and staff_only rule subjects are removed before serialisation, references included, and refused in public configurations | `test_staff_only_items_are_neither_shown_nor_selectable` |
| R5 rule paths | Every rule path must name a real product, variant, group, choice, extra or room. `#boxx` fails validation | 6 misspellings refused; valid paths pass |
| R6 package and extra pricing | Phased resolution: engine selections are built only after schema, visibility, package filtering, applicability and rules all pass. Excluded items are refused, never priced. Selected = resolved normal form = priced request = stored snapshot | `test_selected_resolved_priced_and_stored_configurations_reconcile` |
| R7 raw customer JSON | A strict allowlisted schema: catalog keys, closed literals, bounded numbers, no free text, no city. The snapshot stores only the normal form. Snapshots follow estimate retention (audited soft delete plus event), and staff can action deletion requests | 6 free-text and unknown-field cases; retention; deletion |
| R8 public errors | Malformed payloads get 4xx with fixed messages. Path segments that are not keys or indexes are masked. No value, schema detail, identifier or stack trace is returned | 24 malformed payloads, non-JSON, wrong types |
| R9 rollback (**open**: target selection) | Rollback creates a new release with a previous manifest's exact entries (`rollback_of_id`), re-validated and activated. No release row is reset. The target is `previous_release_id`, fixed at draft time, so it can be stale | Exact versions, rules, pricing, copy and media restored; card identical; estimates untouched |
| R10 scheduled rejection | One step clears the schedule and every approval and returns SCHEDULED records to APPROVED. The event records what was cleared | `test_rejecting_a_scheduled_release_clears_everything_and_keeps_history` |
| R11 image limit | 24,000,000 pixels and 8,000 per side, checked from the header before decoding | Boundary at, below and above; forged bomb headers |
| R12 (**open**) | GLB upload and delivery: open until they are safely disabled or fully sanitised (pre-activation closure) | — |
| R13 | No finding text was supplied, so nothing is claimed under this number | — |
| R14 matrix conflicts | Veneer is consultation-only. Choices priced alike fail validation unless declared price-neutral or consultation-only. Panelling maps to Essential `surface` and the feature wall to `decorative`. Soft-close is blocked | `test_the_slice_follows_essential_1_1`, `test_choices_priced_alike_need_a_decision` |
| R15 import | Each row needs the edit permission of its kind (`catalog.admin` alone is not enough). Repeated imports are a deterministic `NO_CHANGE`. Rows are DRAFT only | Duty per kind; three applies; route all-or-nothing |

## 1. Branch

`feature/catalog-estimator-v3`

## 2. Commit SHAs

| Commit | Content |
|---|---|
| `8735df7`, `6b5732c`, `7270291`, `03310cc`, `5eeb149` | Original V3, phases 1–5 |
| `79f9730` | A1: mypy |
| `77bed5d` | B: R1, R9, R10, R15 |
| `12ced30` | C/D: R4–R8 |
| `1b68b14` | E: R2, R3, R14, E3 |
| `63960cd` | F/G: R11, media, 3D, flags |
| `80d7d33` | Accessibility, performance, admin safeguards |
| `5e95cf0` | A3/H3: isolation and real card |
| The commit adding this revision | Documentation |

## 3. Requirement traceability

The original matrix stands, with these corrections:
- Promise governance follows R2/R3, as above.
- The veneer behaviour is now consultation-only.
- Every snapshot is the allowlisted normal form.
- The staff API, public media and 3D each have their own switch.
- The admin UX gap is classified in §7.

## 4. Architecture

- **Pricing path:** unchanged. The catalog compiles to a rate card, and `compile.resolve` turns the configuration into
  the existing engine request, priced by `engine.calculate`.
- **Resolution phases:** schema, then plan (visibility, package filtering, applicability, options, measurements),
  then rules. Engine selections are built only when nothing failed.
- **Switches:**

  | Switch | Default | Production |
  |---|---|---|
  | `VEDA_CATALOG_ESTIMATOR_ENABLED` | Off | Refused |
  | `VEDA_CATALOG_ADMIN_ENABLED` | Off | Refused |
  | `VEDA_CATALOG_MEDIA_DELIVERY_ENABLED` | Off | Refused |
  | `VEDA_CATALOG_3D_ENABLED` | Off | Refused |
  | `VEDA_CATALOG_ANALYTICS_ENABLED` | Off | Refused |
  | `STAGING_ESTIMATOR_VERSION=v3` | — | Refused by the staging build without an approved V3 record |

## 5. Entity relationship model

The original model stands. Migration 0103 is still unmerged and create-only (tested). It adds:
- `catalog_record.contributors`;
- `catalog_release.rollback_of_id`;
- `catalog_media_object.withdrawn_on`, `withdrawal_reason` and `purged_on`;
- media uniqueness by (hash, role);
- scan states PENDING, CLEAN, INFECTED and FAILED;
- the events CONFIGURATION_PURGED, MEDIA_WITHDRAWN and MEDIA_PURGED.

## 6. Catalog lifecycle

As before, with:
- the contributor-set four-eyes rule (R1);
- release approvers who must not have changed the release's records;
- one-step rejection of a scheduled release (R10);
- rollback as a new release (R9).

## 7. Admin screens: classification

The validated-JSON editor stays for **engineering and review only**. **Typed per-kind forms are required before
operational adoption.** They were not built in this remediation.

Safety properties, confirmed:

| Property | How |
|---|---|
| Schema errors are understandable | The server returns the field path and message, for example `invalid product: variants.0.key: String should match pattern` |
| Unsaved changes are warned | On drawer close and on page unload |
| Drafts cannot activate | Only manifests of APPROVED records are released, and activation re-validates |
| Copy governance cannot be bypassed | Saving refuses promise wording; validation refuses unlinked or unconfirmed promises |
| Unauthorised admins cannot see rates | Pricing is hidden without `catalog.pricing.view` (tested) |
| The workspace says when it is off | It shows that the catalog is not enabled in the environment, because the staff API returns 404 |

## 8. Customer screens

**Flow:** home, then new home or renovation, then package, then rooms, then estimate, then refinement, then quotation.

**Choices:**
- Veneer is shown as consultation-only. It cannot be selected and links to a consultation.
- Soft-close storage is absent.
- 3D is absent unless `VEDA_CATALOG_3D_ENABLED`, so the page is gallery-only.

**The result page (E3) shows every customer-critical field of the estimate response:**
- the range and GST;
- the Site Execution & Handover Package and the Design Personalisation Allowance, named from registered copy, with
  their descriptions, inclusions and amounts;
- the timeline, assumptions, exclusions and client-supplied items;
- validity and expiry, and the disclaimer;
- the specification version, and the catalog release with the configuration reference.

The browser journey reconciles each field against the API response.

**Still open:** the "selection intent" step, and approved impact ranges per extra.

## 9. API catalog

- **Staff routes:** as before, plus `DELETE /configurations/<ref>` and `POST /media/<sha>/withdraw`. **Every staff
  route returns 404, before authentication, unless `VEDA_CATALOG_ADMIN_ENABLED`.**
- **Public routes:** each returns 404 unless `VEDA_CATALOG_ESTIMATOR_ENABLED`. Media also needs
  `VEDA_CATALOG_MEDIA_DELIVERY_ENABLED`.
- **Public validation behaviour:**
  - Malformed bodies get 400 (not JSON) or 422 with `{field, code, message}` errors only.
  - Messages are fixed, and path segments that are not keys or indexes are masked.
  - No value, schema detail, record id, rate or trace is returned. No client input yields 500 (24 cases tested).

## 10. Permission matrix

Unchanged. Import now also requires the edit permission of every imported kind.

## 11. Pricing adapter

As before, with phased resolution and reconciliation (R6).
- A choice that would price exactly like another fails validation unless declared price-neutral or
  consultation-only. Veneer is never priced as laminate.
- City and minimum-charge adjustments remain unsupported, because the engine has no such inputs.

## 12. Rules model

- Ten rule types, as before.
- Strict path validation (R5).
- A `requires_consultation` rule on a choice makes it consultation-only in both the page and the API.

## 13. Media architecture

| Area | Behaviour |
|---|---|
| Image limit (R11) | **24,000,000 pixels and 8,000 pixels per side**, checked from the header before any decode. Pillow's guard is set to the same limit, and its warning is an error. Minimum 320 per side; 15 MB file limit |
| Scan states | PENDING, CLEAN, INFECTED, FAILED; fail closed |
| Storage | Local in development and tests. A private, encrypted S3 bucket is prepared and inactive. Staging and production refuse a catalog without the bucket and ClamAV |
| Delivery | Off by default; when on, only CLEAN, unwithdrawn variants of the ACTIVE release |
| Retention | Withdrawal deletes bytes and keeps hashes; unreferenced sources are purged after 180 days |
| Rights | Client images need a consent reference |

The full design is in the [media infrastructure document](CATALOG-V3-media-infrastructure.md).

## 14. 3D

- **Customers:** gallery only by default.
- **Formats:** glTF and USDZ are disabled, at upload and in records.
- **GLB:** accepted only after sanitisation:
  - container structure checked;
  - no URIs, and no animations, skins or unknown sections;
  - allow-listed extensions only;
  - limits on meshes (200), materials (64), textures and images (32), nodes (1000), accessors (4000) and vertices
    (500,000);
  - embedded textures must really be PNG or JPEG;
  - `extras` and authoring metadata stripped, and the file rewritten to a new generated object;
  - 25 MB, scanned.
- **Real 3D assets:** none uploaded or activated. The slice's model is generated and synthetic.

## 15. Vertical slice (corrected)

Living Room → TV Unit:
- **Laminate panelling:** priced. It maps to Essential `surface`, which covers TV_UNIT.PANEL.
- **Box unit:** priced.
- **Veneer:** consultation-only (R14, H1).
- **Feature wall:** priced and measured. Essential `decorative`; no material is promised.
- **Gallery:** shown. 3D is off.
- **Soft-close storage:** **blocked by release-gate validation and promise-matrix status (H2)**, not by the test helper
  `BLOCKED_FROM_RELEASE`. Its matrix row `spec.soft_close` is BLOCKED and its owner
  UNASSIGNED; there is no explicit price rule and no confirmed applicability.
- **Snapshot:** the normal form re-resolves to the identical request.

## 16. V2 migration

As before. The Essential subtitle promise now names matrix row `package_subtitle` and applies to the Essential
package. It is registered text of that row (tested) and stays BLOCKED.

## 17. V2/V3 equivalence

**Synthetic card (CI):** the card round-trips, and the V2 and V3 requests and results match.

**Real draft-4 card** (local only; the draft-4 card, its digest checked against the one recorded for draft-4, read in place, never copied or committed; SQLite and
PostgreSQL):
- the migrated card compiles back identically;
- for every V2 state, the request is identical, and so are range, GST, package, allowance, timeline and rooms;
- the corrected slice prices laminate and the feature wall, refuses veneer and soft-close, and reproduces its
  snapshot. Result: **pass**.

No amount appears in any output.

## 18. Tests and CI

**Local, on the head before this documentation commit:**

| Suite | Result |
|---|---|
| API, SQLite and PostgreSQL | 2359 tests, 0 failures, 0 errors, **14 skipped** |
| mypy ratchet | 157 (baseline 157), 0 new |
| ruff, format, OpenAPI | Pass |
| Workspace on Node 22.23.3 (the CI version): lint, typecheck, tokens, contrast, unit, staging build, build | Pass |
| V3 browser journey | 34/34 (historical; the journey now has 86 checks) |

**The 14 skips:**

| Count | Reason | Kind |
|---|---|---|
| 6 | `test_backups` (snapshots apply to the SQLite deployment; PostgreSQL uses managed snapshots) | Engine-specific, not run on PostgreSQL |
| 2 | `test_archive_ordering` (snapshots and the volume check are SQLite-only) | Engine-specific |
| 1 | `test_archive_fc13_fc14` (the SQLite database-wide write lock) | Engine-specific |
| 1 | `test_schema` (an SQLite pragma) | Engine-specific |
| 1 | `test_schema` (format CHECKs are SQLite-only; PostgreSQL's uuid enforces format) | Engine-specific |
| 3 | `test_catalog_real_card` (local only; needs the private card) | Run locally and passed, see §17 |

The original package said the 11 pre-existing skips were "anchor-history" skips. **That was wrong** and is
withdrawn: they are the engine-specific skips listed above.

**CI:** reported in the PR. The original package reported local results only, while required CI was failing on the
mypy ratchet; that is corrected here.

## 19. Media-security results

All are in `test_catalog_media.py`:
- **Image limit:** at (6000 × 4000) and below (5999 × 4000) accepted; above (6000 × 4001) refused. Forged headers of
  50,000², 8,000² and 65,535 × 400 are refused without decoding, and nothing is stored.
- **EXIF:** stripped (`test_images_are_reencoded_without_metadata`).
- **Scan states:** PENDING without a scanner on deployed environments; FAILED when the scanner is unreachable.
- **GLB:** ten unsafe-content refusals, plus a mismatched texture and the container structure.
- **Disabled formats:** glTF and USDZ.
- **Consent:** client images need a consent reference.
- **Withdrawal:** stops serving and fails new releases, and estimates still work.
- **Purge:** happens after retention, and only for unreferenced media.
- **Flags:** public media is off without its flag; the staff API is off without its flag.

## 20. Accessibility and performance

All in the browser journey, on Node 22.23.3:
- axe passes on the home, rooms and result screens;
- 360 px with no horizontal overflow on any screen;
- keyboard-only completion, in document order with no positive tabindex, and focus moved to each screen heading;
- reduced motion respected;
- a slow network (API 1.5 s, images 3 s) still completes;
- with images failing, text replaces them, the estimate still works, and all critical content is text;
- the 3D-unavailable state is gallery-only;
- no CSP violation and no page error.

## 21. Rollback plan

- **Catalog:** rollback restores the previous manifest as a new release (R9).
- **Feature:** the switches are off by default.
- **Code:** revert the branch. Migration 0103 is create-only, and no existing table references the new ones.

## 22. Independent-review focus

- `compile.resolve` (the phases);
- `configuration.py` (the allowlist);
- `service.contributors` and `_release_four_eyes`;
- `service.rollback` and `reject_release`;
- `validation._promises` and `_same_price_choices`;
- `media._image_variants`, `sanitize_glb` and `withdraw`;
- `routes._staff_enabled`.

## 23. Owner decisions

See the [owner decisions](CATALOG-V3-owner-decisions.md): 14 proposals, none approved.

## 24. Human-governance dependencies

- Promise owners, backups and verification for every catalog promise. All ESSENTIAL-1.1 matrix rows are BLOCKED today.
- Sales and operations sign-off.
- Owner approval of a V3 release and of a V3 staging record (none exists).
- The V2 track continues separately: Round 1, Part 1 and Part 2, ESSENTIAL-1.1 activation, and public intake.

## 25. Protected-staging blockers

1. Re-certification of this branch and its merge.
2. The private S3 bucket, KMS key, policy and lifecycle rule, plus the ClamAV sidecar (owner decisions 1–3, 9).
   Configuration refuses a staging catalog without them.
3. The media hostname and the V3 page's `img-src` entry (decision 10).
4. An approved V3 staging activation record. The staging build refuses `STAGING_ESTIMATOR_VERSION=v3` without it.
5. Pricing records from the owner's approved card, loaded as DRAFTs and approved under four-eyes.
6. Typed admin forms, if staff other than engineers will use the workspace (§7).
7. Promise governance for any promise a staging release would show. None is in the corrected slice.

## 26. Public-intake blockers

- Everything in §25.
- V2 public-intake approval.
- Homeowner validation of V3.
- Approved real imagery with rights.
- The selection-intent step.
- Analytics approval, if it is to be used.

## 27. Production blockers

- Configuration refuses every V3 switch in production. Lifting that is a reviewed change.
- Everything in §26.
- Production media infrastructure.

## 28. Recommendation

**Re-certify for merge with every switch off.** Then work through the protected-staging blockers in order: the
infrastructure decisions, the approved card, a V3 staging record, and typed forms.

Do not expand the catalog or 3D until the corrected slice is validated with people.
