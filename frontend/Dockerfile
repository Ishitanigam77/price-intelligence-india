# syntax=docker/dockerfile:1
#
# Production image for the PriceRadar India Next.js frontend.
#
# Multi-stage: install dependencies, produce the standalone Next.js build, then copy only the
# standalone server into a minimal runtime image. Runs as a non-root user.
#
# Secrets are never baked in. CLERK_SECRET_KEY and other server-only values are supplied at
# runtime. NEXT_PUBLIC_* values are inlined by Next.js at build time by design (they are
# browser-visible); pass them as build-args from CI, never as committed credentials.

ARG NODE_VERSION=22-alpine

# ---------------------------------------------------------------------------------------------
# Dependencies: install from the lockfile for a deterministic tree.
# ---------------------------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS deps

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

# ---------------------------------------------------------------------------------------------
# Builder: compile the Next.js standalone output.
# ---------------------------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS builder

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Public (browser-visible) configuration only. Never pass CLERK_SECRET_KEY as a build-arg.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
ARG NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
ARG NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up

ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} \
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY} \
    NEXT_PUBLIC_CLERK_SIGN_IN_URL=${NEXT_PUBLIC_CLERK_SIGN_IN_URL} \
    NEXT_PUBLIC_CLERK_SIGN_UP_URL=${NEXT_PUBLIC_CLERK_SIGN_UP_URL}

RUN mkdir -p public && npm run build

# ---------------------------------------------------------------------------------------------
# Runtime: standalone Node server, non-root.
# ---------------------------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS runner

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Apply Alpine security updates so known-fixed OS CVEs are not shipped in the runtime image.
RUN apk upgrade --no-cache \
    && addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 --ingroup nodejs nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000/health').then((r)=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
