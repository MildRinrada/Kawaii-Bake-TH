"""Staff progress routes, mounted at ``/api/v1/admin/progress/``.

The ``admin/`` prefix is a naming convention, not the permission: every
view here declares ``IsAdminUser`` itself, so a future re-mount cannot
accidentally expose them.
"""

from __future__ import annotations

from django.urls import path

from apps.progress.api.views.admin_views import (
    AdminCourseLearnersView,
    AdminCourseStatsView,
    AdminProgressSummaryView,
)

app_name = "progress_admin"

urlpatterns = [
    path("summary/", AdminProgressSummaryView.as_view(), name="summary"),
    path("courses/", AdminCourseStatsView.as_view(), name="courses"),
    path(
        "courses/<str:slug>/enrollments/",
        AdminCourseLearnersView.as_view(),
        name="enrollments",
    ),
]
