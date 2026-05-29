locals {
  log_sink_filter_lines = concat(
    [
      "severity >= ERROR",
      "AND resource.type=\"k8s_container\"",
    ],
    var.log_sink_namespace != "" ? [
      format("AND resource.labels.namespace_name=\"%s\"", var.log_sink_namespace),
    ] : [],
  )
  log_sink_filter = join("\n", local.log_sink_filter_lines)
}

# ------------------------------------------------------------------------------
# CLOUD LOGGING ROUTER SINK (The Alarm)
# ------------------------------------------------------------------------------
resource "google_logging_project_sink" "error_to_hub" {
  project = var.client_project_id
  name    = "aegis-error-log-sink"

  destination = "pubsub.googleapis.com/projects/${var.hub_project_id}/topics/${var.hub_pubsub_topic_name}"

  filter = local.log_sink_filter

  # This creates a unique robot email just for this sink
  unique_writer_identity = true

  depends_on = [google_project_service.enabled_apis]
}

# ------------------------------------------------------------------------------
# CROSS-PROJECT PERMISSION: Allow the Sink to send messages to the Hub
# ------------------------------------------------------------------------------
resource "google_pubsub_topic_iam_member" "allow_log_sink_publish" {
  project = var.hub_project_id
  topic   = var.hub_pubsub_topic_name
  role    = "roles/pubsub.publisher"

  # The unique robot email created by the sink above
  member = google_logging_project_sink.error_to_hub.writer_identity
}
