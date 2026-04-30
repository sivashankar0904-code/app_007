# ── Django core-api service ──────────────────────────────────────────────────
# Multi-stage build:
#   Stage 1 (builder): install deps into a venv
#   Stage 2 (runtime): copy venv only — smaller final image

# ─── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# System deps needed to compile psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps into /opt/venv  ← OUTSIDE /app
# WHY: /app is volume-mounted in dev, which would wipe anything built inside it.
#      /opt/venv is never mounted, so it survives the bind mount.
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ─── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime system dep for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy venv from builder — lives at /opt/venv, safe from volume mounts
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY . .

# Activate venv for all subsequent commands
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings

EXPOSE 8000

# Daphne = ASGI server (handles HTTP + WebSocket)
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
