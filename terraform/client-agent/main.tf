terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  
  # TEAM COLLABORATION: Remote State
  backend "gcs" {
    bucket = "YOUR_STATE_BUCKET_NAME" # Use the SAME bucket as the Hub
    prefix = "terraform/client/state" # But save it in a DIFFERENT folder!
  }
}

provider "google" {
  project = var.client_project_id
  region  = var.region
}

# ------------------------------------------------------------------------------
# ENABLE GCP APIs
# ------------------------------------------------------------------------------
locals {
  services =[
    "compute.googleapis.com",    # Needed for GKE VMs
    "container.googleapis.com",  # Kubernetes Engine
    "logging.googleapis.com",    # Cloud Logging
    "monitoring.googleapis.com"  # Cloud Monitoring
  ]
}

resource "google_project_service" "enabled_apis" {
  for_each           = toset(local.services)
  project            = var.client_project_id
  service            = each.key
  disable_on_destroy = false
}
