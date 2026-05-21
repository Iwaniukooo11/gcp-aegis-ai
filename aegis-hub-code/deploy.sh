#!/usr/bin/env bash
# Build all three Hub services, push to Artifact Registry, then apply Terraform.
# Run from repo root: bash aegis-hub-code/deploy.sh
set -euo pipefail

REGION="${REGION:-europe-central2}"
PROJECT="${PROJECT:-aegis-hub-2137}"
REPO="$REGION-docker.pkg.dev/$PROJECT/aegis-services"

echo ">>> Authenticating Docker with Artifact Registry"
gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet

echo ">>> Building and pushing incident-analyzer"
docker build -t "$REPO/incident-analyzer:latest" aegis-hub-code/incident-analyzer
docker push "$REPO/incident-analyzer:latest"

echo ">>> Building and pushing query-processor"
docker build -t "$REPO/query-processor:latest" aegis-hub-code/query-processor
docker push "$REPO/query-processor:latest"

echo ">>> Building and pushing slack-gateway"
docker build -t "$REPO/slack-gateway:latest" aegis-hub-code/slack-gateway
docker push "$REPO/slack-gateway:latest"

echo ">>> Applying Terraform"
cd terraform/aegis-hub
terraform init -upgrade
terraform apply \
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
