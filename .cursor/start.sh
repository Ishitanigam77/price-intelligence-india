#!/usr/bin/env bash
# Per-boot startup for the PriceRadar India Cloud Agent environment.
#
# 1. Reconciles infrastructure daemons (PostgreSQL + Redis) and applies pending migrations.
# 2. Launches the backend API (uvicorn, :8000) and the frontend dev server (Next.js, :3000) in
#    the background, each only if its port is not already serving.
# Idempotent and safe to run on every boot; returns after the servers are launched.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export DB_USER="priceradar_app"
DB_PASSWORD="changeme"
export DB_NAME="priceradar"
export DATABASE_URL="postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}"
export REDIS_URL="redis://localhost:6379/0"

LOG_DIR="/tmp/priceradar"
mkdir -p "$LOG_DIR"

log() { printf '\n=== %s ===\n' "$*"; }

# Infrastructure daemons + readiness.
bash "$REPO_ROOT/.cursor/services.sh"

# Apply migrations only when the backend venv exists (install.sh handles the first pass).
if [ -x "$REPO_ROOT/backend/.venv/bin/alembic" ]; then
  log "Apply database migrations"
  (cd "$REPO_ROOT/backend" && ./.venv/bin/alembic upgrade head)
fi

log "Backend API (uvicorn :8000)"
if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
  echo "Backend already serving on :8000."
elif [ -x "$REPO_ROOT/backend/.venv/bin/uvicorn" ]; then
  ( cd "$REPO_ROOT/backend" && \
    DATABASE_URL="$DATABASE_URL" REDIS_URL="$REDIS_URL" \
    setsid ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 \
      >"$LOG_DIR/backend.log" 2>&1 < /dev/null & )
  echo "Backend launched (logs: $LOG_DIR/backend.log)."
else
  echo "Backend venv not found; run .cursor/install.sh first." >&2
fi

log "Frontend dev server (Next.js :3000)"
if curl -sf http://localhost:3000/health >/dev/null 2>&1; then
  echo "Frontend already serving on :3000."
elif [ -d "$REPO_ROOT/frontend/node_modules" ]; then
  ( cd "$REPO_ROOT/frontend" && \
    NEXT_PUBLIC_API_BASE_URL="http://localhost:8000" \
    setsid npm run dev >"$LOG_DIR/frontend.log" 2>&1 < /dev/null & )
  echo "Frontend launched (logs: $LOG_DIR/frontend.log)."
else
  echo "Frontend node_modules not found; run .cursor/install.sh first." >&2
fi

log "Start complete"
