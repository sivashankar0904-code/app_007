###############################################################################
# Frontend — Vite + React dev server
#
# WHY dev server in Docker (not production build):
#   This is a learning/dev environment. Vite's dev server gives us HMR
#   (hot module replacement) — code changes reflect instantly without rebuild.
#   Production would use `vite build` + nginx to serve static files.
###############################################################################

FROM node:20-alpine

WORKDIR /app

# Install dependencies first (layer cached unless package.json changes)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source — in docker-compose we mount ./services/frontend:/app
# so this layer is only used on first build; live edits come from the volume
COPY . .

EXPOSE 5173

# --host 0.0.0.0 — required so Vite listens on all interfaces inside Docker,
# not just localhost (which would be unreachable from the host)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
