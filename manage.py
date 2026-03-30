#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

from dotenv import load_dotenv

# Load environment variables from .env file before Django initialises.
# This ensures DB credentials, email settings, and SECRET_KEY are
# available to settings.py without being hard-coded in the codebase.
load_dotenv()


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'newsproject.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError('Could not import Django.') from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
