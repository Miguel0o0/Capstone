from .base import *  # noqa: F401,F403
import os

# ---------------------------------------
# DEBUG / HOSTS
# ---------------------------------------
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# ---------------------------------------
# BASE DE DATOS (PostgreSQL local JuntaUT)
# ---------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "junta_ut"),
        "USER": os.environ.get("DB_USER", "juntaut_superuser"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        "OPTIONS": {},
    }
}

# Si en .env pones DB_SSL=1, forzamos sslmode=require (para Railway/Render, etc.)
if os.environ.get("DB_SSL", "0") == "1":
    DATABASES["default"]["OPTIONS"]["sslmode"] = "require"

# ---------------------------------------
# EMAIL / SMTP (lo que ya tenías)
# ---------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True

# Cuenta Gmail que creaste para la Junta
EMAIL_HOST_USER = "utjunta@gmail.com"       
EMAIL_HOST_PASSWORD = "nase ylwz fxms gmgx"  

# Remitente por defecto (lo que verá el vecino como "De:")
DEFAULT_FROM_EMAIL = "Junta UT <utjunta@gmail.com>"
