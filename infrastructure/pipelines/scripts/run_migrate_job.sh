#!/usr/bin/env bash
# Start the Alembic migrate Container Apps job and wait until it succeeds.
set -euo pipefail

: "${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP is required}"
: "${MIGRATE_JOB_NAME:?MIGRATE_JOB_NAME is required}"

echo "Starting migrate job ${MIGRATE_JOB_NAME}."
EXECUTION_NAME="$(az containerapp job start \
  --name "${MIGRATE_JOB_NAME}" \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --query "name" -o tsv)"

echo "Waiting for migrate execution ${EXECUTION_NAME}."

for _ in $(seq 1 60); do
  STATUS="$(az containerapp job execution show \
    --name "${MIGRATE_JOB_NAME}" \
    --job-execution-name "${EXECUTION_NAME}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --query "properties.status" -o tsv 2>/dev/null || echo "Unknown")"
  echo "migrate status=${STATUS}"
  case "${STATUS}" in
    Succeeded) exit 0 ;;
    Failed|Cancelled) echo "Migrate job failed with status ${STATUS}" >&2; exit 1 ;;
  esac
  sleep 10
done

echo "Timed out waiting for migrate job." >&2
exit 1
