# AUT-002 follow-up: re-apply the bootstrap with GitHub's immutable OIDC subject

- **Date:** 2026-10-04
- **Status:** **authorized and executed** on 2026-10-04 (approval of plan digest `d977a40bd27d062efda5e837bb7953875c2a200937aae7ae4a2a4ca8af24ea78` at 16:29:27Z):
  0 to add, 4 to change, 0 to destroy, `assume_role_policy` subject only. The roles now use immutable GitHub subject
  ID trust, and RR-A is closed. The AUT-301 plan proof that followed passed (AUT-301 review package §8).

## 1. Why

The first OIDC run of AUT-301 (`10-infra-plan`, run 37149305740, 2026-10-04) was refused by AWS: `AccessDenied` on
`sts:AssumeRoleWithWebIdentity` for `veda-gh-plan`. Nothing was planned, created or changed.

| | Subject |
|---|---|
| Trusted by the four `veda-gh-*` roles (bootstrap of 2026-10-03) | `repo:slaggala/veda-spaces:environment:<env>` |
| Issued by GitHub for this repository | `repo:slaggala@37840263/veda-spaces@1392733148:environment:<env>` |

The repository uses GitHub's **immutable OIDC subject** (`use_immutable_subject: true`), which names the owner and
the repository by numeric ID as well. The bootstrap, its plan guard and its tests assumed the name-only form, so no
workflow can assume any `veda-gh-*` role. The offline tests could not show this: it is GitHub's live token format.

The immutable subject is what owner item **RR-A** asked for: a renamed, transferred or re-registered repository can
never match the trust. Adopting it closes RR-A instead of only acknowledging it.

## 2. The change (this pull request; offline, tested)

- **Manifest:** `repository_owner_id: 37840263`, required next to `repository_id`.
- **Bootstrap:** each role's trust subject is `repo:<owner>@<owner id>/<repo>@<repo id>:environment:<env>`, with the
  IDs from the manifest.
- **Plan guard:** GitHub trust must be exactly that subject; the name-only form, another owner ID or another
  repository ID are refused.
- **`github-setup.sh --verify` and `--verify-environments`:** the repository must issue the immutable subject with the
  default template and the expected prefix. A future change of this setting is reported before AWS refuses a run.

## 3. Expected plan

`Plan: 0 to add, 4 to change, 0 to destroy.` The only changes are in-place updates of `assume_role_policy` on:
- `aws_iam_role.github["plan"]`
- `aws_iam_role.github["apply"]`
- `aws_iam_role.github["deploy"]`
- `aws_iam_role.github["evidence"]`

In each one, the subject changes from `repo:slaggala/veda-spaces:environment:<env>` to
`repo:slaggala@37840263/veda-spaces@1392733148:environment:<env>`. The audience (`sts.amazonaws.com`), the provider,
the boundaries, the policies, the state bucket, the key and the guardrails are **unchanged**.

**Any other change is a stop condition.**

## 4. Run-day procedure

The same procedure as the first bootstrap ([P0-release-readiness-report.md](../P0-release-readiness-report.md) §7.1;
the commands proven on 2026-10-03), with these differences:

| Step | Difference |
|---|---|
| 1 Preflight | `main` must include this change. On the operator workstation, run `make -C infra clean` first only if `make -C infra check` fails offline because of the earlier run's `.terraform` (or use the AUT-301 Makefile once merged) |
| 2 Key | Create a new temporary key for `bootstrap-operator` (the first one was deleted); MFA device `arn:aws:iam::813238078849:mfa/Bootstrap` |
| 3–5 | Unchanged: session with MFA and the region-deny policy; validation; inventory (now 3 identities plus AWS service-linked roles, which discovery ignores) |
| 6 Plan | `bootstrap.sh` finds the state bucket and uses the remote state (`s3://veda-tfstate-813238078849/bootstrap/terraform.tfstate`) |
| 7–8 Review | Plan as in §3, and nothing else; record the approval of its digest |
| 9 Apply | Apply of the approved digest; the live bucket and key policies are verified again |
| 10 Validation | `aws iam get-role --role-name veda-gh-<role> --query 'Role.AssumeRolePolicyDocument.Statement[0].Condition'` shows the immutable subject for all four; repository variables unchanged; `make -C infra github-verify` passes |
| 11 Evidence | CloudTrail `UpdateAssumeRolePolicy` × 4 (us-east-1); summary in `docs/release-evidence/AUT-002/` (follow-up section) |
| 12 Key | Deleted; `list-access-keys` empty |

Then re-run the `10-infra-plan` job on PR #17 (AUT-301): it must reach "No changes".

## 5. Authorization

| Field | Value |
|---|---|
| Decision | **Approved by the owner and executed, 2026-10-04** |
| Scope | Re-apply of the bootstrap root to update the four trust policies only (§3), by the controlled local procedure |
| Security requirements | As for the first bootstrap: `bootstrap-owner` only, MFA, a temporary key created and deleted on the run day, no root credentials, no permanent credentials |
