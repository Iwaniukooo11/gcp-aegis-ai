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

# ------------------------------------------------------------------------------
# OUTPUTS (Information for you / Slack Setup)
# ------------------------------------------------------------------------------
output "slack_gateway_url" {
  description = "Put this URL into the Slack API Dashboard for Slash Commands"
  value       = google_cloud_run_v2_service.slack_gateway.uri
}
