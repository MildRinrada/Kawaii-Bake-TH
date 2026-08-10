"""Staff security routes, mounted at ``/api/v1/admin/security/`` by config.

The ``admin/`` prefix is a naming convention, not the permission: every
view here declares ``IsAdminUser`` itself, so a future re-mount cannot
accidentally expose them.
"""

from __future__ import annotations

from django.urls import path

from apps.security.api.views.admin_views import (
    SecurityEventListView,
    SecuritySummaryView,
    SecurityVocabularyView,
    ThreatProfileBlockView,
    ThreatProfileDetailView,
    ThreatProfileListView,
    ThreatProfileReviewView,
)

app_name = "security_admin"

urlpatterns = [
    path("summary/", SecuritySummaryView.as_view(), name="summary"),
    path("vocabulary/", SecurityVocabularyView.as_view(), name="vocabulary"),
    path("events/", SecurityEventListView.as_view(), name="events"),
    path("profiles/", ThreatProfileListView.as_view(), name="profiles"),
    path(
        "profiles/<int:profile_id>/",
        ThreatProfileDetailView.as_view(),
        name="profile-detail",
    ),
    path(
        "profiles/<int:profile_id>/block/",
        ThreatProfileBlockView.as_view(),
        name="profile-block",
    ),
    path(
        "profiles/<int:profile_id>/review/",
        ThreatProfileReviewView.as_view(),
        name="profile-review",
    ),
]
