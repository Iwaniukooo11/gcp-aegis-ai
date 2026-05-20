# ------------------------------------------------------------------------------
# CLIENT ARTIFACT REGISTRY
# ------------------------------------------------------------------------------
resource "google_artifact_registry_repository" "client_services" {
  project       = var.client_project_id
  location      = var.region
  repository_id = var.client_artifact_registry_repository_id
  format        = "DOCKER"
  description   = "Docker repository for Aegis client simulation workloads"

  depends_on = [google_project_service.enabled_apis]
}

resource "google_artifact_registry_repository_iam_member" "gke_can_pull_client_images" {
  project    = var.client_project_id
  location   = google_artifact_registry_repository.client_services.location
  repository = google_artifact_registry_repository.client_services.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${data.google_project.client.number}-compute@developer.gserviceaccount.com"
}
