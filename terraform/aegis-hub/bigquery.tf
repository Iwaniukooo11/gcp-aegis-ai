# ------------------------------------------------------------------------------
# BIGQUERY DATASET (The Filing Cabinet)
# ------------------------------------------------------------------------------
resource "google_bigquery_dataset" "incidents" {
  project    = var.hub_project_id
  dataset_id = "aegis_incidents"
  location   = var.region
}

# ------------------------------------------------------------------------------
# BIGQUERY TABLE (The specific folder inside the cabinet)
# ------------------------------------------------------------------------------
resource "google_bigquery_table" "incidents" {
  project    = var.hub_project_id
  dataset_id = google_bigquery_dataset.incidents.dataset_id
  table_id   = "incidents"

  # Partition by day (makes time-based SLO queries very cheap)
  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }

  # Cluster by common filters (speeds up searching for specific errors)
  clustering = ["client_project_id", "service_name", "severity"]

  # UPDATED SCHEMA based on the new M1 Checkpoint Document
  schema = <<EOF[
  {"name": "incident_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "idempotency_key", "type": "STRING", "mode": "REQUIRED"},
  {"name": "client_project_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "cluster_name", "type": "STRING", "mode": "NULLABLE"},
  {"name": "namespace", "type": "STRING", "mode": "NULLABLE"},
  {"name": "service_name", "type": "STRING", "mode": "REQUIRED"},
  {"name": "pod_name", "type": "STRING", "mode": "NULLABLE"},
  {"name": "severity", "type": "STRING", "mode": "REQUIRED"},
  {"name": "error_type", "type": "STRING", "mode": "NULLABLE"},
  {"name": "short_message", "type": "STRING", "mode": "NULLABLE"},
  {"name": "stack_trace_preview", "type": "STRING", "mode": "NULLABLE"},
  {"name": "ai_summary", "type": "STRING", "mode": "NULLABLE"},
  {"name": "ai_recommendation", "type": "STRING", "mode": "NULLABLE"},
  {"name": "slack_channel", "type": "STRING", "mode": "NULLABLE"},
  {"name": "slack_message_ts", "type": "STRING", "mode": "NULLABLE"},
  {"name": "created_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "hub_received_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "incident_persisted_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "first_alert_sent_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "ai_summary_completed_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "processing_completed_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "terminal_status", "type": "STRING", "mode": "REQUIRED"},
  {"name": "terminal_failure_reason", "type": "STRING", "mode": "NULLABLE"}
]
EOF
}
