"""Read-only rating statistics.

Detail statistics are computed on read: one indexed aggregate query over
``ACTIVE`` rows. For **courses** an additional stored aggregate pair lives on
the Course row (ADR 0021) — maintained by ``review_repository`` at the
mutation choke point, rebuilt by ``manage.py rebuild_rating_aggregates`` — so
course listings carry a rating without an N+1. This selector remains the
source of truth the stored pair is rebuilt from, and the future caching seam:
wrap these functions with the ``infrastructure/cache`` adapter without
touching any caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Avg, Count, Q, QuerySet

from apps.reviews.constants import RATING_MAX, RATING_MIN, ReviewStatus
from apps.reviews.models import Review


@dataclass(frozen=True)
class RatingSummary:
    """Aggregate rating figures for one target."""

    average: Decimal | None
    count: int
    distribution: dict[int, int]


def for_recipe(*, recipe_id: int) -> RatingSummary:
    """Rating summary of one recipe.

    Args:
        recipe_id: Primary key of the recipe.

    Returns:
        The computed summary.
    """
    return _summarize(Review.objects.filter(recipe_id=recipe_id))


def for_course(*, course_id: int) -> RatingSummary:
    """Rating summary of one course.

    Args:
        course_id: Primary key of the course.

    Returns:
        The computed summary.
    """
    return _summarize(Review.objects.filter(course_id=course_id))


@dataclass(frozen=True)
class RatingFact:
    """Average and count for one target — the bulk sibling of ``RatingSummary``.

    Part of the public cross-app API (Phase 12). No star distribution: the
    recommendation scorer needs only the two aggregates, and computing eight
    counts per row for hundreds of candidates would be waste.
    """

    average: float
    count: int


def facts_for_recipes(*, ids: list[int]) -> dict[int, RatingFact]:
    """Rating facts for many recipes, in one query.

    Args:
        ids: Recipe primary keys.

    Returns:
        Mapping of recipe id to its fact (absent = no active reviews).
    """
    return _bulk_facts(field="recipe_id", ids=ids)


def facts_for_courses(*, ids: list[int]) -> dict[int, RatingFact]:
    """Rating facts for many courses, in one query.

    Args:
        ids: Course primary keys.

    Returns:
        Mapping of course id to its fact (absent = no active reviews).
    """
    return _bulk_facts(field="course_id", ids=ids)


def _bulk_facts(*, field: str, ids: list[int]) -> dict[int, RatingFact]:
    """One grouped aggregate over active reviews of the given targets."""
    if not ids:
        return {}
    rows = (
        Review.objects.filter(
            status=ReviewStatus.ACTIVE, **{f"{field}__in": ids}
        )
        .values(field)
        .annotate(average=Avg("rating"), total=Count("id"))
    )
    return {
        row[field]: RatingFact(average=float(row["average"]), count=row["total"])
        for row in rows
    }


def _summarize(queryset: QuerySet[Review]) -> RatingSummary:
    """Aggregate average, count and star distribution in one query."""
    aggregates = queryset.filter(status=ReviewStatus.ACTIVE).aggregate(
        average=Avg("rating"),
        total=Count("id"),
        **{
            f"star_{star}": Count("id", filter=Q(rating=star))
            for star in range(RATING_MIN, RATING_MAX + 1)
        },
    )
    average = aggregates["average"]
    return RatingSummary(
        average=(
            Decimal(average).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if average is not None
            else None
        ),
        count=aggregates["total"],
        distribution={
            star: aggregates[f"star_{star}"]
            for star in range(RATING_MIN, RATING_MAX + 1)
        },
    )
