# Client Workload Deployment

This document describes how to run the mock client workloads on the `aegis-client-420` GKE cluster.

## What Gets Deployed

Namespace:

- `aegis-demo`

Workloads:

- `java-api` on port `8080`
- `python-api` on port `8000`

Services are `ClusterIP`. No external load balancer is created. Use `kubectl port-forward` for demos and tests.

## Prerequisites

Required local tools:

- `gcloud`
- `docker`
- `kubectl`

Required cloud resources:

- client project: `aegis-client-420`
- cluster: `mock-gke-standard`
- region: `europe-central2`
- Artifact Registry repository: `aegis-client-services`

Recommended GKE setup for the course demo:

- one regional GKE Standard node pool pinned to zone `europe-central2-a`
- one `e2-medium` spot node
- `20GB` `pd-standard` node disk
- workload requests kept intentionally low: `25m` CPU per service
- memory limits set so Cloud Monitoring can report meaningful memory pressure
- `strategy: Recreate` on both deployments, because a one-node demo cluster does not have spare capacity for rolling double-pod updates

`e2-small` is too tight after GKE system pods reserve CPU and memory. It caused rollout pressure in live tests. `e2-medium` is the smallest setup that ran both demo services reliably without making the client project expensive. Larger machines are unnecessary for this project.

Create or update the client infrastructure first:

```bash
cd terraform/client-agent
terraform init
terraform apply
```

## Build, Push, And Deploy

From the repository root:

```bash
CLIENT_PROJECT_ID=aegis-client-420 \
REGION=europe-central2 \
CLUSTER_NAME=mock-gke-standard \
REPOSITORY_ID=aegis-client-services \
./client-backend/scripts/deploy-gke.sh
```

Optional image tag override:

```bash
IMAGE_TAG=demo-1 ./client-backend/scripts/deploy-gke.sh
```

The script:

1. configures Docker auth for Artifact Registry
2. fetches GKE credentials
3. builds both images for `linux/amd64`
4. pushes both images
5. applies `client-backend/k8s`
6. updates deployments to the pushed image tag
7. waits for both rollouts

## Smoke Test

From the repository root:

```bash
./client-backend/scripts/smoke-gke.sh
```

This waits for both rollouts, port-forwards `python-api` to `localhost:8000`, and checks:

- `/healthz/ready`
- `/api/info`
- `/api/checkout`

Manual port-forward:

```bash
kubectl -n aegis-demo port-forward svc/python-api 8000:8000
```

Trigger the primary checkout/pricing incident path:

```bash
kubectl -n aegis-demo port-forward svc/java-api 8080:8080
curl -i -X POST "http://localhost:8080/admin/failures/pricing-latency?seconds=15"
curl -i -H "X-Correlation-ID: demo-checkout-timeout-001" "http://localhost:8000/api/checkout"
```

Expected result:

- `python-api` returns HTTP 504 from `/api/checkout`
- the structured error log names `java-api` as `upstream_service`
- the message describes pricing latency, not chaos internals
- Aegis creates the Slack, Firestore, and BigQuery incident from the checkout log

Trigger the optional pricing-unavailable path:

```bash
curl -i -X POST "http://localhost:8080/admin/failures/pricing-unavailable?seconds=60"
curl -i -H "X-Correlation-ID: demo-downstream-001" "http://localhost:8000/api/checkout"
```

This can create both a `java-api` HTTP 503 incident and a `python-api` checkout
HTTP 502 incident. Use the latency path when you want one clean customer-facing
incident during the live demo.

## Stop Workloads

Stop only the mock workloads:

```bash
kubectl delete namespace aegis-demo
```

This does not delete the GKE cluster.

Stop cloud spend more aggressively:

```bash
cd terraform/client-agent
terraform destroy
```

That removes the client cluster and client Artifact Registry repository.

## Logging Contract

The client Log Router sink only exports logs from:

- namespace `aegis-demo`
- cluster `mock-gke-standard`
- `jsonPayload.incident_candidate=true`
- `jsonPayload.service_name` equal to `java-api` or `python-api`
- severity `ERROR` or higher

The analyzer also applies the same candidate check before it creates receipts, calls Gemini, posts Slack, or writes BigQuery.

Auto chaos is disabled in Kubernetes and local Compose by default. Demo incidents should be triggered manually with a known `X-Correlation-ID`; otherwise the log sink can create surprise incidents during the professor demo.
