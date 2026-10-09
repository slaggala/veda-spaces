# Catalog-driven estimator (V3): independent-review package (remediated)

- **Instructions:** VEDA-SPACES-CATALOG-DRIVEN-ESTIMATOR-V3, then VEDA-SPACES-CATALOG-ESTIMATOR-V3-REMEDIATION.
- **Decision record:** [ADR-013](../../architecture/decisions/ADR-013-catalog-driven-estimator.md).
- **Companions:**
  - [media infrastructure design](CATALOG-V3-media-infrastructure.md), prepared, not active;
  - [owner decisions](CATALOG-V3-owner-decisions.md), proposed, not approved.
- **Branch:** `feature/catalog-estimator-v3` (PR #66), from `main` at `18dcf0a`.
- **State:** every V3 switch is off by default, and production refuses each one.

Nothing here activates V3, changes V1 or V2, enables public intake, or changes production behaviour.

## Merge versus activation boundaries

| Boundary | What it allows | Status |
|---|---|---|
| **Merge** | The code on `main` with every switch off: public V3 routes return 404, the staff catalog API returns 404, no media is served, and the V3 page is not in staging builds | Eligible once CI is green and the reviewer re-certifies |
| **Protected-staging review** | V3 on staging behind Cloudflare Access with `VEDA_CATALOG_ADMIN_ENABLED`, then `VEDA_CATALOG_ESTIMATOR_ENABLED` | Blocked: §25 |
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
| R2, R3 promise wording | Promise-like wording is refused in every customer-visible descriptive string and in non-promise copy, with no exemptions: warranty, guarantee, certification, free, included, excluded, installation, delivery, timelines, grades, brands, service, soft-close. A promise is a copy record that names its matrix row and the products, rooms or packages it applies to. It must be registered text of a confirmed ESSENTIAL-1.1 row with named owners | `test_catalog_promises.py`: 18 phrases × 4 places; matrix linkage cases |
| R4 staff-only visibility | Staff-only products, variants, choices, extras, rooms, packages, homes and staff_only rule subjects are removed before serialisation, references included, and refused in public configurations | `test_staff_only_items_are_neither_shown_nor_selectable` |
| R5 rule paths | Every rule path must name a real product, variant, group, choice, extra or room. `#boxx` fails validation | 6 misspellings refused; valid paths pass |
| R6 package and extra pricing | Phased resolution: engine selections are built only after schema, visibility, package filtering, applicability and rules all pass. Excluded items are refused, never priced. Selected = resolved normal form = priced request = stored snapshot | `test_selected_resolved_priced_and_stored_configurations_reconcile` |
| R7 raw customer JSON | A strict allowlisted schema: catalog keys, closed literals, bounded numbers, no free text, no city. The snapshot stores only the normal form. Snapshots follow estimate retention (audited soft delete plus event), and staff can action deletion requests | 6 free-text and unknown-field cases; retention; deletion |
| R8 public errors | Malformed payloads get 4xx with fixed messages. Path segments that are not keys or indexes are masked. No value, schema detail, identifier or stack trace is returned | 24 malformed payloads, non-JSON, wrong types |
| R9 rollback | Rollback creates a new release with the previous manifest's exact entries (`rollback_of_id`), re-validated and activated. No release row is reset | Exact versions, rules, pricing, copy and media restored; card identical; estimates untouched |
| R10 scheduled rejection | One step clears the schedule and every approval and returns SCHEDULED records to APPROVED. The event records what was cleared | `test_rejecting_a_scheduled_release_clears_everything_and_keeps_history` |
| R11 image limit | 24,000,000 pixels and 8,000 per side, checked from the header before decoding | Boundary at, below and above; forged bomb headers |
| R12, R13 | **Not supplied in the remediation instruction.** No finding text was provided for these, so nothing is claimed resolved under these numbers. Layers F (media infrastructure) and G (3D safety) were implemented as written | The reviewer is asked to confirm what R12 and R13 refer to |
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
- **Soft-close storage:** **blocked from every release (H2).** Its matrix row `spec.soft_close` is BLOCKED and its owner
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
| V3 browser journey | 34/34 |

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
