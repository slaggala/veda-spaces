# envs/staging-core

AWS root for the staging account (AUT-101 … AUT-112). Not created yet.

- Backend: S3 bucket from bootstrap output `backend_config`, key `staging/core.tfstate`, KMS-encrypted,
  `use_lockfile = true`.
- Credentials: GitHub OIDC only (`veda-gh-plan` for PR plans, `veda-gh-apply` for apply).
- Region: ap-south-1; `allowed_account_ids` pinned to the staging account.
