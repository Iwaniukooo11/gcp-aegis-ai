# ------------------------------------------------------------------------------
# HUB PROJECT VARIABLES
# ------------------------------------------------------------------------------

variable "hub_project_id" {
  description = "The GCP Project ID for the Aegis Hub SRE Bot"
  type        = string
  # REPLACE THIS when you run Terraform, or pass it via a terraform.tfvars file
  default     = "YOUR_HUB_PROJECT_ID" 
}

variable "region" {
  description = "The GCP region to deploy all resources"
  type        = string
  default     = "us-central1" # Best region for Vertex AI (Gemini) availability
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
  description = "Docker image for the Metrics service"
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}
