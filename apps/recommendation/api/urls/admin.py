"""Staff recommendation routes, mounted at ``/api/v1/admin/recommendations/``.

The ``admin/`` prefix is a naming convention, not the permission: every
view here declares ``IsAdminUser`` itself, so a future re-mount cannot
accidentally expose them.
"""

from __future__ import annotations

from django.urls import path

from apps.recommendation.api.views.admin_views import (
    AdminRecommendationConfigView,
    AdminRecommendationPreviewView,
)

app_name = "recommendations_admin"

urlpatterns = [
    path(
        "preview/",
        AdminRecommendationPreviewView.as_view(),
        name="preview",
    ),
    path("config/", AdminRecommendationConfigView.as_view(), name="config"),
]
