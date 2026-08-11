"""The achievement entity  append-only earned facts."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.certificates.constants import AchievementType


class Achievement(models.Model):
    """One earned achievement  a fact, never edited or deleted.

    The LearningActivity precedent (ADR 0012): facts about the past are
    immutable, so there is no update path and no delete API. Unique
    ``(user, achievement_type)`` makes awarding idempotent  earning is a
    one-time event per type; volume context ("which course?", "how many?")
    goes in ``metadata`` instead of extra rows.

    ``badge`` is display metadata (PROTECT  a referenced definition cannot
    vanish), nullable so an award never fails just because presentation is
    missing.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="achievements",
    )
    achievement_type = models.CharField(
        max_length=30, choices=AchievementType.choices
    )
    badge = models.ForeignKey(
        "certificates.BadgeDefinition",
        on_delete=models.PROTECT,
        related_name="achievements",
        null=True,
        blank=True,
    )
    awarded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "achievement"
        verbose_name_plural = "achievements"
        ordering = ("-awarded_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "achievement_type"),
                name="certificates_one_per_type",
            ),
        ]

    def __str__(self) -> str:
        """Return the achievement description."""
        return f"{self.achievement_type} · user {self.user_id}"
