# backend/junta_ut/asgi.py
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "junta_ut.settings.prod")
application = get_asgi_application()
