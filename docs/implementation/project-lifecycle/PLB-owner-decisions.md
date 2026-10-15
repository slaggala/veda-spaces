# Project Lifecycle: owner decisions (PLB-51)

Every decision below is **undecided**. The record `api/veda/modules/project/fixtures/lifecycle-policy.json` ships with
every slot null (status `UNDECIDED`). A null slot never becomes a decision.

The engine reads nine of these slots. While a slot is null, the engine applies the strict behaviour in the "While
undecided" column. The other six slots are listed so the register is complete; the code does not read them yet.

A decision is recorded by a reviewed change to the record. That change names a reference and is validated against the
lifecycle definition: an unknown stage, transition, gate, item or category is refused. A record marked SYNTHETIC is
refused outside tests.

| Slot | Decision | Read by the engine | While undecided |
|---|---|---|---|
| PLB-OD-01 | The exact lifecycle stages: approve definition `PLB-2026.10.1` (version and digest) or ask for a new version | Yes | Shown PROPOSED; every HIGH-risk move is refused |
| PLB-OD-02 | The mandatory gates of each transition. This covers the scope-freeze, production-readiness, installation-readiness and handover-readiness definitions, and whether variations must be closed | Yes | The strict default gates of the definition; HIGH-risk moves refused |
| PLB-OD-03 | Which transitions need an independent (four-eyes) approval. Candidates: scope freeze, production release, ready for handover, handover complete | Yes | No approval step on STANDARD moves; HIGH-risk moves refused |
| PLB-OD-04 | The ownership responsibilities that must be assigned before each stage | Yes | The owning responsibility of the next stage |
| PLB-OD-05 | Milestone definitions: which milestone types exist and are expected per stage | No | Staff add milestones from the proposed type list; none is mandatory |
| PLB-OD-06 | Which blockers are gating, and who may change a snag between blocking and non-blocking (`snag_reclassification_capability`) | Yes (snag reclassification) | Changing a snag's gating classification is refused (`OWNER_DECISION_REQUIRED`). The person raising a blocker or snag still sets its initial classification, and a gating blocker always gates |
| PLB-OD-07 | Which checklist items are optional | Yes | Every item is required |
| PLB-OD-08 | Quality-check requirements: the categories that must pass, and who may mark a required one `NOT_APPLICABLE` (`not_applicable_capability`, with a reason) | Yes | Every category except `OTHER` is required, and `NOT_APPLICABLE` on a required category is refused (`OWNER_DECISION_REQUIRED`) |
| PLB-OD-09 | Handover evidence requirements | Yes | Both an acknowledgement reference and an evidence attachment |
| PLB-OD-10 | How a project is created from acceptance: an explicit booking or automatic creation, and the evidence an acceptance needs (for example an attached signed copy) | No | Explicit booking by `project.create_from_acceptance`; the B4 decision record (and the CQX evidence for digital acceptance) is required |
| PLB-OD-11 | Whether `THIRD_PARTY` may be named as the responsible party | No | It may be chosen; review its use |
| PLB-OD-12 | Rework (backward transitions), cancellation, on-hold, and correcting the record of a completed stage | No | None exists: stages only move forward, and a completed stage's checklist and milestones cannot be changed through ordinary edits |
| PLB-OD-13 | Who may record, change or clear a customer-promised date (`capability`): a customer commitment | Yes | Recording, changing or clearing one is refused (`OWNER_DECISION_REQUIRED`). Planned and actual dates are unaffected |

## Proposed content needing the owner's review

The following are proposals derived from the instruction (PLB-21 to PLB-29). They are not Veda policy:

- the twelve stage labels;
- the checklist items;
- the risk classes;
- the default gates;
- the mapping of each stage to a Customer Promise stage;
- the quality-check categories;
- the snag categories;
- the blocker categories;
- the milestone types.

## Persona grants

These are also the owner's to decide. The operations / project-lead, installation and quality personas have no
repository role and are granted capabilities individually ([capability map](PLB-capability-map.md)). No role was
created.
