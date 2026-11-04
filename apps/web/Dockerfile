FROM node:24-bookworm-slim@sha256:c86ecead9e55a5210ac1727de38a4ca840bf03dcaf34dc9749addbf383b1920c AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 API_URL=http://api:8000
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web .
RUN npm run build && node node_modules/typescript/bin/tsc next.config.ts --target es2020 --module esnext --moduleResolution bundler --skipLibCheck --outDir /tmp/next-config && cp /tmp/next-config/next.config.js next.config.mjs && npm prune --omit=dev

FROM node:24-bookworm-slim@sha256:c86ecead9e55a5210ac1727de38a4ca840bf03dcaf34dc9749addbf383b1920c
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build --chown=node:node /app/package*.json ./
COPY --from=build --chown=node:node /app/node_modules ./node_modules
COPY --from=build --chown=node:node /app/.next-v1 ./.next-v1
COPY --from=build --chown=node:node /app/public ./public
COPY --from=build --chown=node:node /app/next.config.mjs ./next.config.mjs
USER node
CMD ["node", "node_modules/next/dist/bin/next", "start", "--hostname", "0.0.0.0", "--port", "3000"]
