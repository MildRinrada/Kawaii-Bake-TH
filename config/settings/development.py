"""Development settings.

Defaults to SQLite so the project runs without a local PostgreSQL server.
Set ``DB_ENGINE=postgres`` in ``.env`` to use PostgreSQL instead.
"""

from __future__ import annotations

from config.settings.base import *  # noqa: F403
from config.settings.base import BASE_DIR, env

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]

if env("DB_ENGINE", "sqlite") != "postgres":
    DATABASES = {  # noqa: F405
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Cookies are sent over plain HTTP locally.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Run Celery tasks inline so local development needs no broker. Emails still
# go through the task, so the production code path is the one being exercised.
CELERY_TASK_ALWAYS_EAGER = True

# The browsable API is a convenience while wiring up the Next.js client.
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}
