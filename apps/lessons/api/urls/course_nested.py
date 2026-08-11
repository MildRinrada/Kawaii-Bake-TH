"""Lesson routes addressed by course slug.

Mounted by ``config/urls.py`` under ``/api/v1/courses/`` **alongside** the
courses app's own urlconf. Django tries each include in order and falls through
on no-match, and these two-segment patterns cannot collide with courses'
single-segment ``<str:slug>/`` routes (the ``str`` converter stops at ``/``).
The shared prefix is configuration, not coupling  see ADR 0009.
"""

from __future__ import annotations

from django.urls import path

from apps.lessons.api.views.course_nested_views import (
    CourseLessonListView,
    CourseLessonReorderView,
)

app_name = "course_lessons"

urlpatterns = [
    path("<str:slug>/lessons/", CourseLessonListView.as_view(), name="list"),
    path(
        "<str:slug>/lessons/reorder/",
        CourseLessonReorderView.as_view(),
        name="reorder",
    ),
]
