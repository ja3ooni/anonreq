# Demo UI only. No login. The process listens on 127.0.0.1.
# Do not set HOSTNAME to 0.0.0.0 or publish the port on all interfaces.
# Route handlers attach ANONREQ_API_KEY and ANONREQ_ADMIN_API_KEY.
# Anyone who can reach this app can export audit logs, see raw PII
# through the preview, and spend provider credits.
# A real login comes after the demo.

FROM node:22-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

ENV NODE_ENV=production
ENV HOSTNAME=127.0.0.1
EXPOSE 3000

# next start -H follows HOSTNAME. The default is 127.0.0.1.
# Overriding HOSTNAME is explicit and prints a warning.
CMD ["node", "scripts/docker-entrypoint.mjs"]
