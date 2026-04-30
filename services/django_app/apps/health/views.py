"""
Health check view — core-api.

Checks:
  - PostgreSQL : executes a trivial query
  - Redis      : sends PING via channel layer

Returns 200 if all healthy, 503 if any check fails.
503 is the correct HTTP status for a degraded service —
load balancers and K8s use this to pull the pod from rotation.
"""
import time

from django.db import connection, OperationalError
from django.core.cache import cache
from django.http import JsonResponse


def health(request):
    start  = time.monotonic()
    checks = {}

    # ── PostgreSQL ─────────────────────────────────────────────────────────────
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["postgres"] = "ok"
    except OperationalError as e:
        checks["postgres"] = f"error: {e}"

    # ── Redis ──────────────────────────────────────────────────────────────────
    try:
        from django.core.cache import cache
        cache.set("_health_probe", "1", timeout=5)
        assert cache.get("_health_probe") == "1"
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    healthy     = all(v == "ok" for v in checks.values())
    status_code = 200 if healthy else 503

    return JsonResponse(
        {
            "status":     "healthy" if healthy else "degraded",
            "service":    "core-api",
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
            "checks":     checks,
        },
        status=status_code,
    )
