"""Staff account routes, mounted at ``/api/v1/admin/users/``.

The ``admin/`` prefix is a naming convention, not the permission: every
view here declares ``IsAdminUser`` itself, so a future re-mount cannot
accidentally expose them.
"""

from __future__ import annotations

from django.urls import path

from apps.users.api.views.admin_views import (
    AdminUserDetailView,
    AdminUserListView,
    AdminUserStatsView,
)

app_name = "users_admin"

urlpatterns = [
    path("", AdminUserListView.as_view(), name="list"),
    path("stats/", AdminUserStatsView.as_view(), name="stats"),
    path("<int:user_id>/", AdminUserDetailView.as_view(), name="detail"),
]
