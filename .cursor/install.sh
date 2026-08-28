#!/usr/bin/env bash
# Idempotent repository bootstrap for the PriceRadar India Cloud Agent environment.
#
# Prepares everything tied to the checked-out source: system service packages (guarded so a
# prebuilt snapshot that already has them is a no-op), local .env files, the PostgreSQL
# role/databases, the backend virtualenv + Python deps, the frontend Node deps, and the Alembic
# schema. Safe to re-run: every step checks current state before acting.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export DB_USER="priceradar_app"
DB_PASSWORD="changeme"
export DB_NAME="priceradar"
DB_TEST_NAME="priceradar_test"
export DATABASE_URL="postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}"
export REDIS_URL="redis://localhost:6379/0"

log() { printf '\n=== %s ===\n' "$*"; }

log "System packages"
NEED_PKGS=()
command -v pg_ctlcluster >/dev/null 2>&1 || NEED_PKGS+=(postgresql postgresql-contrib)
command -v redis-server  >/dev/null 2>&1 || NEED_PKGS+=(redis-server)
python3 -c 'import venv, ensurepip' >/dev/null 2>&1 || NEED_PKGS+=(python3-venv)
command -v gcc >/dev/null 2>&1 || NEED_PKGS+=(build-essential)
dpkg -s libpq-dev >/dev/null 2>&1 || NEED_PKGS+=(libpq-dev)
if [ "${#NEED_PKGS[@]}" -gt 0 ]; then
  sudo apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "${NEED_PKGS[@]}"
else
  echo "All required system packages already present."
fi

log "Local env files"
[ -f .env ] || cp .env.example .env
[ -f frontend/.env.local ] || cp frontend/.env.example frontend/.env.local

# PostgreSQL and Redis must be running so migrations can be applied during install.
bash "$REPO_ROOT/.cursor/services.sh"

log "PostgreSQL role and databases"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';
  END IF;
END
\$\$;
SQL
for db in "$DB_NAME" "$DB_TEST_NAME"; do
  if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${db}'" | grep -q 1; then
    sudo -u postgres createdb "$db" --owner="$DB_USER"
  fi
done

log "Backend virtualenv + dependencies"
cd "$REPO_ROOT/backend"
[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"

log "Apply database migrations"
alembic upgrade head
deactivate

log "Frontend dependencies"
cd "$REPO_ROOT/frontend"
npm ci

log "Install complete"
