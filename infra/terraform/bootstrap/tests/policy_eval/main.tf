# Offline IAM policy evaluator used only by the bootstrap tests (no provider, no resources, no AWS call).
#
# For each probe (action, resource, request context) it returns the decision of IAM's evaluation logic for one
# principal in one account:
#   "deny"     an explicit Deny matches in any of the identity policies, the boundary or the resource policy;
#   "allow"    an identity Allow matches and (when a boundary is given) a boundary Allow matches too;
#   "implicit" otherwise (implicitly denied).
# Supported: Action/NotAction, Resource/NotResource with * and ? wildcards (actions case-insensitive), and the
# condition operators the Veda policies use (Null: "true" matches an absent key, "false" a present one). An
# unsupported operator never matches, so a probe that relies on it fails loudly instead of passing silently.
# Principals are not evaluated: set the context keys a resource policy conditions on (for example aws:PrincipalArn).
# Key policies (key_policies) apply only to requests on a KMS key: their Deny statements are evaluated, and their
# account-root Allow is the delegation that lets the identity policies decide.

terraform {
  required_version = ">= 1.10.0, < 2.0.0"
}

variable "identity_policies" {
  description = "Identity policy JSON documents attached to the principal."
  type        = list(string)
  default     = []
}

variable "boundary_policy" {
  description = "Permissions boundary JSON, or empty for none."
  type        = string
  default     = ""
}

variable "resource_policies" {
  description = "Resource policy JSON documents; only their Deny statements are evaluated."
  type        = list(string)
  default     = []
}

variable "key_policies" {
  description = "KMS key policy JSON documents; their Deny statements apply only to requests on a KMS key (a key policy's Resource \"*\" means that key)."
  type        = list(string)
  default     = []
}

variable "default_context" {
  description = "Request context merged under every probe's own context."
  type        = map(string)
  default     = {}
}

variable "probes" {
  type = list(object({
    name     = string
    action   = string
    resource = string
    context  = optional(map(string), {})
    expect   = string
  }))

  validation {
    condition     = alltrue([for p in var.probes : contains(["deny", "allow", "implicit", "not_deny"], p.expect)])
    error_message = "expect must be deny, allow, implicit or not_deny."
  }
}

locals {
  # Glob → anchored regular expression: escape regex metacharacters, then * → .* and ? → .
  documents = concat(
    [for d in var.identity_policies : { source = "identity", json = d }],
    var.boundary_policy == "" ? [] : [{ source = "boundary", json = var.boundary_policy }],
    [for d in var.resource_policies : { source = "resource", json = d }],
    [for d in var.key_policies : { source = "key", json = d }],
  )

  statements = flatten([for d in local.documents : [for s in flatten([jsondecode(d.json).Statement]) : {
    source = d.source
    sid    = try(s.Sid, "")
    effect = s.Effect
    action_patterns = [for a in try(flatten([s.Action]), []) :
    "(?i)^${replace(replace(replace(a, "/([.+(){}|^$\\[\\]\\\\])/", "\\$1"), "*", ".*"), "?", ".")}$"]
    not_action_patterns = [for a in try(flatten([s.NotAction]), []) :
    "(?i)^${replace(replace(replace(a, "/([.+(){}|^$\\[\\]\\\\])/", "\\$1"), "*", ".*"), "?", ".")}$"]
    has_not_action = can(s.NotAction)
    resource_patterns = [for r in try(flatten([s.Resource]), []) :
    "^${replace(replace(replace(r, "/([.+(){}|^$\\[\\]\\\\])/", "\\$1"), "*", ".*"), "?", ".")}$"]
    not_resource_patterns = [for r in try(flatten([s.NotResource]), []) :
    "^${replace(replace(replace(r, "/([.+(){}|^$\\[\\]\\\\])/", "\\$1"), "*", ".*"), "?", ".")}$"]
    has_not_resource = can(s.NotResource)
    conditions = flatten([for op, kv in try(s.Condition, {}) : [for k, v in kv : {
      op     = op
      key    = k
      values = [for x in flatten([v]) : tostring(x)]
      value_patterns = [for x in flatten([v]) :
      "^${replace(replace(replace(tostring(x), "/([.+(){}|^$\\[\\]\\\\])/", "\\$1"), "*", ".*"), "?", ".")}$"]
    }]])
  }]])

  results = [for p in var.probes : {
    name    = p.name
    expect  = p.expect
    context = merge(var.default_context, p.context)
    matched = [for s in local.statements : { source = s.source, sid = s.sid, effect = s.effect } if(
      (s.source != "key" || can(regex("^arn:aws[a-z-]*:kms:[a-z0-9-]+:[0-9]{12}:key/", p.resource)))
      && (s.has_not_action
        ? !anytrue([for r in s.not_action_patterns : can(regex(r, p.action))])
      : anytrue([for r in s.action_patterns : can(regex(r, p.action))]))
      && (s.has_not_resource
        ? !anytrue([for r in s.not_resource_patterns : can(regex(r, p.resource))])
      : anytrue([for r in s.resource_patterns : can(regex(r, p.resource))]))
      && alltrue([for c in s.conditions : (
        contains(["StringEquals", "ArnEquals", "Bool", "ForAnyValue:StringEquals"], c.op)
        ? contains(c.values, lookup(merge(var.default_context, p.context), c.key, "\u0000absent"))
        : contains(["StringNotEquals", "StringNotEqualsIfExists", "ArnNotEquals"], c.op)
        ? !contains(c.values, lookup(merge(var.default_context, p.context), c.key, "\u0000absent"))
        : contains(["StringLike", "ArnLike"], c.op)
        ? anytrue([for r in c.value_patterns : can(regex(r, lookup(merge(var.default_context, p.context), c.key, "\u0000absent")))])
        : contains(["StringNotLike", "StringNotLikeIfExists", "ArnNotLike"], c.op)
        ? !anytrue([for r in c.value_patterns : can(regex(r, lookup(merge(var.default_context, p.context), c.key, "\u0000absent")))])
        : c.op == "Null"
        ? (lookup(merge(var.default_context, p.context), c.key, "\u0000absent") == "\u0000absent") == (c.values[0] == "true")
        : false
      )])
    )]
  }]

  decisions = [for r in local.results : merge(r, {
    decision = (
      anytrue([for m in r.matched : m.effect == "Deny"]) ? "deny" :
      (anytrue([for m in r.matched : m.effect == "Allow" && m.source == "identity"])
        && (var.boundary_policy == "" || anytrue([for m in r.matched : m.effect == "Allow" && m.source == "boundary"]))
      ) ? "allow" : "implicit"
    )
    denied_by = [for m in r.matched : "${m.source}:${m.sid}" if m.effect == "Deny"]
  })]
}

output "decisions" {
  value = { for d in local.decisions : d.name => { decision = d.decision, denied_by = d.denied_by } }
}

output "failures" {
  description = "Probes whose decision differs from the expectation (not_deny accepts allow or implicit)."
  value = [for d in local.decisions : "${d.name}: expected ${d.expect}, got ${d.decision}${length(d.denied_by) > 0 ? " (${join(",", d.denied_by)})" : ""}"
  if !(d.decision == d.expect || (d.expect == "not_deny" && d.decision != "deny"))]
}
