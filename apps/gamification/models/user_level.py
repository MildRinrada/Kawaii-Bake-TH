"""The per-user level row  a recomputed aggregate, not a source of truth."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class UserLevel(models.Model):
    """One user's current level standing.

    **Derived state**: every field is recomputed from the XP ledger by
    ``level_service``  this row exists so the leaderboard can sort without
    summing ledgers, and it can be rebuilt from scratch at any time. No
    history lives here; history is :class:`XPTransaction`.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_level",
    )
    current_level = models.PositiveIntegerField(default=1)
    # XP accumulated *inside* the current level, for progress bars.
    current_xp = models.PositiveIntegerField(default=0)
    total_xp = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "user level"
        verbose_name_plural = "user levels"
        ordering = ("-total_xp", "id")
        indexes = [
            models.Index(fields=["-total_xp"], name="gamif_level_xp_idx"),
        ]

    def __str__(self) -> str:
        """Return the level description."""
        return f"level {self.current_level} · {self.total_xp} XP · user {self.user_id}"
