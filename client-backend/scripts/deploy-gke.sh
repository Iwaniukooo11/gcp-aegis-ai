#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLIENT_DIR="${ROOT_DIR}/client-backend"

CLIENT_PROJECT_ID="${CLIENT_PROJECT_ID:-aegis-client-420}"
REGION="${REGION:-europe-central2}"
CLUSTER_NAME="${CLUSTER_NAME:-mock-gke-standard}"
REPOSITORY_ID="${REPOSITORY_ID:-aegis-client-services}"
IMAGE_TAG="${IMAGE_TAG:-$(git -C "${ROOT_DIR}" rev-parse --short HEAD)}"
IMAGE_BASE="${REGION}-docker.pkg.dev/${CLIENT_PROJECT_ID}/${REPOSITORY_ID}"

JAVA_IMAGE="${IMAGE_BASE}/java-api:${IMAGE_TAG}"
PYTHON_IMAGE="${IMAGE_BASE}/python-api:${IMAGE_TAG}"
JAVA_LATEST_IMAGE="${IMAGE_BASE}/java-api:latest"
PYTHON_LATEST_IMAGE="${IMAGE_BASE}/python-api:latest"

gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
gcloud container clusters get-credentials "${CLUSTER_NAME}" --region "${REGION}" --project "${CLIENT_PROJECT_ID}"

docker build --platform linux/amd64 -t "${JAVA_IMAGE}" -t "${JAVA_LATEST_IMAGE}" "${CLIENT_DIR}/apps/java-api"
docker build --platform linux/amd64 -t "${PYTHON_IMAGE}" -t "${PYTHON_LATEST_IMAGE}" "${CLIENT_DIR}/apps/python-api"

docker push "${JAVA_IMAGE}"
docker push "${PYTHON_IMAGE}"
docker push "${JAVA_LATEST_IMAGE}"
docker push "${PYTHON_LATEST_IMAGE}"

kubectl apply -k "${CLIENT_DIR}/k8s"
kubectl -n aegis-demo set image deployment/java-api "java-api=${JAVA_IMAGE}"
kubectl -n aegis-demo set image deployment/python-api "python-api=${PYTHON_IMAGE}"
kubectl -n aegis-demo rollout status deployment/java-api --timeout=180s
kubectl -n aegis-demo rollout status deployment/python-api --timeout=180s

kubectl -n aegis-demo get pods,svc
