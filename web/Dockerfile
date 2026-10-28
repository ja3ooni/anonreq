# Demo UI. No login.
#
# Inside the container the server listens on 0.0.0.0 so Docker's port
# proxy can reach it. The host publish below is 127.0.0.1:3000:3000,
# which is what keeps the app off other machines.
# Never publish 0.0.0.0:3000. That would expose the gateway and admin
# keys this process attaches. Anyone who can reach it can export audit
# logs, see raw PII through the preview, and spend provider credits.

FROM node:22-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

ENV NODE_ENV=production
# 0.0.0.0 is the container interface, not the host. The compose file
# publishes that port only on the host's 127.0.0.1.
ENV HOSTNAME=0.0.0.0
EXPOSE 3000

CMD ["node", "scripts/docker-entrypoint.mjs"]
