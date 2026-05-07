# ------------------------------------------------------------------------------
# THE MAIN BOT IDENTITY
# ------------------------------------------------------------------------------
# This is the "ID Badge" that your Cloud Run services will wear.
resource "google_service_account" "aegis_bot" {
  project      = var.hub_project_id
  account_id   = "aegis-bot-sa"
  display_name = "Aegis Bot Service Account"
}

# ------------------------------------------------------------------------------
# HUB PERMISSIONS FOR THE BOT
# ------------------------------------------------------------------------------
# We are telling GCP: "The bot is allowed to use Firestore, BigQuery, AI, and Secrets."
locals {
  bot_hub_roles =[
    "roles/datastore.user",               # Read/write chats to Firestore
    "roles/bigquery.dataEditor",          # Save incident records to BigQuery
    "roles/aiplatform.user",              # Talk to Vertex AI (Gemini)
    "roles/secretmanager.secretAccessor"  # Read Slack tokens from the Safe
  ]
}

resource "google_project_iam_member" "bot_hub_permissions" {
  for_each = toset(local.bot_hub_roles)
  project  = var.hub_project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.aegis_bot.email}"
}

# ------------------------------------------------------------------------------
# PUBSUB TRIGGER IDENTITY
# ------------------------------------------------------------------------------
# Pub/Sub needs its own ID badge just to be allowed to "push" messages to Cloud Run.
resource "google_service_account" "pubsub_invoker" {
  project      = var.hub_project_id
  account_id   = "pubsub-invoker-sa"
  display_name = "Pub/Sub Cloud Run Invoker"
}
