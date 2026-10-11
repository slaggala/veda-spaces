variable "record_path" {
  description = "The V3 staging approval record file. A missing or unreadable file is NO_RECORD."
  type        = string
}

variable "bound_sha256" {
  description = "The digest the record must have (catalog_v3.approval_record_sha256), or null when none is bound."
  type        = string
  default     = null
}

variable "today" {
  description = "The current UTC date, YYYY-MM-DD (the calling root passes the plan timestamp's date)."
  type        = string

  validation {
    condition     = can(regex("^[12][0-9]{3}-[0-9]{2}-[0-9]{2}$", var.today)) && can(timecmp("${var.today}T00:00:00Z", "1000-01-01T00:00:00Z"))
    error_message = "today is a YYYY-MM-DD calendar date."
  }
}

variable "policy_path" {
  description = "The shared approval policy (empty: api/veda/modules/catalog/v3_approval_policy.json)."
  type        = string
  default     = ""
}
