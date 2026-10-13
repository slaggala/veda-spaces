# MTQ implementation-entry gate

**Status:** CLOSED (G2, G3, G4 recorded on 2026-10-13; G1 open; G5 partial — see [MTQ-B1-blocker-closure.md](MTQ-B1-blocker-closure.md)). No code generation, migration authoring, table creation, flag change or pricing change for MTQ may begin while any condition below is unmet. This gate follows the repository's pattern of owner-approved gates ([gate-registry.md](../../architecture/gate-registry.md)); it is proposed here and becomes binding when the owner records it.

| Gate | Condition | Evidence required | State (2026-10-13) |
|---|---|---|---|
| MTQ-G1 | **Blueprint independently approved.** A reviewer who did not author [MTQ-BLUEPRINT.md](MTQ-BLUEPRINT.md) records a verdict of CERTIFIED (or CERTIFIED WITH CONDITIONS, with every condition dispositioned) | Review package on its own branch; remediation matrix; owner acknowledgement | **OPEN** — business-reality findings dispositioned in [MTQ-B1-blocker-closure.md §1](MTQ-B1-blocker-closure.md); the architecture review's findings and verdict are not on any PR and cannot be dispositioned until posted |
| MTQ-G2 | **B1 scope frozen.** The B1 table list (§4.1), `SPACE_TYPE`/`OPENING_TYPE`/`MEASUREMENT_METHOD` lookups (§5.1), verification rules (§6.2) and the ATT prerequisite are fixed; later changes go through an amendment | A frozen-scope commit referenced by SHA; amendment procedure named | **RECORDED** 2026-10-13 — d4f14c3 plus closure §6 Δ values; amendment procedure closure §7.2; passes on the owner's approval of PR #85 |
| MTQ-G3 | **B1 owner inputs resolved.** OI-MTQ-01 and OI-MTQ-02 recorded in [MTQ-owner-decisions.md](MTQ-owner-decisions.md) | Register rows filled with date and source instruction | **RECORDED** 2026-10-13 — both rows filled (closure §2, §3); passes on the owner's approval of PR #85 |
| MTQ-G4 | **Migration range approved.** The `0200`–`0203` block (and `0106_attachment` for ATT) is reserved by owner decision and does not collide with any in-flight module | Decision-log entry; `ls api/migrations/versions` shows no occupant | **RECORDED** 2026-10-13 — `0106`, `0200` approved, `0201`–`0203` reserved; no occupant on any remote branch; decision log entry 26; passes on the owner's approval of PR #85 |
| MTQ-G5 | **Historical quotation replay criteria approved.** The E6 quotation set to replay, widened beyond the current three 3 BHK quotations to at least one 2 BHK, one 4 BHK and one independent house, the per-line quantity tolerance (B2) and the total-price tolerance (B3) are agreed, with the rate card in force at each quotation's date identified | Written criteria with tolerances; list of quotation references and their measurement sources | **PARTIAL** 2026-10-13 — criteria, tolerances and set composition recorded (closure §5); the private quotation reference list is still owner data |

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
| 2026-10-13 | MTQ-G1 | Business-reality review findings BR-01…BR-19 and freeze findings SF-01…SF-07 dispositioned; architecture review findings unavailable, gate stays OPEN | [MTQ-B1-blocker-closure.md §1](MTQ-B1-blocker-closure.md) | session under `VEDA-SPACES-MTQ-B1-BLOCKER-CLOSURE` (owner-delegated) |
| 2026-10-13 | MTQ-G2 | B1 scope recorded as frozen: d4f14c3 plus closure §6 Δ values; B1-01…B1-06 in the register; amendment procedure closure §7.2 | closure §7 | same |
| 2026-10-13 | MTQ-G3 | OI-MTQ-01 and OI-MTQ-02 recorded | closure §2, §3; register | same |
| 2026-10-13 | MTQ-G4 | Migration range approved: `0106_attachment`, `0200_mtq_site`; `0201`–`0203` reserved | closure §4; decision log entry 26 | same |
| 2026-10-13 | MTQ-G5 | Replay criteria, tolerances and set composition recorded; quotation reference list pending owner | closure §5 | same |
| 2026-10-13 | MTQ-G1 | **PASSED.** Review of record located and committed verbatim; remaining findings dispositioned AR-01…AR-25 | [reviews/MTQ-independent-review-2026-10-13.md](reviews/MTQ-independent-review-2026-10-13.md); [closure §9.1](MTQ-B1-blocker-closure.md) | session under `VEDA-SPACES-MTQ-B1-END-TO-END-IMPLEMENTATION` |
| 2026-10-13 | MTQ-G2, G3, G4 | **PASSED** on the owner's merge of PR #86 | PR #86 | same |
| 2026-10-13 | MTQ-G5 | **PASSED WITH LIMITATIONS.** Sanitised manifest; only 3 BHK has references; 2/4/5 BHK and independent house UNVALIDATED_NO_HISTORICAL_REFERENCE as a validation limitation, per the owner instruction | [replay/replay-reference-manifest.json](replay/replay-reference-manifest.json); [closure §9.2](MTQ-B1-blocker-closure.md) | same |
| 2026-10-13 | all | **Gate open for B1.** Implementation branch `feature/mtq-b1-end-to-end` created from main | closure §9.3 | same |
