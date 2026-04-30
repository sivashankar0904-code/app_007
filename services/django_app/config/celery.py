"""
Celery application config.
Imported by Django via __init__.py so signals and tasks auto-discover.
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("core_api")

# Read config from Django settings — keys prefixed CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all INSTALLED_APPS
app.autodiscover_tasks()
