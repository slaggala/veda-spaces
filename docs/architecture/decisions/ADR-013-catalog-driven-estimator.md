# ADR-013: Catalog-driven estimator (Estimator V3)

**Status:** Proposed. Implemented behind `VEDA_CATALOG_ESTIMATOR_ENABLED=false`, for independent review.
**Instruction:** `VEDA-SPACES-CATALOG-DRIVEN-ESTIMATOR-V3` (owner).

**Context:**
- V1 and V2 are configured in code and in operator-loaded files: the rate card JSON, the customer specification JSON,
  and the V2 room bundles and copy in `estimate-v2*.js`.
- The owner wants admins to configure homes, rooms, products, extras, materials, hardware, packages, pricing, rules,
  media and copy without code changes.
- Customer-promise governance (ADR-012, the promise matrix and the activation gate) must not be bypassed.

## Decisions

**D1. The catalog is a versioned authoring layer that compiles to the artefacts the engine already uses.**
- A catalog *release* compiles to:
  - a rate-card document, validated by `ratecard.parse`;
  - the customer-facing catalog view (rooms, products, extras, materials, media, copy; no rates);
  - a resolution table from customer choices to engine selections.
- The ADR-012 pricing engine prices every V3 estimate, unchanged. There is no second pricing engine.
- V2/V3 equivalence is provable by round-trip: migrating V2's card and room bundles into the catalog and compiling them
  back yields the same card (canonical JSON) and the same engine request, so the estimate is identical.

**D2. Records are typed, versioned documents.**
- Each catalog record is identified by `(kind, key, version)`.
- Its document is validated by the pydantic schema of its kind: property type, home configuration, room template,
  product family, product (with variants, option groups and options), extra, material, hardware, media, package,
  pricing, rule, copy.
- References between records are by key and resolved within a release.
- *Why not one table per entity:* about 60 entity types with deep nesting would need dozens of tables and
  migrations for every new attribute.
- *Why typed documents:* they keep strict validation, immutability and a full audit trail. A new attribute becomes a
  schema change plus a review, not a database migration. Catalog sizes (hundreds to a few thousand records) do not
  need relational querying inside documents.

**D3. The lifecycle is explicit, and only releases make anything customer-visible.**
- **Records:** `DRAFT → IN_REVIEW → APPROVED`, then `SCHEDULED`, `ACTIVE`, `RETIRED` and `ARCHIVED` through releases.
  Only `DRAFT` versions can be edited; any change to approved or active content creates a new version.
- **Releases:** an immutable manifest of exact `(kind, key, version, sha256)` entries, plus the compiled-artefact
  digests. Lifecycle: `DRAFT → IN_REVIEW → APPROVED → SCHEDULED → ACTIVE → RETIRED`.
- **Activation** needs the full validation suite (D7), a recorded customer-preview approval, and an approver who did
  not author the release when four-eyes review is on (the default).
- **Rollback** re-activates the previous release's whole manifest, never individual rows.

**D4. Every V3 estimate snapshots exact versions.**
- A configuration snapshot stores the release id, the manifest digest, the version of every record the configuration
  used, the customer's selections, the resolved engine request (pricing inputs), and the estimate it produced.
- The estimate also keeps its own rate-card and specification snapshots (ADR-012).
- Admin edits never touch released versions, so history is never rewritten.

**D5. Rates are private.**
- Pricing records (rates, formulas, minimums, package and city adjustments) are readable only with
  `catalog.pricing.view` and are never part of the public catalog view, the customer copy or any browser bundle.
- Estimate impact for an extra is shown only as an approved, rounded range, and only where the record opts in.

**D6. Media is admin-only, private at source and validated.**
- **Uploads:**
  - staff only, with `catalog.media.edit`;
  - size-limited and MIME-sniffed;
  - images re-encoded by Pillow, which strips metadata and generates the thumbnail, mobile and desktop variants;
  - stored under content hashes, never under the uploaded filename.
- **Scanning:** a malware-scan hook marks objects `CLEAN`. Where no scanner is configured, objects stay `PENDING_SCAN`
  on staging and production, so they cannot be approved.
- **Delivery:** only variants referenced by an `ACTIVE` release are served publicly, under immutable, versioned URLs.
  Source objects are never listed or served publicly.
- **3D:** GLB, glTF and USDZ files are validated structurally, require a preview image and a fallback gallery, and are
  never used for price, scope or deliverability.

**D7. Activation validation:**
- schema validity;
- reference integrity;
- pricing completeness (every selectable item resolves to an engine product and option that the compiled card prices);
- specification completeness;
- media validity (clean, approved, alt text, rights not expired);
- promise registration (every customer statement is a registered copy record with its governance fields;
  promise-bearing statements need owners and verification paths);
- compatibility rules (no contradictory rules; every default configuration valid);
- the compiled card validates.

All checks fail closed.

**D8. Rules are data.**
- **Rule types:** `requires`, `excludes`, `compatible_with`, `available_only_for`, `hidden_when`, `default_when`,
  `measurement_bounds`, `requires_consultation`, `unavailable_online`, `staff_only`.
- They are evaluated server-side on every configuration, and unsupported combinations are refused.
- The browser mirrors them for immediate feedback but is never authoritative.

**D9. Isolation.**
- **Flags:**
  - `VEDA_CATALOG_ESTIMATOR_ENABLED` defaults to false; every V3 public route then answers 404, and production
    refuses true.
  - `VEDA_CATALOG_ANALYTICS_ENABLED` defaults to false; production refuses true.
  - `STAGING_ESTIMATOR_VERSION=v3` is refused by the staging build until an approved V3 activation record exists.
- **Compiled cards** are stored as `CATALOG-<release>` card versions and never become the V1/V2 active card;
  `activate-card` refuses them.
- **V1 and V2** are untouched.

**D10. Least privilege.**
- **Permissions:**
  - `catalog.view`
  - `catalog.edit` (content)
  - `catalog.pricing.view` and `catalog.pricing.edit`
  - `catalog.media.edit`
  - `catalog.spec.edit`
  - `catalog.review`
  - `catalog.approve`
  - `catalog.admin` (releases, schedule, rollback)
- **Grants:** the Founder role holds all of them by default; Admin holds only `catalog.view`. Everyone else is
  granted individually. No employee is assigned automatically.
- **Separation of duties:** approval is refused to the record's last editor or the release's author while four-eyes
  review is on.

## Consequences

- One engine, one source of commercial truth per release, and reproducible estimates.
- The admin experience edits documents through typed forms. A new attribute needs a schema change and a review, which
  is a deliberate control on customer-visible content.
- **Owner decisions:**
  - the object-storage bucket and malware scanner on staging (infrastructure);
  - the public media host (API or CDN) and the matching `img-src` entry in the site's Content-Security-Policy;
  - the 3D renderer library to vendor (licence and size);
  - a video transcoder (until then video is an `EXTERNAL_EMBED` record; direct video upload is refused);
  - the XLSX import library;
  - the visual identity of reference imagery.

## Implementation notes

- A record's version column is `record_version`: `version` is the platform's optimistic-lock column on every table.
- The pricing adapter is `compile.resolve`: configuration → `engine.EstimateRequest`. Product order in the compiled card
  follows each pricing record's `position`, so a migrated V2 card compiles back byte-for-byte (canonical JSON).
- A room's preset options apply only to its own variant; a customer who switches variant starts from that variant's
  defaults.
- Copy with `promise: false` may not contain promise words, so the flag cannot be used to skip governance.
- Extras may name hardware or materials; their names are then governed by those records' statements.
