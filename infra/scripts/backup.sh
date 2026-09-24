#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd -P)"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/startupvalue/backups}"
ENV_FILE="${ENV_FILE:-/opt/startupvalue/secrets/production.env}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

case "${BACKUP_ROOT}" in
  /|/opt|/opt/startupvalue) echo "Refusing unsafe BACKUP_ROOT: ${BACKUP_ROOT}" >&2; exit 2 ;;
esac

if [[ "${BACKUP_ROOT}" != /* ]]; then
  echo "BACKUP_ROOT must be an absolute path" >&2
  exit 2
fi
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Environment file not found: ${ENV_FILE}" >&2
  exit 2
fi
if ! [[ "${RETENTION_DAYS}" =~ ^[0-9]+$ ]] || (( RETENTION_DAYS < 1 )); then
  echo "RETENTION_DAYS must be a positive integer" >&2
  exit 2
fi

mkdir -p -- "${BACKUP_ROOT}"
chmod 700 "${BACKUP_ROOT}"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
final_dir="${BACKUP_ROOT}/${timestamp}"
work_dir="$(mktemp -d "${BACKUP_ROOT}/.${timestamp}.partial.XXXXXX")"
trap 'rm -rf -- "${work_dir}"' EXIT

compose=(docker compose --project-directory "${PROJECT_ROOT}" --env-file "${ENV_FILE}" -f "${PROJECT_ROOT}/docker-compose.yml" -f "${PROJECT_ROOT}/docker-compose.prod.yml")

"${compose[@]}" exec -T postgres sh -ec \
  'exec pg_dump --format=custom --no-owner --no-privileges --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"' \
  > "${work_dir}/postgres.dump"

"${compose[@]}" exec -T backend sh -ec \
  'tar --create --gzip --file=- --directory=/data reports samples' \
  > "${work_dir}/private-data.tar.gz"

(
  cd -- "${work_dir}"
  sha256sum postgres.dump private-data.tar.gz > SHA256SUMS
  printf 'created_at=%s\nproject=startupvalue\n' "${timestamp}" > MANIFEST
)

mv -- "${work_dir}" "${final_dir}"
trap - EXIT

printf '%s\n' "${timestamp}" > "${BACKUP_ROOT}/last_success"
find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -name '20????????T??????Z' -mtime "+${RETENTION_DAYS}" -print -exec rm -rf -- {} +

echo "Backup completed: ${final_dir}"
echo "Copy this directory to encrypted offsite storage and verify the remote checksum."
