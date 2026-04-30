"""
ASGI config for core-api.
Django Channels replaces the default ASGI app — HTTP + WebSocket handled here.
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Must be called before any app imports
django_asgi_app = get_asgi_application()

# Import ws urls AFTER django setup
from apps.ws import routing  # noqa: E402

application = ProtocolTypeRouter(
    {
        # HTTP → normal Django views
        "http": django_asgi_app,
        # WebSocket → Django Channels consumers
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(routing.websocket_urlpatterns))
        ),
    }
)
