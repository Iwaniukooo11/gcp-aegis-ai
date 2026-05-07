# ------------------------------------------------------------------------------
# MAIN LOG INGESTION TOPIC
# ------------------------------------------------------------------------------
# This is where the Client Project will send all its error logs.
resource "google_pubsub_topic" "incoming_logs" {
  project = var.hub_project_id
  name    = "aegis-incoming-logs"

  message_storage_policy {
    allowed_persistence_regions = [var.region]
  }

  depends_on = [google_project_service.enabled_apis]
}

# ------------------------------------------------------------------------------
# DEAD LETTER QUEUE (DLQ)
# ------------------------------------------------------------------------------
# If a log is broken and crashes your Incident Analyzer 5 times in a row, 
# Pub/Sub will throw it in this "trash can" queue so it doesn't loop forever.
resource "google_pubsub_topic" "dead_letter" {
  project = var.hub_project_id
  name    = "aegis-dead-letter"

  message_storage_policy {
    allowed_persistence_regions = [var.region]
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_pubsub_topic_iam_member" "pubsub_can_publish_dead_letters" {
  project = var.hub_project_id
  topic   = google_pubsub_topic.dead_letter.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${local.pubsub_service_agent}"
}

# ------------------------------------------------------------------------------
# PUBSUB PUSH SUBSCRIPTION (Connecting the Waiting Room to the Doctor)
# ------------------------------------------------------------------------------
resource "google_pubsub_subscription" "analyzer_push" {
  project               = var.hub_project_id
  name                  = "aegis-analyzer-sub"
  topic                 = google_pubsub_topic.incoming_logs.id
  ack_deadline_seconds  = 30
  retain_acked_messages = false

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
      audience              = google_cloud_run_v2_service.incident_analyzer.uri
    }
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_cloud_run_v2_service_iam_member.pubsub_can_invoke_analyzer,
    google_service_account_iam_member.pubsub_can_sign_push_tokens,
    google_pubsub_topic_iam_member.pubsub_can_publish_dead_letters
  ]
}

resource "google_pubsub_subscription_iam_member" "pubsub_can_ack_dead_lettered_messages" {
  project      = var.hub_project_id
  subscription = google_pubsub_subscription.analyzer_push.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${local.pubsub_service_agent}"
}

resource "google_pubsub_subscription" "dead_letter_pull" {
  project                    = var.hub_project_id
  name                       = "aegis-dead-letter-pull"
  topic                      = google_pubsub_topic.dead_letter.id
  ack_deadline_seconds       = 60
  retain_acked_messages      = false
  message_retention_duration = "1209600s"

  expiration_policy {
    ttl = ""
  }
}

# Give the Pub/Sub ID badge permission to trigger the Incident Analyzer
resource "google_cloud_run_v2_service_iam_member" "pubsub_can_invoke_analyzer" {
  project  = var.hub_project_id
  location = google_cloud_run_v2_service.incident_analyzer.location
  name     = google_cloud_run_v2_service.incident_analyzer.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_invoker.email}"
}
