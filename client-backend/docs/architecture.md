# Client Backend Architecture

## Goal

Build a deterministic local mock client backend that will later run in the
separate GCP client project `aegis-client-420`.

Milestone 1 is local-only:

```text
Docker Compose network
├── python-api
│   └── planned local port: 8000
└── java-api
    └── planned local port: 8080
```

The future cloud shape is:

```text
GKE namespace: aegis-demo
├── Deployment: python-api, replicas=1
├── Service: python-api, ClusterIP
├── Deployment: java-api, replicas=1
└── Service: java-api, ClusterIP
```

Use Deployments with one replica each for the final "two pods" requirement. Do
not deploy raw Kubernetes Pod objects.

## Service Roles

`python-api` is the business-facing mock API. It owns Python-specific failures
and calls `java-api` to create realistic downstream dependency incidents.

`java-api` is the internal pricing dependency. It owns JVM-specific failures and
serves the pricing endpoint used by `python-api`.

## Demo Business Story

The live demo models a small e-commerce checkout flow:

```text
customer checkout -> python-api /api/checkout -> java-api /api/pricing
```

The preferred incident is pricing latency. An operator enables a controlled
failure window through `java-api /admin/failures/pricing-latency`, then calls
`python-api /api/checkout`. `python-api` returns HTTP 504 and emits the
customer-facing incident log. `java-api` eventually returns normally, so the
demo produces one clean checkout incident instead of two unrelated-looking
alerts.

The secondary incident is pricing unavailable. `java-api
/admin/failures/pricing-unavailable` makes `/api/pricing` return HTTP 503.
This is useful for showing a hard dependency failure, but it may create both an
upstream `java-api` incident and a downstream `python-api` checkout incident.

## Observability Contract

Every incident-producing failure must emit one single-line structured JSON log
with these stable fields:

```text
severity
message
client_project_id
service_name
environment
scenario
error_type
incident_candidate
correlation_id
team
http_method
path
status_code
duration_ms
stack_trace_preview
upstream_service, when applicable
```

Example:

```json
{
  "severity": "ERROR",
  "message": "Downstream timeout while calling java-api",
  "client_project_id": "aegis-client-420",
  "service_name": "python-api",
  "environment": "local",
  "scenario": "PYTHON_DOWNSTREAM_TIMEOUT",
  "error_type": "DownstreamTimeout",
  "incident_candidate": true,
  "correlation_id": "demo-2026-05-20-001",
  "team": "demo",
  "http_method": "GET",
  "path": "/api/checkout",
  "status_code": 504,
  "duration_ms": 1008,
  "upstream_service": "java-api",
  "stack_trace_preview": "java-api request exceeded 1000 ms timeout"
}
```

For the main demo, the message should be business-facing, for example:

```text
Checkout failed because java-api pricing request exceeded configured timeout
```

The incident log should not mention `chaos` unless the failing request itself is
a direct `/chaos/*` fallback endpoint.

## HTTP Error Contract

Do not leak full stack traces to HTTP callers. Return structured JSON errors:

```json
{
  "error": {
    "code": "DOWNSTREAM_TIMEOUT",
    "message": "Timed out while calling java-api",
    "service_name": "python-api",
    "scenario": "PYTHON_DOWNSTREAM_TIMEOUT",
    "correlation_id": "demo-2026-05-20-001"
  }
}
```

Use these status codes consistently:

```text
200 - normal health/workload response
202 - accepted background chaos task
400 - invalid chaos parameters
403 - chaos endpoint disabled
409 - mutually exclusive scenario already active
429 - cooldown or max burst guard rejected the scenario
500 - local application exception
502 - dependency returned a bad response
503 - service not ready
504 - dependency timed out
```

## Failure Policy

Failures must be deterministic and manually triggered by default.

```text
CHAOS_ENABLED=true
CHAOS_AUTO_MODE=false
ALLOW_DESTRUCTIVE_CHAOS=false
```

Avoid random always-on failures, public chaos endpoints, OOM loops, and repeated
crash loops. Resource pressure and burst scenarios must enforce bounded limits
from configuration.

Prefer `/admin/failures/*` endpoints in demo docs and professor presentation.
The older `/chaos/*` endpoints remain as compatibility and fallback smoke-test
routes.

## Cloud Constraints For Later

No public Ingress or LoadBalancer should be added for the mock client unless the
project requirements change. In the cloud phase, chaos endpoints should be
reached through `kubectl port-forward`, not through a public endpoint.
