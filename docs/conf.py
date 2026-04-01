# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
import django

sys.path.insert(0, os.path.abspath('..'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'newsproject.settings'

# Override the database to SQLite so Sphinx can run without a live MariaDB
# instance. The documentation build only needs model introspection, not an
# actual database connection. This must be done before django.setup().
os.environ.setdefault('SPHINX_BUILD', '1')

from django.conf import settings  # noqa: E402
settings.DATABASES['default'] = {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': ':memory:',
}

django.setup()

# -- Project information -----------------------------------------------------
project = 'NewsApp'
copyright = '2026, Jerry Dickerson'
author = 'Jerry Dickerson'
release = '1.0'

# -- General configuration ---------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
html_theme = 'alabaster'
html_static_path = ['_static']
