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

## B1-T09 — offline sync

| Frozen text | Implementation | Reason |
|---|---|---|
| `POST /measurement-sets/{id}/sync`: "array of space payloads + notes; returns client_ref → id map; idempotent per (set, client_ref)" (blueprint §11.1) | A batch of up to 50 typed operations (space, note, release, property_capture, attachment), applied in order, each in its own savepoint with its own result (APPLIED, DUPLICATE, CONFLICT, CLAIMED, FROZEN, REJECTED), plus per-space versions; `GET .../sync-state` for reconnection | Partial failure must not undo the rest; attachments and claims travel through the same queue |
| Idempotency per (set, client_ref) | A retried space write whose content already equals the server state is DUPLICATE (no second write, no version bump); notes and attachments by `client_ref`; a whole batch with the same `Idempotency-Key` replays the first response | No new table: the content comparison makes retries safe without a request log |
| Conflicts | A stale or base-less write with different content is CONFLICT with the server state and the conflicting fields; nothing is merged | No last-write-wins (instruction; B1-SCOPE §2.9.3) |
| Revision awareness | Writes into a revision that is no longer a draft are FROZEN with `current_draft_id` when a correction draft exists | The client rebases instead of writing into a sealed revision |
| Version bookkeeping | After a rolled-back operation the unit of work's "already versioned" record is restored, so a later write to the same row still advances its version | Otherwise a rolled-back attempt could suppress the version bump that protects other clients |

## B1-T10 — staff capture UI and PWA

| Frozen text | Implementation | Reason |
|---|---|---|
| Staff capture UI (blueprint §13.1–§13.2; B1-SCOPE §2.8) | Four pages under `/site`: visits and properties, the property with its space tree and revisions, room-by-room capture, and verification review; one nav item shown only to roles holding `measurement.visit.read` or `property.read` | Lite and Full share one capture page; the template's required markers come from the server |
| "Offline capture" (blueprint §6.1 (4)) | Every capture action is queued on the device (IndexedDB, memory fallback) before it is sent through the T09 sync endpoint; conflicts, claims, frozen revisions and refusals stay in the queue with the server's answer until the surveyor resolves them; a conflict resolved as "mine" is resent on the server's version | No last-write-wins on the device either |
| PWA | A service worker scoped to `/site/` caches only the app shell and hashed assets; it never caches an API response; it is registered only after the site API has answered, so with the flag off no worker is installed | Capture data must live in the queue, not a cache; other workspace pages are never controlled by it |
| Photos (closure §6.2) | Long edge scaled to 2048 px, re-encoded as JPEG 0.8 on the device (drops EXIF and GPS), SHA-256 computed on the device; metadata is queued first, bytes upload after acceptance; review shows variants as `data:` URLs | Fits the existing CSP `img-src 'self' data:`; S3 presigned uploads need the bucket origin in `connect-src`, which is a T11/T12 staging change |
| Units (blueprint §6.1, AR-16) | Feet-inches and millimetres parsed to integer millimetres; anything unreadable is refused with the field named, never guessed | Integer millimetres are the stored unit |
| No pricing in the capture UI | The capture and review pages show no rate, amount or currency; a unit test asserts no rupee sign renders | B1 scope excludes pricing |
| Production isolation | The browser E2E opens `/site` with the flag unset and requires the "not enabled" message and a 404 from `/api/v1/properties` | The flag-off default is checked end to end |

## B1-T11 — attachment storage on staging

Full record: [B1-T11-attachment-storage.md](B1-T11-attachment-storage.md). Status: planned, awaiting controlled apply.

| Frozen text | Implementation | Reason |
|---|---|---|
| Bucket `${name_prefix}-attachments-${account_id}`, data key, no Object Lock, versioning with 30-day noncurrent expiry, Intelligent-Tiering after 90 days, TLS only, bucket-owner-enforced, no public access (closure §6.4) | As frozen, from the storage module; the KMS-only upload statements of the media bucket | Reuse, no new key |
| "The API never proxies bytes in staging or production (pre-signed POST)" (closure §6) vs the plan guard's refusal of bucket CORS (AUT-103) | The browser sends the pre-signed POST as a `no-cors` simple request and the server's completion step is the proof of arrival; retries fetch fresh instructions | Keeps both rules: no relay, no CORS, no guard exception |
| — | Uploads never completed expire under `upload/` after 2 days | Not in the freeze; prevents abandoned browser uploads from accumulating |
| Pre-signed uploads | The attachment store uses a regional, virtual-hosted SigV4 S3 client; the staging workspace CSP names exactly that bucket origin | botocore's default global URL would not match an exact CSP origin |
| Scanning (closure §6.3) | The attachment scanner setting follows the media scanner mode on the host (clamd, same Compose service) | One scanner, already certified |
| Flag default false | Planned `VEDA_MTQ_SITE_ENABLED=false`; staging-core refuses another value in this change; the host preflight refuses a flag-on render without the bucket and clamd | Enablement is B1-T12 and needs owner approval |

## B1-T12 — protected-staging enablement and ten-site validation support

Full record: [B1-T12-staging-enablement.md](B1-T12-staging-enablement.md). Status: prepared; the flag stays off.

| Frozen text | Implementation | Reason |
|---|---|---|
| "VEDA_MTQ_SITE_ENABLED=false until explicit owner approval" (instruction) | staging-core plans the flag from `mtq_site` and refuses it on unless an APPROVED, staging-only, non-self-approved record with every evidence field is bound by its SHA-256; the host preflight and the API refuse a flag-on start without the bound digest | Three independent layers, as for the catalog V3 flags |
| Decision record | `infra/config/mtq-site-enablement-record.json`, committed as a DRAFT template with `[OWNER TO FILL]` fields | The owner fills and approves it; never filled on the owner's behalf |
| Ten-site validation (closure §2.1, §2.2) | `veda/modules/mtq/ten_site.py` evaluates any dataset with the recorded tolerance; `tools/mtq_ten_site.py` runs it on files for the live track; `tests/integration/test_mtq_ten_site.py` runs ten synthetic sites through the API | One evaluator for synthetic and live data |
| Labels LIVE_VALIDATED / SYNTHETIC_VALIDATED / UNVALIDATED_NO_REFERENCE | As named, plus VALIDATION_FAILED for ten referenced sites that fail the gate or miss coverage | A failure is not "unvalidated" |
| 5 BHK in replay or fixture validation | The synthetic S10 is a 5 BHK independent house; live 5 BHK only if a real one is available | No historical 5 BHK exists (replay manifest) |
| Evidence privacy | Anonymous site ids (S01–S20 enforced), dimensions and verdicts only; digests `sha256:`-prefixed | No customer data or pricing in evidence |

Pre-existing flaky test observed (not caused by this branch): `tests/unit/test_deploy_scanner.py::test_entrypoint_propagates_a_clean_clamd_exit` waits 5 s for a stub process and fails intermittently under load; it failed 3 of 6 runs on the main checkout as well.

## PR #87 review closure (merge conditions MC-1, MC-2, MC-3)

The independent review of head 7e640df returned **B1 CERTIFIED WITH MERGE CONDITIONS**. Each condition is fixed in its own commit after B1-T12. Nothing was applied to staging, the site flag stays false, and production is unchanged.

| Condition | Root cause | Correction | Regression tests |
|---|---|---|---|
| MC-1 verification order and supersession (commit B1-MC1) | `verify` superseded whichever revision was VERIFIED without comparing survey level or revision; a draft could be opened while a revision was SUBMITTED; `supersedes_set_id` was fixed at draft creation | Every revision transition takes the property lock and re-reads the set under it. Verification refuses `LITE_AFTER_FULL`, `REVISION_OUT_OF_ORDER` and `HIGHER_REVISION_PENDING`; drafts and second submissions are refused while a revision awaits verification (`SUBMITTED_REVISION_PENDING`); `supersedes_set_id` and the predecessor's SUPERSEDED state are set at verification in one transaction | `api/tests/integration/test_mtq_revision_order.py` (six tests, SQLite and PostgreSQL) |
| MC-2 attachment upload after withdrawal or erasure (commit B1-MC2) | `complete` checked only `upload_status`, so late bytes for a withdrawn or erased attachment were scanned CLEAN and given variants; purge looked only at AWAITING_UPLOAD and rescan only at ACTIVE rows | `require_uploadable` gates instructions, local receipt and completion; a refused completion deletes bytes that already arrived and is refused the same way on retry; withdrawal and erasure invalidate a pending upload; scan and variant code never act on a non-active attachment; purge sweeps withdrawn and erased attachments for 24 hours; a rescan that finds an object missing emits `AttachmentObjectMissing` | `api/tests/integration/test_attachment_lifecycle.py` (six tests, local and S3 stand-in, SQLite and PostgreSQL) |
| MC-3 navigation while the flag is off (commit B1-MC3) | The nav item depended on permissions only; the route gate was a blueprint `before_request`, which Flask skips when routing fails, so unsupported methods answered 405 | `/auth/me` reports `features.mtq_site`; the menu and the command palette show an item behind a feature only when the feature is on AND the permission is held; the gate is app-wide `before_app_request` on the exact MTQ and attachment path prefixes, so every method answers 404 | `api/tests/integration/test_mtq_feature_gate.py`; `app/test/feature-nav.test.ts`; the browser E2E checks the Founder's menu |

**About the MC-1 lock.** The concurrency test passes with and without the property lock, and no request returns a server error either way. The ordering rules, the one-verified-per-property index and the row version column already make concurrent attempts refuse safely. The lock makes each decision on committed state; it is defence in depth, not what the test proves.

### Pre-enablement findings (not merge conditions)

Carried from the review, unchanged by these commits:

- Shared-device offline queue.
- Accessibility coverage expansion.
- 44 px touch targets.
- S3 missing-object 403/404 behaviour.
- PostgreSQL submit race. MC-1 now takes the property lock on submit as well; the finding stays open for its own re-check.
- Live validation evaluator defects.
- Missing live-site references.

Found while fixing MC-3:

- The SURVEYOR and DESIGNER roles do not hold `profile.read`, so a user with only those roles cannot load `/auth/me` or the workspace. Staff accounts need SALES as well until the role matrix is reviewed.

### Pre-enablement closure (B1-PE-01 … B1-PE-09, 2026-10-13)

Branch `fix/mtq-b1-pre-enablement`, one commit per item. Every item was classified **must fix before enablement**, because each one either loses or misattributes field data, blocks a surveyor-only user, or makes the live gate unreliable. None was deferred.

| Item | Finding | Fix |
|---|---|---|
| PE-01 | Offline queue not tied to a user | Every queued op and photo records its user; only the signed-in user's ops are sent; ops from before the change are never sent and can only be discarded |
| PE-02 | Queue survived sign-out | Sign-out asks to sync or discard unsent ops, then deletes that user's data from the device; other users' ops are untouched |
| PE-03 | Axe coverage on capture only | Axe on home, property and review at 360 px; empty table headers fixed; visible focus on photo buttons; e2e axe block runs when a stack has the flag on |
| PE-04 | Touch targets 32–36 px | Every site control ≥ 44 × 44 px, measured by a test; design-system tokens unchanged |
| PE-05 | Missing upload read as 403 | Host may list the attachments bucket (no prefix condition), so a missing key is 404 and completion answers 409 `UPLOAD_NOT_RECEIVED`; to be confirmed in the smoke check |
| PE-06 | Submit race on PostgreSQL | Every write into a set's content, and attachment create/withdraw on set entities, takes the property lock submit takes and re-checks DRAFT; forced-interleaving tests on both engines |
| PE-07 | Ten-site evaluator defects | Exactly ten sites; duplicate and missing sites refused; VERIFIED required; profile cross-check; openings and staircase compared; house-levels mix; 5 BHK informational; surveyor minutes; evidence provenance |
| PE-08 | SURVEYOR/DESIGNER lacked `profile.read` | `0204_mtq_self_service` grants `profile.read`, `lookup.read` and `notification.read` (own) only; number taken under closure §4's corrective-migration rule (decision log entry 28) |
| PE-09 | `//` spellings bypassed the 404 gate | The gate matches the normalised path and every route Werkzeug would reach (redirects and other methods), so 308/405 never reveal a gated route |

Infrastructure sequencing (owner decision, 2026-10-13): the merged-main plan 38365213642 (20 / 4 / 0) is applied first with MTQ off. PE-05 then follows as a separate plan that changes only `module.runtime_iam.aws_iam_policy.runtime` in place (0 / 1 / 0).


### PR #88 review remediation (2026-10-13)

The independent review of 129b4a5 returned PR88 NOT CERTIFIED on two findings; everything else passed and is unchanged.

| Finding | Root cause | Correction | Tests |
|---|---|---|---|
| R1 Property-plan writes unlocked after submit | The plan routes (add space, edit space including `is_in_scope`, archive space, reorder, seed from template) predate MC-1 and PE-06: they took no property lock and never looked at the revisions. Verification and the derived counts read the live plan, so while a revision was SUBMITTED a space could be added, archived or taken out of scope and the submitted basis moved under the verifier | `properties.lock_plan` takes the canonical `sets.lock_property` (through `sets.lock_for_write`), re-reads the property and the space under it, and `require_plan_open` refuses with 409 `PROPERTY_PLAN_FROZEN` (and the pending `measurement_set_id`) while any revision of the property is SUBMITTED. The service functions call `require_plan_open` as well, so seeding inside property creation and any later caller are covered. A DRAFT's plan stays editable; returning the revision for correction reopens it; a VERIFIED revision's snapshot is sealed, so later plan edits shape the next revision only | `tests/integration/test_mtq_plan_freeze.py`: A–F each mutation refused while SUBMITTED with the plan and derived counts unchanged; C the measured kitchen stays in verification; G every mutation succeeds on a draft and after reject; H a plan writer paused before its lock while submit commits (PostgreSQL: refused; SQLite: serialised first, submit sees it) and a free race of writers and submit; no plan row is ever changed after `submitted_on`; no 500 |
| R2 If-Match compared before the lock | The routes compared If-Match with the version loaded before the lock; the services then locked and refreshed the row. On PostgreSQL a request that read version n while another committed n+1 passed its check, and the refresh made its flush match n+1: a lost update (two PATCHes of one set with the same If-Match both answered 200). SQLite write units of work start under BEGIN IMMEDIATE, so it was never exposed there. Pre-existing on main (the PR #87 merge) | Every If-Match path in the MTQ routes now runs lock → re-read under the lock → If-Match → mutate: PATCH and DELETE of a space, PATCH of a property, PATCH of a set, note delete (the note is loaded including deleted ones, so a stale request is 409 rather than 404), submit, verify and reject. `sets.lock_for_write` is the one helper; services keep their own re-lock (a no-op) | `tests/integration/test_mtq_if_match_lock.py`: two requests with the same If-Match, B paused just before the lock while A commits, for PATCH set, submit, note delete, verify, reject and PATCH space: exactly one succeeds, the other gets 409 `VERSION_CONFLICT` with `current_version`, the final row shows exactly one accepted mutation; plus a free four-way race for PATCH and submit |

Audit of the remaining If-Match paths: visit PATCH and visit status, attachment withdraw and the V1 routes never refresh the row before writing, so a stale request fails at flush on the row version (409 `VERSION_CONFLICT`); none of them can lose an update. They are unchanged.

Every new test was run against the code before the fix: 30 of the 51 new cases failed there (the rest are the draft-permitted cases and SQLite cases BEGIN IMMEDIATE already serialised) (PostgreSQL PATCH: both requests 200, the second request's value silently replaced the first), and all pass after it on SQLite and PostgreSQL.

The synthetic ten-site evidence was regenerated from the remediation commit on a clean checkout (generator commit without `-dirty`); it remains SYNTHETIC_VALIDATED and is never a live result. The live document remains UNVALIDATED_NO_REFERENCE.
