# ------------------------------------------------------------------------------
# CLIENT PROJECT VARIABLES
# ------------------------------------------------------------------------------
variable "client_project_id" {
  description = "The GCP Project ID for the mock Client environment"
  type        = string
  default     = "YOUR_CLIENT_PROJECT_ID" # Replace with real ID
}

variable "region" {
  description = "The GCP region (Must match the Hub for free network traffic)"
  type        = string
  default     = "us-central1"
}

# ------------------------------------------------------------------------------
# HUB CONNECTION VARIABLES (Copy these from the Hub's outputs!)
# ------------------------------------------------------------------------------
variable "hub_project_id" {
  description = "The GCP Project ID of the Hub"
  type        = string
  default     = "YOUR_HUB_PROJECT_ID"
}

variable "hub_pubsub_topic_name" {
  description = "The name of the Hub's incoming logs topic"
  type        = string
  default     = "aegis-incoming-logs"
}

variable "hub_bot_service_account_email" {
  description = "The email of the Hub's bot service account"
  type        = string
  default     = "aegis-bot-sa@YOUR_HUB_PROJECT_ID.iam.gserviceaccount.com"
}
