#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${CLIENT_BACKEND_DIR}/apps/python-api"
uv run pytest

cd "${CLIENT_BACKEND_DIR}/apps/java-api"
./gradlew test
