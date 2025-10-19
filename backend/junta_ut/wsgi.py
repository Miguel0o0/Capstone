# backend/junta_ut/wsgi.py
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "junta_ut.settings.prod")
application = get_wsgi_application()
