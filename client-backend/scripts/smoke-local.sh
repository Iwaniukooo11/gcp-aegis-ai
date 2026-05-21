#!/usr/bin/env bash
set -euo pipefail

CORRELATION_ID="smoke-test-001"

wait_for_url() {
  local url="$1"
  local label="$2"
  local attempts="${3:-60}"

  for attempt in $(seq 1 "${attempts}"); do
    if curl -fsS "${url}" >/dev/null; then
      echo "ready: ${label}"
      return 0
    fi
    sleep 1
  done

  echo "timed out waiting for ${label}: ${url}" >&2
  return 1
}

assert_json_field() {
  local body="$1"
  local field="$2"
  local expected="$3"

  BODY="${body}" FIELD="${field}" EXPECTED="${expected}" python3 - <<'PY'
import json
import os
import sys

body = os.environ["BODY"]
field = os.environ["FIELD"]
expected = os.environ["EXPECTED"]

try:
    payload = json.loads(body)
except json.JSONDecodeError as exc:
    print(f"invalid JSON body: {exc}: {body}", file=sys.stderr)
    sys.exit(1)

actual = payload
for part in field.split("."):
    if not isinstance(actual, dict) or part not in actual:
        print(f"missing JSON field {field}: {payload}", file=sys.stderr)
        sys.exit(1)
    actual = actual[part]

if str(actual) != expected:
    print(f"expected {field}={expected!r}, got {actual!r}: {payload}", file=sys.stderr)
    sys.exit(1)
PY
}

assert_endpoint() {
  local url="$1"
  local service_name="$2"
  local expected_status="${3:-}"

  local body
  body="$(curl -fsS "${url}")"
  assert_json_field "${body}" "service_name" "${service_name}"
  assert_json_field "${body}" "client_project_id" "aegis-client-420"
  assert_json_field "${body}" "environment" "local"
  if [[ -n "${expected_status}" ]]; then
    assert_json_field "${body}" "status" "${expected_status}"
  fi
  echo "ok: ${url}"
}

assert_correlation_header() {
  local url="$1"
  local header
  header="$(curl -fsS -D - -o /dev/null -H "X-Correlation-ID: ${CORRELATION_ID}" "${url}" \
    | tr -d '\r' \
    | awk -F': ' 'tolower($1) == "x-correlation-id" {print $2}' \
    | tail -n 1)"

  if [[ "${header}" != "${CORRELATION_ID}" ]]; then
    echo "expected X-Correlation-ID=${CORRELATION_ID}, got ${header:-<missing>} for ${url}" >&2
    return 1
  fi
  echo "ok: correlation header for ${url}"
}

wait_for_url "http://localhost:8000/healthz/ready" "python-api"
wait_for_url "http://localhost:8080/healthz/ready" "java-api"

assert_endpoint "http://localhost:8000/healthz/live" "python-api" "live"
assert_endpoint "http://localhost:8000/healthz/ready" "python-api" "ready"
assert_endpoint "http://localhost:8000/api/info" "python-api"
assert_endpoint "http://localhost:8000/api/work" "python-api"
assert_endpoint "http://localhost:8000/api/checkout" "python-api"

assert_endpoint "http://localhost:8080/healthz/live" "java-api" "live"
assert_endpoint "http://localhost:8080/healthz/ready" "java-api" "ready"
assert_endpoint "http://localhost:8080/api/info" "java-api"
assert_endpoint "http://localhost:8080/api/pricing" "java-api"
assert_endpoint "http://localhost:8080/api/work" "java-api"

assert_correlation_header "http://localhost:8000/api/info"
assert_correlation_header "http://localhost:8080/api/info"

echo "smoke checks passed"
