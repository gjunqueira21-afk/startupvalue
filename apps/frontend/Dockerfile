# syntax=docker/dockerfile:1.7
FROM node:24.8.0-bookworm-slim AS dependencies
WORKDIR /workspace
COPY package.json package-lock.json* ./
COPY apps/frontend/package.json ./apps/frontend/package.json
RUN if [ -f package-lock.json ]; then npm ci; else npm install --workspaces --include-workspace-root; fi

FROM node:24.8.0-bookworm-slim AS builder
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /workspace
COPY --from=dependencies /workspace/node_modules ./node_modules
COPY package.json package-lock.json* ./
COPY apps/frontend ./apps/frontend
RUN mkdir -p apps/frontend/public \
    && npm run build --workspace apps/frontend

FROM node:24.8.0-bookworm-slim AS runtime
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
WORKDIR /app

RUN addgroup --system --gid 10001 startupvalue \
    && adduser --system --uid 10001 --ingroup startupvalue --home /nonexistent --no-create-home startupvalue

COPY --from=builder --chown=startupvalue:startupvalue /workspace/apps/frontend/.next/standalone ./
COPY --from=builder --chown=startupvalue:startupvalue /workspace/apps/frontend/.next/static ./apps/frontend/.next/static
COPY --from=builder --chown=startupvalue:startupvalue /workspace/apps/frontend/public ./apps/frontend/public
RUN if [ -f /app/server.js ]; then \
      mkdir -p /app/.next/static /app/public; \
      cp -R /app/apps/frontend/.next/static/. /app/.next/static/; \
      cp -R /app/apps/frontend/public/. /app/public/; \
    fi

USER 10001:10001
EXPOSE 3000

CMD ["sh", "-ec", "if [ -f apps/frontend/server.js ]; then exec node apps/frontend/server.js; else exec node server.js; fi"]
