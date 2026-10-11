# The V3 staging approval rules at plan time: api/veda/modules/catalog/v3_approval_policy.json, implemented exactly as
# written there (the Python validator and app/scripts/v3-approval.mjs implement the same text). The shared conformance
# cases (api/tests/fixtures/v3_approval/cases.json, generated into tests/conformance.tftest.hcl) prove the three decide
# every case identically. A value's JSON type is read from jsonencode(): Terraform converts numbers and booleans to
# strings silently, and the rules compare JSON types.
locals {
  policy = jsondecode(file(var.policy_path != "" ? var.policy_path : "${path.module}/../../../../api/veda/modules/catalog/v3_approval_policy.json"))

  raw    = try(file(var.record_path), null)
  sha256 = try(filesha256(var.record_path), "")
  doc    = local.raw == null ? null : try(jsondecode(local.raw), null)
  is_obj = local.doc != null && try(startswith(jsonencode(local.doc), "{"), false)
  r      = local.is_obj ? local.doc : null # every read of r is inside try()

  # JSON type and value of each top-level field ("null" when the key is absent).
  json = { for k in ["schema", "status", "environment", "release", "approver", "author", "approved_at", "review_by",
  "expires_at", "non_expiring_decision", "revoked_at", "revocation_reason"] : k => try(jsonencode(local.r[k]), "null") }
  str     = { for k, v in local.json : k => startswith(v, "\"") ? local.r[k] : null }
  present = { for k, v in local.json : k => v != "null" }

  ws   = "/[ \\t\\r\\n]+/"
  edge = "/^[ \\t\\r\\n]+|[ \\t\\r\\n]+$/"
  norm = { for k in ["approver", "author"] : k => local.str[k] == null ? null : lower(replace(replace(local.str[k], local.edge, ""), local.ws, " ")) }

  # Dates as RFC 3339 instants (null: not a date). timecmp refuses a day that does not exist.
  day = { for k in ["approved_at", "review_by", "expires_at"] : k => (
    local.str[k] != null && can(regex(local.policy.date_pattern, local.str[k])) && can(timecmp("${local.str[k]}T00:00:00Z", "1000-01-01T00:00:00Z"))
  ) ? "${local.str[k]}T00:00:00Z" : null }
  now          = "${var.today}T00:00:00Z"
  approved     = local.day.approved_at
  review       = local.day.review_by
  expires      = local.day.expires_at
  review_limit = local.approved == null ? null : timeadd(local.approved, "${local.policy.max_review_days * 24}h")

  scope      = try(local.r.approval_scope, null)
  scope_json = { for k in concat(keys(local.policy.scope), ["media_delivery"]) : k => try(jsonencode(local.scope[k]), "null") }
  scope_ok = try(startswith(jsonencode(local.scope), "{"), false) && alltrue([
    for k, v in local.policy.scope : local.scope_json[k] == jsonencode(v)
  ]) && contains(["true", "false"], local.scope_json.media_delivery)

  evidence     = try(local.r.evidence, null)
  required     = concat(local.policy.git_evidence, local.policy.digest_evidence)
  evidence_obj = try(startswith(jsonencode(local.evidence), "{"), false)
  evidence_ok = local.evidence_obj && try(toset(keys(local.evidence)) == toset(local.required), false) && alltrue([
    for k in local.required : try(
      startswith(jsonencode(local.evidence[k]), "{") &&
      startswith(jsonencode(local.evidence[k].reference), "\"") &&
      length(replace(local.evidence[k].reference, local.edge, "")) >= local.policy.reference_min_length &&
      startswith(jsonencode(local.evidence[k][contains(local.policy.git_evidence, k) ? "git_sha" : "sha256"]), "\"") &&
      can(regex(contains(local.policy.git_evidence, k) ? local.policy.git_sha_pattern : local.policy.sha256_pattern,
      local.evidence[k][contains(local.policy.git_evidence, k) ? "git_sha" : "sha256"])),
    false)
  ])

  placeholder = upper(local.policy.placeholder)
  decision_ok = local.str.non_expiring_decision != null && try(
    length(replace(local.str.non_expiring_decision, local.edge, "")) >= local.policy.non_expiring_min_length, false
  )

  failing = local.raw == null ? toset(["NO_RECORD"]) : !local.is_obj ? toset(["MALFORMED"]) : toset(compact([
    local.str.schema == local.policy.schema ? "" : "SCHEMA",
    local.str.status == local.policy.approved_status ? "" : "STATUS",
    local.str.environment == local.policy.environment ? "" : "ENVIRONMENT",
    local.str.release != null && can(regex(local.policy.release_pattern, coalesce(local.str.release, "-"))) ? "" : "RELEASE",
    local.scope_ok ? "" : "SCOPE",
    local.str.status == local.policy.revoked_status || local.present.revoked_at || local.present.revocation_reason ? "REVOKED" : "",
    (local.norm.approver == null || local.norm.author == null ? false :
      local.norm.approver != "" && local.norm.author != "" && local.norm.approver != local.norm.author &&
      !strcontains(upper(local.str.approver), local.placeholder) && !strcontains(upper(local.str.author), local.placeholder)
    ) ? "" : "APPROVER",
    local.approved == null ? "APPROVAL_DATE" : "",
    local.approved != null && try(timecmp(local.approved, local.now) > 0, false) ? "APPROVAL_IN_FUTURE" : "",
    local.review == null || (local.approved != null && !(
      try(timecmp(local.approved, local.review) < 0, false) && try(timecmp(local.review, local.review_limit) <= 0, false)
    )) ? "REVIEW_WINDOW" : "",
    local.review != null && try(timecmp(local.review, local.now) <= 0, false) ? "REVIEW_REACHED" : "",
    local.present.expires_at == local.present.non_expiring_decision ||
    (local.present.expires_at && (local.expires == null || (local.approved != null && try(timecmp(local.expires, local.approved) <= 0, false)))) ||
    (local.present.non_expiring_decision && !local.decision_ok) ? "EXPIRY_POLICY" : "",
    local.expires != null && try(timecmp(local.expires, local.now) <= 0, false) ? "EXPIRED" : "",
    local.evidence_ok ? "" : "EVIDENCE",
    var.bound_sha256 != null && can(regex(local.policy.sha256_pattern, coalesce(var.bound_sha256, "-"))) && var.bound_sha256 == local.sha256 ? "" : "DIGEST_MISMATCH",
  ]))

  codes = [for c in local.policy.codes : c.code if contains(local.failing, c.code)]
}
