"""
Django settings for core-api service.
Reads all sensitive config from environment variables via django-environ.
"""

import environ
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

# ─── Core ─────────────────────────────────────────────────────────────────────
SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

# ─── Apps ─────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "channels",
    "rest_framework",
    "rest_framework_simplejwt",
    # Local apps
    "apps.orgs",
    "apps.users",
    "apps.chat",
    "apps.documents",
    "apps.ws",
]

# ─── Middleware ────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Tenant middleware sits AFTER auth — needs request.user
    "core.middleware.tenant.TenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ─── Templates ────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ─── Database ─────────────────────────────────────────────────────────────────
DATABASES = {
    "default": env.db("DATABASE_URL")
    # Example: postgres://user:pass@postgres:5432/app007
}

# ─── Redis / Channel Layer ────────────────────────────────────────────────────
REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")

# Django cache backend — used by health check and can be used for rate limiting
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    }
}

# ─── Celery ───────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

# ─── Auth ─────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "users.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
}

# ─── Static ───────────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── Internal service auth ────────────────────────────────────────────────────
# Shared secret between Django and FastAPI for internal API calls.
# FastAPI sends this in X-Internal-Key header when posting bot messages.
# WHY not JWT: internal service calls don't need user-level auth — a
#              shared secret is simpler and sufficient here.
INTERNAL_API_KEY = env("INTERNAL_API_KEY", default="dev-internal-key-change-in-prod")

# ─── Media (uploaded files) ────────────────────────────────────────────────────
# WHY MEDIA_ROOT on a shared volume:
#   Both Django (writes) and FastAPI (reads for ingestion) need access to uploaded files.
#   In Docker/K8s, both containers mount the same volume at /media.
#   Django writes to /media/documents/YYYY/MM/<filename>
#   FastAPI reads from the same path to extract text for RAG.
MEDIA_URL = "/media/"
# WHY /media (not BASE_DIR/"media"):
#   The shared Docker volume is mounted at /media in both core-api and ai-service.
#   Using BASE_DIR/"media" would write to /app/media — inside the app container only,
#   invisible to FastAPI. /media is the correct shared mount point.
MEDIA_ROOT = "/media"
