# backend/junta_ut/settings/dev.py
from .base import *

DEBUG = True
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# Opcional: correo en consola, etc.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
