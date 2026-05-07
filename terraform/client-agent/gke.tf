# ------------------------------------------------------------------------------
# GKE AUTOPILOT CLUSTER
# ------------------------------------------------------------------------------
resource "google_container_cluster" "mock_gke" {
  name     = "mock-gke-autopilot"
  location = var.region

  # Autopilot automatically manages the underlying VMs (nodes)
  enable_autopilot = true

  # Set to false so we can easily destroy the project after the course is over
  deletion_protection = false

  depends_on = [google_project_service.enabled_apis]
}
