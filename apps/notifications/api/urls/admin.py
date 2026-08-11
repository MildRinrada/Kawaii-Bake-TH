"""Staff notification routes, mounted at ``/api/v1/admin/notifications/``.

The ``admin/`` prefix is a naming convention, not the permission: every
view here declares ``IsAdminUser`` itself, so a future re-mount cannot
accidentally expose them.
"""

from __future__ import annotations

from django.urls import path

from apps.notifications.api.views.admin_views import (
    AdminBroadcastView,
    AdminNotificationListView,
)

app_name = "notifications_admin"

urlpatterns = [
    path("", AdminNotificationListView.as_view(), name="list"),
    path("broadcast/", AdminBroadcastView.as_view(), name="broadcast"),
]
