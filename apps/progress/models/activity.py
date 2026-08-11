"""The learning activity ledger  streak foundation."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models.base import TimeStampedModel
from apps.progress.constants import ActivityType


class LearningActivity(TimeStampedModel):
    """One "did a thing today" fact per user, day and activity type.

    Append-only and deliberately separate from progress *state*: state is
    mutable (a lesson can be un-completed) but the fact that learning
    happened on a date is not  a streak must not retroactively break
    because a learner tidied their checklist. The unique constraint makes
    daily recording idempotent, which is all a streak needs; XP,
    leaderboards and streak computation itself are future phases reading
    this table, not columns here.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_activity",
    )
    activity_date = models.DateField()
    activity_type = models.CharField(
        max_length=30,
        choices=ActivityType.choices,
    )

    class Meta:
        verbose_name = "learning activity"
        verbose_name_plural = "learning activity"
        ordering = ("-activity_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "activity_date", "activity_type"),
                name="progress_activity_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "-activity_date"], name="progress_activity_idx"
            ),
        ]

    def __str__(self) -> str:
        """Return a readable label."""
        return f"{self.activity_type} · user {self.user_id} · {self.activity_date}"
