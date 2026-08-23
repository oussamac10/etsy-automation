# syntax=docker/dockerfile:1.7
# Nuxt web app: multi-stage build supporting both local dev HMR and production runtime.
FROM node:24-bookworm-slim AS dev

ENV PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH \
    HOST=0.0.0.0 \
    PORT=3000

WORKDIR /srv

RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/* \
    && corepack enable


COPY pnpm-workspace.yaml package.json tsconfig.base.json /srv/
COPY frontend/package.json /srv/frontend/
COPY packages/domain/package.json /srv/packages/domain/

RUN pnpm install --filter @etsy/web... --prod=false --ignore-scripts

COPY packages/domain /srv/packages/domain
COPY frontend /srv/frontend

EXPOSE 3000

CMD ["pnpm", "--filter", "@etsy/web", "dev", "--host", "0.0.0.0"]


FROM dev AS build

RUN pnpm --filter @etsy/web exec nuxt build


FROM node:24-bookworm-slim AS runtime

ENV NODE_ENV=production \
    NITRO_PORT=3000 \
    NITRO_HOST=0.0.0.0

WORKDIR /srv

RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home appuser

COPY --from=build --chown=appuser:appuser /srv/frontend/.output /srv/.output

USER appuser
EXPOSE 3000

CMD ["node", ".output/server/index.mjs"]
