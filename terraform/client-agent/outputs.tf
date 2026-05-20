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

output "log_sink_writer_identity" {
  description = "Unique service account that publishes filtered client logs to the Hub Pub/Sub topic"
  value       = google_logging_project_sink.error_to_hub.writer_identity
}

output "client_artifact_registry_repository_id" {
  description = "Artifact Registry repository for client simulation images"
  value       = google_artifact_registry_repository.client_services.repository_id
}

output "client_image_base_url" {
  description = "Base Docker image URL for client simulation images"
  value       = "${var.region}-docker.pkg.dev/${var.client_project_id}/${google_artifact_registry_repository.client_services.repository_id}"
}
