# ── AWS Cost Controls module ────────────────────────────────────
# Sets up budgets + alerts so spend surprises never reach the card

variable "env"        { type = string }
variable "aws_region" { type = string }
variable "monthly_budget_usd" {
  type    = number
  default = 500           # alert at 80% ($400) and 100% ($500)
}
variable "alert_email" {
  type    = string
  default = "mlops-alerts@example.com"
}

resource "aws_budgets_budget" "mlops_monthly" {
  name         = "mlops-${var.env}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}

# S3 Storage Lens — visibility into storage costs across all buckets
resource "aws_s3control_storage_lens_configuration" "mlops" {
  config_id = "mlops-storage-lens-${var.env}"
  storage_lens_configuration {
    enabled = true
    account_level {
      bucket_level { }
    }
  }
}
