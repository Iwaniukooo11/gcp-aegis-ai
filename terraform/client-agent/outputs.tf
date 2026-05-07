# ------------------------------------------------------------------------------
# OUTPUTS
# ------------------------------------------------------------------------------
output "gke_cluster_name" {
  description = "The name of the mock GKE cluster"
  value       = google_container_cluster.mock_gke.name
}

output "kubectl_connection_command" {
  description = "Run this in your terminal to connect to the cluster:"
  value       = "gcloud container clusters get-credentials ${google_container_cluster.mock_gke.name} --region ${var.region} --project ${var.client_project_id}"
}
