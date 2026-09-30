# P0 merge-readiness report

- **Status on 2026-09-30:** READY FOR CONTROLLED MERGE. This is a governance status only; nothing has been merged or deployed.
- **Why:** every §2 precondition of the merge-safety plan is met on the owner's recorded evidence. AM-4 is approved with conditions, and the owner waived the TG-01/TG-08 decision-log and PR evidence for merge readiness.
- **Controlled:** the merge happens only through option C, and only on a separate owner instruction. Option C has its own preconditions (CI green on `APPROVED`, a clean tree, `git fetch origin`) and checks C4–C7.
- **Recorded at head:** `ca9845c0dd60280fd19cdc9d41843d8567191801`; synchronized at head `1be68c2`. Live site: `main` at `13276a0`.

| Precondition (merge-safety plan §2 and final targeted check) | State |
|---|---|
| Final targeted check recorded (`56c20ba`, CERTIFIED WITH TECHNICAL CONDITIONS) | Met |
| Document-level check (`093cfa6`, READY WITH DOCUMENT CONDITIONS) and document conditions addressed (`ca9845c`) | Met. A confirmation check of `ca9845c` was suggested but not requested. |
| TG-01 | Met: APPROVED (owner decision). The owner waived the registry evidence entry for merge readiness; the certified registry still reads 'Pending'. |
| TG-08 | Met: APPROVED (owner decision). The owner waived the registry evidence entry for merge readiness; the certified registry still reads 'Pending'. |
| OD-2, OD-3 confirmed | Met (APPROVED) |
| Amendments required before merge (AM-1…AM-7, AM-11…AM-13) | Met. AM-4 is APPROVED WITH CONDITIONS: its labelled gaps are accepted for merge as a tracked deviation (DEV-004); RR-12 completes it before production. |
| Merge-safety option | APPROVED: option C, not executed |
| Public intake disabled; WhatsApp fallback; custom domain untouched | Met |
| CI green on the head | Met on `ca9845c` (run 36608504841). CI on the synchronization commit and on the runbook-correction commit (RB-01) is reported with each, and must be green on `APPROVED` before option C starts. |

**Not part of merge readiness (unchanged):**
- Production deployment approval is PENDING.
- Production blockers stay open, including RR-12 (AM-4 completion), AM-9 and AM-10 (deferred), and the release gates.
- The certified registry (`docs/architecture/`) is unchanged.

**Next step:** the owner issues a separate instruction to execute option C, steps C1–C8 of `P0-merge-safety-plan.md`, with `APPROVED` set to the head of `implementation/p0-foundation` that carries runbook correction RB-01 (C3 excludes the site-release fixture from ESLint; C4 expects three changed files; C5 starts CI through the pull request; C7 normalises Cloudflare email obfuscation). The correction changes only the procedure, not the application.
