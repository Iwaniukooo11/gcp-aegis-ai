# ------------------------------------------------------------------------------
# 1. SLACK GATEWAY (The Public Receptionist for Slack)
# ------------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "slack_gateway" {
  project  = var.hub_project_id
  name     = "aegis-slack-gateway"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  template {
    service_account = google_service_account.slack_gateway.email
    containers {
      image = var.slack_gateway_image # Using the dummy "hello world" image for now

      env {
        name  = "GCP_PROJECT"
        value = var.hub_project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "FIRESTORE_DATABASE"
        value = google_firestore_database.session_db.name
      }
      env {
        name  = "ALLOWED_CLIENT_PROJECT_IDS"
        value = join(",", var.allowed_client_project_ids)
      }
      env {
        name  = "SLACK_BOT_TOKEN_SECRET"
        value = google_secret_manager_secret.slack_token.id
      }
      env {
        name  = "SLACK_SIGNING_SECRET_SECRET"
        value = google_secret_manager_secret.slack_signing_secret.id
      }
    }
    scaling {
      min_instance_count = 0 # Scales to zero to save money!
      max_instance_count = 5
    }
  }

  depends_on = [
    google_project_service.enabled_apis,
    google_project_iam_member.slack_gateway_hub_permissions,
    google_firestore_field.sessions_ttl
  ]
}

# Make the Slack Gateway public (so Slack can send webhooks to it)
resource "google_cloud_run_v2_service_iam_member" "slack_gateway_public" {
  project  = var.hub_project_id
  location = google_cloud_run_v2_service.slack_gateway.location
  name     = google_cloud_run_v2_service.slack_gateway.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ------------------------------------------------------------------------------
# 2. INCIDENT ANALYZER (The AI Triage Doctor - PRIVATE)
# ------------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "incident_analyzer" {
  project  = var.hub_project_id
  name     = "aegis-incident-analyzer"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  template {
    service_account = google_service_account.incident_analyzer.email
    containers {
      image = var.incident_analyzer_image

      env {
        name  = "GCP_PROJECT"
        value = var.hub_project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "BIGQUERY_DATASET"
        value = google_bigquery_dataset.incidents.dataset_id
      }
      env {
        name  = "BIGQUERY_INCIDENTS_TABLE"
        value = google_bigquery_table.incidents.table_id
      }
      env {
        name  = "FIRESTORE_DATABASE"
        value = google_firestore_database.session_db.name
      }
      env {
        name  = "SLACK_ALERT_CHANNEL_ID"
        value = var.slack_alert_channel_id
      }
      env {
        name  = "SLACK_GATEWAY_URL"
        value = google_cloud_run_v2_service.slack_gateway.uri
      }
    }
    scaling {
      min_instance_count = 0
      max_instance_count = 10 # Higher max because log bursts can be huge
    }
  }

  depends_on = [
    google_project_service.enabled_apis,
    google_project_iam_member.incident_analyzer_hub_permissions,
    google_firestore_field.sessions_ttl
  ]
}

# ------------------------------------------------------------------------------
# 3. QUERY PROCESSOR (The Vitals Checker - PRIVATE)
# ------------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "query_processor" {
  project  = var.hub_project_id
  name     = "aegis-query-processor"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  template {
    service_account = google_service_account.query_processor.email
    containers {
      image = local.query_processor_image

      env {
        name  = "GCP_PROJECT"
        value = var.hub_project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "ALLOWED_CLIENT_PROJECT_IDS"
        value = join(",", var.allowed_client_project_ids)
      }
      env {
        name  = "BIGQUERY_DATASET"
        value = google_bigquery_dataset.incidents.dataset_id
      }
      env {
        name  = "BIGQUERY_INCIDENTS_TABLE"
        value = google_bigquery_table.incidents.table_id
      }
      env {
        name  = "FIRESTORE_DATABASE"
        value = google_firestore_database.session_db.name
      }
      env {
        name  = "SLACK_GATEWAY_URL"
        value = google_cloud_run_v2_service.slack_gateway.uri
      }
    }
    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
  }

  depends_on = [
    google_project_service.enabled_apis,
    google_project_iam_member.query_processor_hub_permissions,
    google_firestore_field.sessions_ttl
  ]
}

resource "google_cloud_run_v2_service_iam_member" "incident_analyzer_can_invoke_slack_gateway" {
  project  = var.hub_project_id
  location = google_cloud_run_v2_service.slack_gateway.location
  name     = google_cloud_run_v2_service.slack_gateway.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.incident_analyzer.email}"
}

resource "google_cloud_run_v2_service_iam_member" "query_processor_can_invoke_slack_gateway" {
  project  = var.hub_project_id
  location = google_cloud_run_v2_service.slack_gateway.location
  name     = google_cloud_run_v2_service.slack_gateway.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.query_processor.email}"
}
