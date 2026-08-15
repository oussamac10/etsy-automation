# Project Architecture Refactor

This document tracks the repository organization cleanup, refactoring, and directory structure changes executed in Stage 2.

## Why Restructuring Was Needed

1. **Service Boundaries**: The original `apps/` directory grouped backend APIs, background queue workers, Node.js image-processing services, and user interfaces under a single folder. This created ambiguity regarding service boundaries and responsibilities.
2. **Nesting Overhead**: The Python backend (`apps/api`) and worker (`apps/worker`) used a nested `src/app/` layout. Removing `src/` flattens the structure and simplifies linting, static analysis, typechecking, and packaging.
3. **Detached Lifecycles**: alembic migrations were hidden inside the API package instead of being represented as top-level database lifecycle tasks. Playwright E2E tests were located in a root-level `tests/e2e` directory, separating them from the root structures.

## Old-to-New Directory Mapping

| Old Path | New Path | Description |
| --- | --- | --- |
| `apps/api/src/app` | `backend/app` | Flat Python backend application |
| `apps/api/alembic` | `backend/migrations` | Database migrations |
| `apps/api/tests` | `backend/tests` | Backend unit & integration tests |
| `apps/worker/src/worker` | `workers/general-worker/worker` | Background Dramatiq tasks |
| `apps/image-worker` | `workers/image-worker` | Fastify Sharp image server |
| `apps/web` | `frontend` | Nuxt web application |
| `infra/docker/api.Dockerfile` | `backend/Dockerfile` | Backend Docker target |
| `infra/docker/web.Dockerfile` | `frontend/Dockerfile` | Web client Docker target |
| `infra/docker/image-worker.Dockerfile` | `workers/image-worker/Dockerfile` | Image processor Docker target |
| `infra/` | `infrastructure/` | System-wide local and CI rules |

## Directory Responsibilities

### `backend/`

Contains the Python FastAPI server. It implements Clean Architecture:

- `domain/`: Pure business entities and validations.
- `application/`: Application use cases, command validation, and UnitOfWork orchestration.
- `ports/`: Standard interfaces for storage, external APIs, and gateways.
- `infrastructure/`: Implementations of ports (SQLAlchemy, S3 client, Redis broker, encryption).
- `presentation/api/`: FastAPI route configurations, JSON-schemas, and error definitions.

### `frontend/`

Contains the Nuxt 3 web client. Built following standard Nuxt directory layout:

- `components/`: UI components.
- `composables/`: Reusable runtime functions and API request helpers.
- `pages/`: File-based route components.
- `stores/`: Pinia state definitions.

### `workers/`

Contains background queues and asynchronous tasks:

- `general-worker/`: Python Dramatiq consumer that processes long-running workflows.
- `image-worker/`: Node.js worker optimizing and validating output PNG files.

### `infrastructure/`

Contains environment instructions, custom MCP definitions, and base Docker constraints.

### `packages/`

Shared libraries in the monorepo:

- `domain/`: Shared TS workflow dictionary and tag models.
- `image-pipeline/`: Shared TS validation logic using Sharp.

### `tests/`

Root integration and E2E validation:

- `e2e/`: Playwright E2E tests.

---

## Configuration Changes

1. **`pnpm-workspace.yaml`**: Updated to discover packages in `frontend` and `workers/image-worker`.
2. **`compose.yaml`**: Build contexts are updated to match the flat structure; the migration task has its `working_dir` set to `/srv/backend`.
3. **`pyproject.toml` (backend & worker)**: Ruff targets set to `[".", "tests"]` and mypy lookup set to `.`. Mypy lookup for `general-worker` incorporates `../../backend` to successfully resolve imports from the `app` package.
4. **`alembic.ini`**: `script_location` changed from `alembic` to `migrations`; `prepend_sys_path` changed from `src` to `.`.
5. **`.github/workflows/ci.yml`**: Actions steps corrected to reflect new paths for Ruff, mypy, pytest, and pip installations.

---

## Verification Results

All verification suites ran successfully:

- **Backend Tests**: 419 passed (unit & integration)
- **General Worker Tests**: 23 passed
- **Frontend/TypeScript Tests**: 67 passed
- **Playwright E2E Tests**: 11 passed
- **Alembic migrations**: Full downgrade and upgrade cycle completed cleanly.
- **Fixture loading**: Seeded successfully.
- **Docker validation**: All images build successfully.
- **Linter & Formatter**: All files pass ruff check/format and eslint.
- **Type Checking**: Mypy and vue-tsc pass with zero errors.

## Roadmap Alignment

Phase 1, Phase 2, and Phase 3 features remain fully completed and validated. Phase 4 has not been started.
