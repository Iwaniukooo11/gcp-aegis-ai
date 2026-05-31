# gcp-aegis-ai

Terraform for the Aegis AI cross-project SRE bot prototype.

## Terraform Stacks

- `terraform/aegis-hub`: central Hub project resources: Cloud Run services, Pub/Sub, Firestore, BigQuery, Secret Manager, Artifact Registry, and optional billing budget.
- `terraform/client-agent`: mock monitored Client project resources: standard GKE, client Artifact Registry, Cloud Logging sink, Cloud Monitoring, and cross-project IAM.

## Prerequisites

Create or select the GCP projects first, enable billing, and enable Service Usage manually in each project:

```bash
gcloud auth application-default login

gcloud services enable serviceusage.googleapis.com --project=aegis-hub-2137
gcloud services enable serviceusage.googleapis.com --project=<client-project-id>
```

The Terraform state bucket must already exist:

```bash
gsutil mb -p aegis-hub-2137 -l europe-central2 gs://igor-aegis-tf-state-123
gsutil versioning set on gs://igor-aegis-tf-state-123
```

## Hub Deploy

Create `terraform/aegis-hub/terraform.tfvars` from the example. Keep real `.tfvars` files out of git.

```hcl
hub_project_id             = "aegis-hub-2137"
region                     = "europe-central2"
environment                = "dev"
allowed_client_project_ids = ["<client-project-id>"]
slack_alert_channel_id     = ""
```

Then deploy:

```bash
cd terraform/aegis-hub
terraform init
terraform plan
terraform apply
```

After the hub apply, add Slack secret versions manually so secret values do not enter Terraform state:

```bash
printf '%s' '<xoxb-slack-bot-token>' | gcloud secrets versions add slack-bot-token \
  --data-file=- \
  --project=aegis-hub-2137

printf '%s' '<slack-signing-secret>' | gcloud secrets versions add slack-signing-secret \
  --data-file=- \
  --project=aegis-hub-2137
```

If you have Billing Budget permissions, set `billing_account_name` in the hub tfvars to enable the optional monthly budget.

## Client Deploy

Create `terraform/client-agent/terraform.tfvars` from the example using hub outputs:

```hcl
client_project_id                         = "<client-project-id>"
hub_project_id                            = "aegis-hub-2137"
hub_pubsub_topic_name                     = "aegis-incoming-logs"
hub_query_processor_service_account_email = "aegis-query-processor-sa@aegis-hub-2137.iam.gserviceaccount.com"
region                                    = "europe-central2"
environment                               = "dev"
client_artifact_registry_repository_id    = "aegis-client-services"
```

Then deploy:

```bash
cd terraform/client-agent
terraform init
terraform plan
terraform apply
```

The client stack creates the standard GKE cluster, client Artifact Registry repository, Cloud Monitoring access for the Hub Query Processor, and the log sink that routes `k8s_container` logs with `severity >= ERROR` into the Hub Pub/Sub topic.

## Client Workload Deploy

Build, push, and deploy the mock client workloads:

```bash
./client-backend/scripts/deploy-gke.sh
```

Run smoke checks:

```bash
./client-backend/scripts/smoke-gke.sh
```

Full runbook:

- [Client Workload Deployment](docs/client-workload-deployment.md)
- [Live Demo Operations](docs/live-demo-operations.md)
- [Project Status And PR Consolidation](docs/project-status-2026-05-31.md)
