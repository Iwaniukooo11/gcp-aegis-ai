# Client Incident Management

This document is the public source of truth for how the mock client
infrastructure creates incidents for Aegis AI.

The client project is not meant to be a random chaos generator. It is a
deterministic failure laboratory for proving the full Aegis path:

```text
GKE workload error log
-> Cloud Logging sink
-> Hub Pub/Sub
-> Incident Analyzer
-> BigQuery + Firestore + Slack
-> Slack follow-up through Query Processor and Cloud Monitoring
```

## Default Policy

Use manual, controlled incidents by default.

```text
CHAOS_ENABLED=true
CHAOS_AUTO_MODE=false
ALLOW_DESTRUCTIVE_CHAOS=false
```

Do not enable automatic incidents during a professor demo. Constant random
failures make the Slack thread noisy, pollute BigQuery, and make it harder to
prove that one specific customer action produced one specific incident.

The normal demo frequency is:

```text
1. Trigger one incident.
2. Wait for Slack, BigQuery, and Firestore to show it.
3. Ask one or two Slack follow-up questions.
4. Reset or let the failure window expire.
5. Trigger an optional second incident only if there is time.
```

Use a unique `X-Correlation-ID` for every demo request.

## Incident Catalog

| Scenario | Trigger | Expected result | Use in demo |
| --- | --- | --- | --- |
| Checkout pricing latency | `POST /admin/failures/pricing-latency?seconds=15`, then `GET /api/checkout` | `python-api` returns HTTP 504 and emits `PYTHON_DOWNSTREAM_TIMEOUT` with `upstream_service=java-api` | Primary demo |
| Pricing unavailable | `POST /admin/failures/pricing-unavailable?seconds=60`, then `GET /api/checkout` | `python-api` returns HTTP 502 and emits `PYTHON_DOWNSTREAM_5XX`; `java-api` may also emit HTTP 503 | Optional dependency outage demo |
| Python exception | `POST /chaos/exception?type=value_error` | `python-api` returns HTTP 500 | Fallback smoke test only |
| Java exception | `POST /chaos/exception?type=null_pointer` | `java-api` returns HTTP 500 | Fallback smoke test only |

The primary scenario is the strongest one because it looks like a real
customer-facing failure:

```text
customer checkout
-> python-api /api/checkout
-> java-api /api/pricing
-> pricing latency
-> checkout timeout
-> Aegis incident
```

The fallback `/chaos/*` scenarios are valid tests, but they are less impressive
for the demo because the bot is correct to describe them as intentional chaos
experiments.

## Control Endpoints

`java-api` owns the realistic pricing dependency failures:

```text
POST /admin/failures/pricing-latency?seconds=N
POST /admin/failures/pricing-unavailable?seconds=N
GET  /admin/failures
POST /admin/failures/reset
```

`GET /admin/failures` returns whether pricing latency or pricing unavailable is
currently active and when each active window expires.

`POST /admin/failures/reset` clears both active failure windows. Use it before
and after rehearsals so a stale failure does not leak into the next run.

The older compatibility endpoints still exist:

```text
POST /chaos/slow?seconds=N
POST /chaos/pricing-5xx?seconds=N
POST /chaos/exception?type=null_pointer
POST /chaos/exception?type=illegal_state
POST /chaos/exception?type=value_error
POST /chaos/exception?type=runtime_error
```

Prefer `/admin/failures/*` in the professor presentation because these endpoint
names describe business failures instead of implementation mechanics.

## Demo Scripts

From the repository root, after port-forwarding `python-api` to `localhost:8000`
and `java-api` to `localhost:8080`:

```bash
./client-backend/scripts/demo-reset-failures.sh
./client-backend/scripts/demo-checkout-latency.sh
```

Optional second scenario:

```bash
./client-backend/scripts/demo-pricing-unavailable.sh
./client-backend/scripts/demo-reset-failures.sh
```

Useful overrides:

```bash
FAILURE_SECONDS=20 CORRELATION_ID=professor-demo-001 \
  ./client-backend/scripts/demo-checkout-latency.sh

JAVA_API_URL=http://localhost:8080 PYTHON_API_URL=http://localhost:8000 \
  ./client-backend/scripts/demo-pricing-unavailable.sh
```

## Expected Aegis Behavior

For the primary checkout latency incident, Aegis should:

- create one successful BigQuery incident row
- create or update one Firestore session keyed by `incident_id`
- post one Slack alert to the configured incidents channel
- preserve context for follow-up Slack questions
- mention `python-api`, `/api/checkout`, and `java-api`
- report real Cloud Monitoring CPU and memory facts when asked
- avoid claiming CPU or memory caused the issue when metrics are normal
- avoid describing the primary scenario as chaos engineering

The BigQuery row should include:

```text
service_name=python-api
severity=ERROR
scenario=PYTHON_DOWNSTREAM_TIMEOUT
error_type=DownstreamTimeoutError
path=/api/checkout
upstream_service=java-api
terminal_status=SUCCESS
```

The Firestore session should include:

```text
client_project_id
cluster_name
namespace
pod_name
service_name
scenario
path
upstream_service
status_code
log_timestamp
messages
```

## What Not To Run During The Demo

Avoid these unless they are implemented, verified, and explicitly part of a
later demo script:

- automatic chaos mode
- repeated bursts
- process crash loops
- OOM scenarios
- multiple simultaneous active failures
- public LoadBalancer or Ingress for the mock client

The point is to prove the Aegis architecture end-to-end, not to make the mock
client unstable.
