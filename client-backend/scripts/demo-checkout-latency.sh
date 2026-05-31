#!/usr/bin/env bash
set -euo pipefail

JAVA_API_URL="${JAVA_API_URL:-http://localhost:8080}"
PYTHON_API_URL="${PYTHON_API_URL:-http://localhost:8000}"
FAILURE_SECONDS="${FAILURE_SECONDS:-15}"
CORRELATION_ID="${CORRELATION_ID:-demo-checkout-latency-$(date +%s)}"

response_file="$(mktemp)"
trap 'rm -f "${response_file}"' EXIT

echo "enabling pricing latency on java-api for ${FAILURE_SECONDS}s"
curl -fsS -X POST "${JAVA_API_URL}/admin/failures/pricing-latency?seconds=${FAILURE_SECONDS}"
echo

echo "triggering checkout incident with X-Correlation-ID: ${CORRELATION_ID}"
http_status="$(
  curl -sS \
    -o "${response_file}" \
    -w "%{http_code}" \
    -H "X-Correlation-ID: ${CORRELATION_ID}" \
    "${PYTHON_API_URL}/api/checkout"
)"

cat "${response_file}"
echo

if [[ "${http_status}" != "504" ]]; then
  echo "expected checkout HTTP 504, got ${http_status}" >&2
  exit 1
fi

echo "ok: checkout latency incident generated (${CORRELATION_ID})"
