"""Completion routes nested under ``/api/v1/lessons/`` — mounted by config."""

from __future__ import annotations

from django.urls import path

from apps.progress.api.views.progress_views import LessonCompleteView

app_name = "lesson_progress"

urlpatterns = [
    path("<int:lesson_id>/complete/", LessonCompleteView.as_view(), name="complete"),
]
