# AUT-112: the budget as planned. Terraform hides each notification block of the resource (it holds the sensitive
# address), so this output is where the plan text shows the alerts to the reviewer. The precondition stops the plan
# while the owner's limit is undecided (O16).
output "budget" {
  description = "Name, monthly limit and alerts (without the recipient) of the staging cost budget."
  value       = { name = module.budget.name, limit = module.budget.limit, alerts = module.budget.alerts }

  precondition {
    condition     = try(local.budget.monthly_limit_usd > 0, false)
    error_message = "Owner decision O16: monthly_limit_usd in infra/config/staging-budget.json is undecided or not a positive number. Nothing is planned until it is decided."
  }
}

# ADR-012 staging validation: whether the Budgetary Estimate is enabled on staging and the policy page it links to.
output "estimator" {
  description = "Budgetary Estimate on staging (behind Cloudflare Access): enabled, and the warranty policy link."
  value       = { enabled = local.estimator_enabled, warranty_policy_url = var.warranty_policy_url }

  precondition {
    condition     = !local.estimator_enabled || var.warranty_policy_url != ""
    error_message = "The estimator is enabled in infra/config/staging-platform.json but no warranty policy link is set: set the WARRANTY_POLICY_URL variable of the staging-plan environment to the approved policy page. Nothing is planned until then (no broken or placeholder link)."
  }
}

# AUT-101: what the network plan creates, readable in the plan text, and the IDs AUT-108 attaches the host to.
output "network" {
  description = "Staging network summary and IDs."
  value = merge(module.network.summary, {
    vpc_id                 = module.network.vpc_id
    public_subnet_id       = module.network.public_subnet_id
    host_security_group_id = module.network.host_security_group_id
  })
}


# Catalog V3 media and flags (targeted media enablement): what is planned, and the gates that refuse the rest.
output "catalog_v3" {
  description = "Catalog V3 on staging: media settings and flags (all off until an APPROVED, digest-bound approval record)."
  value = {
    media_bucket    = module.storage.bucket_names["media"]
    scanner_mode    = local.scanner.mode
    scanner_option  = local.scanner.option
    flags_on        = alltrue(local.catalog_v3_flags)
    approval_record = local.catalog_v3.approval_record_sha256
    rights_approver = local.rights.approver
    noncurrent_days = local.media.noncurrent_days
  }

  precondition {
    condition     = contains(["none", "clamd"], local.scanner.mode)
    error_message = "media.scanner_mode is none or clamd (the application supports no other scanner; option C needs an application adapter first)."
  }

  precondition {
    condition = local.scanner.mode != "clamd" || (
      contains(["A", "B"], coalesce(local.scanner.option, "-")) &&
      can(regex("^[a-z0-9./_-]+(:[A-Za-z0-9._-]+)?@sha256:[0-9a-f]{64}$", coalesce(local.scanner.clamd_image, "-")))
    )
    error_message = "clamd needs the owner's scanner decision (option A or B, after the capacity evidence) and an image pinned by digest; a placeholder is refused."
  }

  precondition {
    condition     = alltrue(local.catalog_v3_flags) || !anytrue(local.catalog_v3_flags)
    error_message = "catalog_v3 flags turn on together or not at all (no partial activation)."
  }

  precondition {
    condition = !local.activation || (
      local.scanner.status == "DECIDED" && local.scanner.mode == "clamd" && local.rights.status == "DECIDED" &&
      !strcontains(local.rights.approver, "OWNER TO FILL") && trimspace(local.rights.approver) != ""
    )
    error_message = "A catalog_v3 flag is on without media_scanner DECIDED with clamd and media_rights DECIDED with a named approver."
  }

  precondition {
    condition     = length(local.approval_problems) == 0
    error_message = "A catalog_v3 flag is on but the V3 staging approval record is refused: ${join("; ", local.approval_problems)}."
  }
}
