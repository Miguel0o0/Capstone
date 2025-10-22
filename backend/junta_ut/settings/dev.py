# backend/junta_ut/settings/dev.py
from .base import *

DEBUG = True
if not ALLOWED_HOSTS:  # noqa: F405
    ALLOWED_HOSTS = ["127.0.0.1", "localhost"]  # noqa: F405

# Opcional: correo en consola, etc.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = "no-reply@localhost"
