"""
WSGI config — used only for admin/manage.py runserver fallback.
Production traffic goes through ASGI (daphne).
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
