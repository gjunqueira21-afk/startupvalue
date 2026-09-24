#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

if (( $# != 1 )); then
  echo "Usage: $0 /absolute/path/to/backup-directory" >&2
  exit 2
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd -P)"
SOURCE_DIR="$(cd -- "$1" && pwd -P)"
ENV_FILE="${ENV_FILE:-/opt/startupvalue/secrets/production.env}"
RESTORE_DATABASE="${RESTORE_DATABASE:-startupvalue_restore_$(date -u +%Y%m%dT%H%M%SZ)}"
RESTORE_ARTIFACT_ROOT="${RESTORE_ARTIFACT_ROOT:-/opt/startupvalue/restore-drills}"

if [[ ! "${RESTORE_DATABASE}" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
  echo "RESTORE_DATABASE contains unsupported characters" >&2
  exit 2
fi
if [[ "${RESTORE_ARTIFACT_ROOT}" != /* ]] || [[ "${RESTORE_ARTIFACT_ROOT}" == "/" ]]; then
  echo "RESTORE_ARTIFACT_ROOT must be a safe absolute path" >&2
  exit 2
fi
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Environment file not found: ${ENV_FILE}" >&2
  exit 2
fi
for required in SHA256SUMS postgres.dump private-data.tar.gz; do
  [[ -f "${SOURCE_DIR}/${required}" ]] || { echo "Missing ${required}" >&2; exit 2; }
done

manifest_files="$(awk '{print $2}' "${SOURCE_DIR}/SHA256SUMS" | LC_ALL=C sort)"
if [[ "${manifest_files}" != $'private-data.tar.gz\npostgres.dump' ]]; then
  echo "SHA256SUMS must contain exactly postgres.dump and private-data.tar.gz" >&2
  exit 2
fi

(
  cd -- "${SOURCE_DIR}"
  sha256sum --check SHA256SUMS
)

if tar --list --gzip --file="${SOURCE_DIR}/private-data.tar.gz" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then
  echo "Archive contains an unsafe path" >&2
  exit 2
fi

compose=(docker compose --project-directory "${PROJECT_ROOT}" --env-file "${ENV_FILE}" -f "${PROJECT_ROOT}/docker-compose.yml" -f "${PROJECT_ROOT}/docker-compose.prod.yml")
"${compose[@]}" up -d postgres

if "${compose[@]}" exec -T -e RESTORE_DATABASE="${RESTORE_DATABASE}" postgres sh -ec \
  'psql --username="$POSTGRES_USER" --dbname=postgres --list --tuples-only --no-align | cut -d "|" -f 1 | sed "s/[[:space:]]*$//" | grep -Fxq "$RESTORE_DATABASE"'; then
  echo "Refusing to overwrite existing database: ${RESTORE_DATABASE}" >&2
  exit 3
fi

"${compose[@]}" exec -T -e RESTORE_DATABASE="${RESTORE_DATABASE}" postgres sh -ec \
  'createdb --username="$POSTGRES_USER" "$RESTORE_DATABASE"'
"${compose[@]}" exec -T -e RESTORE_DATABASE="${RESTORE_DATABASE}" postgres sh -ec \
  'pg_restore --username="$POSTGRES_USER" --dbname="$RESTORE_DATABASE" --no-owner --no-privileges' \
  < "${SOURCE_DIR}/postgres.dump"

artifact_dir="${RESTORE_ARTIFACT_ROOT}/${RESTORE_DATABASE}"
mkdir -p -- "${artifact_dir}"
chmod 700 "${artifact_dir}"
tar --extract --gzip --file="${SOURCE_DIR}/private-data.tar.gz" --directory="${artifact_dir}" --no-same-owner --no-same-permissions

echo "Restore drill completed into isolated database: ${RESTORE_DATABASE}"
echo "Artifacts extracted for inspection at: ${artifact_dir}"
echo "No production database or active private-data volume was replaced."
