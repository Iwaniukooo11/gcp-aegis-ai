#!/usr/bin/env bash
set -euo pipefail

kubectl -n aegis-demo rollout status deployment/java-api --timeout=120s
kubectl -n aegis-demo rollout status deployment/python-api --timeout=120s

kubectl -n aegis-demo port-forward svc/python-api 8000:8000 >/tmp/aegis-python-api-port-forward.log 2>&1 &
PF_PID="$!"
trap 'kill "${PF_PID}" >/dev/null 2>&1 || true' EXIT

for _ in $(seq 1 20); do
  if curl -fsS http://localhost:8000/healthz/ready >/tmp/aegis-python-api-ready.json 2>/dev/null; then
    break
  fi
  if ! kill -0 "${PF_PID}" >/dev/null 2>&1; then
    cat /tmp/aegis-python-api-port-forward.log >&2 || true
    exit 1
  fi
  sleep 1
done

if [[ ! -s /tmp/aegis-python-api-ready.json ]]; then
  cat /tmp/aegis-python-api-port-forward.log >&2 || true
  exit 1
fi

cat /tmp/aegis-python-api-ready.json
curl -fsS http://localhost:8000/api/info
curl -fsS -H "X-Correlation-ID: gke-smoke-001" http://localhost:8000/api/checkout
