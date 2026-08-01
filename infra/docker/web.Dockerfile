# syntax=docker/dockerfile:1.7
# Nuxt web app, built once and served by the Nitro node-server preset.
FROM node:24-bookworm-slim AS build

ENV PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH

WORKDIR /srv

RUN corepack enable

COPY pnpm-workspace.yaml package.json tsconfig.base.json /srv/
COPY apps/web/package.json /srv/apps/web/
COPY packages/domain/package.json /srv/packages/domain/

RUN pnpm install --filter @etsy/web... --prod=false --ignore-scripts

COPY packages/domain /srv/packages/domain
COPY apps/web /srv/apps/web

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

COPY --from=build --chown=appuser:appuser /srv/apps/web/.output /srv/.output

USER appuser
EXPOSE 3000

CMD ["node", ".output/server/index.mjs"]
