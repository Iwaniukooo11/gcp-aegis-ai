# ------------------------------------------------------------------------------
# SECRET MANAGER (The Safe for Passwords)
# ------------------------------------------------------------------------------
resource "google_secret_manager_secret" "slack_token" {
  project   = var.hub_project_id
  secret_id = "slack-bot-token"

  replication {
    auto {} # Google automatically replicates this secret across data centers
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret" "slack_signing_secret" {
  project   = var.hub_project_id
  secret_id = "slack-signing-secret"

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret_version" "slack_token" {
  secret      = google_secret_manager_secret.slack_token.id
  secret_data = var.slack_bot_token

  lifecycle {
    create_before_destroy = true
  }
}

resource "google_secret_manager_secret_version" "slack_signing_secret" {
  count = var.slack_signing_secret != "" ? 1 : 0

  secret      = google_secret_manager_secret.slack_signing_secret.id
  secret_data = var.slack_signing_secret

  lifecycle {
    create_before_destroy = true
  }
}
