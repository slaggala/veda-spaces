output "codes" {
  description = "The failing rule codes, in policy order (empty: the record authorises V3 on protected staging today)."
  value       = local.codes
}

output "messages" {
  description = "The policy message of each failing code."
  value       = [for c in local.policy.codes : c.message if contains(local.codes, c.code)]
}

output "record_sha256" {
  description = "The SHA-256 of the record file (empty when there is none)."
  value       = local.sha256
}
