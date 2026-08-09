"""The caller's settings composition, mounted at ``/api/v1/me/`` by config.

Shares the ``me/`` prefix with progress, assistant, certificates,
gamification and rewards by config (ADR 0009); the patterns cannot
collide.
"""

from __future__ import annotations

from django.urls import path

from apps.users.api.views.settings_views import MySettingsView

app_name = "my_settings"

urlpatterns = [
    path("settings/", MySettingsView.as_view(), name="settings"),
]
