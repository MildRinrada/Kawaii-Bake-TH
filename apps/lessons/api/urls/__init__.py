"""Standalone lesson routes, mounted at ``/api/v1/lessons/``.

``{id}/complete/`` lives in the progress app's urlconf (mounted under the
same prefix by config)  completion is learner state, not lesson content.
"""

from __future__ import annotations

from django.urls import path

from apps.lessons.api.views.lesson_views import LessonDetailView

app_name = "lessons"

urlpatterns = [
    path("<int:lesson_id>/", LessonDetailView.as_view(), name="detail"),
]
