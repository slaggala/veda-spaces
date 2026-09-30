# envs/staging-edge

Cloudflare root (AUT-201 … AUT-205). Not created yet. Separate state key (`staging/edge.tfstate`) and a
separate Cloudflare token, so the zone-level token is never used by the AWS stack. Reads staging-core outputs
(DKIM tokens, tunnel parameter path) through `terraform_remote_state`. Must never change `@`, `www`, MX,
the apex SPF or the Google verification records (plan guard, AUT-301).
