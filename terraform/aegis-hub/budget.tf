# ------------------------------------------------------------------------------
# OPTIONAL COST CONTROL
# ------------------------------------------------------------------------------
# Budget creation requires permissions on the Cloud Billing account. Leave
# billing_account_name null when those permissions are not available.
resource "google_billing_budget" "hub_monthly" {
  count = var.billing_account_name == null ? 0 : 1

  billing_account = var.billing_account_name
  display_name    = "Aegis AI Hub ${var.environment} monthly budget"

  budget_filter {
    projects        = ["projects/${data.google_project.hub.number}"]
    calendar_period = "MONTH"
  }

  amount {
    specified_amount {
      currency_code = var.budget_currency_code
      units         = tostring(var.monthly_budget_units)
    }
  }

  dynamic "threshold_rules" {
    for_each = var.budget_alert_thresholds

    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }
}
