#!/usr/bin/env bash
set -euo pipefail

JAVA_API_URL="${JAVA_API_URL:-http://localhost:8080}"

echo "resetting java-api demo failures"
curl -fsS -X POST "${JAVA_API_URL}/admin/failures/reset"
echo

echo "current java-api failure status"
curl -fsS "${JAVA_API_URL}/admin/failures"
echo
