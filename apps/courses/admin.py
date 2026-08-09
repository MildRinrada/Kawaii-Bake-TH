"""Django admin registration for courses."""

from __future__ import annotations

from django.contrib import admin

from apps.courses.models import Course, Enrollment


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Admin for courses."""

    list_display = (
        "title",
        "instructor",
        "status",
        "visibility",
        "published_lesson_count",
        "published_at",
    )
    list_filter = ("status", "visibility", "difficulty", "categories")
    search_fields = ("title", "slug", "instructor__username", "instructor__email")
    autocomplete_fields = ("instructor",)
    filter_horizontal = ("categories",)
    readonly_fields = ("published_lesson_count", "created_at", "updated_at")
    date_hierarchy = "created_at"


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    """Admin for enrollments."""

    list_display = ("user", "course", "status", "enrolled_at", "completed_at")
    list_filter = ("status",)
    search_fields = ("user__username", "user__email", "course__title")
    autocomplete_fields = ("user", "course")
    readonly_fields = ("enrolled_at", "completed_at", "created_at", "updated_at")
