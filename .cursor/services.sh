#!/usr/bin/env bash
# Bring up the PriceRadar India infrastructure daemons (PostgreSQL + Redis) and wait until they
# accept connections. Idempotent: starting an already-running service is a no-op. Returns once
# both are ready. Shared by install.sh and start.sh.
set -euo pipefail

DB_USER="${DB_USER:-priceradar_app}"
DB_NAME="${DB_NAME:-priceradar}"

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
  echo "No PostgreSQL cluster found yet." >&2
fi

log "Redis"
if ! redis-cli ping >/dev/null 2>&1; then
  sudo redis-server /etc/redis/redis.conf --daemonize yes
else
  echo "Redis already running."
fi

log "Wait for readiness"
for _ in $(seq 1 30); do
  pg_isready -h localhost -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1 && break
  sleep 1
done
for _ in $(seq 1 30); do
  redis-cli ping >/dev/null 2>&1 && break
  sleep 1
done
pg_isready -h localhost -U "$DB_USER" -d "$DB_NAME"
redis-cli ping
