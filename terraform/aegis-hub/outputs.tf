# ------------------------------------------------------------------------------
# OUTPUTS (Information to copy-paste into the Client Project)
# ------------------------------------------------------------------------------

output "hub_project_id" {
  description = "The ID of the Hub project"
  value       = var.hub_project_id
}

output "slack_gateway_service_account_email" {
  description = "The email of the Slack Gateway service account"
  value       = google_service_account.slack_gateway.email
}

output "incident_analyzer_service_account_email" {
  description = "The email of the Incident Analyzer service account"
  value       = google_service_account.incident_analyzer.email
}

output "query_processor_service_account_email" {
  description = "The email of the Query Processor service account for client Monitoring IAM"
  value       = google_service_account.query_processor.email
}

output "incoming_logs_topic_id" {
  description = "The Pub/Sub Topic ID (The Client Log Sink will send logs here)"
  value       = google_pubsub_topic.incoming_logs.id
}

output "incoming_logs_topic_name" {
  description = "The short Pub/Sub topic name for client Terraform"
  value       = google_pubsub_topic.incoming_logs.name
}

output "dead_letter_subscription_name" {
  description = "Pull subscription for inspecting dead-lettered incident messages"
  value       = google_pubsub_subscription.dead_letter_pull.name
}

# ------------------------------------------------------------------------------
# OUTPUTS (Information for you / Slack Setup)
# ------------------------------------------------------------------------------
output "slack_gateway_url" {
  description = "Put this URL into the Slack API Dashboard for Slash Commands"
  value       = google_cloud_run_v2_service.slack_gateway.uri
}

output "query_processor_url" {
  description = "Private Query Processor URL used by the Slack Gateway"
  value       = google_cloud_run_v2_service.query_processor.uri
}

output "metrics_service_url" {
  description = "Deprecated alias for query_processor_url"
  value       = google_cloud_run_v2_service.query_processor.uri
}
