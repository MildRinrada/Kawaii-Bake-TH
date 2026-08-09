"""The favorite relationship."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models.base import TimeStampedModel
from apps.favorites.constants import FavoriteTargetKind


class Favorite(TimeStampedModel):
    """One user's bookmark of one recipe or course.

    Same explicit-FK target shape as ``Review`` (ADR 0011). A favorite is a
    toggle, not a document: unfavoriting **hard-deletes** the row (the model
    deliberately has no status column), and duplicates are impossible by
    constraint — plain uniques suffice because SQL ``NULL`` never equals
    ``NULL``, so recipe rows cannot collide with course rows.

    ``created_at`` (from ``TimeStampedModel``) is the favorited-at timestamp
    the future recommendation/analytics work will consume.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    recipe = models.ForeignKey(
        "recipes.Recipe",
        on_delete=models.CASCADE,
        related_name="favorites",
        null=True,
        blank=True,
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="favorites",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "favorite"
        verbose_name_plural = "favorites"
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(recipe__isnull=False, course__isnull=True)
                    | Q(recipe__isnull=True, course__isnull=False)
                ),
                name="favorites_exactly_one_target",
            ),
            models.UniqueConstraint(
                fields=("user", "recipe"), name="favorites_unique_recipe"
            ),
            models.UniqueConstraint(
                fields=("user", "course"), name="favorites_unique_course"
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="favorites_user_idx"),
        ]

    def __str__(self) -> str:
        """Return the favorite description."""
        return f"favorite {self.pk} · user {self.user_id}"

    @property
    def target_kind(self) -> str:
        """Which kind of content this favorite points at."""
        return (
            FavoriteTargetKind.RECIPE if self.recipe_id else FavoriteTargetKind.COURSE
        )
