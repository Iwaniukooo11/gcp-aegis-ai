# Client Backend

Local mock client backend for Aegis AI.

Milestone 1 builds two backend services locally before deploying anything to
Google Cloud:

- `python-api`: FastAPI service, later exposed on port `8000`.
- `java-api`: Spring Boot service, later exposed on port `8080`.

The final client infrastructure target is the separate GCP project
`aegis-client-420`. Local development still works with Docker Compose, and the
GKE deployment path now lives in `client-backend/k8s`.

## Current Status

The Python and Java services run together with Docker Compose and deploy to the
client GKE cluster with repeatable Kubernetes manifests.

## Python Service

Run all currently available local tests:

```bash
./scripts/test-local.sh
```

Run the Python service directly:

```bash
cd apps/python-api
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify in another shell:

```bash
curl -i http://localhost:8000/healthz/live
curl -i http://localhost:8000/healthz/ready
curl -i http://localhost:8000/api/info
curl -i http://localhost:8000/api/work
curl -i http://localhost:8000/api/checkout
curl -i -H "X-Correlation-ID: local-test-001" http://localhost:8000/api/info
```

## Java Service

Run the Java test suite directly:

```bash
cd apps/java-api
./gradlew test
```

Run the Java service directly:

```bash
cd apps/java-api
./gradlew bootRun
```

Verify in another shell:

```bash
curl -i http://localhost:8080/healthz/live
curl -i http://localhost:8080/healthz/ready
curl -i http://localhost:8080/api/info
curl -i http://localhost:8080/api/pricing
curl -i http://localhost:8080/api/work
curl -i -H "X-Correlation-ID: local-test-001" http://localhost:8080/api/info
```

## Docker Compose Workflow

Run both services as local containers:

```bash
cd client-backend
docker compose up --build
```

Or use the helper script:

```bash
cd client-backend
./scripts/run-local.sh
```

In another shell, run smoke checks:

```bash
cd client-backend
./scripts/smoke-local.sh
```

Stop the local runtime:

```bash
cd client-backend
docker compose down
```

`test-local.sh` runs the Python and Java test suites without starting
containers.

## GKE Workflow

Deploy both services to the client GKE cluster:

```bash
cd ..
./client-backend/scripts/deploy-gke.sh
```

Run smoke checks:

```bash
./client-backend/scripts/smoke-gke.sh
```

See [Client Workload Deployment](../docs/client-workload-deployment.md) for the full build, deploy, incident trigger, and teardown procedure.

## Local Contract

Both services must eventually use the same configuration and observability
contract:

- `CLIENT_PROJECT_ID=aegis-client-420`
- `ENVIRONMENT=local`
- `TEAM=demo`
- `SERVICE_NAME=python-api` or `SERVICE_NAME=java-api`
- structured single-line JSON logs
- stable correlation IDs via `X-Correlation-ID`
- deterministic failure scenarios, not random failure generation

See `docs/architecture.md` and `docs/milestone-1-plan.md` for the detailed
first milestone design.
