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

The system is no longer obviously incomplete. Still, before the professor demo, run the full live flow once from Slack UI:

1. trigger a fresh incident
2. confirm Slack alert appears
3. run `/aegis-latest-incidents 5`
4. ask `@Aegis INC-... what were cpu and memory during the incident?`
5. confirm the reply includes real Cloud Monitoring facts

This final Slack UI check matters because the backend can be verified from code and Google Cloud, but the exact Slack workspace permissions and visible message behavior are controlled by Slack app configuration.
