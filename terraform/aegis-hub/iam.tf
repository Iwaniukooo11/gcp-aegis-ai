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
  bot_hub_roles = [
    "roles/datastore.user",              # Read/write chats to Firestore
    "roles/bigquery.dataEditor",         # Save incident records to BigQuery
    "roles/bigquery.jobUser",            # Run incident-query and SLO queries
    "roles/aiplatform.user",             # Talk to Vertex AI (Gemini)
    "roles/secretmanager.secretAccessor" # Read Slack tokens from the Safe
  ]

  pubsub_service_agent = "service-${data.google_project.hub.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
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

resource "google_service_account_iam_member" "pubsub_can_sign_push_tokens" {
  service_account_id = google_service_account.pubsub_invoker.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${local.pubsub_service_agent}"
}

resource "google_service_account_iam_member" "terraform_can_attach_aegis_bot" {
  for_each = var.terraform_service_account_user_members

  service_account_id = google_service_account.aegis_bot.name
  role               = "roles/iam.serviceAccountUser"
  member             = each.key
}

resource "google_service_account_iam_member" "terraform_can_attach_pubsub_invoker" {
  for_each = var.terraform_service_account_user_members

  service_account_id = google_service_account.pubsub_invoker.name
  role               = "roles/iam.serviceAccountUser"
  member             = each.key
}
