# Live Demo Operations

This is the runbook for turning Aegis AI on, proving it works, running a live incident demo, and turning it off before it burns credits.

## Projects

- Hub project: `aegis-hub-2137`
- Client project: `aegis-client-420`
- Region: `europe-central2`
- Client cluster: `mock-gke-standard`
- Client namespace: `aegis-demo`

## Before Demo Day

Run this at least one day before the professor demo.

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project aegis-hub-2137
gcloud auth configure-docker europe-central2-docker.pkg.dev --quiet
```

Confirm required CLIs exist:

```bash
gcloud --version
terraform version
kubectl version --client=true
docker version
```

## Turn On Hub

Build and deploy all Hub Cloud Run services:

```bash
PROJECT=aegis-hub-2137 REGION=europe-central2 bash aegis-hub-code/deploy.sh
```

If Slack secrets are missing or rotated, add new versions:

```bash
printf '%s' '<xoxb-slack-bot-token>' | gcloud secrets versions add slack-bot-token \
  --data-file=- \
  --project=aegis-hub-2137

printf '%s' '<slack-signing-secret>' | gcloud secrets versions add slack-signing-secret \
  --data-file=- \
  --project=aegis-hub-2137
```

Get Hub URLs:

```bash
cd terraform/aegis-hub
terraform output -raw slack_gateway_url
terraform output -raw query_processor_url
terraform output -raw incoming_logs_topic_name
cd ../..
```

Update Slack app settings if the Slack Gateway URL changed:

- Events API request URL: `<slack_gateway_url>/slack/events`
- Slash command request URL: `<slack_gateway_url>/slack/commands`

## Turn On Client Infrastructure

Create or refresh the client GKE cluster, Artifact Registry, Monitoring IAM, and log sink:

```bash
cd terraform/client-agent
terraform init
terraform apply
cd ../..
```

Connect `kubectl`:

```bash
gcloud container clusters get-credentials mock-gke-standard \
  --region europe-central2 \
  --project aegis-client-420
```

## Deploy Client Workloads

Build, push, and deploy both mock services:

```bash
CLIENT_PROJECT_ID=aegis-client-420 \
REGION=europe-central2 \
CLUSTER_NAME=mock-gke-standard \
REPOSITORY_ID=aegis-client-services \
./client-backend/scripts/deploy-gke.sh
```

Run smoke checks:

```bash
./client-backend/scripts/smoke-gke.sh
```

Expected result:

- `java-api` rollout succeeds
- `python-api` rollout succeeds
- `/healthz/ready`, `/api/info`, and `/api/checkout` return HTTP 200

## Pre-Demo Health Check

Run this 10 minutes before the demo.

```bash
gcloud run services list --project=aegis-hub-2137 --region=europe-central2
kubectl -n aegis-demo get pods,svc
kubectl -n aegis-demo wait --for=condition=available deployment/java-api --timeout=120s
kubectl -n aegis-demo wait --for=condition=available deployment/python-api --timeout=120s
```

Check Pub/Sub dead letter queue is empty or understood:

```bash
gcloud pubsub subscriptions pull aegis-dead-letter-pull \
  --project=aegis-hub-2137 \
  --limit=5 \
  --auto-ack
```

Check recent successful incidents:

```bash
bq query --project_id=aegis-hub-2137 --use_legacy_sql=false '
SELECT incident_id, service_name, error_type, severity, created_at
FROM `aegis-hub-2137.aegis_incidents.incidents`
WHERE terminal_status = "SUCCESS"
ORDER BY created_at DESC
LIMIT 5'
```

Check Slack:

```text
/aegis-latest-incidents 5
```

## Live Demo Flow

Open port-forward to the Python API:

```bash
kubectl -n aegis-demo port-forward svc/python-api 8000:8000
```

In another terminal, trigger a clean Python incident:

```bash
curl -i -H "X-Correlation-ID: demo-python-$(date +%s)" \
  "http://localhost:8000/chaos/exception?type=value_error"
```

Expected result:

- Python API returns HTTP 500
- GKE writes one structured `ERROR` log with `incident_candidate=true`
- Client Log Router sends it to Hub Pub/Sub
- Incident Analyzer creates one incident
- Slack Gateway posts an alert
- BigQuery stores one row with `terminal_status = SUCCESS`

Get the latest incident:

```bash
bq query --project_id=aegis-hub-2137 --use_legacy_sql=false '
SELECT incident_id, idempotency_key, service_name, error_type, severity, slack_message_ts, created_at
FROM `aegis-hub-2137.aegis_incidents.incidents`
ORDER BY created_at DESC
LIMIT 1'
```

Verify Firestore session context for the returned incident ID:

```bash
INCIDENT_ID="INC-YYYY-NNNNNN"
ACCESS_TOKEN="$(gcloud auth print-access-token)"
curl -sS -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  "https://firestore.googleapis.com/v1/projects/aegis-hub-2137/databases/(default)/documents/sessions/${INCIDENT_ID}"
```

The session must include `client_project_id`, `service_name`, `cluster_name`, `namespace`, `pod_name`, `error_type`, `messages`, and `log_timestamp`.

Verify Cloud Monitoring has real client metrics around the incident:

```bash
START_TIME="$(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%SZ)"
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ACCESS_TOKEN="$(gcloud auth print-access-token)"
curl -sS -G -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  --data-urlencode 'filter=metric.type="kubernetes.io/container/memory/used_bytes" AND resource.type="k8s_container" AND resource.labels.cluster_name="mock-gke-standard" AND resource.labels.namespace_name="aegis-demo" AND resource.labels.container_name="python-api"' \
  --data-urlencode "interval.startTime=${START_TIME}" \
  --data-urlencode "interval.endTime=${END_TIME}" \
  'https://monitoring.googleapis.com/v3/projects/aegis-client-420/timeSeries'
```

Expected result: non-empty `timeSeries[]` with points for `python-api`.

In Slack:

```text
/aegis-latest-incidents 5
@<aegis-bot-name> INC-YYYY-NNNNNN what happened and what should I check first?
```

Optional downstream dependency demo:

```bash
kubectl -n aegis-demo port-forward svc/java-api 8080:8080
curl -i -X POST "http://localhost:8080/chaos/pricing-5xx?seconds=60"
curl -i -H "X-Correlation-ID: demo-downstream-001" "http://localhost:8000/api/checkout"
```

## Debug Commands

Incident Analyzer logs:

```bash
gcloud run services logs read incident-analyzer \
  --project=aegis-hub-2137 \
  --region=europe-central2 \
  --limit=100
```

Slack Gateway logs:

```bash
gcloud run services logs read slack-gateway \
  --project=aegis-hub-2137 \
  --region=europe-central2 \
  --limit=100
```

Client workload logs:

```bash
kubectl -n aegis-demo logs deployment/python-api --tail=100
kubectl -n aegis-demo logs deployment/java-api --tail=100
```

## Turn Off After Working

Cheap off mode: delete only client workloads.

```bash
kubectl delete namespace aegis-demo
```

This stops mock pods but leaves the GKE cluster running. Use this only for short breaks.

Real credit-saving mode: destroy the client infrastructure.

```bash
cd terraform/client-agent
terraform destroy
cd ../..
```

This removes the GKE cluster, node pool, client Artifact Registry repository, and log sink.

Hub services are serverless and scale to zero, so idle cost is low. Leave Hub on while preparing the project unless you need hard off mode.

Hard off mode: destroy Hub after the course/demo is finished.

```bash
cd terraform/aegis-hub
terraform destroy
cd ../..
```

Do not run Hub destroy right before the demo. Recreating Slack secrets and app URLs costs time and creates avoidable risk.

## Minimal Daily Routine

Start:

```bash
cd terraform/client-agent && terraform apply && cd ../..
./client-backend/scripts/deploy-gke.sh
./client-backend/scripts/smoke-gke.sh
```

Stop:

```bash
cd terraform/client-agent && terraform destroy && cd ../..
```
