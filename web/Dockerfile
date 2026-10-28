# Demo UI. No login.
#
# Inside the container the server listens on 0.0.0.0 so Docker's port
# proxy can reach it. The compose publish is 127.0.0.1:3000:3000, which
# is what keeps the app off other machines.
# Never publish 0.0.0.0:3000. That would expose the gateway and admin
# keys this process attaches. Anyone who can reach it can export audit
# logs, see raw PII through the preview, and spend provider credits.
#
# Targets:
#   runtime (default) - production, Next standalone output, no devDependencies.
#   dev               - NODE_ENV=development `next dev`, used only by the mock override.

FROM node:22-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS dev
COPY . .
ENV NODE_ENV=development
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
EXPOSE 3000
CMD ["sh", "-c", "exec npx next dev -H \"$HOSTNAME\" --port \"$PORT\""]

FROM deps AS build
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# 0.0.0.0 is the container interface, not the host. The compose file
# publishes that port only on the host's 127.0.0.1.
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
# Standalone output bundles only the runtime node_modules it traces.
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/scripts/docker-entrypoint.mjs ./scripts/docker-entrypoint.mjs
USER node
EXPOSE 3000
CMD ["node", "scripts/docker-entrypoint.mjs"]
