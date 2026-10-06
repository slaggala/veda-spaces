# Staging first deployment: evidence (RR-14)

**Result: DEPLOYED** on 2026-10-06. Veda is running on the staging host and serves only on loopback. There is no
public path and public intake stays disabled.

| Item | Value |
|---|---|
| Account, region | `veda-staging` (813238078849), ap-south-1 |
| Host | `i-01538ad0e744faaff`, Amazon Linux 2023.12.20260930, aarch64 (t4g.small) |
| Code deployed | `main` at the merge of PR #31; the image tag is the first 12 characters of that commit |
| Raw evidence | `s3://veda-evidence-813238078849/host/2026-10-06/i-01538ad0e744faaff/first-deploy-20261006T172326Z.tgz` |
| Raw evidence SHA-256 | `4460e1a6594359de84cf91a4f5744ada418ebc7babb02a3a9b01793a0caa9b65` |

- **Where the raw evidence lives:** in the evidence bucket, under its COMPLIANCE lock, and in the owner's download.
- **Why it isn't committed:** the repository is public and the files contain the host's private address and container
  IDs. This follows the AUT-002 evidence.
- **How it was checked:** the download's SHA-256 equals the value the collection printed, and every file matches the
  manifest inside the archive (§6). A secret scan of the files found no candidates.

## 1. Runs

| Run | Workflow | Result |
|---|---|---|
| 37468572201 | `10-infra-plan` on `main` (the merge of PR #27) | 1 to add, 11 to change, 0 to destroy (the `deploy.enabled` plan); guard passed |
| 37469748282 | `11-infra-apply` | 1 added, 11 changed, 0 destroyed |
| 37469973775 | `10-infra-plan` (drift check) | No changes (159 resources) |
| 37470701347 | `12-deploy` | Refused at the scan wait: the CLI waiter fails on `ScanNotFoundException` before the scan registers. Fixed in PR #29 |
| 37486256581 | `12-deploy` | Refused by the scan gate: 3 HIGH findings, unfixed in Debian. Reviewed staging exceptions added in PR #30 |
| 37495826594 | `12-deploy` | Stopped at pre-flight: Litestream was never started. Fixed in PR #31 |
| **37499028858** | **`12-deploy`** | **`deployed <tag> (sha256:6b99c54d0943236cb43d2a6e60e17952e0b843578ca6158bd918aa47cd2fcc13) to staging`** |
| 37499707405 | `13-evidence` | Refused before AWS: `staging-evidence` had no required reviewer. Reviewer added; rule in PR #32 |
| **37502867105** | **`13-evidence`** (`first-deploy`) | Approved by `slaggala`; evidence object above |

None of the refused runs changed the database or served traffic.

## 2. Image and bundle

| Item | Value |
|---|---|
| Image | `veda-api:<tag>` (PR #31 merge) → `sha256:6b99c54d0943236cb43d2a6e60e17952e0b843578ca6158bd918aa47cd2fcc13` |
| Scan gate | 3 HIGH findings, each covered by a reviewed staging exception: CVE-2026-95619, CVE-2026-102010 (`gcc-14` 14.2.0-19) and CVE-2026-85091 (`zlib` 1.3.dfsg+really1.3.1-1), expiring 2026-12-31 ([policy](../../operations/image-scan-exceptions.md)). No other HIGH or CRITICAL finding |
| Bundle | `s3://veda-stg-artifacts-813238078849/deploy/<tag>/bundle.tgz`, SHA-256 `02fcad5fd08f7675080a327ae1910ce205ac722bb25ca279808752b3499773b3`, verified on the host before use |
| Deploy | `veda-deploy` on `i-01538ad0e744faaff`, from 16:53:39 to 16:54:27 UTC: **Success** |

## 3. Application state (collected at 17:23:26 UTC)

| Check | Evidence |
|---|---|
| Readiness | `{"status":"ok","checks":{"db":"ok","migrations":"head","foreign_keys":"on","immutability_guards":"present","outbox_lag_s":null,"outbox_dead":0}}` |
| Schema | `{"current": "0010_consent_evidence_guard", "image_head": "0010_consent_evidence_guard", "state": "head", "release": 3}` |
| Migrations run | `0001_kernel` → … → `0100_crm_leads` → `0009_mfa_challenge_binding` → `0010_consent_evidence_guard` |
| Release floors | Image release 3 ≥ floor 3; knows schema floor `0009_mfa_challenge_binding` |
| Pre-deploy snapshot | `veda-20261006T165403Z.db`, 12,288 bytes, SHA-256 `0f100b68ee1202a30c099320d7b18abc5e989ad8b6c78e2e62f4825ce49b0a47`. This is the empty database left by earlier attempts; see finding F1 |

## 4. Containers, listeners, volume

| Container | Image | State | Port |
|---|---|---|---|
| `deploy-api-1` | `veda-api:<tag>` | Up | `127.0.0.1:8000` |
| `deploy-worker-1` | `veda-api:<tag>` | Up | None |
| `deploy-scheduler-1` | `veda-api:<tag>` | Up | None |
| `deploy-litestream-1` | `litestream/litestream:0.3.13@sha256:027eda2a89a86015b9797d2129d4dd447e8953097b4190e1d5a30b73e76d8d58` | Up | `127.0.0.1:9090` |

Host software: Docker 25.0.16, Docker Compose v5.6.0, CloudWatch agent 1.300071.0 (running), SSM agent 3.3.5226.0,
and the `veda-health` timer active.

**Listening sockets:**

| Address | Service |
|---|---|
| `127.0.0.1:8000` | API |
| `127.0.0.1:9090` | Litestream metrics |
| `127.0.0.1:45443` | A local agent |
| `0.0.0.0:22` and `[::]:22` | `sshd`; see finding F2 |
| UDP `127.0.0.1:323`, `[::1]:323` | chrony |
| UDP 68 and 546 | DHCP client |

Nothing listens publicly except `sshd`, and the network blocks it:
- the security group has **no ingress rule**;
- the NACL allows inbound only TCP 1024–65535 (replies) and UDP 1024–65535 from the two tunnel ranges, so port 22 is
  denied.

**Volume:**

| Mount | Device | Size | Used | Use |
|---|---|---|---|---|
| `/var/lib/veda` | `/dev/nvme1n1`, xfs, encrypted data volume | 20G | 181M | 1% |
| `/` | `/dev/nvme0n1p1` | 12G | 3.0G | 25% |

## 5. Findings

| # | Finding | Effect | Follow-up |
|---|---|---|---|
| F1 | The "no database on the volume" check of `deploy.sh` (PR #31) runs **after** step 0. Step 0 runs `schema-status` in a container, and with SQLite that creates an empty `veda.db`. So the empty-replica check never runs, and this deploy took the later-deploy path (Litestream started, empty snapshot, migrations from empty) | None here: the replica was genuinely empty on a new host. But a rebuilt host with an empty volume would not be stopped from starting a new Litestream generation | Record whether the database exists **before** step 0, and test it with the step 0 container creating the file. A `deploy.sh` change, kept out of this evidence PR |
| F2 | `sshd` (Amazon Linux default) listens on `0.0.0.0:22` and `[::]:22`. The host design expects loopback listeners only, with access through Session Manager | Not reachable: no security-group ingress, and the NACL denies inbound 22 | Disable `sshd` in `host-setup.sh`, and have `veda-collect` evidence flag any non-loopback TCP listener. A host change, kept out of this PR |
| F3 | `docker login` stores the ECR token in `/root/.docker/config.json` (Docker's warning in the deploy log) | Root-only, and the ECR token expires after 12 hours | Optional: `docker logout` after the pull in `veda-deploy` |

## 6. Raw evidence files (SHA-256, from the archive's `MANIFEST.sha256`; all verified)

| File | SHA-256 |
|---|---|
| `containers.txt` | `e7a262b2f8b7178626359c333bbcf57b037c1103f7e48ba723ff0ee069cbd8f0` |
| `deploy-log-tail.txt` | `c98f10a7fc555bd511384c53206df349dc05898b643073872034134947446c42` |
| `host.txt` | `8128f829673e7ad955aaf3b8a33ef3bf17990e8e2eccb2fa1765d4e331dd1cec` |
| `listeners.txt` | `41f68663ac58f1a9a07f2a383b1c12109a20a0ec15becaaccca6e075753ee03e` |
| `services.txt` | `5159e1f8a2f4c5cfe6f69c4f3dc3b2b37b5b72d96f90718be66b5603ea85ebd4` |
| `storage.txt` | `364a2f23eb3c2678a33be28cf496dbb2aa5030bd63f65d84edd17d6246a8e116` |
| `ready.json` | `50f382273472f7641759eba21360349e7b1deadee7463bf77712be42baed202d` |
| `schema.json` | `383e29b48e4deb520d000e36717c4bb6917a1c4f10a953a78a7d79e127aabbb2` |
