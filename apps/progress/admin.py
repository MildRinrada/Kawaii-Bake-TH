"""Django admin registration for learner progress."""

from __future__ import annotations

from django.contrib import admin

from apps.progress.models import CourseProgress, LearningActivity, LessonProgress


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    """Read-mostly admin for lesson progress rows."""

    list_display = ("user", "lesson", "completed_at", "first_completed_at")
    search_fields = ("user__username", "user__email", "lesson__title")
    autocomplete_fields = ("user", "lesson")
    readonly_fields = ("first_completed_at", "created_at", "updated_at")


@admin.register(CourseProgress)
class CourseProgressAdmin(admin.ModelAdmin):
    """Read-mostly admin for course progress rows."""

    list_display = ("user", "course", "completed_at")
    search_fields = ("user__username", "user__email", "course__title")
    autocomplete_fields = ("user", "course")
    readonly_fields = ("completed_at", "created_at", "updated_at")


@admin.register(LearningActivity)
class LearningActivityAdmin(admin.ModelAdmin):
    """Read-only admin for the activity ledger."""

    list_display = ("user", "activity_date", "activity_type")
    list_filter = ("activity_type",)
    search_fields = ("user__username", "user__email")
    readonly_fields = ("user", "activity_date", "activity_type", "created_at", "updated_at")
