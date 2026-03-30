"""AppConfig for the news application."""

from django.apps import AppConfig


class NewsConfig(AppConfig):
    """Configuration class that connects signals on app ready."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'news'

    def ready(self):
        """Import signals so they register with Django's dispatcher."""
        import news.signals  # noqa: F401
