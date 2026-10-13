# MTQ B1 implementation record

**Branch:** `feature/mtq-b1-end-to-end` · **Umbrella PR:** #87 · **Instruction:** `VEDA-SPACES-MTQ-B1-END-TO-END-IMPLEMENTATION` (2026-10-13).
**Source of truth:** the merged MTQ package on main (blueprint, templates, B1 scope freeze d4f14c3, blocker closure, register, entry gate, decision log 26 and 27).

This record lists, per task, what was built and every place where the code departs from the letter of a frozen document, with the reason, so an independent reviewer can object. Nothing here changes a frozen decision; where the code is stricter than the text, that is said.

## B1-T01 — kernel media extraction

No deviation. Characterisation snapshot identical before and after.

## B1-T02 — attachment module (0106)

| Frozen text | Implementation | Reason |
|---|---|---|
| Variants generated asynchronously (closure §6.2, B1-SCOPE §2.8) | Variants are generated during the completion call; a scanner outage leaves FAILED and the `attachment-scan` job retries | Images arrive at most 2048 px from the PWA, so decoding is fast; one code path, no new worker. Fail-closed delivery is unchanged |
| Server variants 320 / 768 / 1600 (closure §6.2) | Plus a `full` variant: the metadata-free re-encode at the original size | It is the "re-encoded source" the policy retains in place of the uploaded bytes |
| "Orphans purged after `catalog_media_retention_days`" (closure §6.4) | Bytes are released at the moment a row stops being live (withdrawal, erasure, rejection) unless another live row holds the same content; the daily `attachment-retention` job removes quarantine after 30 days and abandoned uploads after 24 hours | With content-hash keys and reference checks there is no orphan population left to age out |
| `visibility = INTERNAL` for customer floor plans (closure §6.5) | Enforced for `FLOOR_PLAN`; B1 has no customer-facing surface, so INTERNAL and STANDARD read the same for staff | Recorded so B4 (customer portal) honours it |
| Polymorphic `entity_type`/`entity_id` (B1-SCOPE §2.8) | Registered FK-less identifier EXC-011, the eleventh on the 03 §2.11 allow-list | The architecture document requires a registry row and an amendment for any new FK-less column |

## B1-T03 — site tables (0200)

| Frozen text | Implementation | Reason |
|---|---|---|
| EVENT_ONLY audit for `space_measurement`, `space_wall`, `space_opening`, `space_electrical_point` (B1-SCOPE §2.1) | FULL for every MTQ table | EVENT_ONLY needs a contract exception (conformance rule 9); FULL is stricter and needs none |
| `geo_lat`, `geo_lng` DECIMAL(9,6) (blueprint §4.1) | `geo_lat_e6`, `geo_lng_e6` INTEGER microdegrees | The same precision without floating point on SQLite (DATA-016) |
| `property.customer_id` (blueprint §4.1, "added when `customer` exists") | Not created | No `customer` table exists; it is an additive FK later (closure §4.3) |
| PROPERTY_TYPE additions (blueprint §4.5, B1-SCOPE §4 step 2) | None in B1 | The values (duplex, penthouse, row house, hospitality, clinic) name deferred property types; adding them would change the existing lead form's options |
| CHECK lists | `property_type_code` ∈ {APARTMENT, INDEPENDENT_HOUSE}, `usage_code` = RESIDENTIAL, `space_type_code` ∈ the 32-value residential subset | B1-01 scope enforced in the schema; widened by a later migration |
| AR-02 partition flag | `space_wall.is_proposed` with CHECK that only a PARTITION may be proposed | Review of record §10.6 |
| 00 §4 obstruction kinds, FLOORING, EXISTING_CONDITION (closure §3.1 "§4 values not in §2.6 deferred") | Adopted as the B1 capture vocabulary, plus ARCHITRAVE (AR-11), AC_DRAIN (AR-13) and the NONE marker (B1-SCOPE §2.3); natural-light attributes excluded (AR-17) | The parenthesis in closure §3.1 concerns wall-tag values; the capture contract needs these lists to validate input |
| One active draft per property (T06 rule) | Partial unique index `ux_measurement_set__one_draft` | Enforced by the database, not only the service |

## B1-T04 — property and space services

| Frozen text | Implementation | Reason |
|---|---|---|
| Templates as versioned JSON fixtures (B1-06) | `veda/modules/mtq/fixtures/templates-2026.10.1.json`, validated strictly at load: every B1 space type has exactly one space template, every seed space a known type and template, parents earlier in the walk, bedroom counts consistent | A malformed fixture stops the process instead of seeding a wrong tree |
| 02 §3 (4 BHK) says the servant room counts as a bedroom; 02 §4 (5 BHK) says one set per surveyor | Servant room never counts; one set with per-space claims | B1-SCOPE §2.9.4 and §2.9.3 supersede the template text (closure §3.1) |
| 02 §4 and §6 name `HOME_THEATRE`, `LIBRARY`, `GUEST_SUITE`, `WASH_AREA` | Not seeded; `MEDIA_ROOM` or `CUSTOM` used | Not in the B1 `SPACE_TYPE` subset (B1-SCOPE §2.1; closure §3.2) |
| Independent house template "as Villa" (02 §7) | The villa space list (02 §6) adapted as the house seed: porch, parking, garden, ground floor, staircase, upper bedrooms, optional terrace; RENOVATION default | 02 §7 is accepted; §6 is deferred as a property type, so its list is used only as §7's base |
| Machine-checkable FULL requirements per template | Each template lists the subset the verifier can enforce (tags, floor-to-lintel, service attributes, obstruction kinds, wall heights, staircase geometry); the rest of 01 stays as checklist text for the human verifier | Free-text items (sketches, customer preferences) cannot be checked by code; four-eyes verification covers them |
| `If-Match` on every mutation (blueprint §11) | Space edit and archive use the space's version; adding spaces, seeding and ordering do not take the property's version | The property version does not move when spaces change, so it would be a false check; ordering is refused unless it names every live space exactly once |
| Outbox events `property.created` and others (blueprint §11.3) | Not emitted in B1 | No subscriber exists; an unhandled event type dead-letters. The audit log and lead activities are the B1 event record |

## B1-T05 — measurement-visit state machine

| Frozen text | Implementation | Reason |
|---|---|---|
| States REQUESTED → SCHEDULED → IN_PROGRESS → COMPLETED / CANCELLED / NO_SHOW (blueprint §4.1) | Exactly these; reschedule is SCHEDULED → SCHEDULED; cancel allowed from REQUESTED, SCHEDULED and IN_PROGRESS with a reason; NO_SHOW from SCHEDULED | No pause state exists in the frozen model, so none is added |
| `lead_activity_id` → the SITE_VISIT activity created on schedule (blueprint §4.1); "a system activity per visit" (B1-SCOPE §1.1) | A system-generated activity (type SYSTEM) per schedule, reschedule, completion, cancellation and no-show, with `measurement_visit_id` in its metadata (blueprint §4.5); `lead_activity_id` is the scheduling one | A completed SITE_VISIT contact activity at scheduling time would record a visit that has not happened |
| Lead moves to SITE_VISIT on schedule, forward only (blueprint §12.3) | The lead module's `change_status`, called as SYSTEM with authority limited to `lead.status.change`; never backward, never on WON or LOST (scheduling on a closed lead is refused) | No direct lead mutation; the existing lead state rules apply unchanged |
| Start and complete | `measurement.capture` by the assignee (or ALL scope); completion needs a SUBMITTED, VERIFIED or SUPERSEDED set from the visit | Fail closed: a visit cannot be marked done with nothing captured |
| Assignee | Must be an active human holding `measurement.capture` | A visit assigned to someone who cannot capture would be unworkable |

## B1-T06 — measurement sets and revisions

| Frozen text | Implementation | Reason |
|---|---|---|
| Per-space claim: "only that user (or the set's lead surveyor) may edit the space until submission" (B1-SCOPE §2.9.3) | As written, plus claim expiry (4 hours after the holder's last write), explicit release, and explicit takeover (`take_over: true`) of an expired or released claim | The instruction asks for claim expiry and release; without them a surveyor who leaves blocks a space until submission |
| "last write wins within one surveyor's set" (blueprint §13.2) | Never: every write to an existing space carries `base_version`; a stale write gets 409 `VERSION_CONFLICT` with the server state and the conflicting fields, and is resolved by resending on the new base | Superseded by B1-SCOPE §2.9.3 and the instruction's no-silent-merge rule; stricter than field-level merging |
| A second surveyor on one DRAFT set | A second surveyor reaches the lead through their own visit on the property; visit completion needs a set of the property submitted since that visit started (T05 rule widened from "the visit's own set") | One DRAFT per property means the second surveyor's visit has no set of its own |
| Correction creates a new revision (blueprint §6.2) | `reject` moves SUBMITTED → REJECTED and opens DRAFT n+1 copied from it for the same lead surveyor; a re-measure copies with `copy_from_set_id`; copies are new rows, the source never changes | Revisions are immutable; `property_space.id` is the join key |
| Walls keep identity while edited | Within a draft, walls are matched by `wall_index` and openings by `client_ref`, so photo attachments stay with the wall they show; removed walls are soft-deleted | Attachments reference `space_wall.id` |
| `RISK_ACK` notes (B1-SCOPE §2.1) | Refused at capture; written by the verifier at verification (B1-T07) | A risk acknowledgement is the verifier's act |
| Plan-drawing pre-measure (B1-SCOPE §4.2) | `POST /properties/{id}/measurement-sets`: PLAN_DRAWING, LITE, no visit | Staff key in a paper survey |
| Submission completeness | B1-T06 checks every in-scope space is measured and marked complete; B1-T07 adds the Lite and Full rules | Layered by task |

## B1-T07 — derivation and verification engine

| Frozen text | Implementation | Reason |
|---|---|---|
| "Every RECTANGULAR/L_SHAPE/POLYGON space has ceiling height" (blueprint §6.2) | Required for INDOOR and SEMI_OPEN spaces; OUTDOOR spaces (terrace, garden, porch, parking) are exempt; a STAIRCASE uses its staircase geometry instead (B1-T08) | A terrace has no ceiling (01 §11 makes CH conditional on a covered part) |
| Full survey: "every in-scope space has ≥ 1 tagged furniture wall with obstructions captured or an explicit none marker" (B1-SCOPE §2.3) | Every in-scope space has at least one tagged wall, where the `NONE` tag is the explicit "no furniture here" marker; every furniture-tagged wall has its obstructions or the `NONE` obstruction marker | A passage or a toilet without a vanity has no furniture wall; the marker records that it was looked at |
| "Walls whose door or window bounds a tagged wall" (B1-SCOPE §2.3) | The cyclic neighbours of a furniture wall that carry a door or window | The closest machine reading of "bounds" |
| Template requirements | Enforced machine codes per space template (B1-T04 fixture); the rest is checklist text for the verifier | As recorded for B1-T04 |
| Property-level capture (02 §0) at verify for FULL (AR-09) | floor number, lift, main door width and height, narrowest passage, DB location, occupancy; LITE: floor number and lift | The REQ items of 02 §0 that the closed capture schema carries |
| "Fail closed on invalid units" | Plausibility bounds at verification: ceiling 1.8–9 m, room dimensions 0.6–30 m, walls 0.1–30 m | Catches feet keyed as millimetres; values are stored as entered otherwise |
| "Unresolved conflicts" block verification | No conflict can persist server-side: a stale write is refused (B1-T06), so there is no unresolved state to check | Recorded so the reviewer can confirm |
| Four-eyes: verifier ≠ `captured_by` (blueprint §4.1) | The verifier must not have captured the set or any of its spaces | Stricter with two surveyors |
| Tolerance policy (OI-MTQ-01) | `tolerance.py`: agreement tolerances and the site and gate verdicts for the B1-T12 validation harness; runtime thresholds (50 mm closure, ±25 % built-up with a verifier `RISK_ACK`) in verification | Closure §2 separates the two |
| Verify sets `snapshot_sha256` | RFC 8785 canonical JSON of the revision without versions or claims, reproducible from the stored rows | Tamper evidence (blueprint §14) |

## B1-T08 — electrical, staircase and L-shape geometry

| Frozen text | Implementation | Reason |
|---|---|---|
| L-shape: two legs, turn read standing at W1 (B1-SCOPE §2.9.1) | Leg A holds W1 (width `w_a`) and runs `l_a` in; leg B continues sideways from leg A's far end by `l_b` over a depth `w_b`; the six walls clockwise from W1 are fixed by the turn; verification compares each wall to its expected length within 50 mm | The freeze names the legs and the closure rule; this fixes the one reading that makes "close within 50 mm of the leg dimensions" checkable |
| "Do not introduce JSON escape hatches for approved schema attributes" (instruction) vs `space_measurement.attributes` JSON (B1-SCOPE §2.1, §2.4, §2.9.1) | The frozen JSON column stays; every key is a closed, typed model (staircase geometry, L-shape legs, survey readings), unknown keys are refused, and staircase geometry is refused on any non-staircase space | Changing the frozen column layout would be a redesign; a closed schema is not an escape hatch |
| Staircase headroom under 2 m, largest panel under 900 mm → RISK (B1-SCOPE §2.4) | Verification requires a RISK note on the staircase when either holds | "RISK" read as a recorded risk the verifier sees |
| Electrical points (B1-SCOPE §2.5) | Written with their space, matched by `client_ref` (ids and photos survive edits), re-linked to the copied walls in a new revision; a wall point lying past its wall's end is refused; Full surveys need a matching point (same wall, offset within 50 mm) for every switchboard or DB box on a furniture wall | "The capture UI creates both" made enforceable |
| Door-less spaces (B1-SCOPE §2.9.2) | `wall_index` 0 is allowed only for an OPEN edge; further open edges use ordinary indices with type OPEN | Several open edges cannot all be index 0 (unique per space) |
| Attachment ids named by a note or an electrical point | Must belong to the same lead | Prevents linking another lead's photo |
