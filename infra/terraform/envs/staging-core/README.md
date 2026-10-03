# envs/staging-core

AWS root for the staging account (AUT-101 … AUT-112). **AUT-301: the root exists and is empty.** Its first plan,
through the `10-infra-plan` workflow and the `veda-gh-plan` role, must show "No changes".

- Backend: the bootstrap state bucket (`veda-tfstate-<account>`), key `staging/core.tfstate`, SSE-KMS with the state
  key, S3 native locking (`use_lockfile`). Configured at `init` by `infra/scripts/stack.sh`; never committed.
- Credentials: GitHub OIDC only. `veda-gh-plan` for plans (state read, lock files only); `veda-gh-apply` for applies,
  which stay disabled until owner decision OD-B7 (`infra/config/apply-gate.json`).
- Account and region come from the reviewed manifest (`infra/config/staging-account.json`); the provider pins
  `allowed_account_ids`, and the region must be ap-south-1.
- Every plan passes `infra/scripts/check-plan.sh` (no destroy, Mumbai only, bounded roles at path `/`, no GitHub or
  external trust) before it can be applied.
