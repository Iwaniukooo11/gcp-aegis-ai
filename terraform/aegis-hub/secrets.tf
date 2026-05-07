# ------------------------------------------------------------------------------
# SECRET MANAGER (The Safe for Passwords)
# ------------------------------------------------------------------------------
resource "google_secret_manager_secret" "slack_token" {
  project   = var.hub_project_id
  secret_id = "slack-bot-token"

  replication {
    auto {} # Google automatically replicates this secret across data centers
  }
}

resource "google_secret_manager_secret" "slack_signing_secret" {
  project   = var.hub_project_id
  secret_id = "slack-signing-secret"

  replication {
    auto {}
  }
}
