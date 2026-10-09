# Catalog-driven estimator (V3): independent-review package

**Instruction:** VEDA-SPACES-CATALOG-DRIVEN-ESTIMATOR-V3.
**Decision record:** [ADR-013](../../architecture/decisions/ADR-013-catalog-driven-estimator.md).
**Branch:** `feature/catalog-estimator-v3`, from `main` at `18dcf0a`.
**State:** implemented behind `VEDA_CATALOG_ESTIMATOR_ENABLED=false` and `STAGING_ESTIMATOR_VERSION=v2`.

Nothing in this package activates V3, changes V1 or V2, enables public intake or touches production.

This is the single consolidated review package. It covers:
- architecture and schema;
- permissions;
- admin and customer experience;
- the pricing adapter and rules;
- images and the 3D abstraction;
- media security;
- versioning, migration and rollback;
- trust and customer promises.

---

## 1. Branch name

`feature/catalog-estimator-v3`

## 2. Commit SHAs by phase

| Phase | Commit | Content |
|---|---|---|
| 1 | `8735df7` | ADR-013, flags and production refusals, nine `catalog.*` permissions, Pillow dependency |
| 2 | `6b5732c` | Catalog module, migration `0103_catalog`, wiring (models, audit, RBX-008, CLI, scheduler), `activate-card` guard |
| 3 | `7270291` | API tests: lifecycle, four-eyes, vertical slice, security, V2/V3 equivalence, rules, config |
| 4 | `03310cc` | Workspace catalog screen, V3 customer page, staging-build gate, browser journey |
| 5 | the commit adding this file | Review package, ADR notes, public-route pin update, OpenAPI snapshot (32 added paths, 12 added schemas, nothing existing changed), `Catalog`-prefixed request schemas, V3 page refinements, known-commit register |

## 3. Requirement traceability matrix

Status key:
- **Done** means implemented and tested.
- **Partial** means it works for the slice, and the gap is named.
- **Open** means not built, with the reason given.

| Requirement (instruction section) | Status | Where | Evidence |
|---|---|---|---|
| Explicit lifecycle DRAFT…ARCHIVED (principle 3) | Done | `catalog/service.py` | `test_records_are_versioned_and_only_drafts_change` |
| Nothing customer-visible on save (principle 2) | Done | Only an ACTIVE release is served | `test_public_catalog_is_disabled_by_default`, release lifecycle tests |
| Only ACTIVE versions priced (principle 4) | Done | `configure._active`, manifest digest checks | `test_manifest_drift_is_refused` |
| Estimate snapshots exact versions (principle 5) | Done | `CatalogConfiguration.versions`, the card snapshot | `test_vertical_slice_estimate_and_snapshot` |
| Admin update never rewrites history (principle 6) | Done | Released versions are immutable; edits create new versions | Lifecycle and rollback tests |
| Images illustrative (principle 7) | Done | Media `label`; page statement | Browser journey: "images are labelled as illustrative" |
| Pricing engine authoritative (principle 8) | Done | `compile.resolve` → `engine.calculate` | Equivalence test |
| Rule engine authoritative (principle 9) | Done | `rules.evaluate` server-side | `test_unsupported_combinations_fail_closed` (9 cases), rules unit tests |
| 3D never authoritative (principle 10) | Done | `ThreeD` has no engine fields; the viewer does not reach pricing | `test_three_d_needs_a_preview_and_a_fallback_and_never_prices` |
| No rate in a browser bundle (principle 11) | Done | Pricing staff-only; customer view strips staff fields | `test_public_catalog_view_has_no_rates_or_staff_data`; browser journey |
| Promises need sourcing and verification (principle 12) | Done | Copy governance; validation `promises` check | `test_release_validation_fails_closed_on_an_unconfirmed_promise` |
| Unsupported combinations fail closed (principle 13) | Done | `compile.resolve`, `rules` | 9 refusal cases |
| No activation without preview, validation and approval (principle 14) | Done | `service.activate_release` | `test_release_four_eyes_and_full_lifecycle` |
| V2 outputs reproducible (principle 15) | Done | V1/V2 code paths untouched; `activate-card` refuses `CATALOG-` cards | Full suite; `test_v1_v2_activate_card_refuses_compiled_catalog_cards` |
| Domain model A–H | Done (typed documents) | `catalog/kinds.py` | §5 |
| Product hierarchy, not hardcoded | Done | Data only; the slice is seed data | `seed.py` |
| Admin dashboard | Done | `GET /catalog/dashboard`, Dashboard tab | API test |
| Room, product, extras, package and rules management | Partial | Created, edited, cloned, versioned and reviewed as validated JSON documents | Typed per-kind forms are open (§7) |
| Pricing management, rates private | Partial | Pricing records are engine `ProductSpec` bodies | City adjustments and minimum charges are open: the engine has no such inputs (§11) |
| Media library | Partial | Upload, list, variants, scan state | Video upload, media manifest import and retire/replace UI are open (§13) |
| Preview and publishing | Done | Customer view, preview estimate, diff against active, validate, approve, schedule, activate, roll back | API tests; Releases tab |
| Least-privilege permissions, four-eyes, audit | Done | `catalog/permissions.py`; audit registry | `test_staff_permissions_least_privilege`, `test_permissions_are_least_privilege` |
| Customer flow, estimate first | Partial | Home, project kind, package, rooms, estimate, refine, quotation link | "Selection intent" step and impact ranges are open (§8) |
| Image experience | Done | Primary image, galleries, srcset variants, labels, alt text, broken-image text fallback | Browser journey |
| 3D and 360 architecture | Done (abstraction) | Types, `ThreeD` metadata, GLB/USDZ validation, viewer abstraction with fallback | Browser journey: "3D falls back to the gallery" |
| Vertical slice: Living Room → TV Unit | Done | `seed.py`, `tools/e2e_catalog.py` | §15 |
| Pricing adapter, V2 equivalence | Done | `compile.py`, `migrate_v2.py` | §17 |
| Specification and promise integration | Partial | Registered copy, governance, promise words refused | Validation of `matrix_row` against the packaged ESSENTIAL-1.1 matrix is open |
| Secure media storage | Partial | Private sources, hash keys, variants, scanning, immutable URLs | Bucket, CDN and lifecycle rules are owner decisions (§23) |
| Release manifest and activation validation | Done | `service.py`, `validation.py` | §6 |
| Analytics (staging only) | Done | 12 events as counts; flag off; production refuses | Config tests |
| Import/export, imports stay DRAFT | Partial | CSV/JSON dry run and apply; versioned export | XLSX waits for a library decision |
| V2 migration | Done | `migrate_v2.py`, `v2_bundles.json` | `test_v2_migration_is_idempotent_and_draft_only`; bundle parity test |
| Tests on PostgreSQL and SQLite | Done | Full suite on both engines | §18 |

## 4. Architecture

```
Admin (workspace /catalog)                    Customer (/estimate-v3, flag-gated)
  │ typed documents, DRAFT                       │ GET /public/catalog (ACTIVE release view, no rates)
  ▼                                              │ POST /public/catalog/estimates {configuration}
catalog_record ──review (four-eyes)──► APPROVED   ▼
  │                                           compile.resolve ── rules.evaluate (fail closed)
  ▼                                              │ engine.EstimateRequest (resolved pricing inputs)
catalog_release (immutable manifest)             ▼
  validate → preview approval → submit →     ADR-012 engine.calculate (unchanged, single engine)
  approve → schedule/activate → rollback         │
  │ compile.card_document                        ▼
  ▼                                           budget_estimate (rate-card snapshot, spec snapshot)
estimator_rate_card "CATALOG-<code>"             + catalog_configuration (release, manifest digest,
  (DRAFT forever; never the V1/V2 card)            every record version, selections, request)
```

The catalog compiles into three artefacts the estimator already understands:
- the rate card;
- the customer view;
- the engine request.

That is why there is no second pricing engine (D1).

## 5. Entity relationship model

**Tables** (migration `0103_catalog`; expand-only, no change to existing tables):

| Table | Purpose |
|---|---|
| `catalog_record` | One version of one typed document: `(kind, record_key, record_version)` unique, at most one ACTIVE per `(kind, key)`, plus the document and its SHA-256, submitter and reviewer |
| `catalog_release` | The manifest of `(kind, key, version, sha256, record_id)`, its SHA-256, validation report, compiled digests, `rate_card_id`, `previous_release_id`, approvals, schedule, activation and deactivation |
| `catalog_event` | The lifecycle trail; details never hold rates |
| `catalog_media_object` | Content-addressed source or variant objects, scan state, `source_object_id` |
| `catalog_configuration` | The snapshot of each V3 estimate (FK to `budget_estimate`) |
| `catalog_analytics_daily` | Counts by day, event, catalog key and release |

**Document kinds and how they map to the instruction's domain model:**

| Kind | Instruction area | References |
|---|---|---|
| `property_type`, `home_config` | A | `home_config` → `property_type`, `room_template`, `package` |
| `room_template` | A | → `product` (slots with variant and options), `extra`, `media` |
| `product_family`, `product` | B | `product` → `product_family`, `material`, `hardware`, `media`. Variants → option groups → choices, each with engine product and options |
| `material` | C | → `copy` statements |
| `hardware` | D | → `copy` statements, `product_family` |
| `extra` | E | Room, product or package extra; fixed, count or measured; `add` or `set_option` → `product`, `material`, `hardware`, `media` |
| `media` | F | Galleries → items. 3D → preview image and fallback gallery |
| `pricing`, `rule`, `package` | G | `package` → `copy`, `product`, `extra`. `rule` → reference paths, `copy` |
| `copy` | — | Governed statements |

Availability (markets, property types, home sizes, project kinds, effective dates), sort order, customer and staff visibility, staff notes and customer descriptions are common fields.

## 6. Catalog lifecycle

**Records**
- DRAFT → IN_REVIEW (submit) → APPROVED (reviewer ≠ creator, editor or submitter).
- A rejection returns the record to DRAFT and needs a reason.
- Only a DRAFT can be edited. A new version copies the latest version.
- Archiving applies to DRAFT, APPROVED-but-unreleased and RETIRED records.
- Releases move records through SCHEDULED, ACTIVE and RETIRED.

**Releases**
- **Create.** The release takes the newest APPROVED version of each key, otherwise its ACTIVE version, and keys can be excluded to retire them. This freezes the manifest and its digest.
- **Validate.** Ten checks run: schema, references, pricing, measurements, defaults, promises, media, 3D, rules and card. Any error fails the release.
- **Approve the preview.** Someone other than the author must approve.
- **Submit, then approve.** The approver must not be the author or the submitter, and must give an approval reference.
- **Schedule or activate.** Activation:
  - re-validates;
  - re-checks every record digest;
  - retires the previous release;
  - stores the compiled card.
- **Roll back.** The release this one replaced is re-activated as a whole manifest.
- **Scheduler.** The `catalog-activation` job activates scheduled releases when they fall due.

## 7. Admin screens

Workspace route `/catalog`, shown with `catalog.view`:

| Tab | What it does |
|---|---|
| Dashboard | Active release, drafts, pending review, approved-unreleased, products missing images, extras without "What is this?", materials without statements, unpriced items (pricing access only), unsupported combinations, scheduled releases, recent changes |
| Records | Filter by kind. The drawer holds a JSON document editor, validated by the server, with create, save, submit, approve, reject, new version and archive. Each button shows only with the right permission |
| Releases | New release, validation report, change summary against the active release, customer preview (the exact public payload), preview approval, submit, approve (with reference), schedule, activate, roll back |
| Media | Upload images or models (filename discarded), the object list with scan state |
| Import and export | Dry run, create drafts, export |

**Gap (stated):** records are edited as JSON documents, not per-kind forms. The server validates every field, so a wrong document is refused, not stored. Typed forms per kind are the next UX increment. The slice was created through the same service paths the forms would use.

## 8. Customer screens

`/estimate-v3` is a separate page. It runs only when `veda-estimator-version=v3` and is stripped from staging builds without an approval record. The flow:

1. **Home.** Choose a home (from home configurations), new home or renovation, and a package. Consultation-only packages are shown disabled.
2. **Rooms.** Room cards show:
   - the representative image, labelled;
   - the include toggle;
   - counts of included items and selected extras;
   - room ideas (gallery);
   - per item: name, description, "What is this?", "Typically used for", style choice, finish choices with their material statements, "See examples" and "View in 3D";
   - extras with images and quantity where countable.
3. **Estimate.** The page shows:
   - the range;
   - rounded room amounts;
   - the configuration reference and the catalog release;
   - next-step and disclaimer copy from catalog records.

   "Refine with measurements" lists only the measurements of the selected items. The quotation link records `quotation_requested`.

**Open:**
- The "selection intent" step.
- Approved estimate-impact ranges per extra. The `show_impact` flag exists, but no approved ranges exist.

## 9. API catalog

**Staff** (`/api/v1/catalog`):

| Method | Path | Permission |
|---|---|---|
| GET | `/dashboard`, `/records`, `/records/<id>`, `/records/<id>/events` | `catalog.view` (pricing hidden without `catalog.pricing.view`) |
| POST | `/records`; `/records/<id>/submit`, `/archive`, `/new-version`, `/clone` | The kind's edit permission |
| PUT | `/records/<id>` | The kind's edit permission (DRAFT only) |
| POST | `/records/<id>/approve`, `/reject` | `catalog.review` (never one's own) |
| GET | `/releases`, `/releases/<id>`, `/releases/<id>/customer-view` | `catalog.view` |
| POST | `/releases/<id>/preview-estimate` | `catalog.view` (ranges only, nothing stored) |
| POST | `/releases`, `/releases/<id>/validate`, `/submit`, `/schedule`, `/activate`, `/rollback` | `catalog.admin` |
| POST | `/releases/<id>/preview-approval`, `/approve`, `/reject` | `catalog.approve` |
| POST, GET | `/media`; `/media`, `/media/<sha>` | `catalog.media.edit`; `catalog.view` (variants only) |
| POST, GET | `/import`, `/export` | `catalog.admin` (pricing rows need `catalog.pricing.edit` / `.view`) |
| GET | `/configurations/<reference>`, `/analytics` | `catalog.view` |

**Public** (RBX-008). Each route returns 404 unless the flag is on:

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/public/catalog` | Customer view |
| POST | `/api/v1/public/catalog/estimates` | Turnstile; the same layered limits as V2 |
| GET | `/api/v1/public/catalog/media/<sha>` | CLEAN variants of the ACTIVE release only; immutable cache; `nosniff`; sandbox CSP |
| POST | `/api/v1/public/catalog/events` | Also needs the analytics flag |

## 10. Permission matrix

| Permission | Founder | Admin | Sales | Sensitive (MFA) | Grants |
|---|---|---|---|---|---|
| `catalog.view` | ✓ | ✓ | | | View records, releases, previews (no rates) |
| `catalog.edit` | ✓ | | | | Homes, rooms, products, extras, packages, rules |
| `catalog.pricing.view` | ✓ | | | BULK_DATA | Read pricing records |
| `catalog.pricing.edit` | ✓ | | | BULK_DATA | Edit pricing records |
| `catalog.media.edit` | ✓ | | | | Upload media; media records |
| `catalog.spec.edit` | ✓ | | | | Materials, hardware, copy |
| `catalog.review` | ✓ | | | | Approve or reject records (four-eyes) |
| `catalog.approve` | ✓ | | | ACCESS_CONTROL | Preview and release approval (four-eyes) |
| `catalog.admin` | ✓ | | | ACCESS_CONTROL | Releases, schedule, activate, roll back, import, export |

- No employee is granted anything automatically.
- A denied request returns 403 or 404 with no record contents.
- Pricing records answer 404 to users without pricing access.
- Every table is audited `FULL`. Catalog documents are excluded from the audit trail because pricing documents hold rates; their SHA-256 is audited instead.

## 11. Pricing adapter

Configuration → `compile.resolve` → `engine.EstimateRequest` → `engine.calculate` (unchanged) → `service.store` (unchanged).

**Mapping:**
- Each item resolves to its variant's engine product plus options. Choices add options, and option-setting extras override them.
- Adding extras append engine selections.
- Measurements are accepted only for declared prompts, within their bounds.

**Pricing records:**
- A pricing record is either the card settings or one engine product (`ratecard.ProductSpec`, validated on save).
- The release compiles them into `CATALOG-<code>`. `ratecard.parse` validates the card, and so does the estimator's PII refusal.

**Fail-closed behaviour:**

| Case | Result |
|---|---|
| Pricing missing (unpriced product, option, room or package) | Validation error |
| Two records for one engine product | Validation error |
| More than one settings record | Validation error |
| An inactive record | Never in a release |

**Not supported:** city adjustments, minimum charges and waste rules beyond the engine's own. The engine has no such inputs, and changing it was not in scope.

## 12. Rules model

**Ten rule types** over reference paths (`room:`, `product:k[#variant][@group=choice]`, `extra:`), with optional conditions (property type, home size, project kind, package, market):

| Rule type | Effect |
|---|---|
| `requires` | Refuses the subject unless its objects are also selected |
| `excludes` | Refuses the subject with any of its objects |
| `compatible_with` | Refuses the subject without at least one of its objects |
| `available_only_for` | Refuses the subject outside the condition |
| `hidden_when` | Refuses the subject inside the condition |
| `default_when` | Preselects; never refuses |
| `measurement_bounds` | Refuses a measurement outside its range |
| `requires_consultation` | Refuses; the subject is priced after a consultation |
| `unavailable_online` | Refuses online; staff preview may price it |
| `staff_only` | Refuses in public and hides the subject |

- **Implicit rules:** each record's availability, the package's products, the room's offered items and extras, and variant and choice visibility.
- **Contradictions** (requires-and-excludes, mutually exclusive requirements, self-reference) fail validation.

## 13. Media architecture

| Area | Behaviour |
|---|---|
| Upload | Staff only. Base64 JSON over the authenticated API (size-capped body); no public upload |
| Sniffing | By magic bytes; the declared type and filename are ignored |
| Images | 15 MB limit; decompression-bomb cap of 40 MP |
| Models | 25 MB limit; GLB must be glTF 2.0, JSON chunk first, length exact, no external URIs, no required extensions. USDZ must be stored entries only, USD first, no path escapes, allow-listed types |
| Re-encoding | EXIF orientation applied, every metadata block dropped, WebP thumbnail (320), mobile (768) and desktop (1600) |
| Storage | `source/<sha>` and `variant/<sha>`; never the filename. Local filesystem now; bucket is an owner decision |
| Scanning | clamd INSTREAM when configured. With no scanner, CLEAN only in local and test; staging and production stay PENDING_SCAN, which validation refuses. The `catalog-media-scan` job rescans |
| Delivery | Only CLEAN variants referenced by the ACTIVE release. `public, max-age=31536000, immutable`, plus `nosniff` and a sandbox CSP. Content-hash URLs version the cache (CDN-compatible). Sources are never served or listed publicly |
| Rights | Each media record has owner, licence, usage and expiry. Expired rights fail validation |

**Open:**
- Video upload: refused until a transcoder is chosen; video is an EXTERNAL_EMBED record on youtube-nocookie or Vimeo meanwhile.
- Media manifest import.
- Retire/replace UI and storage lifecycle rules.

## 14. 3D abstraction

**Data (`media.three_d`):**
- model version;
- preview image (IMAGE record) and fallback gallery (GALLERY record);
- supported devices and dimensions;
- material, variant and finish maps;
- hotspots and camera presets;
- rights in the media record;
- created by and reviewed by in the record trail.

**Validation:**
- the preview must be an IMAGE and the fallback a GALLERY;
- the web file must be a validated model;
- the variant and finish maps must name existing records.

**Customer component (`Viewer3D`):**
- the preview image shows first;
- nothing loads until "View in 3D";
- it renders only if a `<model-viewer>` renderer is present, and none is vendored (owner decision), so today it falls back to the gallery with an explanation;
- 3D analytics (start, success, fallback) are recorded;
- it never blocks or changes the estimate. The configuration is recorded by the API, independently of the viewer.

Full-catalog 3D is **not** started, as instructed.

## 15. Representative vertical slice

The slice is synthetic and generated: `seed.py`. Its images are drawn in code and labelled "Illustrative example".

**Contents:**
- Living Room → TV Unit:
  - **wall-panelled variant:** laminate or veneer panelling (materials with statements);
  - **box variant:** open shelves or soft-close storage drawers (hardware with a governed promise).
- **Feature-wall extra:** measured, engine `FEATURE_WALL`.
- **Soft-close storage extra:** sets the box option and requires the box variant (rule).
- **Room and product galleries.**
- **A GLB model:** preview image and fallback gallery.
- **TV-wall width rule:** 3–20 ft.
- **Disclaimer and next-step copy.**

**Proven:**

| Claim | Evidence |
|---|---|
| Admin can create and approve records | API tests, staff API |
| A valid configuration is accepted; invalid ones are blocked | API and browser |
| The gallery displays | Browser |
| 3D falls back safely | Browser |
| Pricing uses approved rules | Box < soft-close storage; feature wall adds; measurement refines; laminate = veneer on the synthetic card, stated |
| The snapshot persists exact versions | Asserted per kind |
| Staff can reopen the configuration | `GET /catalog/configurations/<ref>` |

**Promise owner:** the seed leaves the soft-close promise owner `UNASSIGNED`/BLOCKED, so the seed alone cannot be released (validation shows it). Tests and the local tool use role placeholders, never people.

## 16. V2 migration

`veda catalog migrate-v2 <private card file> [--dry-run]`.

**Inputs:**
- the operator's card;
- `v2_bundles.json`, extracted from `estimate-v2.js` and kept in step by `test_v2_bundles_match_the_v2_page`;
- the V2 copy file.

**Creates DRAFT records only:**
- the card settings and one pricing record per engine product (order kept);
- property types and packages (Essential's subtitle as a promise, BLOCKED with UNASSIGNED owners);
- one product per V2 included item, with V2's refine measurements;
- one extra per V2 extra (counts kept; the asta chakra as a pooja option);
- one room template per V2 room;
- the 3 BHK home.

**Behaviour:**
- Idempotent: unchanged records are skipped, and an open draft is reported, never overwritten.
- V2 stays authoritative: nothing is released.
- V3 can be discarded by dropping the six tables. No V2 row references them.

## 17. V2/V3 equivalence evidence

`test_v2_migration_round_trips_the_card_and_every_request` (synthetic card) checks:
1. The migrated pricing compiles back to the V2 card. Canonical JSON is identical apart from the version string.
2. For three representative V2 states (default 3 BHK; extras plus asta plus measurements; a room off, counted extras and optional painting), a Python port of `estimate-v2.js selections()` and V3 `resolve()` produce the **same `EstimateRequest`**.
3. The engine results are identical: low, high and base. GST, allowance, package and preparation follow from the identical request and card.

Not run in this package: real-card equivalence (`run-real-card.sh` style) against the private card. It needs the owner's card, outside the repository.

## 18. Tests and results

| Suite | Result |
|---|---|
| API, full (SQLite and PostgreSQL) | 2160 tests: 0 failures, 0 errors, 11 skipped (pre-existing anchor-history skips) |
| `tests/integration/test_catalog.py` | 85: 41 on each engine plus 3 engine-independent. Covers lifecycle, four-eyes, releases, rollback, schedule, slice, 9 refusals, public view, media delivery, RBAC, media security, import/export, migration, equivalence and bundle parity |
| OpenAPI snapshot, ruff, format | Pass |
| `tests/unit/test_catalog_rules.py` | 14: every rule type, default_when, availability, contradictions, 3D, permission matrix |
| Config | V3 flags refused in production, allowed in staging; four-eyes enforced when deployed |
| Workspace unit (wtr), lint, types, tokens, contrast | Pass (77 unit tests) |
| Staging build | 10/10, including "V3 not in a build without its approval record" |
| Browser journey `estimator-v3.e2e.mjs` | 20/20 (in `run-all.sh`) |
| Secret scan (`detect-secrets` baseline) | No new findings |

## 19. Media-security results

All are in `test_catalog.py`:

| Test | What it proves |
|---|---|
| `test_images_are_reencoded_without_metadata` | A JPEG carrying camera make and GPS EXIF comes out as WebP with no EXIF, stored by hash, CLEAN in test |
| `test_unsafe_uploads_are_refused` | SVG, executable, MP4 (transcoder), truncated JPEG and truncated GLB are refused |
| `test_glb_with_external_references_is_refused` | A GLB pointing at an external file is refused |
| `test_without_a_scanner_deployed_media_stays_pending` | No scanner on staging means PENDING_SCAN |
| `test_public_media_serves_only_active_clean_variants` | The variant is served with immutable caching and `nosniff`; the private source and unknown hashes give 404 |
| `test_media_upload_route_needs_media_permission` | Admin without `catalog.media.edit` gets 403 |

## 20. Accessibility results

**Browser journey (390 px wide):**
- axe (WCAG 2.0/2.1/2.2 A and AA) passes on the home, rooms and result screens;
- no CSP violations and no page errors.

**Page structure:**
- fieldsets with legends;
- labelled inputs;
- native `<dialog>` gallery (Escape closes);
- `<details>` disclosures;
- an alert summary that takes focus;
- 44 px targets;
- reduced motion respected.

**Fallbacks:** alt text is required by schema for every visual type, and a broken image is replaced by its text.

**Workspace screen:** uses the design-system components, and the contrast check passes.

## 21. Rollback plan

| Level | Action | Effect |
|---|---|---|
| Catalog content | `POST /catalog/rollback` | Re-activates the previous release's whole manifest (tested) |
| Feature | Leave or set `VEDA_CATALOG_ESTIMATOR_ENABLED=false` | Every public V3 route returns 404; the staging build has no V3 page without approval |
| Code | Revert the branch's commits | V1 and V2 are untouched. Migration 0103 is expand-only: the N-1 image never reads the six tables |
| Data | The tables can be left in place or dropped | No existing row references them; V3 estimates are ordinary `budget_estimate` rows with origin PUBLIC |

## 22. Independent-review package

This document is the package.

**Suggested review focus:**
- `compile.resolve` (the only path from customer choice to price);
- `validation.py` (the activation gate);
- `media.py` (untrusted input);
- `routes.py` (permission per action, pricing hiding);
- `kinds.parse` (promise-word governance);
- the public customer view (`compile.customer_view`).

## 23. Open owner decisions

1. Object-storage bucket and malware scanner for staging, and the media host or CDN with its `img-src` CSP entry.
2. 3D renderer library (licence and size), or keep the gallery fallback.
3. Video transcoder (or embeds only).
4. XLSX library for imports.
5. The imagery identity: real project photography with rights, or commissioned references.
6. Whether approved estimate-impact ranges per extra are shown, and who approves them.
7. Whether pricing needs city or minimum-charge adjustments (an engine change, reviewed separately).

## 24. Human-governance dependencies

These are not done, and none of them is fabricated:
- Promise owners, backups and verification paths for every catalog promise. The slice's soft-close statement is `UNASSIGNED`/BLOCKED.
- Sales and operations sign-off on V3 copy.
- Owner approval of a V3 release, and of a V3 staging activation record (the file `api/veda/modules/catalog/approved/v3-staging-approval.json` does not exist).
- The V2 track continues separately:
  - Round 1 homeowner validation;
  - Part 1 and Part 2 approvals;
  - ESSENTIAL-1.1 activation;
  - public-intake approval.

## 25. Staging blockers

- An approved V3 staging activation record. The build refuses `STAGING_ESTIMATOR_VERSION=v3` without it.
- A media bucket and scanner. Without a scanner, uploads stay PENDING_SCAN and no release with media validates.
- A media host and the matching CSP entry.
- Promise governance for every promise a staging release would show.
- Migration 0103 applied on staging. It is expand-only.

## 26. Public-intake blockers

- Everything in §25.
- The V2 public-intake approval, which is still pending.
- The homeowner validation of V3.
- Approved real imagery with rights.
- Pricing records from the owner's approved card.
- Independent review of this branch.

## 27. Production blockers

- `config.validate_environment` refuses `VEDA_CATALOG_ESTIMATOR_ENABLED` and `VEDA_CATALOG_ANALYTICS_ENABLED` in production. Lifting that is a reviewed change.
- Everything in §26.
- A production media host, bucket and scanner.

## 28. Recommendation

- **Review this branch independently** as a unit, focused on §22.
- **Do not merge before that review.** If it is merged after review, it changes nothing for customers: the flags stay off, and the V3 page is not in staging builds.
- **Next increment, after review:**
  - typed per-kind admin forms;
  - the selection-intent step;
  - real-card equivalence against the private card;
  - the owner decisions in §23.

  Full-catalog expansion and full 3D wait for the vertical slice to be validated with people.

**Verdict:** READY FOR CATALOG-DRIVEN ESTIMATOR V3 INDEPENDENT REVIEW
