"""
Root URL configuration.
Each app owns its own urls.py — we include them here.
"""

import time

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.db import connection, OperationalError
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    """
    Health check — inline in urls.py to avoid any module import issues.
    Checks PostgreSQL + Redis. Returns 200 healthy / 503 degraded.
    """
    start  = time.monotonic()
    checks = {}

    # PostgreSQL
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["postgres"] = "ok"
    except OperationalError as e:
        checks["postgres"] = f"error: {e}"

    # Redis
    try:
        from django.core.cache import cache
        cache.set("_health", "1", timeout=5)
        assert cache.get("_health") == "1"
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    healthy = all(v == "ok" for v in checks.values())
    return JsonResponse(
        {
            "status":     "healthy" if healthy else "degraded",
            "service":    "core-api",
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
            "checks":     checks,
        },
        status=200 if healthy else 503,
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    # Health check — inline, no auth, load balancers call this
    path("health/", health, name="health"),
    path("api/orgs/",      include("apps.orgs.urls")),
    path("api/users/",     include("apps.users.urls")),
    path("api/chat/",      include("apps.chat.urls")),
    path("api/documents/", include("apps.documents.urls")),
]

# Serve uploaded files in development
# WHY: Django doesn't serve media files by default — only in DEBUG mode via this helper.
# In production (K8s), NGINX or S3 handles /media/ — this line has no effect there.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
