from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        """Import signals when the app is ready."""
        try:
            from . import signals
        except ImportError:
            pass
        try:
            # This ensures the extension gets loaded
            import accounts.spectacular_extensions
        except ImportError:
            pass
