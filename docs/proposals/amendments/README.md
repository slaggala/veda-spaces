# Proposed architecture amendments

> All entries are **PROPOSED, NOT APPROVED**. They were moved out of `docs/architecture/` (RR-A23) so that merging the implementation never places unapproved text inside the certified tree. The certified documents are unchanged since `778aa8fdd918da48340319696ada3ff673e9fb8e`.

Sources: the independent implementation review (AM-1…AM-10), the remediation (AM-11), and the targeted re-review (review/p0-independent-implementation-review @ 15d25a759cfc0342bdca45ba4a9c51550270f305) with owner decisions OD-1…OD-3 (AM-7 rewritten; AM-12, AM-13 added).

| ID | Amends | Related findings | Approval readiness | Decision owner | Status |
|---|---|---|---|---|---|
| [AM-1](AM-1.md) | 03 §5.5 | DEV-001 (condition IR-20) | Wording complete and behaviour matches (OD-1). Submit for owner approval after the reviewer's final targeted check confirms. | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-2](AM-2.md) | 08 §4.5, 05 §11.3 | DEV-002 (conditions IR-01, IR-21, IR-25) | Wording corrected per RR assessment; submit with the reviewer's confirmation. | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-3](AM-3.md) | 08 §4.1, §4.7 | DEV-003 (conditions IR-22, IR-09, IR-02) | Ready to submit. | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-4](AM-4.md) | 04 §5.4 vs 08 §8.5; LEAD-027 | IR-16, RR-12 | Not ready: behaviour does not yet match the proposal (RR-12). | Architecture Owner, Data Protection lead | PROPOSED, NOT APPROVED |
| [AM-5](AM-5.md) | 08 §1, 06 §11 (RBX-003), 06 §7.5, 09 | IR-07, IR-A10, RR-A11 | Wording complete; submit after IR-A10 has a configuration check or an accepted operational control. | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-6](AM-6.md) | LOG-005, 08 §3, 02 §12.4 | IR-10, IR-A17, RR-17 | Wording complete and behaviour matches; submit with the reviewer's confirmation (OD-1). No rehearsal is claimed. | Architecture Owner, Operations | PROPOSED, NOT APPROVED |
| [AM-7](AM-7.md) | 08 §12, 05 §4 | IR-23, RR-04 | New text; behaviour matches. Requires the reviewer's confirmation before submission. | Architecture Owner, Security | PROPOSED, NOT APPROVED |
| [AM-8](AM-8.md) | 05 / 03 | IR-A22 (OI-3) | Ready to submit. | Architecture Owner, Security | PROPOSED, NOT APPROVED |
| [AM-9](AM-9.md) | 06 §7.5 | IR-A11, IR-05 | Decision needed before implementation. | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-10](AM-10.md) | 07 §2, 04 §14 | IR-A15, RR-13 | Decision needed. | Architecture Owner, Data Protection lead | PROPOSED, NOT APPROVED |
| [AM-11](AM-11.md) | 03 §5.7 (mfa_challenge), 05 §11.3, 05 §6.1, 02 §8.3 | IR-01, RR-08, RR-17, RR-A17 | Wording complete and behaviour matches; submit with the reviewer's confirmation (OD-1). | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-12](AM-12.md) | 06 §7.2.2, 06 §7.1 (G11), 08 §5.11 | RR-02, OD-2 | Behaviour matches OD-2; submit with the reviewer's confirmation. | Architecture Owner | PROPOSED, NOT APPROVED |
| [AM-13](AM-13.md) | 06 §7.4, 05 §8.6 | RR-03, OD-3 | Behaviour matches OD-3; submit with the reviewer's confirmation. | Architecture Owner | PROPOSED, NOT APPROVED |
