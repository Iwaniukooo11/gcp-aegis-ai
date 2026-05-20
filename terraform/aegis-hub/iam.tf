# ------------------------------------------------------------------------------
# CLOUD RUN SERVICE IDENTITIES
# ------------------------------------------------------------------------------
resource "google_service_account" "slack_gateway" {
  project      = var.hub_project_id
  account_id   = "aegis-slack-gateway-sa"
  display_name = "Aegis Slack Gateway Service Account"
}

resource "google_service_account" "incident_analyzer" {
  project      = var.hub_project_id
  account_id   = "aegis-incident-analyzer-sa"
  display_name = "Aegis Incident Analyzer Service Account"
}

resource "google_service_account" "query_processor" {
  project      = var.hub_project_id
  account_id   = "aegis-query-processor-sa"
  display_name = "Aegis Query Processor Service Account"
}

# ------------------------------------------------------------------------------
# HUB PERMISSIONS FOR CLOUD RUN SERVICES
# ------------------------------------------------------------------------------
locals {
  slack_gateway_hub_roles = [
    "roles/secretmanager.secretAccessor"
  ]

  incident_analyzer_hub_roles = [
    "roles/aiplatform.user",
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/datastore.user"
  ]

  query_processor_hub_roles = [
    "roles/aiplatform.user",
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/datastore.user"
  ]

  pubsub_service_agent = "service-${data.google_project.hub.number}@gcp-sa-pubsub.iam.gserviceaccount.com"

  cloud_run_service_accounts = {
    slack_gateway     = google_service_account.slack_gateway.name
    incident_analyzer = google_service_account.incident_analyzer.name
    query_processor   = google_service_account.query_processor.name
  }
}

resource "google_project_iam_member" "slack_gateway_hub_permissions" {
  for_each = toset(local.slack_gateway_hub_roles)
  project  = var.hub_project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.slack_gateway.email}"
}

resource "google_project_iam_member" "incident_analyzer_hub_permissions" {
  for_each = toset(local.incident_analyzer_hub_roles)
  project  = var.hub_project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.incident_analyzer.email}"
}

resource "google_project_iam_member" "query_processor_hub_permissions" {
  for_each = toset(local.query_processor_hub_roles)
  project  = var.hub_project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.query_processor.email}"
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

resource "google_service_account_iam_member" "terraform_can_attach_cloud_run_service_accounts" {
  for_each = {
    for binding in setproduct(keys(local.cloud_run_service_accounts), var.terraform_service_account_user_members) :
    "${binding[0]}:${binding[1]}" => {
      service_account_name = local.cloud_run_service_accounts[binding[0]]
      member               = binding[1]
    }
  }

  service_account_id = each.value.service_account_name
  role               = "roles/iam.serviceAccountUser"
  member             = each.value.member
}

resource "google_service_account_iam_member" "terraform_can_attach_pubsub_invoker" {
  for_each = var.terraform_service_account_user_members

  service_account_id = google_service_account.pubsub_invoker.name
  role               = "roles/iam.serviceAccountUser"
  member             = each.key
}
