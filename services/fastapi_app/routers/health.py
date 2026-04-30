"""
Health check endpoint — ai-service.

Checks:
  - Redis  : can we reach the broker / stream store?

WHY real checks: returning {"status": "ok"} unconditionally is useless.
K8s readiness probes and docker-compose healthchecks need a response that
reflects actual dependency health, not just "the process is running".
"""
import os
import time

import redis.asyncio as aioredis
from fastapi import APIRouter

router = APIRouter(tags=["health"])

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


@router.get("/health")
async def health_check():
    start = time.monotonic()
    checks = {}

    # ── Redis ──────────────────────────────────────────────────────────────────
    try:
        client = aioredis.from_url(REDIS_URL, socket_connect_timeout=2)
        await client.ping()
        await client.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # ── Overall ────────────────────────────────────────────────────────────────
    healthy = all(v == "ok" for v in checks.values())
    return {
        "status":   "healthy" if healthy else "degraded",
        "service":  "ai-service",
        "latency_ms": round((time.monotonic() - start) * 1000, 1),
        "checks":   checks,
    }
