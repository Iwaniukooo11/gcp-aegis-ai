# ------------------------------------------------------------------------------
# CLOUD LOGGING ROUTER SINK (The Alarm)
# ------------------------------------------------------------------------------
resource "google_logging_project_sink" "error_to_hub" {
  name        = "aegis-error-log-sink"
  
  # Point the sink directly to the Hub's Pub/Sub topic
  destination = "pubsub.googleapis.com/projects/${var.hub_project_id}/topics/${var.hub_pubsub_topic_name}"

  # ONLY catch errors from Kubernetes containers (ignores normal info logs to save money)
  filter      = <<-EOT
    severity >= ERROR
    AND resource.type="k8s_container"
  EOT

  # This creates a unique robot email just for this sink
  unique_writer_identity = true
}

# ------------------------------------------------------------------------------
# CROSS-PROJECT PERMISSION: Allow the Sink to send messages to the Hub
# ------------------------------------------------------------------------------
resource "google_pubsub_topic_iam_member" "allow_log_sink_publish" {
  project = var.hub_project_id
  topic   = var.hub_pubsub_topic_name
  role    = "roles/pubsub.publisher"
  
  # The unique robot email created by the sink above
  member  = google_logging_project_sink.error_to_hub.writer_identity
}
