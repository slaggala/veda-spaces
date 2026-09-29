# Proposed architecture amendments

> All entries are **PROPOSED, NOT APPROVED**. Reviewed implementation `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`; final targeted check review/p0-independent-implementation-review @ 56c20ba992b519daa79aa3802a28343aab8c0b41. No owner decision is recorded here; see [the owner decision package](../../implementation/P0-owner-decision-package.md).

| ID | Amends | Classification (final targeted check) | Approval readiness | Decision owner | Status |
|---|---|---|---|---|---|
| [AM-1](AM-1.md) | 03 §5.5 | TECHNICALLY SOUND | Wording complete and behaviour matches (OD-1). Submit for owner approval after the reviewer's final targeted check confirms. | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-2](AM-2.md) | 08 §4.5, 05 §11.3 | TECHNICALLY SOUND WITH OWNER CONDITIONS (accept invite-link password-overwrite residual) | Wording corrected per RR assessment; submit with the reviewer's confirmation. | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-3](AM-3.md) | 08 §4.1, §4.7 | TECHNICALLY SOUND | Ready to submit. | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-4](AM-4.md) | 04 §5.4 vs 08 §8.5; LEAD-027 | INCOMPLETE (later-version rule, create-time consent, immutability) — corrected text states the gaps | Not ready for approval as a complete behaviour. The owner may accept the labelled gaps for merge; completion (RR-12) before production. | Architecture Owner, Data Protection lead | PROPOSED, NOT APPROVED |
| [AM-5](AM-5.md) | 08 §1, 06 §11 (RBX-003), 06 §7.5, 09 | TECHNICALLY SOUND WITH OWNER CONDITIONS (outbox retention bound not enforced) | Wording complete; submit after IR-A10 has a configuration check or an accepted operational control. | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-6](AM-6.md) | LOG-005, 08 §3, 02 §12.4 | TECHNICALLY SOUND WITH OWNER CONDITIONS (release floor, FC-12 — now enforced in every deploy mode) | Wording complete and behaviour matches; submit with the reviewer's confirmation (OD-1). No rehearsal is claimed. | Architecture Owner, Operations | PROPOSED, NOT APPROVED |
| [AM-7](AM-7.md) | 08 §12, 05 §4 | INCOMPLETE (FC-05 reset-link disclosure; FC-A06 outage bound) — corrected in this text | Text corrected for FC-05, FC-A05 and FC-A06; submit after the reviewer's document-level check. | Architecture Owner, Security | PROPOSED, NOT APPROVED |
| [AM-8](AM-8.md) | 05 / 03 | TECHNICALLY SOUND | Ready to submit. | Architecture Owner, Security | PROPOSED, NOT APPROVED |
| [AM-9](AM-9.md) | 06 §7.5 | INCOMPLETE (no decision; not implemented) — completed as a decision request | Decision needed before production; not a merge condition. | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-10](AM-10.md) | 07 §2, 04 §14 | INCOMPLETE (honestly labelled) — evidence requirements completed | Decision needed before production; not a merge condition. | Architecture Owner, Data Protection lead | PROPOSED, NOT APPROVED |
| [AM-11](AM-11.md) | 03 §5.7 (mfa_challenge), 05 §11.3, 05 §6.1, 02 §8.3 | TECHNICALLY SOUND WITH OWNER CONDITIONS (refresh-rule wording FC-A08; N-1 wording FC-12) — corrected | Wording complete and behaviour matches; submit with the reviewer's confirmation (OD-1). | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-12](AM-12.md) | 06 §7.2.2, 06 §7.1 (G11), 08 §5.11 | TECHNICALLY SOUND WITH OWNER CONDITIONS (FC-A10, FC-A11, FC-A12 wording) — corrected | Behaviour matches OD-2; submit with the reviewer's confirmation. | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-13](AM-13.md) | 06 §7.4, 05 §8.6 | TECHNICALLY SOUND WITH OWNER CONDITIONS (withdrawal over-claim FC-08, FC-A09) — corrected | Behaviour matches OD-3; submit with the reviewer's confirmation. | Architecture Owner | PROPOSED, NOT APPROVED |
