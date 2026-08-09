"""App configuration for the lessons app."""

from __future__ import annotations

from django.apps import AppConfig


class LessonsConfig(AppConfig):
    """Lesson content, ordering, progress and completion.

    The dependent side of the courses boundary: this app imports courses'
    public selectors and services; courses imports nothing of this app.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.lessons"
    label = "lessons"
    verbose_name = "Lessons"
