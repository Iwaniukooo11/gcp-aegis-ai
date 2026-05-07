# ------------------------------------------------------------------------------
# ARTIFACT REGISTRY (The Docker Image Storage)
# ------------------------------------------------------------------------------
resource "google_artifact_registry_repository" "services" {
  project       = var.hub_project_id
  location      = var.region
  repository_id = "aegis-services"
  format        = "DOCKER"
  description   = "Docker repository for Aegis AI microservices"

  depends_on = [google_project_service.enabled_apis]
}
