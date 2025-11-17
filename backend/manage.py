#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def main():
    """Run administrative tasks."""
    # Cargar variables desde backend/.env (misma carpeta que manage.py)
    BASE_DIR = Path(__file__).resolve().parent
    load_dotenv(BASE_DIR / ".env")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "junta_ut.settings.dev")

    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
