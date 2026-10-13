# MTQ B1 — field validation kit

What the owner and the surveyors take to the ten live sites, and what comes back. [B1-T12 §2](B1-T12-staging-enablement.md) is the enablement sequence and §4 is the evaluator; this page covers the field side. Nothing here prices, scopes or quotes anything: B1 measures.

## 1. Before the first site

- MTQ is enabled on staging only, by the approved enablement record (B1-T12 §2 step 8). Production refuses the flag.
- The smoke checks (B1-T12 §3) passed, including one upload that is completed before its bytes arrive. It must answer **409 `UPLOAD_NOT_RECEIVED`**, never a 500. That confirms the attachments bucket answers a missing object with 404 (B1-PE-05).
- Each surveyor has a staff account with the SURVEYOR role only, with no SALES role (B1-PE-08), and a second account for the four-eyes verifier.
- **Each surveyor uses their own device.** If a device is shared, the first surveyor signs out first. The sign-out asks them to sync or discard anything not yet sent (B1-PE-02), and nothing is ever sent under the next surveyor's name (B1-PE-01).

## 2. Site selection (closure §2.2)

| Slot | Required |
|---|---|
| Apartments | Five, covering at least one 2 BHK, one 3 BHK and one 4 BHK |
| Independent houses | Five, at least two with two or more levels |
| 5 BHK | Wanted, not required. If none is available, the evidence says `ABSENT`. A synthetic 5 BHK is never counted as live |
| Survey level | At least one Lite and at least one Full |
| Events | At least one second-surveyor conflict and one offline retry, both observed |

Sites get anonymous ids S01–S10. Customer names, addresses and phone numbers never go into the reference file, the feedback forms or the evidence.

## 3. At each site

1. **The app survey (surveyor A).**
   - Note the arrival time.
   - Create the visit and capture in the PWA, at the survey level planned for the site.
   - Take photos as the template asks.
   - Note the departure time. Minutes on site go into `survey_minutes`.
2. **The reference measurement (surveyor B).**
   - Use a different instrument from A: tape against laser.
   - Measure, without seeing the app:
     - every wall length, by wall index from the template's start corner;
     - the ceiling height;
     - each space's length and width;
     - every opening: wall, type, width, height, offset from the wall start, and sill;
     - the staircase: run, width, riser and tread.
   - Record it on paper or a sheet, never in the app.
3. **Planned events at the chosen sites.**
   - **Conflict:** surveyor B edits a space A already captured.
   - **Offline retry:** switch on flight mode during capture, then reconnect.
4. **Submit and verify.** A submits, and a second user verifies, so four-eyes is enforced. A rejection becomes a new revision; record it in the site log.

## 4. Site log (one per site, private)

| Field | What to record |
|---|---|
| Site id, configuration | S0n, apartment/house, BHK, levels |
| Survey level | LITE or FULL; for a Full, whether a Lite came first |
| Survey minutes | Arrival to departure, surveyor A |
| Attachments | Photos taken, uploaded, and any that failed or were retried |
| Sync reliability | Number of offline periods, operations queued, and any CONFLICT or CLAIMED results; anything lost or duplicated (expected: none) |
| Conflict behaviour | Where planned: fields in conflict, which version was kept, and whether the server answered CONFLICT (never last-write-wins) |
| Revision workflow | Revisions created, rejections and their reasons, the verifier, the final VERIFIED revision |
| Runtime verification | Codes raised at submit and verify (closure §2.3), and RISK_ACK notes |
| Outcome | The evaluator's site verdict (filled in afterwards) |

## 5. Feedback form (surveyor, same day)

For each item: what happened, where (space or step), and a priority. Priorities mean:

| Priority | Meaning |
|---|---|
| Critical | Wrong or lost measurement data, data under the wrong user, or the survey cannot be completed in the app |
| High | A required measurement or room type cannot be captured, or a workaround costs more than 10 minutes on site |
| Medium | Friction that slows capture but has a workaround |
| Low | Wording, layout or preference |

Prompts:
- Which room types did the template lack?
- Which measurements could not be entered?
- Which attributes were missing (finish, condition, services)?
- Which step took longest?
- Was anything hard to tap or read in sunlight?
- Did sign-out or the offline queue surprise you?

## 6. Assembling the evaluation inputs

- **`ref.json`:** the reference readings from §3.2, in the [B1-T12 §4](B1-T12-staging-enablement.md) schema, with `dataset_kind: "LIVE"`. The `reference_method` must not start with `SYNTHETIC`.
- **`measured.json`:** for each site, two responses from staging saved as JSON:
  - `GET /api/v1/measurement-sets/{verified set id}`
  - `GET /api/v1/properties/{property id}`
  
  Both go in as `{"S0n": {"set": …, "property": …}}`. Use a staff session in the browser, or the staging API through Cloudflare Access.
- **`events.json`:** for each site, `{"second_surveyor_conflict": bool, "offline_retry": bool}`, taken from the site logs.

Then run `tools/mtq_ten_site.py` as B1-T12 §4 shows, with `--database-engine postgresql` when staging runs PostgreSQL (`sqlite` otherwise). The input files stay private. Only the evidence document, which holds dimensions and verdicts with no customer data, is committed.

## 7. Classification

Every configuration gets exactly one label in the B1 staging-validation report:

| Label | When |
|---|---|
| LIVE_VALIDATED | The ten-site evaluator's live dataset is LIVE_VALIDATED, and at least one site of this configuration passed in it |
| SYNTHETIC_VALIDATED | Only the synthetic run covers it (the committed synthetic evidence) |
| UNVALIDATED | No live site of this configuration passed, or the live dataset did not reach LIVE_VALIDATED, and no synthetic run covers it |

A live site that fails is reported as it is. The synthetic result for the same configuration never stands in for it.

## 8. Questions to answer for B2

The field data must show:

1. **Net wall areas.** Do the net wall areas and usable segments (B1-T07) match what a designer would measure for wardrobe and TV-unit placement?
2. **Kitchens.** Are the plumbing and gas flags enough to lay out a counter, or are positions on the wall needed? B1 records only booleans: `has_water_inlet`, `has_gas_line`, `has_drain`.
3. **Squareness.** Are rooms square enough for modular fitting? B1 captures no diagonals for RECTANGULAR rooms.
4. **Beams and lintels.** Do beam-bottom and floor-to-lintel heights cover loft and false-ceiling decisions?
5. **Missing room types.** Which room types were missing from the templates (feedback §5)?

The answers go into the B2 readiness assessment. They are findings, not B1 defects, unless the data was wrong.
