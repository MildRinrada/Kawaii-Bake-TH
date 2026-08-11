"""The per-user streak row  derived from the LearningActivity ledger."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class DailyStreak(models.Model):
    """One user's learning-streak standing.

    **Derived state**, never manually incremented: the streak service
    recomputes every field from progress' append-only ``LearningActivity``
    day-facts (ADR 0012 built that ledger precisely as "the streak
    substrate"). Because the source is append-only, this row can always be
    rebuilt  including ``longest_streak``, which needs no separate
    history.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_streak",
    )
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "daily streak"
        verbose_name_plural = "daily streaks"

    def __str__(self) -> str:
        """Return the streak description."""
        return (
            f"streak {self.current_streak} (best {self.longest_streak}) · "
            f"user {self.user_id}"
        )
