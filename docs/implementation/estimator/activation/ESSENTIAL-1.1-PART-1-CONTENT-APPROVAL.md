# Essential Specification 1.1: Part 1 content approval record

**Status: NOT SIGNED.** This record is prepared for the owner's signature. Nobody else may sign it, and it is not
signed until the owner fills the signature block.

## This is content approval only

By signing, the owner approves the content listed below and nothing else. In particular this approval:

- **does not authorise activation** of Essential Specification 1.1 on any environment;
- **does not enable Estimator UX V2.** Staging stays on `STAGING_ESTIMATOR_UX=v1`;
- **does not enable public intake**, which stays disabled;
- **does not approve production use**;
- **is not Part 2.** Part 2 (activation approval) needs fresh digests after the sales decisions and the operations
  confirmations are recorded. The promise-matrix digest below changes as soon as any of them is recorded, and the
  activation gate refuses an approval that carries an old digest.

## What is approved

| # | Content | Reference |
|---|---|---|
| 1 | Essential Specification 1.1 content: material categories, room promises that follow the priced lines, brand examples with the approved-equivalent rule, final selection in the detailed quotation, no material warranty duration | Digest `6f798ef6cd3cea06f491041a4143e35776900107e73e6c953fbed4bd37ad286d` ([rendered](../specifications/ESSENTIAL-SPECIFICATION-v1.1.md)) |
| 2 | Customer-promise wording: the 54 visible promises **as wording only**. Each still needs sales and operations confirmation before activation | Promise matrix version 1, digest `ed3b14e0afadecfbb350d022f3bbd028407f7b3f790ff4ec85f0aacf53bbcb3b` ([rendered](../specifications/essential-1.1-promise-matrix.md)) |
| 3 | The separation of manufacturer-backed protection (for the exact selected and documented product) from Veda Spaces workmanship and fitment service support (one year from handover, subject to the Warranty, Service & Customer Care Policy) | Customer copy, `service` and `manufacturer` promises |
| 4 | Validation scope: protected staging behind Cloudflare Access and local moderated sessions only; Essential only; 3 BHK apartments; V1 kept available | [Validation plan](../validation/HOMEOWNER-VALIDATION-PLAN.md) |
| 5 | Public intake remains disabled | `public_intake: disabled` in the staging configuration |
| 6 | Recording retention: recordings of screen and voice only, made with consent, and the participant code list are deleted 30 days after the final synthesis | Validation plan §4 |

Both digests were recomputed on `main` after the PR #63 merge and match the values above.

## Effect on Round 1

- **Signed:** sessions may be recorded, with each participant's consent, under rule 6.
- **Not signed:** Round 1 runs **notes only**, with no recording.

## Signature

| Owner name | Signature | Date | Notes |
|---|---|---|---|
| [OWNER TO FILL] | [OWNER TO SIGN] | [OWNER TO FILL] | |

Once signed, a copy of this page (or a statement from the owner quoting this record) is kept with the governance
records. The signature is not entered into the activation approval record. That record stays `PENDING` until Part 2.
