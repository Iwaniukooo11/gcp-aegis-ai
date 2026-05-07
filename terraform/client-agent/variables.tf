# ------------------------------------------------------------------------------
# CLIENT PROJECT VARIABLES
# ------------------------------------------------------------------------------
variable "client_project_id" {
  description = "The GCP Project ID for the mock Client environment"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.client_project_id))
    error_message = "client_project_id must be a real GCP project ID: 6-30 chars, lowercase letters/numbers/hyphens, start with a letter, and not end with a hyphen."
  }
}

variable "region" {
  description = "The GCP region (Must match the Hub for free network traffic)"
  type        = string
  default     = "europe-central2"
}

variable "environment" {
  description = "Short environment label applied to managed resources"
  type        = string
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,61}[a-z0-9]$", var.environment))
    error_message = "environment must be a valid GCP label value: lowercase letters, numbers, and hyphens."
  }
}

# ------------------------------------------------------------------------------
# HUB CONNECTION VARIABLES (Copy these from the Hub's outputs!)
# ------------------------------------------------------------------------------
variable "hub_project_id" {
  description = "The GCP Project ID of the Hub"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.hub_project_id))
    error_message = "hub_project_id must be a real GCP project ID."
  }
}

variable "hub_pubsub_topic_name" {
  description = "The name of the Hub's incoming logs topic"
  type        = string
  default     = "aegis-incoming-logs"
}

variable "hub_bot_service_account_email" {
  description = "The email of the Hub's bot service account"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]+@[a-z][a-z0-9-]{4,28}[a-z0-9]\\.iam\\.gserviceaccount\\.com$", var.hub_bot_service_account_email))
    error_message = "hub_bot_service_account_email must be a valid service account email."
  }
}
