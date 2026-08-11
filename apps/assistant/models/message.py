"""The message entity - append-only."""

from __future__ import annotations

from django.db import models

from apps.assistant.constants import MessageRole


class AssistantMessage(models.Model):
    """One turn of a conversation.

    Append-only: there is no edit or delete API, no ``updated_at``, and the
    repository exposes only ``add``. The transcript is a record of what was
    actually said - to the user *and* to the provider - so it must never be
    rewritten (the LearningActivity precedent, ADR 0012).

    ``system`` never appears here: the system prompt is rebuilt from the
    versioned template on every send, which is the prompt-injection boundary -
    stored user content structurally cannot become a system turn.

    ``provider``/``model_name``/token counts are stamped per message, not per
    conversation, because the configured provider can change mid-thread.
    """

    conversation = models.ForeignKey(
        "assistant.AssistantConversation",
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=10, choices=MessageRole.choices)
    content = models.TextField()
    provider = models.CharField(max_length=32, blank=True)
    model_name = models.CharField(max_length=100, blank=True)
    token_input = models.PositiveIntegerField(null=True, blank=True)
    token_output = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "assistant message"
        verbose_name_plural = "assistant messages"
        # Chronological - a transcript reads top to bottom.
        ordering = ("created_at", "id")
        indexes = [
            models.Index(
                fields=["conversation", "created_at"],
                name="assistant_msg_conv_idx",
            ),
        ]

    def __str__(self) -> str:
        """Return the message description."""
        return f"message {self.pk} · {self.role} · conversation {self.conversation_id}"
