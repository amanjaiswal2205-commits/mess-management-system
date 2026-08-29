from django.apps import AppConfig
import logging


logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import core.signals
        from django.conf import settings
        masked_user = (settings.EMAIL_HOST_USER or '')[:3] + '***' if settings.EMAIL_HOST_USER else 'not set'
        logger.info(
            "Email config | backend=%s | host=%s | port=%s | tls=%s | ssl=%s | user=%s | timeout=%s",
            settings.EMAIL_BACKEND,
            settings.EMAIL_HOST,
            settings.EMAIL_PORT,
            settings.EMAIL_USE_TLS,
            settings.EMAIL_USE_SSL,
            masked_user,
            settings.EMAIL_TIMEOUT,
        )
