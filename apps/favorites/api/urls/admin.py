"""Staff favorites routes, mounted at ``/api/v1/admin/favorites/``.

The ``admin/`` prefix is a naming convention, not the permission: every
view here declares ``IsAdminUser`` itself, so a future re-mount cannot
accidentally expose them.
"""

from __future__ import annotations

from django.urls import path

from apps.favorites.api.views.admin_views import (
    AdminFavoriteListView,
    AdminFavoriteTopView,
)

app_name = "favorites_admin"

urlpatterns = [
    path("", AdminFavoriteListView.as_view(), name="list"),
    path("top/", AdminFavoriteTopView.as_view(), name="top"),
]
