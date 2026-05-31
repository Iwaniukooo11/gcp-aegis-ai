#!/usr/bin/env bash
set -euo pipefail

kubectl -n aegis-demo rollout status deployment/java-api --timeout=120s
kubectl -n aegis-demo rollout status deployment/python-api --timeout=120s

kubectl -n aegis-demo port-forward svc/python-api 8000:8000 >/tmp/aegis-python-api-port-forward.log 2>&1 &
PF_PID="$!"
trap 'kill "${PF_PID}" >/dev/null 2>&1 || true' EXIT

sleep 3

curl -fsS http://localhost:8000/healthz/ready
curl -fsS http://localhost:8000/api/info
curl -fsS -H "X-Correlation-ID: gke-smoke-001" http://localhost:8000/api/checkout
