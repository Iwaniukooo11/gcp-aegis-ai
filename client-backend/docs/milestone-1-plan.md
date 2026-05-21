# Milestone 1 Plan

Milestone 1 builds and verifies the two local backend services. It does not
include Terraform changes, GKE deployment, Artifact Registry, Cloud Logging, or
Pub/Sub.

## Commit Sequence

### 1. Client backend skeleton

Create the tracked `client-backend/` structure, environment contract,
architecture docs, and placeholder scripts.

Verification:

```bash
find client-backend -maxdepth 4 -type f | sort
```

### 2. Python minimum service

Add the first FastAPI service with:

```text
/healthz/live
/healthz/ready
/api/info
configuration loading
correlation ID middleware
single-line structured JSON logging
basic tests
```

Verification:

```bash
cd client-backend/apps/python-api
uv run pytest
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
curl -i http://localhost:8000/healthz/live
curl -i http://localhost:8000/api/info
```

Status: implemented in the Python minimum-service commit.

### 3. Java minimum service

Add the Spring Boot service with:

```text
/healthz/live
/healthz/ready
/api/info
configuration properties
correlation ID filter
single-line structured JSON logging
basic tests
```

Verification:

```bash
cd client-backend/apps/java-api
./gradlew test
./gradlew bootRun
curl -i http://localhost:8080/healthz/live
curl -i http://localhost:8080/api/info
```

Status: implemented in the Java minimum-service commit.

### 4. Docker Compose integration

Add Dockerfiles and make both services run together.

Verification:

```bash
cd client-backend
docker compose up --build
./scripts/smoke-local.sh
```

Status: implemented in the Docker Compose integration commit.

### 5. Java workload and basic failures

Add:

```text
GET  /api/pricing
GET  /api/work
POST /chaos/exception?type=null_pointer
POST /chaos/exception?type=illegal_state
POST /chaos/slow?seconds=15
POST /chaos/pricing-5xx?seconds=60
```

Verification:

```bash
curl -i http://localhost:8080/api/pricing
curl -i -X POST "http://localhost:8080/chaos/exception?type=null_pointer"
docker compose logs java-api | tail -n 50
```

Status: implemented in the Java workload and basic-failures commit.

### 6. Python workload and dependency failures

Add:

```text
GET  /api/work
GET  /api/checkout
POST /chaos/exception?type=value_error
POST /chaos/exception?type=runtime_error
downstream timeout handling
downstream 5xx handling
```

Verification:

```bash
curl -i http://localhost:8000/api/checkout
curl -i -X POST "http://localhost:8080/chaos/slow?seconds=15"
curl -i http://localhost:8000/api/checkout
docker compose logs python-api | tail -n 80
```

Status: implemented in the Python workload and dependency-failures commit.

### 7. Controlled chaos scenarios

Add bounded scenarios:

```text
POST /chaos/cpu
POST /chaos/memory-pressure
POST /chaos/readiness-fail
POST /chaos/burst
POST /chaos/reset
POST /chaos/crash, behind safety controls
```

Verification:

```bash
curl -i -X POST "http://localhost:8000/chaos/readiness-fail?seconds=10"
curl -i http://localhost:8000/healthz/ready
sleep 12
curl -i http://localhost:8000/healthz/ready
curl -i -X POST "http://localhost:8000/chaos/burst?count=3"
```

### 8. Scenario scripts and documentation tightening

Add repeatable local scripts:

```text
smoke-local.sh
scenario-java-exception.sh
scenario-python-timeout.sh
scenario-readiness.sh
scenario-burst.sh
```

Verification:

```bash
cd client-backend
./scripts/smoke-local.sh
./scripts/scenario-java-exception.sh
./scripts/scenario-python-timeout.sh
```

## Definition Of Done

Milestone 1 is complete when:

```text
[ ] python-api starts locally.
[ ] java-api starts locally.
[ ] docker compose up --build starts both services.
[ ] python-api calls java-api by Docker Compose service name.
[ ] both services expose /healthz/live and /healthz/ready.
[ ] both services expose /api/info.
[ ] java-api exposes /api/pricing.
[ ] python-api exposes /api/checkout.
[ ] both services emit single-line structured JSON logs.
[ ] ERROR logs include client_project_id, service_name, scenario, error_type,
    correlation_id, and severity.
[ ] simple Python exception scenario works.
[ ] simple Java exception scenario works.
[ ] Python dependency timeout scenario works.
[ ] readiness failure scenario works and recovers.
[ ] burst scenario works with configured max count.
[ ] destructive crash/OOM behavior is disabled unless explicitly enabled.
[ ] scenario scripts are repeatable.
[ ] tests cover the error response contract and core scenario state.
```
