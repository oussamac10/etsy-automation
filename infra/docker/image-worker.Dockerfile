# syntax=docker/dockerfile:1.7
# Node/Sharp image service.
FROM node:24-bookworm-slim AS base

ENV NODE_ENV=production \
    PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH

WORKDIR /srv

RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/* \
    && corepack enable

COPY pnpm-workspace.yaml package.json tsconfig.base.json /srv/
COPY apps/image-worker/package.json /srv/apps/image-worker/
COPY packages/domain/package.json /srv/packages/domain/
COPY packages/image-pipeline/package.json /srv/packages/image-pipeline/

# --ignore-scripts is unsafe for sharp (it needs its platform binary), so the
# allowBuilds list in pnpm-workspace.yaml is what limits install scripts here.
RUN pnpm install --filter @etsy/image-worker... --prod=false

COPY packages/domain /srv/packages/domain
COPY packages/image-pipeline /srv/packages/image-pipeline
COPY apps/image-worker /srv/apps/image-worker

RUN useradd --system --uid 10001 --create-home appuser \
    && chown -R appuser:appuser /srv
USER appuser

WORKDIR /srv/apps/image-worker
EXPOSE 8100

CMD ["pnpm", "start"]
