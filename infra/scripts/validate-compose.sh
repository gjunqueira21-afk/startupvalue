#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd -P)"
DEV_ENV_FILE="${1:-${PROJECT_ROOT}/.env}"
PROD_ENV_FILE="${2:-}"

docker compose --project-directory "${PROJECT_ROOT}" --env-file "${DEV_ENV_FILE}" \
  -f "${PROJECT_ROOT}/docker-compose.yml" config --quiet

echo "Development Compose configuration is valid."

if [[ -n "${PROD_ENV_FILE}" ]]; then
  docker compose --project-directory "${PROJECT_ROOT}" --env-file "${PROD_ENV_FILE}" \
    -f "${PROJECT_ROOT}/docker-compose.yml" -f "${PROJECT_ROOT}/docker-compose.prod.yml" config --quiet
  echo "Production Compose configuration is valid."
else
  echo "Production validation skipped; pass a production env file as the second argument."
fi
