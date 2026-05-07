# ------------------------------------------------------------------------------
# 1. SLACK GATEWAY (The Public Receptionist for Slack)
# ------------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "slack_gateway" {
  project  = var.hub_project_id
  name     = "aegis-slack-gateway"
  location = var.region

  template {
    service_account = google_service_account.aegis_bot.email
    containers {
      image = var.slack_gateway_image # Using the dummy "hello world" image for now
    }
    scaling {
      min_instance_count = 0 # Scales to zero to save money!
      max_instance_count = 5
    }
  }
}

# Make the Slack Gateway public (so Slack can send webhooks to it)
resource "google_cloud_run_service_iam_member" "slack_gateway_public" {
  project  = var.hub_project_id
  location = google_cloud_run_v2_service.slack_gateway.location
  service  = google_cloud_run_v2_service.slack_gateway.name
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

  template {
    service_account = google_service_account.aegis_bot.email
    containers {
      image = var.incident_analyzer_image
    }
    scaling {
      min_instance_count = 0
      max_instance_count = 10 # Higher max because log bursts can be huge
    }
  }
}

# ------------------------------------------------------------------------------
# 3. METRICS SERVICE (The Vitals Checker - PRIVATE)
# ------------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "metrics_service" {
  project  = var.hub_project_id
  name     = "aegis-metrics-service"
  location = var.region

  template {
    service_account = google_service_account.aegis_bot.email
    containers {
      image = var.metrics_service_image
    }
    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
  }
}
