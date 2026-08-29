#!/usr/bin/env bash
# Update Container Apps and Jobs to an immutable CI image tag already present in ACR.
# Does not print secret values. Does not run terraform destroy.
set -euo pipefail

: "${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP is required}"
: "${ACR_LOGIN_SERVER:?ACR_LOGIN_SERVER is required}"
: "${IMAGE_TAG:?IMAGE_TAG is required}"
: "${BACKEND_APP_NAME:?BACKEND_APP_NAME is required}"
: "${FRONTEND_APP_NAME:?FRONTEND_APP_NAME is required}"
: "${WORKER_APP_NAME:?WORKER_APP_NAME is required}"
: "${ML_APP_NAME:?ML_APP_NAME is required}"

BACKEND_IMAGE="${ACR_LOGIN_SERVER}/priceradar/backend:${IMAGE_TAG}"
FRONTEND_IMAGE="${ACR_LOGIN_SERVER}/priceradar/frontend:${IMAGE_TAG}"
WORKER_IMAGE="${ACR_LOGIN_SERVER}/priceradar/workers:${IMAGE_TAG}"
ML_IMAGE="${ACR_LOGIN_SERVER}/priceradar/ml:${IMAGE_TAG}"

echo "Updating container apps to image tag ${IMAGE_TAG} (digest/tag only; no credentials logged)."

az containerapp update --name "${BACKEND_APP_NAME}" --resource-group "${AZURE_RESOURCE_GROUP}" --image "${BACKEND_IMAGE}" --output none
az containerapp update --name "${FRONTEND_APP_NAME}" --resource-group "${AZURE_RESOURCE_GROUP}" --image "${FRONTEND_IMAGE}" --output none
az containerapp update --name "${WORKER_APP_NAME}" --resource-group "${AZURE_RESOURCE_GROUP}" --image "${WORKER_IMAGE}" --output none
az containerapp update --name "${ML_APP_NAME}" --resource-group "${AZURE_RESOURCE_GROUP}" --image "${ML_IMAGE}" --output none

if [[ -n "${MIGRATE_JOB_NAME:-}" ]]; then
  echo "Updating migrate job image."
  az containerapp job update --name "${MIGRATE_JOB_NAME}" --resource-group "${AZURE_RESOURCE_GROUP}" --image "${BACKEND_IMAGE}" --output none
fi

if [[ -n "${ML_TRAIN_JOB_NAME:-}" ]]; then
  echo "Updating ML train job image."
  az containerapp job update --name "${ML_TRAIN_JOB_NAME}" --resource-group "${AZURE_RESOURCE_GROUP}" --image "${ML_IMAGE}" --output none
fi

echo "Container app image update completed."
