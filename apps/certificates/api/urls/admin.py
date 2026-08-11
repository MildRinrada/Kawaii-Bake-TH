"""Staff achievements routes, mounted at ``/api/v1/admin/achievements/``.

The ``admin/`` prefix is a naming convention, not the permission: every
view here declares ``IsAdminUser`` itself, so a future re-mount cannot
accidentally expose them.

``awards/`` is routed before ``<slug:slug>/`` so the literal wins.
"""

from __future__ import annotations

from django.urls import path

from apps.certificates.api.views.admin_views import (
    AdminAwardListView,
    AdminBadgeDetailView,
    AdminBadgeListView,
)

app_name = "achievements_admin"

urlpatterns = [
    path("", AdminBadgeListView.as_view(), name="badges"),
    path("awards/", AdminAwardListView.as_view(), name="awards"),
    path("<slug:slug>/", AdminBadgeDetailView.as_view(), name="badge-detail"),
]
