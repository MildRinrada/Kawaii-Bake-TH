"""Progress routes nested under ``/api/v1/courses/``  mounted by config."""

from __future__ import annotations

from django.urls import path

from apps.progress.api.views.progress_views import CourseProgressView

app_name = "course_progress"

urlpatterns = [
    path("<str:slug>/progress/", CourseProgressView.as_view(), name="detail"),
]
