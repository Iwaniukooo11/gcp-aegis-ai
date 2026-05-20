# ------------------------------------------------------------------------------
# CROSS-PROJECT PERMISSIONS: Allow the Hub Query Processor to read Client data
# ------------------------------------------------------------------------------

# Allow the Query Processor to read live CPU/Memory metrics
resource "google_project_iam_member" "hub_monitoring_viewer" {
  project = var.client_project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${var.hub_query_processor_service_account_email}"

  depends_on = [google_project_service.enabled_apis]
}
