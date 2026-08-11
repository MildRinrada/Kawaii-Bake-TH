"""Django admin registration for quizzes."""

from __future__ import annotations

from django.contrib import admin

from apps.quizzes.models import Quiz, QuizAttempt, QuizAttemptAnswer, QuizQuestion


class QuizQuestionInline(admin.TabularInline):
    """Composition rows edited inline with their quiz."""

    model = QuizQuestion
    extra = 0
    autocomplete_fields = ("question",)


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    """Admin for quizzes."""

    list_display = ("title", "owner", "status", "visibility", "pass_percent", "published_at")
    list_filter = ("status", "visibility")
    search_fields = ("title", "slug", "owner__username", "owner__email")
    autocomplete_fields = ("owner",)
    readonly_fields = ("created_at", "updated_at")
    inlines = (QuizQuestionInline,)
    date_hierarchy = "created_at"


class QuizAttemptAnswerInline(admin.TabularInline):
    """Snapshot rows shown read-only with their attempt."""

    model = QuizAttemptAnswer
    extra = 0
    can_delete = False
    readonly_fields = (
        "question",
        "position",
        "points_possible",
        "was_correct",
        "points_awarded",
    )


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    """Admin for attempts  read-only history."""

    list_display = ("id", "quiz", "user", "status", "percentage", "passed", "submitted_at")
    list_filter = ("status", "passed")
    search_fields = ("quiz__title", "user__username", "user__email")
    autocomplete_fields = ("user", "quiz")
    readonly_fields = (
        "user",
        "quiz",
        "status",
        "started_at",
        "submitted_at",
        "score",
        "max_score",
        "correct_count",
        "incorrect_count",
        "percentage",
        "passed",
        "created_at",
        "updated_at",
    )
    inlines = (QuizAttemptAnswerInline,)
