# syntax=docker/dockerfile:1
#
# Production image for PriceRadar India ML (sale-price training job + liveness probe).
#
# Build from the repository root:
#   docker build -f ml/Dockerfile -t priceradar/ml:local .
#
# The ML package is used by the backend for inference; this image exists so CI can version,
# scan, and run training as its own ACR repository. Predictions are not served here.
#
# No secrets are baked in. DATABASE_URL / ML_MODEL_ARTIFACT_PATH come from the environment
# or Key Vault at runtime.

ARG PYTHON_VERSION=3.12-slim

# ---------------------------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY backend/pyproject.toml ./backend/pyproject.toml
COPY backend/app ./backend/app
COPY ml ./ml

WORKDIR /build/backend
RUN pip install --no-cache-dir ".[ml]"

# ---------------------------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH="/app:/app/backend" \
    ML_HEALTH_HOST=0.0.0.0 \
    ML_HEALTH_PORT=8080 \
    RUN_DB_MIGRATIONS=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY ml ./ml
COPY backend/app ./backend/app
COPY backend/alembic ./backend/alembic
COPY backend/alembic.ini ./backend/alembic.ini
COPY backend/scripts ./backend/scripts
COPY backend/pyproject.toml ./backend/pyproject.toml

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl --fail "http://127.0.0.1:${ML_HEALTH_PORT}/health" || exit 1

# Default: liveness server for the deployed ML service. Override in CI/CD to train:
#   python -m scripts.train_sale_price_model   (working directory /app/backend)
WORKDIR /app/backend
CMD ["python", "/app/ml/health_server.py"]
