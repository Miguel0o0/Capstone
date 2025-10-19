# backend/junta_ut/settings/prod.py
from .base import *
import os
from django.core.exceptions import ImproperlyConfigured

DEBUG = False

# Exigir SECRET_KEY real en producción
if os.getenv("SECRET_KEY") in (None, "", "dev-insecure-key"):
    raise ImproperlyConfigured("SECRET_KEY debe definirse en .env para producción")

# Define tus hosts de despliegue
if not ALLOWED_HOSTS:
    # Ejemplo: "mi-dominio.com, www.mi-dominio.com"
    ALLOWED_HOSTS = []

# (Opcional) endurecer seguridad:
SECURE_BROWSER_XSS_FILTER = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"
