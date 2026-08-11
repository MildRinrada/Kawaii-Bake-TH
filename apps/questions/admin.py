"""Django admin registration for the question bank."""

from __future__ import annotations

from django.contrib import admin

from apps.questions.models import AnswerChoice, Question, QuestionTag


class AnswerChoiceInline(admin.TabularInline):
    """Choices edited inline with their question."""

    model = AnswerChoice
    extra = 0


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """Admin for questions.

    Admin edits bypass the service-layer frozen gate  an operator override,
    same stance as lesson counter edits (repaired by ``recount_lessons``).
    ``frozen_at`` is read-only here so it cannot be cleared casually.
    """

    list_display = ("__str__", "author", "question_type", "difficulty", "frozen_at")
    list_filter = ("question_type", "difficulty", "tags")
    search_fields = ("text", "author__username", "author__email")
    autocomplete_fields = ("author", "supersedes")
    filter_horizontal = ("tags",)
    readonly_fields = ("frozen_at", "version", "created_at", "updated_at")
    inlines = (AnswerChoiceInline,)


@admin.register(QuestionTag)
class QuestionTagAdmin(admin.ModelAdmin):
    """Admin for tags."""

    list_display = ("name", "slug")
    search_fields = ("name", "slug")
