# The approved account and repository, from the reviewed manifest (F3, PB-01). Empty of resources until AUT-101.
locals {
  manifest_path = var.account_manifest_path != "" ? var.account_manifest_path : "${path.module}/../../../config/staging-account.json"
  manifest      = jsondecode(file(local.manifest_path))
  account_id    = regex("^[0-9]{12}$", local.manifest.account_id)
}
