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
    condition     = local.scanner.option == null || contains(["B", "C"], coalesce(local.scanner.option, "-"))
    error_message = "media_scanner.option is B (resize the host, then the clamd sidecar) or C (asynchronous scanning), or null while undecided. Option A (clamd on the current 2 GiB host) is refused: ClamAV needs at least 3 GiB."
  }

  precondition {
    condition     = contains(["none", "clamd"], local.scanner.mode)
    error_message = "media.scanner_mode is none or clamd (the application supports no other scanner; option C needs an application adapter first)."
  }

  precondition {
    condition = local.scanner.mode != "clamd" || (
      coalesce(local.scanner.option, "-") == "B" &&
      can(regex("^[a-z0-9./_-]+(:[A-Za-z0-9._-]+)?@sha256:[0-9a-f]{64}$", coalesce(local.scanner.clamd_image, "-")))
    )
    error_message = "clamd needs the owner's scanner decision option B (a resized host, after the capacity evidence) and an image pinned by digest; a placeholder is refused."
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

# MTQ B1 site attachments (B1-T11): what is planned, and the gates that refuse the rest.
output "mtq_attachments" {
  description = "MTQ B1 on staging: the attachment bucket and settings, and the site flag (false until an owner-approved, digest-bound enablement record)."
  value = {
    bucket             = module.storage.bucket_names["attachments"]
    site_enabled       = local.attachment_config.VEDA_MTQ_SITE_ENABLED
    enablement_record  = local.mtq_site.enablement_record_sha256
    scanner_mode       = local.attachment_config.VEDA_ATTACHMENT_SCANNER
    noncurrent_days    = local.attachments.noncurrent_days
    tiering_days       = local.attachments.tiering_days
    upload_expire_days = local.attachments.upload_expire_days
    upload_ttl_seconds = local.attachments.upload_ttl_seconds
  }

  precondition {
    condition     = local.attachments.status == "DECIDED"
    error_message = "attachments must be DECIDED (closure §6.4) before its bucket and settings are planned."
  }

  precondition {
    condition     = local.attachments.upload_ttl_seconds >= 60 && local.attachments.upload_ttl_seconds <= 900
    error_message = "A pre-signed upload lives 60 to 900 seconds (the API refuses anything else)."
  }

  precondition {
    condition     = local.mtq_site.status == "DECIDED" && (local.mtq_site.site_enabled || local.mtq_site.enablement_record_sha256 == null)
    error_message = "mtq_site must be DECIDED, and a digest is bound only together with site_enabled (rollback clears both)."
  }

  precondition {
    condition     = !local.mtq_site.site_enabled || (local.scanner.mode == "clamd" && length(local.mtq_record_problems) == 0)
    error_message = "VEDA_MTQ_SITE_ENABLED turns on only with the clamd scanner and an owner-APPROVED infra/config/mtq-site-enablement-record.json bound by its SHA-256 with every evidence field filled: ${join("; ", local.mtq_record_problems)}."
  }
}

# MTQ B2-B4 commercial flags (decision log 33): what is planned, and the gates that refuse the rest.
output "mtq_commercial" {
  description = "MTQ B2-B4 on staging: the estimation and quotation flags (false until an owner-approved, digest-bound, internal-validation-only enablement record)."
  value = {
    estimation_enabled = local.commercial_config.VEDA_MTQ_ESTIMATION_ENABLED
    quotation_enabled  = local.commercial_config.VEDA_MTQ_QUOTATION_ENABLED
    enablement_record  = local.mtq_commercial.enablement_record_sha256
  }

  precondition {
    condition     = local.mtq_commercial.status == "DECIDED" && (local.mtq_commercial.estimation_enabled || local.mtq_commercial.enablement_record_sha256 == null)
    error_message = "mtq_commercial must be DECIDED, and a digest is bound only together with estimation_enabled (rollback clears both flags and the digest)."
  }

  precondition {
    condition     = !local.mtq_commercial.quotation_enabled || local.mtq_commercial.estimation_enabled
    error_message = "VEDA_MTQ_QUOTATION_ENABLED needs VEDA_MTQ_ESTIMATION_ENABLED (a quotation is built on an estimate)."
  }

  precondition {
    condition     = !local.mtq_commercial.estimation_enabled || local.mtq_site.site_enabled
    error_message = "VEDA_MTQ_ESTIMATION_ENABLED needs VEDA_MTQ_SITE_ENABLED (scope is built on verified measurements)."
  }

  precondition {
    condition     = !local.mtq_commercial.estimation_enabled || length(local.commercial_record_problems) == 0
    error_message = "VEDA_MTQ_ESTIMATION_ENABLED turns on only with an owner-APPROVED infra/config/mtq-commercial-enablement-record.json bound by its SHA-256 with every evidence field filled: ${join("; ", local.commercial_record_problems)}."
  }
}

# Customer quotation experience (decision log 35): what is planned, and the gates that refuse the rest.
output "customer_proposal" {
  description = "Customer proposals on staging: viewing, interaction and acceptance flags (false until an owner-approved, digest-bound, synthetic-customers-only enablement record whose scope names each one)."
  value = {
    proposal_enabled    = local.cqx_config.VEDA_CUSTOMER_PROPOSAL_ENABLED
    interaction_enabled = local.cqx_config.VEDA_CUSTOMER_PROPOSAL_INTERACTION_ENABLED
    acceptance_enabled  = local.cqx_config.VEDA_CUSTOMER_QUOTATION_ACCEPTANCE_ENABLED
    enablement_record   = local.cqx.enablement_record_sha256
  }

  precondition {
    condition     = local.cqx.status == "DECIDED" && (local.cqx_any || local.cqx.enablement_record_sha256 == null)
    error_message = "customer_proposal must be DECIDED, and a digest is bound only together with a flag (rollback clears every flag and the digest)."
  }

  precondition {
    condition     = !local.cqx.proposal_enabled || local.mtq_commercial.quotation_enabled
    error_message = "VEDA_CUSTOMER_PROPOSAL_ENABLED needs VEDA_MTQ_QUOTATION_ENABLED (a proposal is an issued quotation)."
  }

  precondition {
    condition     = !local.cqx.interaction_enabled || local.cqx.proposal_enabled
    error_message = "VEDA_CUSTOMER_PROPOSAL_INTERACTION_ENABLED needs VEDA_CUSTOMER_PROPOSAL_ENABLED."
  }

  precondition {
    condition     = !local.cqx.acceptance_enabled || local.cqx.interaction_enabled
    error_message = "VEDA_CUSTOMER_QUOTATION_ACCEPTANCE_ENABLED needs VEDA_CUSTOMER_PROPOSAL_INTERACTION_ENABLED."
  }

  precondition {
    condition     = !local.cqx_any || length(local.cqx_record_problems) == 0
    error_message = "Customer-proposal flags turn on only with an owner-APPROVED infra/config/customer-proposal-enablement-record.json bound by its SHA-256, scoped to each flag, with every evidence field filled: ${join("; ", local.cqx_record_problems)}."
  }
}
