"""The conversation entity."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.assistant.constants import TITLE_MAX_LENGTH, AssistantLanguage, ContextType
from apps.core.models.base import TimeStampedModel


class AssistantConversation(TimeStampedModel):
    """One user's chat thread with the assistant.

    **Explicit nullable FKs, not a GenericForeignKey** - the same call as
    reviews/favorites (ADR 0011): real referential integrity, OpenAPI-clear
    payloads, and joinable columns for future per-content analytics. The
    check constraint allows only the FK matching ``context_type`` to be set -
    but does **not** require it, because targets use ``SET_NULL``: deleting a
    recipe must not delete the user's chat history, so a typed conversation
    whose target vanished degrades to context-free answers instead.

    ``prompt_version`` is stamped at creation from the then-active
    :class:`~apps.assistant.models.PromptTemplate` and never rewritten:
    old conversations keep answering under the prompt they started with.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assistant_conversations",
    )
    title = models.CharField(max_length=TITLE_MAX_LENGTH, blank=True)
    language = models.CharField(
        max_length=5,
        choices=AssistantLanguage.choices,
        default=AssistantLanguage.TH,
    )
    context_type = models.CharField(
        max_length=20,
        choices=ContextType.choices,
        default=ContextType.GENERAL,
    )
    recipe = models.ForeignKey(
        "recipes.Recipe",
        on_delete=models.SET_NULL,
        related_name="assistant_conversations",
        null=True,
        blank=True,
    )
    lesson = models.ForeignKey(
        "lessons.Lesson",
        on_delete=models.SET_NULL,
        related_name="assistant_conversations",
        null=True,
        blank=True,
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        related_name="assistant_conversations",
        null=True,
        blank=True,
    )
    prompt_version = models.CharField(max_length=20)

    class Meta:
        verbose_name = "assistant conversation"
        verbose_name_plural = "assistant conversations"
        # Most recently active first - `updated_at` is touched on every send.
        ordering = ("-updated_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        context_type=ContextType.RECIPE,
                        lesson__isnull=True,
                        course__isnull=True,
                    )
                    | Q(
                        context_type=ContextType.LESSON,
                        recipe__isnull=True,
                        course__isnull=True,
                    )
                    | Q(
                        context_type=ContextType.COURSE,
                        recipe__isnull=True,
                        lesson__isnull=True,
                    )
                    | Q(
                        context_type=ContextType.GENERAL,
                        recipe__isnull=True,
                        lesson__isnull=True,
                        course__isnull=True,
                    )
                ),
                name="assistant_context_matches_type",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "-updated_at"], name="assistant_conv_user_idx"
            ),
        ]

    def __str__(self) -> str:
        """Return the conversation description."""
        return f"conversation {self.pk} · {self.context_type} · user {self.user_id}"
