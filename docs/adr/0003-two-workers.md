# ADR-0003 — Two worker processes: a Python queue worker and a Node image service

- **Status**: Accepted
- **Date**: 2026-08-01
- **Phase**: 1

## Context

The root CLAUDE.md specifies a Python queue (Redis plus Dramatiq or Celery) and,
separately, "image processing: Node.js TypeScript service using Sharp and SVG
templates". The repository already contained `apps/worker/CLAUDE.md` describing
a background worker that runs research, generation, packaging and Etsy calls,
while `packages/image-pipeline/CLAUDE.md` describes the Sharp pipeline.

The Phase 1 request also asked for `apps/image-worker`. These are two different
things, and collapsing them would mean either running the domain in Node or
running Sharp from Python.

## Decision

Ship **both**:

- `apps/worker` — Python, Dramatiq. Consumes the queue, runs research, artwork
  generation, packaging and Etsy calls, and owns retry and idempotency policy.
  It shares the domain, ports and settings with `apps/api` by installing the
  `etsy-automation-api` package from the same repository.
- `apps/image-worker` — Node 24, Fastify, calling `@etsy/image-pipeline`
  (Sharp). An HTTP service the API and the Python worker call for image
  validation, inspection and, from Phase 6, trimming, typography and mockups.

## Why

- **Sharp is a Node library.** libvips bindings, SVG rendering and the
  typography pipeline all live in the Node ecosystem. Reimplementing them in
  Python, or shelling out to a CLI, would be worse in both directions.
- **The domain is Python.** Workflow invariants, cost calculation and provider
  orchestration belong next to the API's domain model, not duplicated across
  runtimes.
- **Different failure modes deserve different processes.** A malformed image can
  exhaust memory in libvips. Isolating that in its own container keeps a decode
  bomb from taking down job orchestration, and lets the two scale independently.
- **The boundary is already a port.** `ImageProcessingProvider` is an interface;
  whether it is satisfied in-process or over HTTP is an implementation detail
  the domain never sees.

## Consequences

- One extra service in Compose and in deployment, with its own health check.
- An HTTP hop for image work, so the contract between the API and the image
  worker must be explicit and versioned. Large payloads move by object-storage
  key rather than by request body.
- Two dependency ecosystems to keep current — already true, since the web app is
  Node and the API is Python.
- `apps/worker` and `apps/api` share one virtualenv in development. The worker
  declares no runtime dependency on PyPI for `etsy-automation-api`; both are
  installed editable from the repository.

## Alternatives considered

- **One Node worker for everything** — would move the domain into TypeScript,
  contradicting the stack decision and duplicating the state machine.
- **One Python worker calling Sharp via a subprocess** — fragile process
  management, no type safety across the boundary, and worse error reporting than
  an HTTP contract.
- **Python imaging (Pillow/pyvips) instead of Sharp** — possible, but the
  project specifies Sharp and SVG templates, and the typography path depends on
  deterministic SVG rendering.
