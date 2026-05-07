# ------------------------------------------------------------------------------
# TERRAFORM & PROVIDER SETUP
# ------------------------------------------------------------------------------
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # TEAM COLLABORATION: Remote State Bucket
  # NOTE: You must manually create this bucket in GCP before running Terraform!
  backend "gcs" {
    bucket = "igor-aegis-tf-state-123" # e.g., "aegis-tf-state-team4"
    prefix = "terraform/hub/state"     # Saves the file in a specific folder inside the bucket
  }
}

provider "google" {
  project = var.hub_project_id
  region  = var.region

  default_labels = {
    app         = "aegis-ai"
    component   = "hub"
    environment = var.environment
    managed_by  = "terraform"
  }
}

data "google_project" "hub" {
  project_id = var.hub_project_id
}

# ------------------------------------------------------------------------------
# ENABLE GCP APIs ("Turning on the electricity")
# ------------------------------------------------------------------------------
# A brand new GCP project has everything turned off. We must enable these to use them.
locals {
  services = [
    "run.googleapis.com",        # Cloud Run
    "pubsub.googleapis.com",     # Pub/Sub
    "firestore.googleapis.com",  # Firestore
    "aiplatform.googleapis.com", # Vertex AI (Gemini)
    "bigquery.googleapis.com",   # BigQuery
    "logging.googleapis.com",    # Cloud Logging
    "monitoring.googleapis.com", # Cloud Monitoring
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "serviceusage.googleapis.com",
    "secretmanager.googleapis.com",   # Secret Manager
    "artifactregistry.googleapis.com" # Artifact Registry
  ]
}

resource "google_project_service" "enabled_apis" {
  for_each           = toset(local.services)
  project            = var.hub_project_id
  service            = each.key
  disable_on_destroy = false # Prevents accidentally turning off APIs if you destroy resources
}

# ------------------------------------------------------------------------------
# FIRESTORE DATABASE (The "Sticky Note Pad" for Chat History)
# ------------------------------------------------------------------------------
# Wait for the Firestore API to be enabled before trying to create the database.
resource "google_firestore_database" "session_db" {
  project     = var.hub_project_id
  name        = "(default)" # GCP requires the first database to be named exactly this
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  # For a university project, it's safe to delete the DB if we destroy Terraform.
  # In a real company, this would be "RETAIN".
  deletion_policy = "DELETE"

  depends_on = [google_project_service.enabled_apis]
}

resource "google_firestore_field" "sessions_ttl" {
  project    = var.hub_project_id
  database   = google_firestore_database.session_db.name
  collection = "sessions"
  field      = "ttl"

  # The session TTL field is only used by Firestore's expiration worker. Avoid
  # indexing it to reduce write overhead and hotspot risk on timestamp values.
  index_config {}
  ttl_config {}

  depends_on = [google_firestore_database.session_db]
}
