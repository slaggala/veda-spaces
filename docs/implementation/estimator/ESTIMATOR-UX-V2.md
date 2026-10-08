# Budgetary Estimate: customer experience V2

**Owner decision (2026-10-08, decision log 21):**
- Do not continue the room-by-room, measurement-first wizard.
- The ADR-012 pricing engine is complete; its rules, API and rate card stay unchanged.
- The estimator customer experience becomes a separate product workstream.

This document holds the UX brief, the wireframes, the clickable prototype specification, the data still needed for
other home sizes, and the migration plan.

## 1. UX brief

### 1.1 Problem

The V1 wizard was shaped like a quotation:
- a grid of rooms × products (about 60 checkboxes for a 3 BHK);
- width, height and units for every product before any number appears;
- options on a separate step;
- errors reported after the fact ("At most 1").

Customers do not think in products or dimensions. Staging validation showed the result: a confusing flow and avoidable
dead ends.

### 1.2 What customers need

| Customer question | V2 answer |
|---|---|
| "Roughly what will my home cost?" | A range within about a minute, without measurements or contact details |
| "What does that include?" | Plain-language inclusions for each room, the grouped preparation package, the allowance, GST shown separately |
| "Can I make it fit my budget?" | Rooms on and off, a few optional extras, the package, and the range again |
| "How sure is this number?" | Assumptions stated. "Tighten your range" with measurements, only if wanted |
| "What happens next?" | One clear call to action: get a detailed quotation (designer call, site measurement) |

### 1.3 Principles

1. **Estimate first.** The first range comes from home type, BHK, project type, rooms and package only.
2. **Measurements later.** Typical sizes are used and labelled. Measurements are an optional refinement.
3. **Homes, not products.** Customers choose rooms and recognisable extras ("Study desk", "Dressing unit"), never
   product codes, units or quantities of carcass.
4. **Prevent, don't reject.** Only choices the active card can price are shown. One-per-home items appear once.
   Nothing reachable produces a server validation error.
5. **No contact details to see the estimate.** This is a differentiator: Bonito and Asian Paints ask for contact
   details before the result.
6. **Honest and complete.** Range not price; GST separate; the Project Preparation & Protection Package and the Custom
   Features Allowance are always visible (ADR-012 D4, D5, D9).
7. **Mobile first.** One decision per screen, thumb-reachable actions, 360 px without horizontal scroll, WCAG 2.2 AA.

### 1.4 Success measures (prototype test and staging)

| Measure | Target |
|---|---|
| Completion to the first estimate (unaided) | 5 of 5 participants |
| Time to the first estimate | Under 2 minutes |
| Dead ends or error messages met | 0 |
| Participants who can say what the range includes | 4 of 5 |
| System Usability Scale | 80 or more |
| Accessibility | axe clean on every screen; keyboard-only completion |

### 1.5 Out of scope

- No change to the pricing engine, the rate card, the API, the database or the staff panel.
- Premium pricing stays disabled until validated (D1).
- Luxury stays consultation-only (D2).
- Public intake (E7) is a separate decision.

## 2. Flow and wireframes (mobile, 360 px)

```
Home type → BHK → New / Renovation → Rooms → Package → Your budget range → Get my quotation → (optional) Tighten your range
   1         2          3              4        5              6                   7                     8
```

A progress bar shows **"Step n of 5"** across screens 1–5. Screens 6–8 are outcomes, not steps. Back always keeps
every answer. A change on any screen re-enables the estimate (§3.4).

### Screen 1: Home type
```
┌────────────────────────────────────┐
│ VEDA SPACES               Contact │
│ Step 1 of 5  ■□□□□                 │
│                                    │
│ What kind of home is it?           │
│                                    │
│ ┌────────────────────────────────┐ │
│ │ ▣  Apartment                   │ │
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ □  Villa / independent house   │ │
│ │    Online estimates coming     │ │
│ │    soon. Talk to a designer →  │ │
│ └────────────────────────────────┘ │
│                                    │
│ [            Continue →          ] │
└────────────────────────────────────┘
```
- Only the property types the active card prices can be selected (`veda-estimator-property-types`). The others are
  shown with "coming soon" and a consultation link, never an error later.

### Screen 2: BHK
```
┌────────────────────────────────────┐
│ Step 2 of 5  ■■□□□                 │
│ How many bedrooms?                 │
│                                    │
│  ( 1 BHK )  ( 2 BHK )  [ 3 BHK ]   │
│  ( 4 BHK )                         │
│                                    │
│  1, 2 and 4 BHK: coming soon.      │
│  Talk to a designer →              │
│                                    │
│ City or area (optional)            │
│ [ Kondapur, Hyderabad            ] │
│                                    │
│ [ ← Back ]        [ Continue → ]   │
└────────────────────────────────────┘
```
- The sizes come from `veda-estimator-home-sizes`. In staging only 3 BHK can be selected.

### Screen 3: New home or renovation
```
┌────────────────────────────────────┐
│ Step 3 of 5  ■■■□□                 │
│ Is this a new home or a            │
│ renovation?                        │
│                                    │
│ ┌────────────────────────────────┐ │
│ │ ▣ New home                     │ │
│ │   Just handed over, empty      │ │
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ □ Renovation                   │ │
│ │   Lived-in home, some work     │ │
│ │   to replace                   │ │
│ └────────────────────────────────┘ │
│ [ ← Back ]        [ Continue → ]   │
└────────────────────────────────────┘
```

### Screen 4: Rooms (the heart of V2)
```
┌────────────────────────────────────┐
│ Step 4 of 5  ■■■■□                 │
│ Which rooms should we design?      │
│ We've selected what most 3 BHK     │
│ homes include. Change anything.    │
│                                    │
│ ┌──────────────────────────── ✓ ┐  │
│ │ Kitchen                        │  │
│ │ Modular kitchen, wall units,   │  │
│ │ loft                           │  │
│ │ + Tall pantry storage      [ ] │  │
│ └────────────────────────────────┘  │
│ ┌──────────────────────────── ✓ ┐  │
│ │ Master bedroom                 │  │
│ │ Wardrobe with loft, bed with   │  │
│ │ storage                        │  │
│ │ + Dressing unit            [ ] │  │
│ │ + Study desk               [ ] │  │
│ │ + TV unit                  [ ] │  │
│ │ + Bedside tables     [–] 0 [+] │  │
│ └────────────────────────────────┘  │
│ … Bedroom 2, Bedroom 3, Living,     │
│   Dining, Pooja, Utility …          │
│ ┌──────────────────────────── ✓ ┐  │
│ │ Whole home                     │  │
│ │ False ceiling with lights,     │  │
│ │ profile lighting               │  │
│ │ + Painting (optional)      [ ] │  │
│ │ + Electrical work (optional)[ ]│  │
│ └────────────────────────────────┘  │
│ [ ← Back ]        [ Continue → ]   │
└────────────────────────────────────┘
```
- **Room card on or off:** the ✓ on each card turns the room on or off. A room that is off contributes nothing.
- **Inclusions:** each card lists the room's standard inclusions in plain language.
- **Extras:** shown as switches, or as a −/+ count where countable. Extras appear only when the room is on.
- **Whole-home items appear once.** Profile lighting, painting and electrical are one per home. The pooja unit is in
  the Pooja room card, or offered as "Pooja unit" in Dining when there is no Pooja room. Nothing can be chosen twice.
- **Defaults:** the starting selection is the owner-approved typical selection for the BHK (§3.2).

### Screen 5: Package
```
┌────────────────────────────────────┐
│ Step 5 of 5  ■■■■■                 │
│ Choose your finish                 │
│                                    │
│ ┌────────────────────────────────┐ │
│ │ ▣ Essential                    │ │
│ │   Laminate finishes, branded   │ │
│ │   plywood, soft-close hardware │ │
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ □ Premium — pricing coming soon│ │  (disabled)
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ □ Luxury — Priced after a      │ │
│ │   design consultation          │ │
│ └────────────────────────────────┘ │
│ [Cloudflare: verify you're human]  │
│ [ ← Back ]  [ See my budget → ]    │
└────────────────────────────────────┘
```
- **Turnstile** sits here, the first point that calls the API.
- **Luxury** turns the button into "Request a design consultation" and goes to screen 7 in consultation mode, with no
  amount (D2).

### Screen 6: Your budget range
```
┌────────────────────────────────────┐
│ VEDA SPACES PRELIMINARY            │
│ BUDGETARY ESTIMATE                 │
│                                    │
│   ₹18,50,000 – ₹24,50,000          │
│   + GST (about ₹3.3 – 4.4 L)       │
│   3 BHK apartment · Essential      │
│   Based on typical 3 BHK sizes     │
│                                    │
│ [   Get my detailed quotation →  ] │
│ [   Tighten your range (optional)] │
│                                    │
│ ▸ What's included (by room)        │
│ ▸ Project Preparation & Protection │
│   Package                          │
│ ▸ Custom Features Allowance        │
│ ▸ Timeline · Warranty · Not included│
│ ▸ Assumptions                      │
│                                    │
│ Estimate VS-AB12-CD34 · valid 30 d │
└────────────────────────────────────┘
```
- **Range first** in large type, then the two actions.
- **Details below in disclosure sections:** room subtotals rounded to ₹1,000, the package with its six inclusions,
  the allowance range and its explanation, timeline, warranty summary and policy link, exclusions, client scope, and
  the assumptions list.
- **Disclaimer:** always visible at the bottom, verbatim from the engine.

### Screen 7: Get my detailed quotation (lead capture)
```
┌────────────────────────────────────┐
│ Get my detailed quotation          │
│ A designer will call you within    │
│ one working day and arrange a      │
│ free site measurement.             │
│                                    │
│ Name *            [              ] │
│ Phone *           [ +91          ] │
│ Email             [              ] │
│ Prefer   (•) Call ( ) WhatsApp     │
│          ( ) Email                 │
│ [✓] I agree to be contacted …      │
│     (Privacy Notice v2026-09-v1)   │
│ [Cloudflare: verify you're human]  │
│                                    │
│ Want a tighter range first?        │
│ Tighten your range →  (optional)   │
│                                    │
│ [ ← Back ]  [ Send my request → ]  │
└────────────────────────────────────┘
```
- **Confirmation** shows the customer reference and "what happens next". In consultation mode (Luxury) the heading,
  button and confirmation say "design consultation", and no estimate is shown or linked.

### Screen 8: Tighten your range (optional refinement)
```
┌────────────────────────────────────┐
│ Tighten your range                 │
│ Add what you know. Leave the rest  │
│ — we'll keep typical sizes.        │
│                                    │
│ Kitchen                            │
│  Counter length   [ 12 ] ft ▾  ⓘ   │
│ Master bedroom wardrobe            │
│  Width            [    ] ft ▾  ⓘ   │
│  Sliding doors    [ ]              │
│ Living TV wall                     │
│  Width            [    ] ft ▾  ⓘ   │
│ Whole home ceiling                 │
│  Ceiling area     [    ] sq ft ▾ ⓘ │
│                                    │
│ [   Update my range   ]            │
│  ₹19,00,000 – ₹23,50,000  (new)    │
│ [ Get my detailed quotation → ]    │
└────────────────────────────────────┘
```
- **Fields:** only the measurements that move the price most, at most one or two per selected item, in the order of
  the rooms. Each has a hint and a typical-size placeholder. A few options that matter (sliding doors) sit next to
  them. Everything is optional.
- **"Update my range"** requests a new estimate (an immutable snapshot, as today) and shows the new range. Screen 7
  then links the latest estimate.

## 3. Clickable prototype specification

### 3.1 Prototype scope and build

| Item | Specification |
|---|---|
| Purpose | Usability test of the V2 flow before building it. Five moderated sessions (§3.6) |
| Build | Static HTML/CSS/JS in the site's visual language, mobile first, no framework. Hosted as a Pages preview behind Cloudflare Access (staging), **never on the public site** |
| Pricing in the prototype | **No API and no rates.** Ranges come from a canned table keyed by rooms on and off, extras and package. The numbers are illustrative, from the synthetic card, and labelled "prototype" in small text. Real numbers come only from the built V2 on staging |
| Lead capture | The form validates but sends nothing |
| Instrumentation | A local event log (screen shown, control changed, time on screen) exported at the end of a session for the facilitator. No personal data |

### 3.2 Room bundles (configuration, owner-approved; no rates)

Each room card expands to the engine selections below: product, room and the default options of the card. **No
measurements are sent unless screen 8 adds them**, so typical sizes are used.

| Room card (3 BHK default) | Standard inclusions → engine selections | Extras (off by default) → engine selections |
|---|---|---|
| Kitchen ✓ | KITCHEN (wall units, loft, granite laying) | Tall pantry storage → STORAGE_BOXES (TALL, room KITCHEN) |
| Living room ✓ | TV unit → TV_UNIT (PANELLED) | Feature wall → FEATURE_WALL; Sofa-back beading → VENEER_ACCENTS (BEADING); Partition → PARTITION; Window seating → WINDOW_SEATING |
| Dining ✓ | Crockery unit → CROCKERY_UNIT | Wash-basin vanity → VANITY_UNIT (DRESSER, room DINING); Feature wall; Veneer arch → VENEER_ACCENTS (ARCH); Pooja unit (when there is no Pooja room) → POOJA_UNIT (room DINING) |
| Master bedroom ✓ | Wardrobe → WARDROBE; Bed with storage → BED (KING); Bathroom vanity → VANITY_UNIT (TOILET) | Dressing unit → VANITY_UNIT (DRESSER); Study desk → STUDY_UNIT; TV unit → TV_UNIT (BOX); Window seating; Feature wall; Bedside tables (count 0–2) → STORAGE_BOXES (BEDSIDE_TABLE) × n |
| Bedroom 2 ✓, Bedroom 3 ✓ | WARDROBE; BED (QUEEN); VANITY_UNIT (TOILET) | As for the master bedroom |
| Pooja room ✓ | POOJA_UNIT (room POOJA) | Ceiling asta chakra → POOJA_UNIT option ASTA_CHAKRA = YES |
| Utility ✓ | UTILITY | — |
| Whole home ✓ | False ceiling with lights → FALSE_CEILING (WHOLE_HOME); Profile lighting → CEILING_PROFILE_LIGHTING (WHOLE_HOME) | Painting → PAINTING; Electrical work → ELECTRICAL (both optional, D6) |

- **Default selection:** the typical 3 BHK selection is 16 selections, well within the API limit of 40.
- **Engine limits are enforced in the UI, never by an error.** The bundle configuration carries each product's
  per-home limit from the card (for example vanity units 6, storage boxes 10, kitchen 1) and the API limit of 40
  selections:
  - an extra that would pass a limit is shown disabled, with "Limit reached for your home";
  - the room card says which choice uses the limit.
  - **Worked check (every extra on, 3 BHK):** vanity units would reach 7 (three bathroom vanities, three dressing
    units, a dining wash-basin) against 6, and the total would reach about 47 against 40.
  - **Owner choice U2-10:** prevent those combinations (the default rule above), or ask for an API change raising
    the limits. That is a deliberate exception to "engine unchanged", so it is not assumed.
- **Source:** the defaults reflect what all three historical 3 BHK quotations contained.
- **Owner approval:** the inclusions per room are a business decision. **Owner approval of this table is input U2-1**
  (§4).

### 3.3 Screen states, validation and copy

| Screen | States | Validation (prevent, never reject) |
|---|---|---|
| 1 Home type | default (Apartment); unsupported type (disabled, consultation link) | None reachable |
| 2 BHK | default (the only supported size); unsupported sizes (disabled, consultation link) | City optional, at most 60 characters, allowed characters only |
| 3 Project | default (New home) | None |
| 4 Rooms | per card: on, off, extras open; "nothing selected"; limit reached | Continue is disabled until at least one room is on, with an inline hint. Counts are clamped (bedside tables 0–2). Extras that would pass a per-home product limit or the 40-selection limit are disabled with "Limit reached for your home" (§3.2) |
| 5 Package | Essential selected; Premium disabled; Luxury selected (consultation mode) | Turnstile: the button stays enabled and a failed check is explained inline, not as an error page |
| 6 Result | loading (skeleton, up to 10 s); result; API unavailable (friendly message plus WhatsApp and phone) | Network failure: "We couldn't reach our estimator. Try again, or WhatsApp us." Not "You appear to be offline" |
| 7 Lead | form; sending; sent; consultation mode | Name and phone required; consent required; inline messages linked from the summary (U7 pattern) |
| 8 Refine | fields empty with typical placeholders; updating; updated | Numbers only; bounds hinted beforehand (for example "between 0.5 and 150 ft"); units switch per field |

### 3.4 Navigation and state rules

- **Back keeps every answer.** A change before screen 6 marks the estimate stale and shows "See my budget" again.
  Screen 6 is never shown with stale inputs.
- **State lives in the tab (`sessionStorage`).** A reload returns to the same screen, with expired estimates dropped.
  A new tab starts fresh.
- **One request per action.** Screens 5 and 8 obtain a fresh Turnstile token for each request (Turnstile `execute`
  mode, so no repeated checkbox) and debounce double clicks.
- **The latest estimate is the one linked** when the lead is sent from screen 7.

### 3.5 Mapping to the unchanged API

- **Estimate requests:** `POST /api/v1/public/estimates` with `property_type`, `home_size`, `project_kind`, `city`,
  `package` and `selections[]` built from the room bundles (§3.2), with `measurements` only from screen 8.
- **Lead requests:** `POST /api/v1/public/enquiries` as today: `estimate_reference`, `preferred_contact`, or
  `consultation: "LUXURY_DESIGN"`.

**Refinement after the lead is sent:** the unchanged API cannot attach a later estimate to an existing lead. V2
therefore offers refinement **before** sending (screen 7 links to it). After sending, the confirmation says the
designer will measure at the site visit, and staff can revise the estimate from the lead (the existing staff
"Revise"). Customer refinement after sending would need a small API addition; it is out of scope.

### 3.6 Usability test plan

| Item | Plan |
|---|---|
| Participants | Five Hyderabad homeowners planning interiors for a 3 BHK apartment (new or recent handover), mixed ages, at least two who mainly use phones |
| Format | Remote, moderated, 30 minutes, think-aloud, on their own phone. Prototype first, then 5 minutes on V1 for comparison |
| Tasks | 1) "Find out roughly what interiors for your home would cost." 2) "Leave out the third bedroom and add a study desk in the master bedroom." 3) "You know your kitchen counter is 14 feet: use that." 4) "Ask Veda Spaces for a detailed quotation." 5) "What does the 'Project Preparation & Protection Package' include?" |
| Measures | §1.4 |
| Output | Findings, severity and changes; a go/no-go for building V2 |

## 4. Data still needed

The engine refuses what the card cannot price, and V2 does not show it. Each item below unlocks one scope; none is
needed to start V2 for 3 BHK apartments.

| ID | Input | Needed for | Detail |
|---|---|---|---|
| U2-1 | **Room bundles** (§3.2): standard inclusions and extras per room | V2 build (3 BHK) | Approve or edit the table |
| U2-2 | Room list per size | Other sizes | Which room cards exist for each size (for example 1 BHK: kitchen, living, 1 bedroom, utility; 4 BHK: 4 bedrooms, often a study or family room) |
| U2-3 | **Preparation amounts** for 1, 2 and 4 BHK | Unlocks each size | The six components: floor protection, plywood protection, freight, debris handling, deep cleaning, pest control |
| U2-4 | **Typical sizes** for 1, 2 and 4 BHK | Each size | Median kitchen run and drawers, wardrobe widths and heights per bedroom, TV wall, ceiling area, painting wall area, carpet area, profile length, pooja and utility widths. **Five or more past projects per size** preferred (3 BHK used three) |
| U2-5 | **Historical quotations** for calibration | Each size | At least 2–3 per size (2 BHK first), to re-run E6: every total inside its range, base within ±10 % |
| U2-6 | **Villas**: villa factors for the preparation components; typical sizes; whether villas have rooms the current list lacks (staircase panelling, extra floors, family lounge) | Villas | The engine has no floors or staircase concept. Villas may need new product types (an ADR-012 data change, not a UX one) |
| U2-7 | Timeline bands for larger homes | 4 BHK, villas | Confirm the open last band ("confirmed after design") suits large projects |
| U2-8 | A fourth independent 3 BHK quotation | Confidence | Already open |
| U2-9 | Customer copy for each room card and extra | V2 build | Plain-language names and one-line descriptions, reviewed by sales |
| U2-10 | Limits with every extra on | V2 build | Keep the engine limits and prevent the combinations in the UI (default), or approve an API change raising them |

## 5. Migration plan from the current wizard

| Phase | Work | Gate |
|---|---|---|
| M0 Now | Keep V1 on staging only for correctness validation (pricing, privacy, scope, linking, accessibility: V1–V12, not usability). Merge the stopgaps (#53 CORS, #54 one-per-home). **No V1 usability work** | Owner (done: this decision) |
| M1 Prototype | Build the clickable prototype (§3.1). Test it with five participants (§3.6). Iterate once | Test meets §1.4, or findings accepted by the owner |
| M2 Build V2 | Rewrite `estimate.html`/`estimate.js` for V2 in `site-release`, behind a build switch `STAGING_ESTIMATOR_UX=v2`, so V1 stays for rollback. Room bundles live in one config object (no rates), with a test that every bundle maps to products, rooms and options the card accepts, and that the
  "everything on" selection for each supported size respects every per-home and request limit (the synthetic card in CI; the private card in a local rehearsal). Keep the U7 error pattern, Turnstile, the CSP and the rounding | CI: e2e for every screen and state, axe on every screen, 360 px, no CSP violations |
| M3 Staging | Pages `STAGING_ESTIMATOR_UX=v2`. Re-run V1–V12, plus the §1.4 measures with 2–3 internal users. Compare stored estimates for identical scopes in V1 and V2 (the same engine input gives the same range) | Owner sign-off |
| M4 Retire V1 | Remove the V1 code and the switch. Update the runbook and the e2e | After M3 |
| M5 Public | ADR-011 E7 (intake hostname, edge rate limit), legal review of the policy, owner enablement | Separate owner decision |

**Unchanged throughout:**
- the pricing engine, the rate card, the API, the database and the stored-estimate format;
- the staff panel, which already shows estimates as products and lines;
- retention and the privacy rules.

Estimates created by V1 and V2 are indistinguishable to staff and to the engine.
