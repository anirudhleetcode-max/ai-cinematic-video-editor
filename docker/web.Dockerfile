# Cutroom web app (Next.js standalone server).
#   docker build -f docker/web.Dockerfile --build-arg NEXT_PUBLIC_API_URL=https://api.example.com -t cutroom-web .
# NEXT_PUBLIC_API_URL is compiled into the browser bundle; it is the only configuration the web app has (no secrets).
ARG BASE=mirror.gcr.io/library/node:22-bookworm-slim

FROM ${BASE} AS build
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web ./
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run lint && npm run build

FROM ${BASE}
WORKDIR /web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build --chown=node /web/.next/standalone ./
COPY --from=build --chown=node /web/.next/static ./.next/static
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s CMD node -e "fetch('http://localhost:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.js"]
