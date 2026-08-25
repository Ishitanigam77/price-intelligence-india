#!/bin/sh
# Container entrypoint: optionally applies Alembic migrations, then execs the given command
# (normally `uvicorn app.main:app ...`, see the Dockerfile's CMD).
#
# `RUN_DB_MIGRATIONS` defaults to "true" for local development convenience (docker compose).
# In a real deployment, migrations are typically run as their own release step against a single
# instance rather than on every replica's startup — set RUN_DB_MIGRATIONS=false there and run
# `alembic upgrade head` explicitly as part of the deployment pipeline instead.
set -e

if [ "${RUN_DB_MIGRATIONS:-true}" = "true" ]; then
    echo "docker-entrypoint: applying database migrations (alembic upgrade head)..."
    alembic upgrade head
fi

exec "$@"
