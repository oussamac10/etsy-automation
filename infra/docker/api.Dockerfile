# syntax=docker/dockerfile:1.7
# FastAPI service. Also used for the Dramatiq worker (same code, different CMD).
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

COPY apps/api/pyproject.toml /srv/apps/api/pyproject.toml
COPY apps/api/src /srv/apps/api/src
COPY apps/worker/pyproject.toml /srv/apps/worker/pyproject.toml
COPY apps/worker/src /srv/apps/worker/src
COPY apps/api/alembic.ini /srv/apps/api/alembic.ini
COPY apps/api/alembic /srv/apps/api/alembic

RUN pip install --no-cache-dir /srv/apps/api /srv/apps/worker

# Non-root by default (infra/CLAUDE.md).
RUN useradd --system --uid 10001 --create-home appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
