#!/usr/bin/env bash
# First and recurring deploy on the Hostinger VPS (srv1682017), where a shared
# Traefik owns 80/443. Run as root in the VPS terminal:
#
#   bash infra/scripts/hostinger-deploy.sh [git-ref]     # default: origin/main
#
# What it does: clones/updates the repo under /opt/startupvalue/app, generates
# /opt/startupvalue/secrets/production.env once (random secrets, mode 600),
# pins the GHCR images to the release commit, pulls, migrates and starts the
# stack. Rollback = run again with the previous commit sha.
set -Eeuo pipefail

REPO=https://github.com/gjunqueira21-afk/startupvalue
GHCR=ghcr.io/gjunqueira21-afk
BASE=/opt/startupvalue
APP=$BASE/app
ENVF=$BASE/secrets/production.env
DEFAULT_DOMAIN=marketwatchrf.com

command -v docker >/dev/null || { echo "docker nao encontrado"; exit 1; }
command -v git >/dev/null || { echo "git nao encontrado"; exit 1; }

mkdir -p "$BASE/secrets"
chmod 700 "$BASE/secrets"

# ---------------------------------------------------------------- code checkout
if [ ! -d "$APP/.git" ]; then
  git clone "$REPO" "$APP"
fi
cd "$APP"
git fetch origin --prune
git checkout --force --detach "${1:-origin/main}"
SHA=$(git rev-parse HEAD)
echo "==> release commit: $SHA"

# ---------------------------------------------------------------- env/secrets
if [ ! -f "$ENVF" ]; then
  echo "==> gerando $ENVF (primeira vez)"
  umask 077
  cat > "$ENVF" <<ENV
# Gerado por hostinger-deploy.sh. Mantem fora do Git; mode 600.
DOMAIN=$DEFAULT_DOMAIN
APP_ENV=production
MODEL_VERSION=3.1.0
TAX_VERSION=br-simplified-2026.09
PUBLIC_APP_URL=https://$DEFAULT_DOMAIN

POSTGRES_DB=startupvalue
POSTGRES_USER=startupvalue_app
POSTGRES_PASSWORD=$(openssl rand -hex 32)
REDIS_PASSWORD=$(openssl rand -hex 32)
SESSION_SECRET=$(openssl rand -hex 32)
CSRF_SECRET=$(openssl rand -hex 32)
SENTRY_DSN=

# SMTP fica vazio ate configurar um provedor de email (reset de senha).
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_USE_TLS=true

# Preenchido a cada deploy pelo proprio script (tags imutaveis por commit).
FRONTEND_IMAGE=
BACKEND_IMAGE=
ENV
fi

PREV_FRONTEND=$(grep '^FRONTEND_IMAGE=' "$ENVF" | cut -d= -f2- || true)
sed -i "s|^FRONTEND_IMAGE=.*|FRONTEND_IMAGE=$GHCR/startupvalue-frontend:sha-$SHA|" "$ENVF"
sed -i "s|^BACKEND_IMAGE=.*|BACKEND_IMAGE=$GHCR/startupvalue-backend:sha-$SHA|" "$ENVF"

COMPOSE=(docker compose --project-directory "$APP" --env-file "$ENVF"
  -f "$APP/docker-compose.yml" -f "$APP/docker-compose.prod.yml" -f "$APP/docker-compose.hostinger.yml")

# ---------------------------------------------------------------- release
"${COMPOSE[@]}" config --quiet
echo "==> pull das imagens"
"${COMPOSE[@]}" pull --quiet postgres redis frontend backend worker
echo "==> subindo banco/cache"
"${COMPOSE[@]}" up -d --wait postgres redis
echo "==> migrations (alembic upgrade head)"
"${COMPOSE[@]}" --profile tools run --rm migrate
echo "==> subindo app"
"${COMPOSE[@]}" up -d --remove-orphans backend worker frontend

echo "==> aguardando health do backend"
STATUS=starting
for _ in $(seq 1 36); do
  CID=$("${COMPOSE[@]}" ps -q backend)
  STATUS=$(docker inspect -f '{{.State.Health.Status}}' "$CID" 2>/dev/null || echo unknown)
  [ "$STATUS" = healthy ] && break
  sleep 5
done
echo "backend: $STATUS"
"${COMPOSE[@]}" ps

echo
echo "==> release $SHA aplicado."
if [ -n "$PREV_FRONTEND" ]; then
  PREV_SHA=${PREV_FRONTEND##*:sha-}
  echo "    rollback: bash infra/scripts/hostinger-deploy.sh $PREV_SHA"
fi
echo "    smoke: curl -fsS https://$DEFAULT_DOMAIN/health/ready"
