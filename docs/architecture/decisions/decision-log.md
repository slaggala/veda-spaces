# Owner Decision Log

This log records every owner decision that governs the P0 architecture, with its source instruction. It addresses review finding F-18: acceptance evidence in the repository.

**Limitation.** These entries record decisions communicated by the repository owner in the architecture-authoring sessions identified below. They are not cryptographic signatures. **Tracked gate TG-01:** before implementation begins, the owner approves the architecture pull request (or equivalent) from the owner's GitHub account. That approval is the verifiable sign-off.

| # | Date | Source instruction | Decision | Recorded in |
|---|---|---|---|---|
| 1 | 2026-09-29 | `VEDA-SPACES-P0-ARCHITECTURE-SIGNOFF-AND-FREEZE` | ADR-001 physical table `app_user` | [ADR-001](ADR-001-app-user-table.md) |
| 2 | 2026-09-29 | same | ADR-002 UUIDv7 identifiers, 32-hex | [ADR-002](ADR-002-uuidv7-identifiers.md) |
| 3 | 2026-09-29 | same | ADR-003 mandatory audit contract | [ADR-003](ADR-003-audit-contract.md) |
| 4 | 2026-09-29 | same | ADR-004 dedicated security-event log | [ADR-004](ADR-004-security-event-log.md) |
| 5 | 2026-09-29 | same | ADR-005 lead-form required fields | [ADR-005](ADR-005-lead-required-fields.md) |
| 6 | 2026-09-29 | same | ADR-006 MFA for Founder/Admin, configurable for Sales | [ADR-006](ADR-006-mfa-policy.md) |
| 7 | 2026-09-29 | same | ADR-007 technology stack | [ADR-007](ADR-007-technology-stack.md) |
| 8 | 2026-09-29 | same | ADR-008 AWS hosting | [ADR-008](ADR-008-aws-hosting.md) |
| 9 | 2026-09-29 | same | ADR-009 P0 scope | [ADR-009](ADR-009-p0-scope.md) |
| 10 | 2026-09-29 | `VEDA-SPACES-P0-ARCHITECTURE-REMEDIATION-01`, Decision 1 | Sales MFA optional by default. `security_event.read` removed from Sales. Sensitive permissions require MFA before becoming effective. | ADR-006 (amended), ADR-004 (amended), 06 §3, §6 |
| 11 | 2026-09-29 | same, Decision 2 | MFA recovery: password + recovery code → restricted session, re-enrollment, cooling-off. Dual-controlled administrative reset. Founder break-glass. | ADR-006 (amended), 05 §11.5, §11.7, 06 §7.4–7.5 |
| 12 | 2026-09-29 | same, Decision 3 | Granular account-control permissions, proposed-email workflow, privileged-account protection | [ADR-010](ADR-010-account-control-and-privileged-protection.md) |
| 13 | 2026-09-29 | same, Decision 4 | `property_type` optional on the public form. Values APARTMENT, INDEPENDENT_HOUSE, VILLA, OFFICE, RETAIL, OTHER. | ADR-005 (amended), 04 §5.1 |
| 14 | 2026-09-29 | same, Decision 5 | AWS region ap-south-1 (Mumbai), configurable, no multi-region claim | ADR-008 (amended) |
| 15 | 2026-09-29 | same, Decision 6 | RPO, RTO, availability target, retention periods and restore-rehearsal cadence stay unresolved production release gates. No values are invented. | 11 §7 (OWNER-INPUT-001…003) |
