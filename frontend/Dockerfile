FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
# Rewrites are resolved at build time: the API origin must be known here.
ARG CM_API_ORIGIN=http://backend:8000
ENV CM_API_ORIGIN=$CM_API_ORIGIN
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# Runtime: only the standalone server (output: "standalone" traces the production dependencies it needs), the static
# assets and public/. No node_modules from the build stage, no dev dependencies, no npm; runs as the non-root `node`.
FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
