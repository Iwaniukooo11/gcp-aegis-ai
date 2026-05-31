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

## Remaining Demo Caution

The system is no longer obviously incomplete. Before the professor demo, still run
one short Slack UI check from the real workspace:

1. trigger a fresh incident
2. confirm Slack alert appears
3. run `/aegis-latest-incidents 5`
4. ask `@Aegis INC-... what were cpu and memory during the incident?`
5. confirm the reply includes real Cloud Monitoring facts

This final Slack UI check matters because the backend can be verified from code
and Google Cloud, but exact visible Slack rendering is controlled by Slack app
configuration.

## Final Live Verification - 2026-05-31 13:30 UTC

Pull request #30 fixed a real Slack Events SLO issue. Before the fix,
`POST /slack/events` request latency was `10.551997026s`, which violates
Slack's 3 second acknowledgement requirement. The Gateway now acknowledges
Slack first, then runs Query Processor and Slack posting work in detached
tracked asyncio tasks. Cloud Run `cpu_idle = false` is enabled so those detached
tasks can finish after the response.

Latest merged main commit at verification time:

- `c373ae7 Ack Slack webhooks before async work (#30)`

Open pull requests:

- none

Local verification:

- `cd tests && uv run pytest -q` -> `49 passed`
- `python -m compileall aegis-hub-code/slack-gateway/app aegis-hub-code/incident-analyzer/app aegis-hub-code/query-processor/app` -> success
- `terraform/aegis-hub` plan -> no changes
- `terraform/client-agent` plan -> no changes
- `./client-backend/scripts/smoke-gke.sh` -> rollouts healthy, readiness OK, checkout path OK
- Pub/Sub dead-letter subscription `aegis-dead-letter-pull` -> empty

Fresh incident verified:

- client correlation id: `demo-final-1780234199`
- client log timestamp: `2026-05-31T13:30:01.100099959Z`
- client pod: `python-api-8496d86956-56jj8`
- service: `python-api`
- error type: `ValueError`
- `incident_candidate`: `true`
- BigQuery incident: `INC-2026-671169`
- terminal status: `SUCCESS`
- Slack channel: `C0B4LVB5YR5`
- Slack message timestamp: `1780234233.603399`
- Firestore session exists with `client_project_id`, `service_name`,
  `cluster_name`, `namespace`, `pod_name`, `error_type`, `log_timestamp`, and
  initial `messages`
- Firestore receipt has `analysis_completed=true`, `session_created=true`,
  `slack_handoff_succeeded=true`, and `bigquery_persisted=true`

Observed live SLI/SLO evidence:

| SLI | Target | Observed |
| --- | --- | --- |
| Slack Events ack latency | `< 3s` | `0.003671534s` Cloud Run latency on revision `aegis-slack-gateway-00007-jg6` |
| Slash command ack latency | `< 3s` | `0.005001521s` Cloud Run latency on revision `aegis-slack-gateway-00007-jg6` |
| Incident query end-to-end | `< 30s` | `9.646508471s` for `INC-2026-671169` |
| Latest incidents query | `< 5s` | Query Processor returned `200`; Gateway ack stayed `0.005001521s` |
| Alert relay latency | `< 2s` | `0.355391194s` for Incident Analyzer -> Slack Gateway -> Slack |

Cloud Monitoring verification for `INC-2026-671169`:

- project: `aegis-client-420`
- cluster: `mock-gke-standard`
- namespace: `aegis-demo`
- pod: `python-api-8496d86956-56jj8`
- container: `python-api`
- anchor time: `2026-05-31T13:30:01.100099+00:00`
- CPU at incident time: `0.59% of container CPU limit`
- memory at incident time: `6.9 MiB`
- CPU request utilization: `11.73% of requested CPU`
- memory limit utilization: `1.35% of container memory limit`

The Firestore conversation for `INC-2026-671169` contains the initial incident
model context, the user question, and the model reply with the same CPU and
memory facts. This proves the bot keeps incident context by `incident_id` and
uses true Cloud Monitoring values instead of invented metrics.

Slack API limitation:

- `conversations.replies` cannot be used by the current bot token because Slack
  returns `missing_scope` and requires one of `channels:history`,
  `groups:history`, `mpim:history`, or `im:history`.
- Because of that, backend verification can prove `chat.postMessage` returned
  `200 OK` and Firestore has the generated messages, but the exact rendered
  Slack thread cannot be pulled back through the Slack API unless the app gets
  history scopes.

Demo reliability note:

- Kubernetes auto chaos remains disabled by default. This is intentional for
  the professor demo because incidents should be deterministic and manually
  triggered with a known `X-Correlation-ID`.
- Manual chaos endpoints produce valid structured error logs at sensible demo
  frequency. Do not enable auto chaos unless you explicitly want continuous
  surprise incidents.
