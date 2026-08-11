"""Django admin for the assistant app.

Messages and usage logs are append-only domains; the admin mirrors that by
exposing them read-only. Prompt templates are the one intentionally editable
surface - that is how operators ship a new prompt version.
"""

from __future__ import annotations

from django.contrib import admin

from apps.assistant.models import (
    AIUsageLog,
    AssistantConversation,
    AssistantMessage,
    PromptTemplate,
)


@admin.register(AssistantConversation)
class AssistantConversationAdmin(admin.ModelAdmin):
    """Browse conversations."""

    list_display = (
        "id",
        "user",
        "context_type",
        "language",
        "prompt_version",
        "title",
        "updated_at",
    )
    list_filter = ("context_type", "language")
    search_fields = ("title", "user__email")
    raw_id_fields = ("user", "recipe", "lesson", "course")
    readonly_fields = ("prompt_version", "created_at", "updated_at")


@admin.register(AssistantMessage)
class AssistantMessageAdmin(admin.ModelAdmin):
    """Inspect transcripts - strictly read-only."""

    list_display = ("id", "conversation", "role", "provider", "created_at")
    list_filter = ("role", "provider")
    raw_id_fields = ("conversation",)

    def has_add_permission(self, request) -> bool:  # noqa: D102
        return False

    def has_change_permission(self, request, obj=None) -> bool:  # noqa: D102
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # noqa: D102
        return False


@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):
    """Manage prompt versions; activate a new row rather than editing old ones."""

    list_display = ("name", "language", "version", "is_active", "created_at")
    list_filter = ("name", "language", "is_active")


@admin.register(AIUsageLog)
class AIUsageLogAdmin(admin.ModelAdmin):
    """Inspect the usage ledger - strictly read-only."""

    list_display = (
        "id",
        "user",
        "provider",
        "model_name",
        "input_tokens",
        "output_tokens",
        "created_at",
    )
    list_filter = ("provider",)
    raw_id_fields = ("user",)

    def has_add_permission(self, request) -> bool:  # noqa: D102
        return False

    def has_change_permission(self, request, obj=None) -> bool:  # noqa: D102
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # noqa: D102
        return False
