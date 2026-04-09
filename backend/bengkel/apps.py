from django.apps import AppConfig


class BengkelConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bengkel"
    verbose_name = "Pengurusan Bengkel"

    def ready(self):
        import bengkel.signals  # noqa: F401
