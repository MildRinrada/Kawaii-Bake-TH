"""Private per-user configuration: privacy, learning and notifications."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models.base import TimeStampedModel
from apps.users.constants import (
    WEEKLY_GOAL_DEFAULT_MINUTES,
    BakingExperienceLevel,
    PreferredLanguage,
    ProfileVisibility,
    Theme,
)


class UserPreference(TimeStampedModel):
    """Settings that belong to the user but are never publicly visible.

    Kept in its own table so that privacy switches are physically separated
    from the profile data they govern  a public profile serializer has no
    access path to them.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="preference",
    )

    # --- Privacy -----------------------------------------------------------
    profile_visibility = models.CharField(
        max_length=20,
        choices=ProfileVisibility.choices,
        default=ProfileVisibility.PUBLIC,
    )
    show_birthday = models.BooleanField(default=False)
    show_location = models.BooleanField(default=True)

    # --- Learning ----------------------------------------------------------
    preferred_difficulty = models.CharField(
        max_length=20,
        choices=BakingExperienceLevel.choices,
        default=BakingExperienceLevel.BEGINNER,
    )
    weekly_goal_minutes = models.PositiveIntegerField(
        default=WEEKLY_GOAL_DEFAULT_MINUTES
    )
    # Slugs from `constants.DietaryRestriction`.
    dietary_restrictions = models.JSONField(default=list, blank=True)

    # --- Interface ---------------------------------------------------------
    theme = models.CharField(max_length=20, choices=Theme.choices, default=Theme.SYSTEM)
    # Constrained in Phase 14 from a free-text BCP-47-ish field nothing
    # consumed to the assistant-compatible code set, Thai default 
    # the platform's one language preference (ADR 0020 §8).
    locale = models.CharField(
        max_length=10,
        choices=PreferredLanguage.choices,
        default=PreferredLanguage.TH,
    )

    # --- Notifications -----------------------------------------------------
    email_course_updates = models.BooleanField(default=True)
    email_product_updates = models.BooleanField(default=True)
    email_marketing = models.BooleanField(default=False)

    class Meta:
        verbose_name = "user preference"
        verbose_name_plural = "user preferences"

    def __str__(self) -> str:
        """Return a readable label for the admin."""
        return f"UserPreference<{self.user_id}>"
