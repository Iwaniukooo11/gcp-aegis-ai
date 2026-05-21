#!/usr/bin/env bash
# Build all three Hub services, push to Artifact Registry, then apply Terraform.
# Run from repo root: bash aegis-hub-code/deploy.sh
set -euo pipefail

REGION="${REGION:-europe-central2}"
PROJECT="${PROJECT:-aegis-hub-2137}"
REPO="$REGION-docker.pkg.dev/$PROJECT/aegis-services"

build_and_push() {
  local name="$1"
  local context="$2"
  echo ">>> Building and pushing ${name} (linux/amd64, no attestations — Cloud Run requirement)"
  docker buildx build \
    --platform linux/amd64 \
    --provenance=false \
    --sbom=false \
    -t "${REPO}/${name}:latest" \
    --push \
    "${context}"
}

echo ">>> Authenticating Docker with Artifact Registry"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

build_and_push "incident-analyzer" "aegis-hub-code/incident-analyzer"
build_and_push "query-processor" "aegis-hub-code/query-processor"
build_and_push "slack-gateway" "aegis-hub-code/slack-gateway"

echo ">>> Applying Terraform"
cd terraform/aegis-hub
terraform init -upgrade
terraform apply \
  -var="hub_project_id=$PROJECT" \
  -var="incident_analyzer_image=$REPO/incident-analyzer:latest" \
  -var="query_processor_image=$REPO/query-processor:latest" \
  -var="slack_gateway_image=$REPO/slack-gateway:latest" \
  -auto-approve

echo ""
echo "=== Deployment complete ==="
echo "Slack Gateway URL: $(terraform output -raw slack_gateway_url)"
echo "Query Processor URL: $(terraform output -raw query_processor_url)"
echo ""
echo "Next steps:"
echo "  1. Set Slack Events API URL: <slack_gateway_url>/slack/events"
echo "  2. Set slash command URL:    <slack_gateway_url>/slack/commands"
echo "  3. Push Slack bot token to Secret Manager:"
echo "     gcloud secrets versions add slack-bot-token --data-file=- <<< 'xoxb-your-token'"
