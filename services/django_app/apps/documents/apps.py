from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.documents"
    label = "documents"

    def ready(self):
        # Import signals here so they register when Django starts.
        # WHY in ready() and not at module level:
        #   Importing signals at module level causes AppRegistryNotReady errors
        #   because models may not be loaded yet. ready() is the safe place.
        import apps.documents.signals  # noqa: F401
