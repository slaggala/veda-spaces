# ADR-012: Budget Estimator (budgetary estimate, then lead capture)

- **Status:** **Proposed.** Design only, nothing implemented. Owner inputs in §9 are needed before implementation.
- **Date:** 2026-10-08
- **Constraints:**
  - `public_intake` stays **disabled**, and Cloudflare Access stays on; anonymous use waits for ADR-011.
  - **The estimator never produces a quotation.** It produces a **Budgetary Estimate**: a range, a timeline band and a
    warranty summary.
  - **No rates in this repository.** The repository is public and the rate card is commercially sensitive, so rates
    live in a versioned rate card loaded as data (§3.4). Tests use a synthetic card.

## 1. Context

A visitor wants a rough budget before talking to Veda Spaces. Staff price real projects with a **quotation workbook**,
whose structure is:
- **Rooms** (sections A, B, C…), each with **lines**: description, specification, width, height, quantity
  (sq ft, running ft or pieces) × rate = amount.
- **Mandatory project items:** deep cleaning, debris removal, protection sheets, freight, soft-close hinges, pest
  control. These scale with home size.
- **Client scope**, excluded from the quotation: sink, tiles, granite, taps.
- **GST** at 18%, shown separately.
- Tabs for specifications, commercial terms, the payment schedule and client scope.
- **Timeline bands by project value:**
  - below ₹20 L: 2 months + 10 days;
  - ₹20–27 L: 2.5 months + 12 days;
  - ₹27–35 L: 3 months + 14 days;
  - each plus a 10-day grace period.
- The **Warranty, Service & Customer Care Policy**: plywood up to 10 years, tandems 3 years, channels and hinges
  5 years, electrical 1 year, one year of free service, and the exclusions.

The roadmap `QUOTE` module (10-future-roadmap) models a quotation as `quotation` and `quotation_line` (room, item,
spec, quantity, UOM, rate, tax). **The estimator reuses that line structure as its pricing engine**, so an estimate can
later seed a draft quotation.

## 2. Decision

Build the estimator as a **server-side pricing engine** over a **versioned rate card**:
- **On the site:** a **wizard** on the public site collects rooms, measurements and preferences.
- **On the server:** the API turns these into quotation-style lines at a chosen package level (Essential, Premium,
  Luxury). It returns a **range**, a **timeline band**, a **warranty summary** and the disclaimers, and keeps an
  immutable snapshot under a reference.
- **Lead capture:** the visitor can then request a detailed quotation through the **existing public lead intake**
  (Turnstile, consent, idempotency), with the estimate reference attached.

**Why server-side:**
- one engine for the site, the staff app and later quotations;
- the rate card stays versioned and auditable;
- staff see exactly what the customer saw;
- nothing in the browser can change a price.

## 3. Pricing model

### 3.1 Supported rooms and their lines (from the quotation structure)

| Room | Customer inputs (typical defaults offered) | Lines priced (quotation item → quantity basis) |
|---|---|---|
| **Kitchen** | Layout (straight, L, U, parallel), counter run length (ft), wall units yes/no, loft yes/no, drawer count | Base unit (run × base height, sq ft); wall unit (run × wall height); loft (run × loft height); tandem drawers (each); plumbing labour and materials (lump); granite laying (lump). Sink, tiles, granite and taps are client scope |
| **Wardrobe** | Width (ft), height (default 7 ft), hinged or sliding, loft yes/no, glass profile yes/no | Wardrobe (W × H); loft (W × loft height); sliding-door hardware (lump); glass profile (sq ft) |
| **TV unit** | Wall width, unit style (box only, box + side storage, full panelling), glass profile | Side storage (W × H); TV box (W × H); wall panelling (W × H, panelling rate); glass profile |
| **False ceiling** | Ceiling area (sq ft) or room size, design (plain, cove, cloud), lighting density, veneer accent (running ft) | Gypsum ceiling (sq ft); cove or cloud (running ft); panel, COB, spot and profile lights (each or running ft); fan points (each) |
| **Study unit** | Width, with overhead storage yes/no | Study unit (W × H); overhead storage (W × H) |
| **Vanity** | Type (toilet 2×2, dresser/standing), width, mirror type, storage above | Vanity (W × H, vanity rate) or toilet vanity (lump); mirror (each); storage above (W × H) |
| **Bed** | Size (queen, king), storage (none, hydraulic), headboard (panel, cushioned) | Bed (W × L); hydraulic fitting (lump); headboard panel (W × H, panel rate); cushion (lump) |
| **Living room** | Feature wall (panelling, wallpaper, texture), crockery unit width, partition width, sofa-back beading length | Panelling (W × H); wallpaper (rolls); texture paint (sq ft); crockery unit (W × H); partition (W × H, partition rate); beading (running ft) |

**Project-level lines**, added once and scaled by home size (1/2/3/4 BHK):
- mandatory items (cleaning, debris, protection, freight, soft-close hinges, pest control);
- optional painting (sq ft, paint tier per package).

Electrical wiring is quoted per home and is offered as an optional line.

### 3.2 Package levels

| Level | Meaning (from the specification tab and the paint sheet) | Rate basis |
|---|---|---|
| **Essential** | The current quotation specification: laminate finish (up to the stated laminate sheet value), specified plywood and block board, standard hardware brands | The rate card's base rates |
| **Premium** | Upgraded finishes (higher laminate or acrylic), upgraded hardware | Base × a per-item Premium factor, or explicit Premium rates. **Owner input** |
| **Luxury** | Premium finishes (PU/lacquer/veneer), top hardware tiers | Base × a per-item Luxury factor, or explicit Luxury rates. **Owner input** |

Painting already has three tiers on the painting rate sheet (Premium, Luxury, Super Luxury). They map to Essential,
Premium and Luxury.

### 3.3 Computation

For each selected room and line:
```
quantity = f(inputs)                      # e.g. width × height (sq ft), run length, count; rounded to 0.1
line     = quantity × rate[package]       # integer paise, half-up rounding per line
room     = Σ lines
subtotal = Σ rooms + project lines(BHK)
low      = subtotal × (1 − band_low)      # band from the input confidence: measured vs typical sizes
high     = subtotal × (1 + band_high)
```

- **Range:**
  - measured inputs use a narrower band than "use typical size" inputs. **Owner input**; the proposal is
    −10 % / +15 % measured and −15 % / +25 % typical;
  - both ends are rounded to the nearest ₹5,000.
- **GST:** shown separately ("plus GST at 18 % as applicable"). The workbook applies GST to part of the value, which is
  a commercial decision for the final quotation, not the estimate.
- **Excluded and listed:** client-scope items (sink, tiles, granite, taps), civil work, appliances and décor.
- **Timeline band:** from the **upper** estimate, using the commercial-terms bands. Above the last band:
  "confirmed after design".
- **Warranty summary:** fixed text derived from the policy, filtered to the selected rooms (for example tandems only
  when a kitchen is selected), always with "subject to the Warranty, Service & Customer Care Policy".
- **Lead lookup mapping:**
  - the range's midpoint gives `budget_range_code` (existing `BUDGET_RANGE` lookups);
  - the room selection gives `project_type_code` (`FULL_HOME` for three or more room types or any BHK package,
    `MODULAR_KITCHEN`, `BEDROOM_WARDROBE`, `LIVING_DINING`).

### 3.4 Rate card

A **rate card** is a versioned document. Each item has:
- `item_code`, `room_type`, label and specification text;
- `uom` (`SFT`, `RFT`, `NOS`, `LUMP`);
- `rates` for the three package levels (integer paise);
- default dimensions;
- a quantity formula, from a closed set of formula kinds (`area`, `length`, `count`, `lump`, `rolls`).

A card has `version`, `effective_on`, a status (`DRAFT`, `ACTIVE`, `RETIRED`) and `approved_by`. Only one card is
ACTIVE. Every estimate records the card version it used.

- **Storage:** database rows loaded by an admin CLI from a private file, **not committed**.
- **Repository:** the schema and a **synthetic** test card only.

## 4. Data model (additive; no change to `lead`)

| Table | Columns (main) | Notes |
|---|---|---|
| `estimator_rate_card` | `version` (unique), `status`, `effective_on`, `approved_by`, `notes` | One ACTIVE (partial unique index) |
| `estimator_item` | `rate_card_id`, `room_type`, `item_code`, `label`, `spec`, `uom`, `formula`, `rate_essential_minor`, `rate_premium_minor`, `rate_luxury_minor`, `default_params` (JSON) | Read-only once the card is ACTIVE |
| `budget_estimate` | `public_reference` (short, unguessable), `rate_card_version`, `package_level`, `home_size`, `inputs` (JSON: rooms, measurements, preferences), `lines` (JSON snapshot, quotation-line shaped), `subtotal_minor`, `range_low_minor`, `range_high_minor`, `timeline_band`, `warranty_items` (JSON), `lead_id` (nullable, set at capture), `expires_on` (created + 15 days, the quotation validity), `created_via` | **No personal data.** Immutable after creation, except `lead_id` |
| `lead` | unchanged | Linked from `budget_estimate.lead_id` |

**Audit and retention:**
- rate cards: FULL audit;
- estimates: EVENT_ONLY;
- unlinked estimates are deleted after a retention period (**owner input**; proposal: 90 days);
- linked estimates follow the lead's retention (OWNER-INPUT-002).

## 5. Customer flow

1. **Home:** apartment or villa, and 1/2/3/4 BHK. This sets the project lines and the typical sizes.
2. **Rooms:** select any of the eight room types, with counts (for example 3 wardrobes, 2 vanities).
3. **Measurements:** per room, simple inputs with a **"use a typical size"** option. Imperial feet, matching the
   workbook, with an inline diagram.
4. **Preferences:** package level (Essential, Premium, Luxury, with "what's included" from the specification tab) and
   per-room options (layout, sliding or hinged, loft, lighting).
5. **Budgetary Estimate:**
   - the range (low to high), with a breakdown by room;
   - the timeline band and the warranty summary;
   - exclusions and disclaimers;
   - the reference and its validity (15 days).
6. **"Get my detailed quotation":** the existing enquiry form, pre-filled from the estimate (project type, budget
   range, rooms in the message), plus name, phone, consent and Turnstile.
7. **Thank you:**
   - the lead reference;
   - "our designer will call within one working day";
   - the WhatsApp hand-off is kept.

**Disclaimers** (always shown):
- "This is a Budgetary Estimate, not a quotation."
- "Final pricing follows a site measurement and approved design."
- "Excludes GST, civil work and client-scope items (sink, tiles, granite, taps)."
- "Valid for 15 days."

## 6. UI flow

- **Public site:** a new `/estimate` page in `app/e2e/site-release`, using the site's plain JavaScript and design
  tokens.
  - A progress stepper, one step per screen on mobile, with Back and Next.
  - State is kept in `sessionStorage` (nothing personal).
  - The result is accessible: the range as text, the breakdown as a table, axe-clean.
- **Feature flag:** `<meta name="veda-estimator">`. It is empty in the committed (production) site, so the page shows
  "coming soon" and the "Estimate my budget" call to action is hidden. The staging build switches it on.
- **Staff app:** a "Budgetary Estimate" panel on the lead detail (rooms, package, range, card version, created
  date), a link to the snapshot, and later "Start quotation from estimate" (QUOTE module).
- **Telemetry:** step completion counts only (no personal data), to tune drop-off.

## 7. Lead-capture integration

| Step | Mechanism |
|---|---|
| Create the estimate | `POST /api/v1/public/estimates`: no personal data; returns `{reference, range, lines_by_room, timeline, warranty, disclaimers, expires_on}`. Anonymous route under `/api/v1/public/`, so same CORS rules and rate limits. Turnstile is **not** required here (no personal data), but it is per-IP rate-limited |
| Read it back | `GET /api/v1/public/estimates/<reference>`: the same body, until expiry (lets the page reload) |
| Capture the lead | The existing `POST /api/v1/public/leads`, plus one **optional** field `estimate_reference`. **This needs an ADR-005 amendment**, because the public schema is closed. Unknown or expired references are ignored (stored in `intake_unmapped`) and **never reject the enquiry** (LEAD-030). `budget_range_code` and `project_type_code` come from the estimate. The message summarises rooms and package |
| Link | In the lead-creation transaction: `budget_estimate.lead_id = lead.id` |
| Notify | The `lead.created` email and in-app notification add "Budgetary Estimate ₹X–Y (Essential, 3 rooms)" |
| Staff view | The lead detail panel (§6). A new permission `estimate.read`, granted with `lead.read` |

**Not changed:** public intake stays disabled; the estimator runs on staging behind Access. Anonymous production use
needs ADR-011 (its intake host must also forward `/api/v1/public/estimates`) and an owner decision.

## 8. Implementation roadmap

| Phase | PR | Contents | Gate |
|---|---|---|---|
| E0 | (owner) | §9 inputs; rate card v1 prepared privately from the quotation workbook | Owner |
| E1 | Pricing engine | `veda/modules/estimator/engine.py` (pure; formula kinds; rounding; range; timeline; warranty; lookup mapping); rate card schema validation; **synthetic** card; unit tests (golden cases, rounding, bands, every room, package factors, BHK scaling); property tests (monotonic in size and level) | CI |
| E2 | API + data | Migration (3 tables, expand-only); admin CLI `estimator load-card / activate-card`; public estimate routes; RBAC `estimate.read`; staff `GET /leads/<id>/estimate`; rate limits; OpenAPI; tests (no personal data stored, card version recorded, expired reference, inactive card refused) | CI; `12-deploy` |
| E3 | Lead integration | ADR-005 amendment; `estimate_reference` on public intake (never rejects); link in transaction; notification text; tests | CI; `12-deploy` |
| E4 | Public wizard | `/estimate` page, flag-gated; staging build sets the flag; site e2e (each room, each package, typical sizes, result, capture) and axe | CI; Pages |
| E5 | Staff panel | Lead detail panel; tests; e2e | CI; Pages |
| E6 | Staging validation | Rate card v1 loaded on staging (owner); end-to-end: estimate, then lead, then the staff panel; spot-check three real past quotations against the engine (within the stated band); `13-evidence` | Owner sign-off |
| E7 | (later) | Anonymous production use under ADR-011; QUOTE module "start quotation from estimate" | Owner decisions |

## 9. Owner inputs needed

1. **Premium and Luxury rates** or factors per item (only Essential, the quotation specification, is known).
2. **Range bands** (proposal: measured −10/+15 %, typical −15/+25 %), and whether to show a single "from ₹X" number
   instead.
3. **Mandatory-item scaling** for 1, 2 and 4 BHK and villas (the workbook gives 3 BHK only).
4. **Typical sizes** per room and BHK (defaults for "use a typical size").
5. **Painting and electrical:** included as optional lines?
6. **Retention** of unlinked estimates (proposal: 90 days).
7. Whether rate cards are maintained by staff in the app (later) or only loaded by an admin.
8. **Policy text review:** the warranty policy notes legal and tax review before it becomes standard. The estimator
   shows a summary only, with a link to the full policy.

## 10. Security and privacy

- **No personal data before consent:** the estimate holds only rooms, measurements and preferences; personal data
  enters only through the existing consented lead form.
- **Prices cannot be tampered with:** all computation is server-side; the client sends inputs, never prices.
- **Bounded input:** closed schema; numeric ranges per input (for example width 1–60 ft); at most 30 rooms; body size
  limit.
- **Abuse:** per-IP rate limit on estimate creation; references are random and unguessable; snapshots expire.
- **Rate confidentiality:** the rate card is not in the repository. Individual line amounts are visible to whoever
  uses the estimator. Showing only room totals is an **owner option** (§9).
