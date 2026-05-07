# ------------------------------------------------------------------------------
# CROSS-PROJECT PERMISSIONS: Allow the Hub Bot to read Client data
# ------------------------------------------------------------------------------

# Allow the bot to read live CPU/Memory metrics
resource "google_project_iam_member" "hub_monitoring_viewer" {
  project = var.client_project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${var.hub_bot_service_account_email}"
}

# Allow the bot to read historical logs (if needed for context)
resource "google_project_iam_member" "hub_logging_viewer" {
  project = var.client_project_id
  role    = "roles/logging.viewer"
  member  = "serviceAccount:${var.hub_bot_service_account_email}"
}
