# java-api

Spring Boot mock client service for Aegis AI.

## Run Locally

```bash
./gradlew bootRun
```

## Test

```bash
./gradlew test
```

## Endpoints

```text
GET /healthz/live
GET /healthz/ready
GET /api/info
GET /api/pricing
GET /api/work
POST /admin/failures/pricing-latency?seconds=15
POST /admin/failures/pricing-unavailable?seconds=60
POST /chaos/exception?type=null_pointer
POST /chaos/exception?type=illegal_state
POST /chaos/slow?seconds=15
POST /chaos/pricing-5xx?seconds=60
```

Use `/admin/failures/pricing-latency` for the primary live demo. It makes
`python-api /api/checkout` time out while keeping the incident context focused
on the customer-facing checkout failure.

With `CHAOS_AUTO_MODE=true`, java-api triggers one chaos exception every `CHAOS_AUTO_INTERVAL_SECONDS` (default 120s). Pair with python-api auto mode (60s initial delay) for about one ERROR log per minute across both services.
