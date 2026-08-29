# syntax=docker/dockerfile:1
#
# Production-oriented image for the PriceRadar India FastAPI backend.
#
# Multi-stage build: dependencies are compiled/installed in a throwaway `builder` stage, and only
# the resulting virtualenv + application source are copied into the slim runtime image. The
# container never bakes in secrets — all configuration (DATABASE_URL, REDIS_URL, ...) is supplied
# at runtime via environment variables (see `.env.example` at the repo root).

ARG PYTHON_VERSION=3.12-slim

# ---------------------------------------------------------------------------------------------
# Builder: install Python dependencies into an isolated virtualenv.
# ---------------------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# System build dependencies for psycopg[binary] wheels and friends.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# ---------------------------------------------------------------------------------------------
# Runtime: slim image with only the built virtualenv + application source.
# ---------------------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    API_HOST=0.0.0.0 \
    API_PORT=8000

# Upgrade the slim base so known-fixed OS CVEs (e.g. OpenSSL CVE-2026-14456) are not
# shipped in the scanned runtime image. Do not ignore those findings in Trivy.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY pyproject.toml ./pyproject.toml
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN chmod +x ./docker-entrypoint.sh && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail "http://localhost:${API_PORT}/health" || exit 1

# No secrets are baked in: DATABASE_URL, REDIS_URL, CORS_ALLOWED_ORIGINS, etc. are all read from
# the environment at container start (see `.env.example`).
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------------------------
# Worker: same runtime filesystem as the API, different process (Celery). Separate ACR image
# via `--target worker`. Migrations must not run on workers — set RUN_DB_MIGRATIONS=false.
# ---------------------------------------------------------------------------------------------
FROM runtime AS worker

ENV RUN_DB_MIGRATIONS=false

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=25s --retries=3 \
    CMD celery -A app.workers.celery_app inspect ping || exit 1

# Entrypoint is inherited; with RUN_DB_MIGRATIONS=false it only execs this command.
CMD ["celery", "-A", "app.workers.celery_app", "worker", "--loglevel=INFO"]

# ---------------------------------------------------------------------------------------------
# API: explicit target so `docker build` without `--target` is not the worker stage.
# Keep this last so the default image remains the FastAPI process.
# ---------------------------------------------------------------------------------------------
FROM runtime AS api
