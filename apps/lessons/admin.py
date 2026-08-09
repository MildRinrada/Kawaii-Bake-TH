"""Django admin registration for lessons."""

from __future__ import annotations

from django.contrib import admin

from apps.lessons.models import Lesson


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    """Admin for lessons.

    Status changes made here bypass the repository choke point, so the
    published-lesson counter may drift until ``manage.py recount_lessons``
    runs. Prefer the API for lesson management.
    """

    list_display = ("title", "course", "position", "status", "is_preview")
    list_filter = ("status", "is_preview", "video_provider")
    search_fields = ("title", "course__title", "course__slug")
    autocomplete_fields = ("course", "recipe")
    readonly_fields = ("position", "created_at", "updated_at")
