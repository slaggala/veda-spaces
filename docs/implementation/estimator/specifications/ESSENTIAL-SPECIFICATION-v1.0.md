# Essential Specification v1.0 (customer-facing)

**Source of truth:** [`essential-specification-v1.0.json`](essential-specification-v1.0.json), spec code
`ESSENTIAL-1.0`, schema `veda.estimator.customer-spec/1`, effective 2026-10-08. This page renders it for independent
review.

**Owner decisions:** T1 (October baseline, conflicts reconciled explicitly), T2 (brands may be named), T3 (approved
brand examples or an approved equivalent; final selection confirmed in the quotation), T4 (no price limits), T7 (no
warranty durations).

**Loading:** through the controlled procedure: `veda estimator validate-spec`, then `load-spec`, then `activate-spec
--spec ESSENTIAL-1.0 --approval "<owner approval, date>"` (runbook §6.8). The file holds no rates, costs or
personal data, and the validator refuses them.

## Package-level wording

| Field | Text |
|---|---|
| Name | Essential Specification |
| Summary | Branded plywood interiors with laminate finishes and soft-close hardware, made and installed by Veda Spaces. |
| Equivalent policy | Approved brands such as the named examples, or an approved equivalent of the same grade and specification. |
| Final-selection checkpoint | Final material and brand selections are confirmed in your detailed quotation. |
| Warranty | Material and hardware warranties depend on the selected manufacturer, product and documented warranty terms. Applicable workmanship and fitment service is provided according to the Veda Spaces Warranty, Service & Customer Care Policy. |

## Categories

For each category:
- **Material requirement:** what is promised.
- **Approved brand examples:** examples, not an unconditional promise.
- **Equivalent rule:** for every category, "Approved brands such as the named examples, or an approved equivalent of
  the same grade and specification."
- **Final selection:** for every category, "confirmed in your detailed quotation".

| Category | Room-card summary | Material requirement | Grade, thickness, finish | Approved brand examples | Applies to |
|---|---|---|---|---|---|
| Cabinet structure | Branded plywood structure | Cabinet bodies in branded plywood | Plywood of the approved grade; 18 mm cabinet bodies, 9 mm back panels, 12 mm behind the TV | Sylvan Blu | All carpentry rooms |
| Doors and shutters | Branded block-board doors | Door shutters in branded block board | Block board of the approved grade; 18 to 19 mm shutters | Sylvan Primo Plus | All carpentry rooms |
| Surface finish | Laminate finish | Laminate on every visible surface, in colours you choose from the approved range | 1.0 mm outer, 0.8 mm inner; outer your choice, inner a standard colour | Merino, Century, Greenlam, Royal Touch, Stylam, Plain Art, Dazzle Berry, Airolam | All carpentry rooms |
| Edges | Sealed edges | Edge banding on every exposed edge | 2 mm outer, 0.8 mm inner | Solid Edge, E3, URO, Red Star | All carpentry rooms |
| Hardware | Soft-close hardware | Soft-close hinges and kitchen drawers, with branded channels for drawers, sliding and folding doors | Hinges: Hettich; kitchen drawer systems: Hettich; drawer channels: Blum; sliding: Nimmi or Hettich; folding: Ebco or Hettich | Hettich, Blum, Nimmi, Ebco | All carpentry rooms |
| Handles | Standard handles | Handles chosen by you from the standard range | 1 ft, 1.5 ft or 2 ft lengths | — | All carpentry rooms |
| Kitchen accessories | Kitchen accessories | Wicker baskets, rolling shutters and pantry pull-outs where your kitchen design includes them | — | Nimmi, Hettich, Samsung Irex, Olive | Kitchen |
| Ceiling and lighting | Gypsum ceiling, LED lights | Gypsum false ceiling on steel channels, with LED panel, COB, spot and profile lights installed | Gypsum board on Bright 04/06 channels; panel lights: Philips; COB and spot lights: Wipro; profile lights: Crompton or Avion | Saint-Gobain, Philips, Wipro, Crompton, Avion | Whole home (false ceiling, profile lighting) |
| Optional electrical and painting | Branded wiring and paint, if added | If you add them: branded copper wiring, and premium emulsion paint over putty in one wall colour | Wiring: Polycab or Finolex; putty: Birla or Asian; paint: Asian Paints Premium emulsion | Polycab, Finolex, Asian Paints, Birla | Whole home (painting, electrical) |

Every category's warranty summary: "Manufacturer’s warranty for the supplied product, on the manufacturer’s documented
terms."

## Reconciliation of the historical specifications (T1)

| Item | October 2026 | June 2026 | v1.0 | Reason |
|---|---|---|---|---|
| Cabinet plywood | Sylvan Blu, with a 30-year manufacturer warranty | Sylvan ply, with a 10-year warranty | **Sylvan Blu as the approved example; no warranty years** | October baseline. Durations conflict with each other and with the policy ("up to 10 years"), so none is shown (T7) |
| Door shutters | Sylvan Primo Plus | Sylvan Primo Plus (the June workbook also charged an upgrade to it) | **Sylvan Primo Plus, standard** | October baseline: Essential includes it |
| Inner edge banding | 0.8 mm | 1.3 mm | **0.8 mm** | October baseline |
| Inner laminate | 0.8 mm, standard selection | 0.72 mm Luxura, standard colour | **0.8 mm, standard colour** | October baseline |
| Laminate brands | 8 brands | the same 8 plus Velmica | **October's 8** | October baseline; Velmica can qualify as an approved equivalent |
| Drawer channels | Blum | Hettich | **Blum** (Hettich of the same grade is an approved equivalent) | October baseline |
| Folding channels | Ebco or Hettich | not listed | **Ebco or Hettich** | October baseline |
| Panel and COB lights | Philips panels; Wipro COB | Wipro panels; Philips COB | **Philips panels; Wipro COB and spots** | October baseline |
| Price limits (laminate per sheet, handles, extra paint colours) | stated | stated | **Not shown** | T4: kept in the detailed quotation and the staff view |
| Plywood, hinge and drawer warranty periods | stated | stated | **Not shown in the specification** | T7: the warranty policy is the one source; the estimate shows the controlled wording |

## Review checklist

- [ ] Every category has a material requirement, approved examples, the equivalent rule and the final-selection
      checkpoint.
- [ ] No amount, price limit, cost, margin or rate (validator-enforced).
- [ ] No warranty duration (validator-enforced).
- [ ] Brands are examples ("such as … or an approved equivalent"), never an unconditional promise.
- [ ] Each conflicting historical value is decided above, not chosen silently.
- [ ] Sales review of the customer wording before activation on staging.
