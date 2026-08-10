"""Django application configuration."""

from django.apps import AppConfig


class WebConfig(AppConfig):
    """Configuration for the dashboard and device-control app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "web"
    verbose_name = "LED Controller Dashboard"

    def ready(self) -> None:
        from . import signals  # noqa: F401
