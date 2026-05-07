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
