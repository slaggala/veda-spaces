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
