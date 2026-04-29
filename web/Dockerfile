# ── Next.js frontend (standalone output) ────────────────────────────────────

# Stage 1: install deps
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# Stage 2: build
FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
# NEXT_PUBLIC_API_BASE_URL must be provided as a build arg so it is
# embedded in the client bundle.  Railway sets this via the "Variables" panel.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

ARG DEFAULT_TEAM_NAME=""
ARG DEFAULT_TEAM_TAG=""
ENV DEFAULT_TEAM_NAME=$DEFAULT_TEAM_NAME
ENV DEFAULT_TEAM_TAG=$DEFAULT_TEAM_TAG

RUN npm run build

# Stage 3: production runner
FROM node:20-slim AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Copy standalone build
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

# Writable directory for player avatar uploads
RUN mkdir -p public/players

EXPOSE 3000

CMD ["node", "server.js"]
