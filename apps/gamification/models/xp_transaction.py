"""The XP ledger — append-only history."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.gamification.constants import XPReason


class XPTransaction(models.Model):
    """One earning event — a fact, never edited or deleted.

    The append-only family (LearningActivity, AssistantMessage, AIUsageLog,
    Achievement): the ledger is the *history*, and every stored aggregate
    (``UserLevel``) is recomputed from it — the ledger can therefore repair
    the aggregate, never the other way round. The repository exposes only
    an append.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="xp_transactions",
    )
    reason = models.CharField(max_length=30, choices=XPReason.choices)
    points = models.PositiveIntegerField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "XP transaction"
        verbose_name_plural = "XP transactions"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=["user", "-created_at"], name="gamif_xp_user_idx"
            ),
        ]

    def __str__(self) -> str:
        """Return the ledger-entry description."""
        return f"+{self.points} XP · {self.reason} · user {self.user_id}"
