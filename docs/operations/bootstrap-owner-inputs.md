# Staging bootstrap: owner inputs (PB-01, PB-09)

What the owner must create and commit before the controlled first run of the staging bootstrap. It is written for
the approved decisions: **ap-south-1 (Mumbai) only**, a **standalone** AWS account (no Organizations), a controlled
**local** first run, and **no Cloudflare token**. Everything here is checked by code. The templates are tested to be
exactly what the checks accept (`infra/tests/run.sh`, "Owner inputs").

Nothing in this document is run by automation. Run the commands yourself, in the dedicated account only. They create
the account alias and the owner identities, not Veda infrastructure.

## 1. Values you provide

| # | Value | Rules (enforced) | Where it goes |
|---|---|---|---|
| 1 | `ACCOUNT_ID` | 12 digits; the dedicated staging account; not `123456789012` or `000000000000` | manifest `account_id`, inside the owner ARNs |
| 2 | `ACCOUNT_NAME` | Exactly what `aws account get-account-information --query AccountName` returns; must not contain `prod` or `aurion` | manifest `account_name` |
| 3 | `ACCOUNT_ALIAS` | Required. `^[a-z0-9]([a-z0-9-]{1,61}[a-z0-9])$`, globally unique, must not contain `prod` or `aurion`; for example `veda-spaces-staging` | manifest `account_alias`; created with `aws iam create-account-alias` |
| 4 | `OWNER_ROLE_NAME` | IAM role at path `/`; **must not** start with `veda-`; no `aurion` or `swing-trader`; for example `bootstrap-owner` | manifest `bootstrap_principal_arns` and `allowed_foreign_resources.iam_roles` |
| 5 | `OWNER_USER_NAME` | The one IAM user allowed to assume the owner role, with MFA; not `veda-*`; no `aurion` or `swing-trader`; for example `bootstrap-operator` | manifest `allowed_foreign_resources.iam_users`; the role's trust policy |
| 6 | `manage_account_guardrails` | `true` for a new account (default) | manifest |

Nothing else. `region`, `organizations_mode`, `repository`, `repository_id` (1392733148) and
`max_owner_session_seconds` (3600) are fixed owner decisions, already set.

None of these values is a secret. **Never** put an access key, secret key, session token, password or MFA seed in
the repository.

## 2. Manifest schema (`infra/config/staging-account.json`, schema version 2)

| Field | Type | Required value | Checked by |
|---|---|---|---|
| `schema_version` | number | `2` | `check-manifest.sh` |
| `account_id` | string | 12 digits (no placeholder) | `check-manifest.sh --complete`, Terraform `expected_account_id`, scripts, workflow |
| `account_name` | string | non-empty, equals the live account name, no `prod`/`aurion` | `--complete`, discovery |
| `account_alias` | string | IAM alias syntax, equals the live alias, no `prod`/`aurion` | `--complete`, discovery |
| `region` | string | `ap-south-1` | `check-manifest.sh`, Terraform `aws_region` |
| `organizations_mode` | string | `standalone` | `check-manifest.sh`, discovery (the account must not be an Organizations member) |
| `repository` | string | `slaggala/veda-spaces` | `check-manifest.sh`, Terraform `github_repo`, scripts, workflow |
| `repository_id` | number | `1392733148` (GitHub's ID for this repository) | scripts and workflow |
| `max_owner_session_seconds` | number | 900–3600 (set: 3600) | `check-manifest.sh`, discovery (owner role `MaxSessionDuration`) |
| `manage_account_guardrails` | boolean | `true` | `check-manifest.sh`, Terraform |
| `bootstrap_principal_arns` | list of strings | exactly `["arn:aws:iam::<ACCOUNT_ID>:role/<OWNER_ROLE_NAME>"]`: roles only, exact ARN with path, no wildcard, no `veda-*`, this account | `--complete`, Terraform preconditions, discovery |
| `allowed_foreign_resources.iam_roles` | list | must include `<OWNER_ROLE_NAME>` | `--complete`, all-region inventory |
| `allowed_foreign_resources.iam_users` | list | `["<OWNER_USER_NAME>"]` | all-region inventory |
| `allowed_foreign_resources.saml_providers`, `s3_buckets`, `ec2_instances`, `lambda_functions` | lists | `[]` for a new account | all-region inventory |

Template: [`infra/config/templates/staging-account.template.json`](../../infra/config/templates/staging-account.template.json).
Replace every `<…>` and copy it over `infra/config/staging-account.json`. An unreplaced placeholder is refused.

## 3. Owner role specification

| Property | Required |
|---|---|
| Type, path | IAM role at path `/`, in the dedicated account |
| Name | `<OWNER_ROLE_NAME>`, not `veda-*` |
| Maximum session duration | **3600 seconds** (checked live) |
| Trust policy | Only principals of this account (checked live: no identity provider, no service, no other account, no `*`). Required form: only `<OWNER_USER_NAME>`, with MFA ([template](../../infra/config/templates/owner-role-trust-policy.template.json)) |
| Permissions | `arn:aws:iam::aws:policy/AdministratorAccess`. The bootstrap creates IAM roles, policies, an OIDC provider, S3, KMS, EC2 account settings and Access Analyzer, and reads account information. Every session is confined to ap-south-1 by the session policy (PB-06) |
| Permissions boundary | None (the owner is outside `veda-boundary` by design; the region guard is the session policy) |
| Who assumes it | `<OWNER_USER_NAME>` only, with MFA, through `sts:AssumeRole` with the region-deny session policy |
| Not allowed | Running the bootstrap as the root user or directly as an IAM user (refused by Terraform and discovery) |

The owner IAM user needs only `sts:AssumeRole` on that role, with MFA
([template](../../infra/config/templates/owner-user-policy.template.json)), plus an MFA device. It needs one
access key for the local run. Deactivate that key when the run is over.

Commands (owner-run, as the root user with MFA, once, in the dedicated account; replace the placeholders first):

```sh
aws iam create-account-alias --account-alias <ACCOUNT_ALIAS>
aws iam create-user --user-name <OWNER_USER_NAME>
aws iam put-user-policy --user-name <OWNER_USER_NAME> --policy-name assume-bootstrap-owner \
  --policy-document file://owner-user-policy.json                  # from the template
# enable an MFA device for <OWNER_USER_NAME> (console: IAM > Users > Security credentials)
aws iam create-role --role-name <OWNER_ROLE_NAME> --path / --max-session-duration 3600 \
  --assume-role-policy-document file://owner-role-trust-policy.json # from the template
aws iam attach-role-policy --role-name <OWNER_ROLE_NAME> --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
aws iam create-access-key --user-name <OWNER_USER_NAME>            # kept on the operator machine only
```

Then stop using the root user. The account must hold nothing else in any region: no instances, VPCs other than the
defaults, functions, databases, clusters, secrets, customer KMS keys, SAML or other OIDC providers, and no other
roles or users. Service-linked roles are fine.

## 4. After committing the values

```sh
infra/scripts/check-manifest.sh --complete        # must print "valid (complete)"
make -C infra check                               # offline, exit 0
```

Open a pull request with the manifest change and merge it after review. The first run (runbook §3, Option A)
starts with a one-hour, MFA-backed, region-guarded session:

```sh
aws sts assume-role --role-arn arn:aws:iam::<ACCOUNT_ID>:role/<OWNER_ROLE_NAME> \
  --role-session-name veda-bootstrap-$(date -u +%Y%m%d) --duration-seconds 3600 \
  --serial-number arn:aws:iam::<ACCOUNT_ID>:mfa/<MFA_DEVICE_NAME> --token-code <MFA_CODE> \
  --policy file://infra/config/bootstrap-session-policy.json
```
