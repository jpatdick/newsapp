"""
test_settings.py - Settings overrides for running the test suite.

Inherits everything from the main settings and overrides only the
database configuration so tests run against an in-memory SQLite
database rather than requiring a live MariaDB connection.

Usage:
    python manage.py test news --settings=newsproject.test_settings

This is standard Django practice: production/staging use MariaDB (set
via the main settings.py + environment variables), while the isolated
test runner uses SQLite :memory: for speed and zero infrastructure
dependency.
"""

from .settings import *  # noqa: F401,F403

# ---------------------------------------------------------------------------
# Override database: use SQLite in-memory for the test runner
# ---------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Disable password hashing for speed during tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Suppress logging noise during tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {
        'null': {'class': 'logging.NullHandler'},
    },
    'root': {
        'handlers': ['null'],
    },
}
