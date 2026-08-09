"""The per-call usage ledger."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class AIUsageLog(models.Model):
    """One provider call's accounting — append-only.

    Separate from :class:`AssistantMessage` on purpose: messages are the
    user's transcript (CASCADE with their conversation), while this ledger
    is the operator's billing/quota record and must survive conversation
    deletion. Future quota enforcement aggregates this table at read time —
    no counter columns anywhere, as everywhere else in the project.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_usage_logs",
    )
    provider = models.CharField(max_length=32)
    model_name = models.CharField(max_length=100, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    estimated_cost = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "AI usage log"
        verbose_name_plural = "AI usage logs"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=["user", "-created_at"], name="assistant_usage_user_idx"
            ),
        ]

    def __str__(self) -> str:
        """Return the log-row description."""
        return (
            f"usage {self.pk} · {self.provider} · user {self.user_id} · "
            f"{self.input_tokens}/{self.output_tokens} tokens"
        )
