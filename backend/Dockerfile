# syntax=docker/dockerfile:1.7
# FastAPI service.
FROM python:3.12-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# curl is required by the Compose health check.
RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml /srv/backend/pyproject.toml
COPY backend/app /srv/backend/app
COPY workers/general-worker/pyproject.toml /srv/workers/general-worker/pyproject.toml
COPY workers/general-worker/worker /srv/workers/general-worker/worker
COPY backend/alembic.ini /srv/backend/alembic.ini
COPY backend/migrations /srv/backend/migrations

RUN pip install --no-cache-dir /srv/backend /srv/workers/general-worker

# Non-root by default.
RUN useradd --system --uid 10001 --create-home appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
