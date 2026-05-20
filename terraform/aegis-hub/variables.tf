# ------------------------------------------------------------------------------
# HUB PROJECT VARIABLES
# ------------------------------------------------------------------------------

variable "hub_project_id" {
  description = "The GCP Project ID for the Aegis Hub SRE Bot"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.hub_project_id))
    error_message = "hub_project_id must be a real GCP project ID: 6-30 chars, lowercase letters/numbers/hyphens, start with a letter, and not end with a hyphen."
  }
}

variable "region" {
  description = "The GCP region to deploy all resources"
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

variable "allowed_client_project_ids" {
  description = "Client project IDs that the Query Processor may query"
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for project_id in var.allowed_client_project_ids : can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", project_id))])
    error_message = "Every allowed client project ID must be a valid GCP project ID."
  }
}

variable "slack_alert_channel_id" {
  description = "Slack channel ID where incident alerts should be posted. Leave empty until the Slack app is configured."
  type        = string
  default     = ""
}

variable "terraform_service_account_user_members" {
  description = "Optional IAM members allowed to attach the Cloud Run and Pub/Sub service accounts, e.g. user:you@example.com or serviceAccount:terraform@project.iam.gserviceaccount.com"
  type        = set(string)
  default     = []
}

variable "billing_account_name" {
  description = "Optional billing account resource name for a monthly budget, e.g. billingAccounts/000000-000000-000000. Leave null to skip budget creation."
  type        = string
  default     = null
}

variable "monthly_budget_units" {
  description = "Whole currency units for the optional monthly budget."
  type        = number
  default     = 25
}

variable "budget_currency_code" {
  description = "Currency code for the optional billing budget."
  type        = string
  default     = "USD"
}

variable "budget_alert_thresholds" {
  description = "Budget alert threshold percentages expressed as 1.0-based values."
  type        = list(number)
  default     = [0.5, 0.9, 1.0]
}

# ------------------------------------------------------------------------------
# DUMMY CONTAINER IMAGES (For Initial Setup)
# ------------------------------------------------------------------------------
# We use a public Google "hello world" image so Terraform can build the Cloud Run 
# services immediately. Later, your CI/CD will replace these with your real code.

variable "slack_gateway_image" {
  description = "Docker image for the Slack Gateway service"
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "incident_analyzer_image" {
  description = "Docker image for the Incident Analyzer service"
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "metrics_service_image" {
  description = "Deprecated compatibility image for the former Metrics service. Use query_processor_image instead."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "query_processor_image" {
  description = "Docker image for the Query Processor service"
  type        = string
  default     = null
}

locals {
  query_processor_image = coalesce(var.query_processor_image, var.metrics_service_image)
}
