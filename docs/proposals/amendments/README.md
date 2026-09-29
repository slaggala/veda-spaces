# Proposed architecture amendments

> All entries are **PROPOSED, NOT APPROVED**. Implementation logic `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`; reviewed tree `3f5920b17d21214b39414d080d34246746c8c40d`; document-level check review/p0-independent-implementation-review @ 093cfa6872c209deb9991910c457afcdb4ad2d04. No owner decision is recorded here; see [the owner decision package](../../implementation/P0-owner-decision-package.md).

| ID | Amends | Final targeted check (verbatim) | Document-level check (verbatim) | Decision owner | Status |
|---|---|---|---|---|---|
| [AM-1](AM-1.md) | 03 §5.5 | TECHNICALLY SOUND | TECHNICALLY SOUND | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-2](AM-2.md) | 08 §4.5, 05 §11.3 | TECHNICALLY SOUND WITH OWNER CONDITIONS (accept invite-link password-overwrite residual) | TECHNICALLY SOUND WITH OWNER CONDITIONS | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-3](AM-3.md) | 08 §4.1, §4.7 | TECHNICALLY SOUND | TECHNICALLY SOUND | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-4](AM-4.md) | 04 §5.4 vs 08 §8.5; LEAD-027 | INCOMPLETE (gaps honestly labelled: later-version rule, create-time consent, immutability) | INCOMPLETE — states 422 where code/tests return 409; 'later version' has no ordering rule; the immutability option conflicts with erasure rewriting consent notes (DC-02) | Architecture Owner, Data Protection lead | PROPOSED, NOT APPROVED |
| [AM-5](AM-5.md) | 08 §1, 06 §11 (RBX-003), 06 §7.5, 09 | TECHNICALLY SOUND WITH OWNER CONDITIONS (outbox retention bound not enforced) | TECHNICALLY SOUND WITH OWNER CONDITIONS | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-6](AM-6.md) | LOG-005, 08 §3, 02 §12.4 | TECHNICALLY SOUND WITH OWNER CONDITIONS (resolve FC-12 release floor) | TECHNICALLY SOUND WITH OWNER CONDITIONS | Architecture Owner, Operations | PROPOSED, NOT APPROVED |
| [AM-7](AM-7.md) | 08 §12, 05 §4 | INCOMPLETE (FC-05 reset-link disclosure; FC-A06 outage bound) | TECHNICALLY SOUND WITH OWNER CONDITIONS — upgraded from INCOMPLETE: every claim verified against kernel/ratelimit.py, auth/throttle.py, auth/service.py; discloses reset-link suppression and that a Turnstile outage is fail-closed with unbounded availability impact under attack; makes none of the forbidden claims | Architecture Owner, Security | PROPOSED, NOT APPROVED |
| [AM-8](AM-8.md) | 05 / 03 | TECHNICALLY SOUND | TECHNICALLY SOUND | Architecture Owner, Security | PROPOSED, NOT APPROVED |
| [AM-9](AM-9.md) | 06 §7.5 | INCOMPLETE (no decision; not implemented) | INCOMPLETE — owner decision not yet taken; repository/staging/production/provider/owner evidence are separated, but the policy itself is undecided | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-10](AM-10.md) | 07 §2, 04 §14 | INCOMPLETE (honestly labelled) | INCOMPLETE — omits PII entering outbox_event.last_error from SQL and handler exception text (DC-03) | Architecture Owner, Data Protection lead | PROPOSED, NOT APPROVED |
| [AM-11](AM-11.md) | 03 §5.7 (mfa_challenge), 05 §11.3, 05 §6.1, 02 §8.3 | TECHNICALLY SOUND WITH OWNER CONDITIONS (refresh rule wording FC-A08; N-1 wording FC-12) | TECHNICALLY SOUND WITH OWNER CONDITIONS | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-12](AM-12.md) | 06 §7.2.2, 06 §7.1 (G11), 08 §5.11 | TECHNICALLY SOUND WITH OWNER CONDITIONS (FC-A10, FC-A12 wording) | TECHNICALLY SOUND WITH OWNER CONDITIONS | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-13](AM-13.md) | 06 §7.4, 05 §8.6 | TECHNICALLY SOUND WITH OWNER CONDITIONS (correct withdrawal over-claim FC-08, FC-A09) | TECHNICALLY SOUND WITH OWNER CONDITIONS | Architecture Owner | PROPOSED, NOT APPROVED |
