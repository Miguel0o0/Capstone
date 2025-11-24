# backend/junta_ut/settings/prod.py
import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403,F401


# ---------------------------------------
# DEBUG
# ---------------------------------------
DEBUG = False

# Exigir SECRET_KEY real en producción
if os.getenv("SECRET_KEY") in (None, "", "dev-insecure-key"):
    raise ImproperlyConfigured("SECRET_KEY debe definirse en .env para producción")


# ---------------------------------------
# ALLOWED_HOSTS (Render + opcional env)
# ---------------------------------------
# Prioridad:
#   1) ALLOWED_HOSTS desde variable de entorno (separados por coma)
#   2) RENDER_EXTERNAL_HOSTNAME (lo pone Render automáticamente)
#   3) localhost (fallback)
allowed_hosts_env = os.getenv("ALLOWED_HOSTS")
render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME")

if allowed_hosts_env:
    ALLOWED_HOSTS = [
        h.strip()
        for h in allowed_hosts_env.split(",")
        if h.strip()
    ]
elif render_host:
    ALLOWED_HOSTS = [render_host]
else:
    ALLOWED_HOSTS = ["localhost"]  # Fallback de seguridad mínima


# ---------------------------------------
# BASE DE DATOS (extiende lo de base.py)
# ---------------------------------------
# En base.py ya se configuran NAME, USER, PASSWORD, HOST, PORT y OPTIONS.
# Aquí solo afinamos cosas para producción (conexión persistente y SSL opcional).

# Tiempo de conexión persistente (para mejorar performance)
DATABASES["default"]["CONN_MAX_AGE"] = int(os.environ.get("DB_CONN_MAX_AGE", "60"))

# Si en Render pones DB_SSL=1, forzamos sslmode=require (útil con Supabase)
if os.environ.get("DB_SSL", "0") == "1":
    # Nos aseguramos de no pisar otras opciones que ya puedas tener
    db_options = DATABASES["default"].get("OPTIONS", {})
    db_options["sslmode"] = "require"
    DATABASES["default"]["OPTIONS"] = db_options


# ---------------------------------------
# SEGURIDAD ADICIONAL
# ---------------------------------------
SECURE_BROWSER_XSS_FILTER = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

# Configuración de EMAIL para producción (Render)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") == "1"

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    EMAIL_HOST_USER or "no-reply@junta-ut.example"
)

# ==========================================
# Email en producción: SendGrid + Anymail
# ==========================================

# Backend de email: usa la API HTTP de SendGrid (no SMTP)
EMAIL_BACKEND = "anymail.backends.sendgrid.EmailBackend"

# Configuración de Anymail para SendGrid
ANYMAIL = {
    "SENDGRID_API_KEY": os.getenv("SENDGRID_API_KEY"),
}

# Remitente por defecto (debe estar verificado en SendGrid)
DEFAULT_FROM_EMAIL = os.getenv(
    "Junta UT <utjunta@gmail.com>",  # o el que hayas verificado
)