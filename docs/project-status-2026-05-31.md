# Project Status And PR Consolidation - 2026-05-31

## Current Standing

The project is deployed and the main demo path has been verified live:

- client GKE workloads run in namespace `aegis-demo`
- client log sink exports only structured incident candidates
- Incident Analyzer creates Firestore session state, posts through Slack Gateway, and writes BigQuery
- Query Processor can use Firestore incident context and Cloud Monitoring metrics for follow-up Slack questions
- Slack Gateway stays thin: Slack ingress, Slack egress, Query Processor relay, internal alert relay

## Old Pull Requests

### PR #13 - `add aegis-demo yaml`

Decision: reject as obsolete.

Reason: it adds one monolithic `client-backend/aegis-demo.yaml`. Main now has modular manifests in `client-backend/k8s/`, rollout-safe `Recreate` strategy, resource requests/limits, a ConfigMap, deployment scripts, and smoke checks. The old YAML also enabled auto-chaos, which is bad for a deterministic live demo.

### PR #14 - `change k8s machine`

Decision: reject as already integrated.

Reason: its only useful change is `e2-small` to `e2-medium`. Main already uses `e2-medium`, and live rollout testing confirmed that `e2-small` is too tight after GKE system pod reservations.

### PR #15 - `fix`

Decision: do not merge directly; extract valid changes.

Useful parts extracted:

- local/default auto-chaos disabled
- better error log messages for Java and Python services
- Firestore sessions now include `log_timestamp`
- Firestore sessions now include `pod_name` so Monitoring queries target the exact incident pod
- Query Processor uses incident log time for Monitoring lookback
- Query Processor metric catalog now includes CPU limit utilization, CPU request utilization, CPU core usage, memory used, memory limit utilization, and restarts
- Slack Gateway has better Query Processor error mapping and short retry when the incident session is not ready yet
- `/aegis-latest-incidents` formatting avoids useless `Request completed` summaries

Reason direct merge was rejected: PR #15 conflicts with main and would regress the final architecture by removing Slack signature dependencies, weakening the narrowed log processing path, replacing modular Kubernetes manifests with older YAML, and adding Firestore access to Slack Gateway, which violates the agreed thin-gateway architecture.

## Kubernetes Setup Decision

Use one GKE Standard node pool:

- machine: `e2-medium`
- nodes: `1`
- disk: `20GB pd-standard`
- spot: `true`
- zone: `europe-central2-a`

Workload resources:

- `java-api`: `25m` CPU request, `384Mi` memory request, `500m` CPU limit, `768Mi` memory limit
- `python-api`: `25m` CPU request, `256Mi` memory request, `500m` CPU limit, `512Mi` memory limit

This is the smallest live-tested setup that runs both mock services reliably and still gives Cloud Monitoring useful CPU/memory signals.

## Final Live Verification - 2026-05-31 16:25 UTC

Main is now verified with the realistic checkout/pricing dependency demo, not
the older direct `ValueError` fallback.

Merged pull requests in this verification pass:

- #33 `Model realistic checkout dependency demo`
- #34 `Format metric facts with safe units`
- #35 `Aggregate memory metric series`

Deployed revisions:

- Incident Analyzer: `aegis-incident-analyzer-00008-dzw`
- Query Processor: `aegis-query-processor-00009-2vs`
- Slack Gateway: `aegis-slack-gateway-00008-kc5`
- client images: tag `948b203`

Local verification:

- `uv run pytest` in `client-backend/apps/python-api` -> `21 passed`
- `./gradlew test` in `client-backend/apps/java-api` -> build successful
- `uv run python -m unittest discover -s tests` in `aegis-hub-code/incident-analyzer` -> `1 passed`
- `uv run python -m unittest discover -s tests` in `aegis-hub-code/query-processor` -> `2 passed`
- `uv run python -m compileall app` in Incident Analyzer and Query Processor -> success
- `terraform/aegis-hub plan` -> no changes after reconciliation
- `./client-backend/scripts/smoke-gke.sh` -> readiness, info, and normal checkout OK
- Pub/Sub dead-letter subscription `aegis-dead-letter-pull` -> empty

Fresh incident verified:

- trigger: `POST /admin/failures/pricing-latency?seconds=15` on `java-api`
- customer request: `GET /api/checkout` on `python-api`
- client correlation id: `demo-checkout-latency-1780244741`
- client log timestamp: `2026-05-31T16:25:43.629220961Z`
- client pod: `python-api-566d4c54c5-pfjmh`
- service: `python-api`
- error type: `DownstreamTimeoutError`
- scenario: `PYTHON_DOWNSTREAM_TIMEOUT`
- path: `/api/checkout`
- upstream service: `java-api`
- HTTP status: `504`
- log message: `Checkout failed because java-api pricing request exceeded configured timeout`
- BigQuery incident: `INC-2026-567060`
- terminal status: `SUCCESS`
- Slack channel: `C0B4Z47V5RB`
- Slack message timestamp: `1780244759.470559`

BigQuery row for `INC-2026-567060` contains:

- `service_name=python-api`
- `error_type=DownstreamTimeoutError`
- `severity=ERROR`
- `short_message=Checkout failed because java-api pricing request exceeded configured timeout`
- `ai_summary=Customer checkout failed because the java-api pricing dependency did not respond before the configured timeout.`
- `terminal_status=SUCCESS`
- Slack channel and message timestamp

Firestore session for `INC-2026-567060` contains:

- `client_project_id=aegis-client-420`
- `cluster_name=mock-gke-standard`
- `namespace=aegis-demo`
- `pod_name=python-api-566d4c54c5-pfjmh`
- `service_name=python-api`
- `scenario=PYTHON_DOWNSTREAM_TIMEOUT`
- `path=/api/checkout`
- `upstream_service=java-api`
- `status_code=504`
- `log_timestamp=2026-05-31T16:25:43.629220961Z`
- `messages` with the initial incident context, user questions, and model replies

Slack readback now works with the installed Slack history scopes:

- `conversations.replies` returned the alert thread successfully
- alert text: checkout failed due to `java-api` pricing timeout
- slash command simulation returned recent incidents and includes `INC-2026-567060`
- no INFO/startup logs appear in the latest incidents result
- older direct `/chaos/exception` fallback incidents still appear because they are real historical ERROR incidents

Final Slack follow-up reply for `INC-2026-567060`:

```text
CPU near incident time: 8.92% of container CPU limit
Memory near incident time: 54.6 MiB

Root Cause Candidates:
- The java-api service was unresponsive or experiencing high latency, causing python-api's pricing request to exceed its configured timeout.
- Network latency or connectivity issues between python-api and java-api led to the timeout.
```

This proves the bot keeps incident context by `incident_id`, uses the Firestore
conversation state, queries real Cloud Monitoring data, and does not invent CPU
or memory values.

Demo reliability note:

- Kubernetes auto chaos remains disabled by default.
- Use `/admin/failures/pricing-latency?seconds=15` as the primary demo trigger.
- Keep `/chaos/exception` only as a fallback smoke test; it is expected and
  correct for the bot to identify that fallback as intentional chaos.
- Leave Hub Cloud Run services on for preparation; they scale to zero.
- Destroy the client Terraform stack when done working if GCP credits matter.
