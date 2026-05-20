# python-api

FastAPI mock client service for Aegis AI.

## Run Locally

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Test

```bash
uv run pytest
```

## Endpoints

```text
GET /healthz/live
GET /healthz/ready
GET /api/info
GET /api/work
GET /api/checkout
POST /chaos/exception?type=value_error
POST /chaos/exception?type=runtime_error
```
