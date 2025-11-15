# backend/junta_ut/settings/dev.py
from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# --- EMAIL / SMTP ---

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True

# Cuenta Gmail que creaste para la Junta
EMAIL_HOST_USER = "utjunta@gmail.com"          # <-- pon aquí el correo
EMAIL_HOST_PASSWORD = "zqps fkfm zmse qqyq"       # <-- contraseña de aplicación, NO la normal

# Remitente por defecto (lo que verá el vecino como "De:")
DEFAULT_FROM_EMAIL = "Junta UT <utjunta@gmail.com>"

