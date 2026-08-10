"""WSGI entry point for Django administrative deployments."""

from __future__ import annotations

import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web_config.settings")
application = get_wsgi_application()
