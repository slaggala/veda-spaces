# MTQ independent review of record (business-reality review, 2026-10-13)

**Status:** IMMUTABLE RECORD. Verbatim text of the only independent review of the MTQ blueprint (PR #83) and the survey and scope-template system (PR #84) that exists on record. It is the review of record for gate MTQ-G1. Do not edit; corrections are appended to [MTQ-B1-blocker-closure.md](../MTQ-B1-blocker-closure.md).

| Provenance | Value |
|---|---|
| Instruction | `VEDA-SPACES-MTQ-BUSINESS-REALITY-REVIEW` (owner, 2026-10-13) |
| Reviewer independence | The instruction states "You did not author PR #83 or PR #84. Review only. Do not implement." The review session wrote nothing to the repository |
| Lenses | Principal Architect, Senior Interior Design Consultant, Commercial Head, Estimation Lead, Operations Lead |
| Review session | Claude Code session `2f2a9290-a5eb-405a-9491-b7ede39b2fb3`, final message `9e08786d-a34e-44ea-8267-edf73910feb8`, 2026-10-12T19:36:16Z (UTC; 2026-10-13 IST) |
| Session transcript fingerprint (SHA-256, owner-held file) | `f4d6514091121f39f7a7d316488cd601cc0329fbbbac52f9762299a94d30989e` |
| Verdict | **READY WITH REQUIRED CHANGES** (B1 only) |
| Reviewed revisions | PR #83 blueprint package, PR #84 template system, as cited in the text below |
| Transcribed | 2026-10-13 under `VEDA-SPACES-MTQ-B1-END-TO-END-IMPLEMENTATION`; text copied byte-for-byte from the final message except this header and the closing offer line, which is kept |

The owner also reported a separate "architecture review". No such review exists on PR #83, #84, #85 or #86, in the repository, in the owner's private folders, or in any session transcript on the owner's machine. This review carries the architecture-soundness lens (§1 below) and is the only non-author review, so it is the review of record. Dispositions of every finding are in [closure §1.1 and §1.4](../MTQ-B1-blocker-closure.md).

---

# VEDA-SPACES-MTQ-BUSINESS-REALITY-REVIEW

Scope reviewed: PR #83 (`faf7bb8`, blueprint package, 6 files) and PR #84 (`e7e319d`, survey and scope-template system, 7 files), read in full and checked against the Essential 1.1 rate-card schema and fixture, ADR-012, the E6 historical validation and the specification. Nothing was written to the repository.

**Headline.** The architecture is sound and genuinely BHK-free. The survey system is thorough but over-specified for a first deployment. The scope templates are strong on carpentry and weak on the small recurring items that E6 showed create the price gap. Quotation generation cannot yet reproduce today's quotation because five commercial facts are missing (preparation-package basis beyond 4 BHK, GST practice, payment schedule, discount authority, post-acceptance variations). Villas are structurally covered but operationally under-designed. Commercial is structurally covered and commercially absent.

## 1. Architecture soundness

Sound in its core commitments: property as a space tree, walls as the unit of truth, millimetre storage with derived centi-feet, one pricing engine, revisioned hash-sealed aggregates pinned to a catalogue release. The coverage matrix's claim that no property type needs a new column holds for residential.

Weak points the templates expose:

- **Rule evaluation model is too small for the rules proposed.** Blueprint §8.1 evaluates rules per space in priority order. PR #84 proposes about 70 rules, several of which read sibling spaces or the whole property: dining ceiling fires when the living ceiling is included, one plumbing lump per property shared across kitchen and utility, a false-ceiling bundle when two or more spaces confirm, project rules driven by counts across spaces. The engine needs a property-level pass and a specified grammar before any rule is keyed (coverage gap G-1 is now blocking, not advisory).
- **"No new column" already strains.** Niche depth has no column (author notes it), commercial partitions are triggered by a free-text note "proposed", and L-shaped rooms cannot be reconstructed from wall lengths without a turn direction per corner. Three small schema additions are needed and should be admitted now rather than smuggled into JSON.
- **Rate-card driver change is not additive.** Replacing the home-size band with declared drivers changes the card document schema, the validator and the engine's refusal logic, and requires the private card to be re-authored and re-approved. The blueprint calls this additive; it is a new card major version.
- **B1 depends on catalogue authoring it says it does not need.** B1 creates the `space_template` kind and the first templates, and seeds spaces from them, while Catalogue V3 administration is off in production and AD-4/6/8 remain open. Either templates ship as migration seeds in B1 or Catalogue V3 activation becomes a B1 prerequisite.
- **No design stage.** The lineage goes measurement to scope to quotation. Real quotations follow a layout drawing. There is a `DESIGN_CHECK` visit type but no design artefact linked to a scope revision and no "design confirmed" state. Rules derive widths from walls; designers decide module splits, loft heights and layouts, and the quotation must follow the designer.

## 2. Survey practicality

A trained surveyor can follow the W1-clockwise, offset-from-start-corner convention; it is the method the better survey apps use. The problem is volume and blocking.

Excessive:

- Photo minimums produce 120 to 180 photos for a 2 BHK and 400 to 700 for a villa, each uploaded through the malware scanner that was deployed yesterday and has not finished its soak. Keep the laser-reading photo on tagged walls only and one entry-door photo per room; make the rest optional.
- Offset and swing are REQ for every opening on every wall, including toilets and balconies. Offsets matter only on walls that carry a product; elsewhere width and height suffice for paint deductions.
- The toilet template has nine REQ items for a space whose only product is a recommended vanity. Make them COND on the vanity being wanted.
- Sixteen submit checks and fifteen property-level REQ items block submission. Several belong in the ops hand-off, not the capture gate.
- The playbook's 2.0 to 2.5 hours for a 2 BHK including discovery is roughly three times today's visit. The blueprint's own adoption risk (§19) is the right one.

Missing:

- Turn direction per wall (left or right) or mandatory vertex entry for L-shaped rooms. Without it floor area and perimeter cannot be derived.
- Door architrave intrusion from the adjacent wall at a corner, the commonest reason a wardrobe is 100 mm narrower than the wall.
- Floor-to-lintel is COND on "loft wanted", which is only known after discovery. Make it REQ in bedrooms and kitchens; it is one laser shot.
- Existing light, fan and AC drain positions on the ceiling; the templates capture AC type and counts but not positions, which drive the ceiling design.

Ambiguous:

- W1 for rooms with no door (open-plan living entered from a foyer) or two doors (kitchen with dining and utility doors).
- `derived_level_count`: the blueprint counts distinct level indices, template 01 §11.5 proposes indoor spaces only. Pick one.
- Servant room counts as a bedroom in the lookup but is excluded from the preparation driver by proposal. Decide, because it moves the mandatory package amount.
- Unit system fixed per set, while surveyors mix laser (mm) and tape (feet-inches) within one room.

## 3. Scope-template quality

Mandatory choices are defensible: TV unit in living, wardrobe plus loft in master and secondary bedrooms, kitchen base auto with declinable wall units, crockery unit in a true dining room, desk in a study, pooja unit in a pooja room, nothing mandatory in guest rooms, toilets, utilities and balconies. Master-bedroom false ceiling as MANDATORY for new homes is the one I would drop to RECOMMENDED.

Mandatory items missing:

- Dismantling and disposal on renovation projects is RECOMMENDED. It is a cost incurred on every renovation and should be MANDATORY when existing work is marked "going".
- Kitchen tall unit is a NEW LINE priced manually. Nearly every kitchen quoted today has one.

Optional items missing (these are exactly what E6 found uncovered and folded into the allowance):

- Curtain pelmets in gypsum on window walls.
- Extra drawers, mirror panels, sensor lights.
- Electrical point shifting when a switchboard sits on a tagged wall (the rule shortens the wardrobe instead; today's practice is to move the switchboard).
- Loft above the entry and toilet doors in bedrooms, present only in the toilet template.
- Chimney duct boxing.
- Handle system choice (G-profile versus handles) as a priced option.

Unnecessary or mislabeled:

- Beading is marked NEW LINE; the card carries `VENEER_ACCENTS.BEADING` and ADR-012 §3.1 lists it.
- The plumbing lump "code to confirm" is `KITCHEN.PLUMBING`. `UTILITY.SINK_LAYING` exists on the card and no template references it.
- ADR-012 §3.1 lists granite laying as a priced kitchen lump; the card has no such line and the template calls it client scope. One of the three is wrong.
- `TRANSPORT` adjustment "by distance band" double counts the package's `FREIGHT` component unless defined as an out-of-city delta.
- Natural light and sunlight side attributes carry no pricing effect and add capture time.

## 4. Quotation-generation readiness

Structure matches today's document: room-wise lines with quantity, UOM and amount, a grouped preparation package, optional painting and electrical, exclusions, terms, timeline bands from the card. Beyond structure:

- **Allowance contradiction.** Property rule `PROJECT_ALLOWANCE` emits a 5 to 15 % range on every quotation "always". Blueprint §9.4 says a fully measured estimate is a single number. A signed quotation cannot carry an open range. Replace with fixed provisional-sum lines or the itemised extras above.
- **Preparation package basis.** The card prices the six components by home size 1 BHK to 4 BHK plus CUSTOM with a per-component villa factor. At E6 only 3 BHK amounts were approved. There is no basis for 5 BHK, duplex levels or commercial, so the one mandatory line on every quotation cannot be priced for most of the property types the mission names until OI-MTQ-05 is resolved with new card content.
- **GST.** ADR-012 §3.3 records that the workbook applies GST to part of the value. Per-line rates can express that, but which lines are taxable is a compliance decision, and the customer total can move by up to 18 % of the untaxed portion.
- **Payment schedule and terms** exist only in the private workbook tab. No quotation can be sent.
- **Materials.** The promise matrix requires brand and material named per line, and HDHMR shutters named explicitly. `material_key` and `hardware_key` exist on scope items, but the catalogue material and hardware records they point at do not.
- **Labour and installation** are embedded in rates, consistent with Essential 1.1 "room amounts include installation". Fine.
- **Execution variances.** Deviations are recorded after the fact, but there is no variation or change-order quotation. ACCEPTED is terminal and a v+1 supersedes it, which destroys the contract basis. E6 quotation C is exactly an execution-stage revision.
- **Unit rates hidden by default** changes the document customers receive today, where rate per square foot per line is shown.

## 5. Villa readiness

- **Staircase** has a space type but no template, no rule group and no wall-area formula; stair walls are stepped or sloped, so `length × CH` is wrong. Add a minimal template and per-segment wall heights.
- **Terraces and sit-outs** are adequately covered as outdoor and semi-open spaces with furniture confined to covered parts. Exterior painting, deck flooring and pergolas are NEW LINE or exclusions; exterior painting is a large villa item and should be in the OI-MTQ-05 list.
- **Utility spaces, servant rooms, stores, basements** are covered, with the dampness risk check in the right place.
- **External structures** are notes and exclusions only, which is correct for an interiors business.
- **Operational gap.** Villas need two or three surveyors over one or two days, and the second-set policy is "verifier re-keys the other surveyor's spaces". With 400 to 700 photos that is not a workable interim. The merge rule must exist before villas enter the ten-site B1 validation.
- **Two pricing mechanisms** for multi-level work: the card's existing villa factor on package components and the blueprint's `level_count` driver plus `FLOOR_FACTOR`. Reconcile to one.
- Double-height living volumes are captured but scaffolding cost is only an unprompted site factor.

## 6. Commercial readiness

The model supports commercial structurally: a polygon shell per level, zones as child spaces, partitions from zone edges, workstations as counts, per-line GST. Commercially it is absent:

- The estimator, specification and promise matrix are residential only; the engine's property types are APARTMENT and VILLA.
- Reception desks, workstations, conference tables, glass partitions, grid ceilings, carpet and display units are all NEW LINE, so most of the value of a commercial quotation is manually rated.
- Shared partitions between adjacent zones are captured on both zones' wall rows and double count. A partition needs one identity.
- The partition trigger is a note reading "proposed". Add a boolean.
- No preparation-package driver or amounts for commercial.
- Company customers need a legal entity name and GSTIN on the quotation; neither lead nor property carries them.

Keep commercial as a structural non-goal for B1 to B3 and give it its own specification, card and go/no-go decision.

## 7. Missing capabilities

- Variation and change-order quotations after acceptance.
- Fixed provisional sums in place of the allowance range.
- Design artefact linked to a scope revision with a design-confirmed state.
- Second-surveyor set merge.
- Staircase template and stair-wall area.
- L-shape geometry capture.
- Shared partition entity and `is_proposed` flag.
- Catalogue material and hardware records for per-line naming.
- Customer legal entity and GSTIN.
- Stable scope-item identity across regeneration so BOQ diffs survive a scope revision (today's diff key is the scope item id, which changes).
- Attachment anonymisation cascade with the lead purge (interior photographs of occupied homes).

## 8. Top 10 business risks

1. **High.** A quotation document carries a percentage range (allowance rule) and is not a contract.
2. **High.** The mandatory preparation package has no pricing basis for 5 BHK, duplex, commercial and most villas.
3. **High.** No post-acceptance variation model while execution-stage revisions are the norm.
4. **High.** Survey burden drives surveyors to FREEFORM and ASSUMED, so quotations come out banded and adoption fails.
5. **High.** GST practice today is partial; any formalisation changes customer totals and carries compliance exposure.
6. **High.** Catalogue V3 administration is off in production with AD-4/6/8 open; every block after B1 depends on it.
7. **Medium.** Seventy rules with cross-space dependencies on an unspecified per-space engine.
8. **Medium.** Tall units, dismantling and exterior painting priced manually on most jobs, producing override noise and inconsistent pricing.
9. **Medium.** The E6 replay set is three 3 BHK quotations, two in one building; the B2 and B3 gates prove nothing for other property types.
10. **Medium.** Villa and 5 BHK visits rely on manual merging of surveyor sets; these are the highest-value jobs and the likeliest to lose data.

## 9. Top 10 missing requirements

1. Variation quotation referencing an accepted base version.
2. Provisional-sum lines and itemised extras (pelmets, mirrors, drawers, sensor lights, point shifting, loft above doors).
3. Preparation-package driver and amounts per property type, as a card major version with the private card re-approved.
4. Capture tiers: Full for tagged walls, Lite elsewhere; photo minimums reduced; toilet and balcony lite.
5. L-shape turn direction or mandatory vertices; W1 convention for door-less and multi-door rooms.
6. Second-surveyor merge policy.
7. Staircase template with per-segment wall heights.
8. Shared partition entity and `is_proposed` boolean; niche depth column.
9. Design-stage linkage before quotation.
10. Material and hardware catalogue records for per-line naming; GSTIN and legal entity for company customers.

## 10. Recommended changes before B1

1. Rewrite the capture minimums in 00 §9, CORE and the playbook §8 to the Full/Lite tiers and re-estimate visit times; the ten-site gate must record time per site against today's visit.
2. Add turn direction or vertex entry for L_SHAPE; add the W1 rule for door-less rooms; make floor-to-lintel REQ in bedrooms and kitchens.
3. Design the second-set merge before any multi-surveyor site enters validation.
4. Add a STAIRCASE template and stair-wall height capture.
5. Decide `derived_level_count` and the servant-room driver rule; record both.
6. Admit the three schema additions (niche depth, partition `is_proposed`, wall turn direction) in the 0200 migration.
7. Resolve the B1 catalogue dependency: seed templates by migration in B1, or add Catalogue V3 activation to the B1 entry gate.
8. Size the attachment pipeline for 150 to 700 photos per visit through the scanner and add the attachment purge to the lead anonymisation contract.
9. Fix the card mislabels in 01 and 04 (beading, plumbing code, sink laying, granite laying) and remove the always-on allowance from PROJECT_RULES.
10. Register new owner inputs before B2 starts: variation policy, provisional sums, preparation-package drivers, design-stage linkage, commercial go/no-go. Widen the E6 set with at least one 2 BHK, one 4 BHK and one villa before MTQ-G5 is accepted.

**OI-MTQ-01 to 12 ranking**

| Risk | Inputs | Why |
|---|---|---|
| High | 05, 07, 09, 03, 06 | Without rates, GST treatment, terms and payment schedule, scope content and discount limits, no quotation beyond a laminate 3 BHK can be sent |
| Medium | 02, 04, 01, 10, 11 | Templates exist in proposal form and need trimming; rounding gates BOQ accuracy; tolerance gates only B1 validation; rate visibility and acceptance mechanism change the customer experience |
| Low | 08, 12 | Validity of 30 days is already practice; B5 is distant |

I can publish this as a shareable review page for the owner if useful.

READY WITH REQUIRED CHANGES
