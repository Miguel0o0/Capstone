#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

from dotenv import load_dotenv  # <-- importamos python-dotenv


def main():
    """Run administrative tasks."""
    # Cargar variables desde el archivo .env de la raíz del proyecto
    load_dotenv()

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "junta_ut.settings.dev")

    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
