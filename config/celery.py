"""Celery application.

Each feature app declares its own tasks in ``<app>/tasks/``; autodiscovery
picks them up from ``INSTALLED_APPS``.
"""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("kawaiibake")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
