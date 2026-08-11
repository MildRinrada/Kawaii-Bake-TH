"""Notification routes, mounted at ``/api/v1/me/notifications/`` by config.

Everything here is the caller's own - the ``me/`` prefix is shared with
progress, assistant and certificates by config (ADR 0009); these patterns
cannot collide with theirs.
"""

from __future__ import annotations

from django.urls import path

from apps.notifications.api.views.notification_views import (
    MyNotificationsView,
    NotificationPreferencesView,
    NotificationReadAllView,
    NotificationReadView,
)

app_name = "my_notifications"

urlpatterns = [
    path("", MyNotificationsView.as_view(), name="list"),
    path("read-all/", NotificationReadAllView.as_view(), name="read-all"),
    path(
        "preferences/",
        NotificationPreferencesView.as_view(),
        name="preferences",
    ),
    path(
        "<int:notification_id>/read/",
        NotificationReadView.as_view(),
        name="read",
    ),
]
