# CLAUDE.md — Infrastructure

These rules extend the root instructions for `infra` and deployment files.

## Local environment

Docker Compose must provide:

- web
- api
- worker
- PostgreSQL
- Redis
- MinIO

Add health checks and named volumes. Development starts with one documented command and no paid API keys; fake providers are the default.

## Deployment

- Separate web, API, and worker processes.
- Managed PostgreSQL and S3-compatible storage are preferred in production.
- Redis persistence is not the system of record.
- Run migrations as an explicit release job, not implicitly in every replica.
- Use encrypted secret management, TLS, backups, and restore tests.
- Pin container base images and application dependencies.
- Containers run as non-root with read-only root filesystems where practical.
- Set CPU, memory, timeout, concurrency, and upload limits.

## Environments

- `local`: fake providers by default
- `staging`: sandbox/test shop and strict low budget
- `production`: real providers, manual gates, alerts, backups

Never share provider credentials or OAuth redirect URIs across environments.

## CI

CI runs formatting, lint, type checks, unit tests, integration tests, migration checks, dependency audit, secret scan, container build, and Compose validation. CI must never call paid APIs or create Etsy resources.
