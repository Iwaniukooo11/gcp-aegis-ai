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
POST /chaos/exception?type=null_pointer
POST /chaos/exception?type=illegal_state
POST /chaos/slow?seconds=15
POST /chaos/pricing-5xx?seconds=60

With `CHAOS_AUTO_MODE=true`, java-api triggers pricing-5xx and a chaos exception on a fixed interval (defaults: every 20s, 10s pricing failure window).
```
