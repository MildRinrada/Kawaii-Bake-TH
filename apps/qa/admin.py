"""Django admin for the Q&A app."""

from __future__ import annotations

from django.contrib import admin

from apps.qa.models import QuestionAnswer, QuestionThread


@admin.register(QuestionThread)
class QuestionThreadAdmin(admin.ModelAdmin):
    """Browse and moderate threads (hide/restore via status)."""

    list_display = ("id", "author", "title", "status", "recipe", "course", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "body", "author__username")
    raw_id_fields = ("author", "recipe", "course", "accepted_answer")


@admin.register(QuestionAnswer)
class QuestionAnswerAdmin(admin.ModelAdmin):
    """Inspect answers."""

    list_display = ("id", "thread", "author", "created_at")
    search_fields = ("body", "author__username")
    raw_id_fields = ("thread", "author")
