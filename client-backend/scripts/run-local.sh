#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${CLIENT_BACKEND_DIR}"
docker compose up --build
