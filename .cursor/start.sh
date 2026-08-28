#!/usr/bin/env bash
# Per-boot service reconciliation for the PriceRadar India Cloud Agent environment.
#
# Starts the PostgreSQL cluster and Redis (both no-ops if already running), waits for them to
# accept connections, and applies any pending Alembic migrations. Long-running app servers
# (backend API, frontend dev server) run as named terminals, not here. Idempotent and safe on
# every boot.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DB_USER="priceradar_app"
DB_PASSWORD="changeme"
DB_NAME="priceradar"
export DATABASE_URL="postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}"

log() { printf '\n=== %s ===\n' "$*"; }

log "PostgreSQL"
PG_VERSION="$(ls /etc/postgresql 2>/dev/null | sort -V | tail -1 || true)"
if [ -n "$PG_VERSION" ]; then
  if ! sudo pg_ctlcluster "$PG_VERSION" main status >/dev/null 2>&1; then
    sudo pg_ctlcluster "$PG_VERSION" main start
  else
    echo "PostgreSQL cluster ${PG_VERSION}/main already running."
  fi
else
  echo "No PostgreSQL cluster found (expected it to be installed by install.sh)." >&2
fi

log "Redis"
if ! redis-cli ping >/dev/null 2>&1; then
  sudo redis-server /etc/redis/redis.conf --daemonize yes
else
  echo "Redis already running."
fi

log "Wait for services"
for _ in $(seq 1 30); do
  if pg_isready -h localhost -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then break; fi
  sleep 1
done
for _ in $(seq 1 30); do
  if redis-cli ping >/dev/null 2>&1; then break; fi
  sleep 1
done
pg_isready -h localhost -U "$DB_USER" -d "$DB_NAME"
redis-cli ping

# Apply migrations only when the backend venv exists (skipped during the first install pass,
# where install.sh runs migrations itself right after creating the venv).
if [ -x "$REPO_ROOT/backend/.venv/bin/alembic" ]; then
  log "Apply database migrations"
  (cd "$REPO_ROOT/backend" && ./.venv/bin/alembic upgrade head)
fi

log "Start complete"
