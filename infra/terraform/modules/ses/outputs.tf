output "from_address" {
  description = "The only From address the host may use."
  value       = "${var.sender_local_part}@${var.sender_domain}"
}

output "sender" {
  description = "VEDA_EMAIL_SENDER."
  value       = "Veda Spaces Staging <${var.sender_local_part}@${var.sender_domain}>"
}

output "configuration_set" {
  description = "VEDA_SES_CONFIGURATION_SET."
  value       = aws_sesv2_configuration_set.this.configuration_set_name
}

output "send_resources" {
  description = "Resources the host may send through (AUT-106): the sender identity, the configuration set and, while the account is in the SES sandbox, the verified recipient addresses (SES checks the recipient identity too)."
  value = [
    "arn:aws:ses:${var.region}:${var.account_id}:identity/${var.sender_domain}",
    "arn:aws:ses:${var.region}:${var.account_id}:configuration-set/${var.name_prefix}",
    # Email-address identities only, never another domain: the sandbox recipients the owner verified (O11). Named by
    # pattern, so the (sensitive) owner address never appears in the plan text. The From address stays pinned by the
    # ses:FromAddress condition of the host policy.
    "arn:aws:ses:${var.region}:${var.account_id}:identity/*@*",
  ]
}

output "dkim_tokens" {
  description = "Easy DKIM tokens: AUT-202 publishes <token>._domainkey.<domain> CNAME <token>.dkim.amazonses.com."
  value       = aws_sesv2_email_identity.sender.dkim_signing_attributes[0].tokens
}
