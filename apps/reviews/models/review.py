"""The review entity."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models.base import TimeStampedModel
from apps.reviews.constants import (
    COMMENT_MAX_LENGTH,
    RATING_MAX,
    RATING_MIN,
    ReviewStatus,
    ReviewTargetKind,
)


class Review(TimeStampedModel):
    """One user's rating (and optional comment) of one recipe or course.

    **Explicit nullable FKs, not a GenericForeignKey** (ADR 0011): a check
    constraint guarantees exactly one target is set, the database keeps real
    referential integrity with CASCADE, and the content apps' prefix-
    parameterised visibility ``Q`` builders compose across the join — none of
    which contenttypes can offer. Adding a future reviewable type is one
    nullable column plus two constraints.

    Duplicate prevention is a partial unique per target **on active rows
    only**: soft-deleting a review frees the slot for a fresh one, while the
    deleted row keeps history. Ratings are aggregated from ``ACTIVE`` rows at
    read time — there are deliberately no ``rating_average``/``review_count``
    columns anywhere (see Database.md, "Counters deliberately not added").
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    recipe = models.ForeignKey(
        "recipes.Recipe",
        on_delete=models.CASCADE,
        related_name="reviews",
        null=True,
        blank=True,
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="reviews",
        null=True,
        blank=True,
    )

    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(max_length=COMMENT_MAX_LENGTH, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.ACTIVE,
        db_index=True,
    )

    class Meta:
        verbose_name = "review"
        verbose_name_plural = "reviews"
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(recipe__isnull=False, course__isnull=True)
                    | Q(recipe__isnull=True, course__isnull=False)
                ),
                name="reviews_exactly_one_target",
            ),
            models.CheckConstraint(
                condition=Q(rating__gte=RATING_MIN, rating__lte=RATING_MAX),
                name="reviews_rating_range",
            ),
            models.UniqueConstraint(
                fields=("user", "recipe"),
                condition=Q(status="active"),
                name="reviews_one_active_per_recipe",
            ),
            models.UniqueConstraint(
                fields=("user", "course"),
                condition=Q(status="active"),
                name="reviews_one_active_per_course",
            ),
        ]
        indexes = [
            models.Index(
                fields=["recipe", "status", "-created_at"],
                name="reviews_recipe_idx",
            ),
            models.Index(
                fields=["course", "status", "-created_at"],
                name="reviews_course_idx",
            ),
        ]

    def __str__(self) -> str:
        """Return the review description."""
        return f"review {self.pk} · {self.rating}★ by user {self.user_id}"

    @property
    def target_kind(self) -> str:
        """Which kind of content this review points at."""
        return ReviewTargetKind.RECIPE if self.recipe_id else ReviewTargetKind.COURSE
