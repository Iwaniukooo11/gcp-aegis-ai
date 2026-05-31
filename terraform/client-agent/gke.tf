# ------------------------------------------------------------------------------
# STANDARD GKE CLUSTER
# ------------------------------------------------------------------------------
resource "google_container_cluster" "mock_gke" {
  name     = "mock-gke-standard"
  location = var.region

  remove_default_node_pool = true
  initial_node_count       = 1
  node_locations           = ["${var.region}-a"]

  logging_config {
    enable_components = [
      "SYSTEM_COMPONENTS",
      "WORKLOADS"
    ]
  }

  monitoring_config {
    enable_components = [
      "SYSTEM_COMPONENTS",
      "STORAGE",
      "HPA",
      "POD",
      "DAEMONSET",
      "DEPLOYMENT",
      "STATEFULSET",
      "CADVISOR",
      "KUBELET",
      "DCGM",
      "JOBSET"
    ]

    managed_prometheus {
      enabled = true
    }
  }

  # Set to false so we can easily destroy the project after the course is over
  deletion_protection = false

  depends_on = [google_project_service.enabled_apis]
}

resource "google_container_node_pool" "mock_gke_primary" {
  name     = "mock-gke-primary-pool"
  project  = var.client_project_id
  location = var.region
  cluster  = google_container_cluster.mock_gke.name

  node_count = 1

  node_config {
    machine_type = "e2-medium"
    disk_size_gb = 20
    disk_type    = "pd-standard"
    spot         = true

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    labels = {
      app         = "aegis-ai"
      component   = "client-agent"
      environment = var.environment
    }
  }
}
