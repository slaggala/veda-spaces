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
  description = "Resources the host may send through (AUT-106): the sender identity and the configuration set."
  value = [
    "arn:aws:ses:${var.region}:${var.account_id}:identity/${var.sender_domain}",
    "arn:aws:ses:${var.region}:${var.account_id}:configuration-set/${var.name_prefix}",
  ]
}

output "dkim_tokens" {
  description = "Easy DKIM tokens: AUT-202 publishes <token>._domainkey.<domain> CNAME <token>.dkim.amazonses.com."
  value       = aws_sesv2_email_identity.sender.dkim_signing_attributes[0].tokens
}
