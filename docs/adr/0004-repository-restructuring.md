# ADR 0004: Repository Restructuring and Flattening

## Status

Accepted

## Context

The repository contains multiple services written in Python (FastAPI, Dramatiq worker) and Node.js/TypeScript (Nuxt frontend, Fastify image-worker). These services, as well as shared packages, were originally grouped into a single, generic `apps/` directory.

Additionally:

- Python services utilized a nested `src/app/` layout, causing typechecking and runtime import configurations to be unnecessarily complex and deeply nested.
- Database migrations and Docker configuration directories were nested deep inside package structures or placed in isolated stubs, reducing visibility into core lifecycle artifacts.

## Decision

Refactor the root directory tree to clearly separate projects by domain and flatten nesting levels where appropriate:

1. **Top-level Directories**:
   - `backend/`: Hosts the FastAPI backend application.
   - `frontend/`: Hosts the Nuxt 3 web client.
   - `workers/`: Holds decoupled background task servers (`general-worker` and `image-worker`).
   - `infrastructure/`: Houses global environment constraints and orchestration files.
   - `tests/e2e/`: Root-level Playwright integration tests.

2. **Flattening of Python Apps**:
   - Relocate `backend/src/app` to `backend/app`.
   - Relocate `workers/general-worker/src/worker` to `workers/general-worker/worker`.
   - Update setuptools packaging configs, Ruff targets, and Mypy path-mappings to resolve modules from `.`.

3. **Migrations & Docker isolation**:
   - Re-route Alembic configuration to manage scripts inside `backend/migrations/` rather than a local subfolder.
   - Retain Dockerfiles inside their respective service directories (`backend/Dockerfile`, etc.) to align build contexts.

## Consequences

- **Simplified Imports**: Backend developer imports remain `from app.api...` and `from app.domain...` without needing `src.` prefix paths or nested python path configurations in linting tools.
- **Improved Maintainability**: Service responsibilities are clearly demarcated. Frontend and backend developers can navigate directly to their respective domains.
- **Testing Alignment**: Parent resolving logic in tests is simplified (from 3 levels to 2 levels relative to the workspace root).
