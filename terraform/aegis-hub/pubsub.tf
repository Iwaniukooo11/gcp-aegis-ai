# ------------------------------------------------------------------------------
# MAIN LOG INGESTION TOPIC
# ------------------------------------------------------------------------------
# This is where the Client Project will send all its error logs.
resource "google_pubsub_topic" "incoming_logs" {
  project = var.hub_project_id
  name    = "aegis-incoming-logs"
}

# ------------------------------------------------------------------------------
# DEAD LETTER QUEUE (DLQ)
# ------------------------------------------------------------------------------
# If a log is broken and crashes your Incident Analyzer 5 times in a row, 
# Pub/Sub will throw it in this "trash can" queue so it doesn't loop forever.
resource "google_pubsub_topic" "dead_letter" {
  project = var.hub_project_id
  name    = "aegis-dead-letter"
}

# ------------------------------------------------------------------------------
# PUBSUB PUSH SUBSCRIPTION (Connecting the Waiting Room to the Doctor)
# ------------------------------------------------------------------------------
resource "google_pubsub_subscription" "analyzer_push" {
  project = var.hub_project_id
  name    = "aegis-analyzer-sub"
  topic   = google_pubsub_topic.incoming_logs.name

  # If it fails 5 times, send it to the Dead Letter Queue
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }

  # Push the message to the Incident Analyzer Cloud Run URL
  push_config {
    push_endpoint = google_cloud_run_v2_service.incident_analyzer.uri
    
    # Use the special Pub/Sub ID badge we created in iam.tf
    oidc_token {
      service_account_email = google_service_account.pubsub_invoker.email
    }
  }
}

# Give the Pub/Sub ID badge permission to trigger the Incident Analyzer
resource "google_cloud_run_service_iam_member" "pubsub_can_invoke_analyzer" {
  project  = var.hub_project_id
  location = google_cloud_run_v2_service.incident_analyzer.location
  service  = google_cloud_run_v2_service.incident_analyzer.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_invoker.email}"
}
