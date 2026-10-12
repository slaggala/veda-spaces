# MTQ implementation-entry gate

**Status:** CLOSED. No code generation, migration authoring, table creation, flag change or pricing change for MTQ may begin while any condition below is unmet. This gate follows the repository's pattern of owner-approved gates ([gate-registry.md](../../architecture/gate-registry.md)); it is proposed here and becomes binding when the owner records it.

| Gate | Condition | Evidence required | State (2026-10-13) |
|---|---|---|---|
| MTQ-G1 | **Blueprint independently approved.** A reviewer who did not author [MTQ-BLUEPRINT.md](MTQ-BLUEPRINT.md) records a verdict of CERTIFIED (or CERTIFIED WITH CONDITIONS, with every condition dispositioned) | Review package on its own branch; remediation matrix; owner acknowledgement | **OPEN** — review not started |
| MTQ-G2 | **B1 scope frozen.** The B1 table list (§4.1), `SPACE_TYPE`/`OPENING_TYPE`/`MEASUREMENT_METHOD` lookups (§5.1), verification rules (§6.2) and the ATT prerequisite are fixed; later changes go through an amendment | A frozen-scope commit referenced by SHA; amendment procedure named | **OPEN** |
| MTQ-G3 | **B1 owner inputs resolved.** OI-MTQ-01 and OI-MTQ-02 recorded in [MTQ-owner-decisions.md](MTQ-owner-decisions.md) | Register rows filled with date and source instruction | **OPEN** — both blank |
| MTQ-G4 | **Migration range approved.** The `0200`–`0203` block (and `0106_attachment` for ATT) is reserved by owner decision and does not collide with any in-flight module | Decision-log entry; `ls api/migrations/versions` shows no occupant | **OPEN** — `0106` and `0200` free as of this date (highest existing: `0105_catalog_claim_control`) |
| MTQ-G5 | **Historical quotation replay criteria approved.** The E6 quotation set to replay, widened beyond the current three 3 BHK quotations to at least one 2 BHK, one 4 BHK and one independent house, the per-line quantity tolerance (B2) and the total-price tolerance (B3) are agreed, with the rate card in force at each quotation's date identified | Written criteria with tolerances; list of quotation references and their measurement sources | **OPEN** — proposals ±5 % quantity, ±3 % total; not approved |

## Rules

- All five gates must be **PASSED** before the first MTQ implementation branch is created. Partial passes do not permit partial implementation.
- Passing MTQ-G1 does not resolve owner inputs; passing MTQ-G3 does not substitute for review.
- B2 and later blocks have their own entry conditions in the blueprint (§16) and the dependency matrix; this gate covers entry into B1 only.
- Gate state changes are recorded in this file with date, evidence reference and the recording actor. Rows are appended, never rewritten.

## Gate log

| Date | Gate | Change | Evidence | Recorded by |
|---|---|---|---|---|
| 2026-10-13 | all | Gate proposed with the blueprint publication PR | this PR | author |
| 2026-10-13 | MTQ-G2 | B1 scope proposed for freeze in [MTQ-B1-SCOPE.md](MTQ-B1-SCOPE.md); not yet recorded by the owner | this branch | author |
