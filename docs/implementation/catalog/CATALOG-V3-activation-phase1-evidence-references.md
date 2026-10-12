# Catalog V3 activation phase 1: evidence-reference matrix (correction of 2026-10-12)

The independent review of PR #75 found that the first revision of
[CATALOG-V3-activation-phase1.md](CATALOG-V3-activation-phase1.md) failed the governance SHA check
(`api/tests/unit/test_governance_docs.py::test_every_cited_sha_is_a_known_commit`) on 16 tokens: abbreviated and full
commit SHAs that the allowlist (`KNOWN_COMMITS`) did not name, and SHA-256 digests abbreviated to their first eight hex
digits. This matrix records every correction. Nothing here is new evidence; every value below already appeared in full
in the record, in a workflow log or in the phase-0 record, and is copied unchanged.

**Convention applied (the repository's own):** a commit is cited as its full 40-hex SHA and is named, with its exact
subject, in `KNOWN_COMMITS` of the governance test in the same change, where `test_known_commits_exist_with_the_recorded_subjects`
verifies it against the history in CI; a SHA-256 evidence digest is cited in full (64 hex digits), never abbreviated;
a merge is otherwise named by its pull-request number and subject in prose. The only shorter hex strings that remain
are literal artifact names (the ECR image tag and the evidence label and object key, which the deploy and evidence
workflows form from the first 12 hex digits of the commit); they are exact names, not abbreviations, and each is a
prefix of an allowlisted commit. The governance test itself was not changed in tolerance or scope: its allowlist grew by
the three verified merge commits below, which is the mechanism its comment prescribes.

Line numbers refer to the first revision of the record (the PR #75 head the review examined); "§" refers to the
corrected record.

| # | Old text (first revision) | Corrected identifier | Evidence type | Authoritative source | Full immutable value | Verification method |
|---|---|---|---|---|---|---|
| 1 | line 17, `main` row: full SHA of the PR #74 merge, not allowlisted | the same full SHA, now allowlisted with its subject | git commit (main; the activation record's `application_commit` candidate) | GitHub `slaggala/veda-spaces` `main`; `git log -1 --format=%H%n%s` | `c9b1ba35db33328a7d769dba9d1bad483274d63c` — "Merge pull request #74 from slaggala/docs/v3-activation-preparation" | `KNOWN_COMMITS` entry; `test_known_commits_exist_with_the_recorded_subjects` (CI, full history); `git ls-remote` over HTTPS |
| 2 | line 20, Staging release row: `main` followed by the first 7 hex digits of the PR #74 merge | the full SHA of row 1 | git commit | as row 1 | as row 1 | as row 1 |
| 3 | line 20, Staging release row: image tag `veda-api:c9b1ba35db33` (12-hex) | kept as the literal ECR tag, labelled "the first 12 hex digits of that commit" | artifact name (ECR image tag), prefix of the allowlisted commit | `12-deploy` run 38163064366 log (deploy job) | tag `veda-api:c9b1ba35db33`; image digest `sha256:b9a55479db3c32df3c8e677d67e1bc5d3d1d9940cc6ea265ea039787241162fe` | run log; the tag is formed by `12-deploy` from the commit; prefix check against row 1 |
| 4 | line 29, Pages build row: "check runs on" the first 7 hex digits of the PR #74 merge | "check runs on the PR #74 merge commit (the `main` row)" | prose reference to row 1 | GitHub check runs on that commit | as row 1 | as row 1 |
| 5 | line 66, §3: the PR #73 merge as its first 7 hex digits plus an ellipsis | the full SHA, now allowlisted with its subject | git commit (commit of the phase-0 real-card artifact) | `git log -1 --format=%H%n%s 246ffee`; phase-0 record §5 | `246ffeeddf2b9612c6a55be9aa34ce1366c2f5a6` — "Merge pull request #73 from slaggala/docs/v3-activation-readiness-corrections" | `KNOWN_COMMITS` entry; CI history check |
| 6 | line 68, §3: "clean checkout of" the PR #74 merge as its first 12 hex digits plus an ellipsis | the full SHA of row 1 | git commit | the real-card artifact's `commit_sha` field | as row 1 | as row 1; artifact `--verify` ("artifact intact") |
| 7 | line 74, §3 Commit row: full SHA of the PR #74 merge, not allowlisted | unchanged text, now allowlisted | git commit | the artifact's `commit_sha` | as row 1 | as row 1 |
| 8 | line 81, §3: phase-0 artifact as its first 8 hex digits plus ellipsis | the full `artifact_sha256` | SHA-256 of the phase-0 real-card artifact (`~/veda-private/evidence/real-card-evidence-2026-10-11T091650+0000.json`) | phase-0 record [CATALOG-V3-activation-preparation.md §5](CATALOG-V3-activation-preparation.md) | `e309a8683c28e99bebdcd51eecabf685a62777e5fb92dfd501a99bb1b90ac91b` | `python api/tools/catalog_real_card_evidence.py --verify` on the owner's machine; equality with the phase-0 record |
| 9 | line 247, §7 `application_commit` row: full SHA of the PR #74 merge, not allowlisted | unchanged text, now allowlisted | git commit (record evidence `application_commit`) | as row 1 | as row 1 | as row 1 |
| 10 | line 248, §7 `pr69_merge` row: full SHA of the PR #69 merge, not allowlisted | unchanged text, now allowlisted with its subject | git commit (record evidence `pr69_merge`) | `git log -1 --format=%H%n%s bb4cbf6` | `bb4cbf6405610269d9f23e58e4c6c97dbd30b5ce` — "Merge pull request #69 from slaggala/fix/catalog-v3-canonical-customer-copy" | `KNOWN_COMMITS` entry; CI history check |
| 11 | line 267, §8 Certified application row: the PR #74 merge as its first 12 hex digits plus an ellipsis | the full SHA of row 1 | git commit | as row 1 | as row 1 | as row 1 |
| 12 | line 268, §8 Approval-digest row: plan digest as its first 8 hex digits plus ellipsis | the full plan digest | SHA-256 of the approved plan file (run 38127613791) | `10-infra-plan` run 38127613791 summary; `11-infra-apply` run 38128798960 log (bound plan digest) | `9d7a13a65808be962d62a30b0e6ca0c526f70f998068653fb096551453a37a85` | the apply workflow refuses a plan whose digest differs from the approved one; run logs |
| 13 | line 270, §8 Release row: image digest as its first 8 hex digits plus ellipsis | the full image digest | SHA-256 image digest of `veda-api:c9b1ba35db33` | `12-deploy` run 38163064366 log | `sha256:b9a55479db3c32df3c8e677d67e1bc5d3d1d9940cc6ea265ea039787241162fe` | run log; ECR describe-images (owner) |
| 14 | line 271, §8 Release evidence row: object digest as its first 8 hex digits plus ellipsis | the full object digest | SHA-256 of the evidence tarball `phase0-release-c9b1ba35db33-20261011T184252Z.tgz` | `13-evidence` run 38164329788 log (owner-approved `staging-evidence` run) | `47977a7f647d8532e6cc59d029fac01a03c5436796fb25cec525ff94cc56580c` | run log prints key and digest; owner-only object in `s3://veda-evidence-813238078849/host/2026-10-11/i-01538ad0e744faaff/` |
| 15 | line 272, §8 Real-card row: `artifact_sha256` as its first 8 hex digits plus ellipsis, artifact name as `…T184922+0000.json` | the full digest and the full artifact file name | SHA-256 of the phase-1 real-card artifact (record evidence `real_card_evidence`) | the artifact on the owner's machine; §3 of the record | `0e4e1b11fac8ce4da38df31546ccc05f96dff1c454fdeb101fbe19642f04f9f7`; `real-card-evidence-2026-10-11T184922+0000.json` | `--verify` ("artifact intact"); equality with §3 and §7 |
| 16 | line 273, §8 Scanner-capacity row: object digest as its first 8 hex digits plus ellipsis | the full object digest | SHA-256 of `scanner-capacity-20261011T184622Z.tgz` (record evidence `scanner_capacity`; `media_scanner.capacity_evidence_sha256`) | `13-evidence` run 38164988919 log (owner-approved) | `ab25630c5f0e8b2934a8181acd9b55dc5a59de21e05c778d8cefc1da05058517` | run log; equality with §2 and §7 and with AD-1 in the owner-decisions file |

**Result:** the governance test reports 0 SHA-allowlist failures on the corrected record; `test_activation_phase1_docs.py`
additionally refuses any hex string abbreviated with an ellipsis in the activation documents and checks that every full
value above appears in the record.

No SHA or digest in this matrix was created or altered by the correction. The evidence objects themselves were not read
(no AWS credentials on this machine); the values come from the workflow logs and the phase-0 record, as before.
