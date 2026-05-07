# ------------------------------------------------------------------------------
# OUTPUTS (Information to copy-paste into the Client Project)
# ------------------------------------------------------------------------------

output "hub_project_id" {
  description = "The ID of the Hub project"
  value       = var.hub_project_id
}

output "bot_service_account_email" {
  description = "The email of the SRE Bot (Give this access to the Client Project)"
  value       = google_service_account.aegis_bot.email
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

output "metrics_service_url" {
  description = "Private Metrics Service URL used by the Slack Gateway"
  value       = google_cloud_run_v2_service.metrics_service.uri
}
