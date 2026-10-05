# ssm-documents

The SSM Command documents are defined in Terraform: `veda-deploy` and `veda-collect` in
`terraform/modules/deploy` (the Session Manager preferences in `terraform/modules/ssm`). The GitHub deploy and
evidence roles may run only `veda-deploy`, `veda-drill-*`, `veda-seed-fixtures` and `veda-collect`, and only on the
instance tagged project=veda-spaces, env=staging (enforced since AUT-002). `veda-drill-*` and `veda-seed-fixtures`
belong to the rehearsals (RR-09) and are not created yet.
