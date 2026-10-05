# Terraform modules

Reusable modules for the staging stacks. Empty until the items below. Every module is called from
`envs/staging-core` (AWS) or `envs/staging-edge` (Cloudflare) and never applied on its own.

| Module | Backlog item |
|---|---|
| `network` | AUT-101 (**designed**: [AUT-101 design package](../../../docs/implementation/staging/AUT-101-design-package.md)) |
| `kms` | AUT-102 |
| `storage` (buckets, Object Lock) | AUT-103 |
| `cloudtrail` | AUT-104 |
| `ecr` | AUT-105 |
| `iam` (host, anchor writer/verifier, operator, custodians) | AUT-106 |
| `ssm` (config parameters, documents, Session Manager) | AUT-107 |
| `compute` (EC2, data volume, recovery, DLM) | AUT-108 |
| `observability` | AUT-110 |
| `ses` | AUT-111 |
| `budgets` | AUT-112 (**written**: [budgets/README.md](budgets/README.md)) |
| `cf-tunnel`, `cf-dns`, `cf-turnstile`, `cf-pages`, `cf-waf` | AUT-201 … AUT-205 |

Rules for every module: roles are created with the `veda-boundary` permissions boundary (the apply role
cannot create them otherwise); secret SSM parameters under `/veda/staging/app/*` are never managed by
Terraform (they are seeded by AUT-302); `prevent_destroy` on data-bearing resources.
