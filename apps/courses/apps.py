"""App configuration for the courses app."""

from __future__ import annotations

from django.apps import AppConfig


class CoursesConfig(AppConfig):
    """Course structure, metadata, enrollment and lifecycle.

    Deliberately a leaf toward ``lessons``: this app never imports ``lessons``
    and never touches the ``course.lessons`` reverse accessor, so it remains
    shippable without it. See ``docs/adr/0009-courses-lessons-boundary.md``.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.courses"
    label = "courses"
    verbose_name = "Courses"
