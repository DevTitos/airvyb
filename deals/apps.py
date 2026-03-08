from django.apps import AppConfig


class DealsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'deals'

    def ready(self):
        """Import signals when app is ready"""
        try:
            import deals.signals  # noqa
        except ImportError:
            pass