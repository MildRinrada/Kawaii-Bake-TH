"""Write-side database access for courses."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction

from apps.courses.constants import COURSE_SLUG_ATTEMPTS
from apps.courses.exceptions import CourseSlugGenerationError
from apps.courses.models import Course
from apps.courses.utils import course_slug_with_suffix


def create_course(*, instructor_id: int, slug_base: str, **fields: Any) -> Course:
    """Create a course, resolving slug collisions optimistically.

    Attempt-and-catch rather than check-then-insert: the check races under
    concurrency. Each attempt is its own ``atomic`` block, which is a SAVEPOINT
    inside the service's outer transaction — on PostgreSQL, catching
    ``IntegrityError`` without one poisons the whole transaction.

    Args:
        instructor_id: Primary key of the instructor.
        slug_base: Slug base derived from the title; may be empty.
        **fields: Remaining course field values.

    Returns:
        The created course.

    Raises:
        CourseSlugGenerationError: If no free slug was found.
    """
    candidate = slug_base or course_slug_with_suffix("")

    for _ in range(COURSE_SLUG_ATTEMPTS):
        try:
            with transaction.atomic():
                return Course.objects.create(
                    instructor_id=instructor_id, slug=candidate, **fields
                )
        except IntegrityError:
            candidate = course_slug_with_suffix(slug_base)

    raise CourseSlugGenerationError


def update_course(*, course: Course, changes: Mapping[str, Any]) -> Course:
    """Apply changes to a course in a single UPDATE.

    Args:
        course: The course to update.
        changes: Field name to new value.

    Returns:
        The updated course.
    """
    if not changes:
        return course

    for field, value in changes.items():
        setattr(course, field, value)
    course.save(update_fields=[*changes.keys(), "updated_at"])
    return course


def set_categories(*, course: Course, category_ids: Sequence[int]) -> None:
    """Replace a course's category assignments.

    Args:
        course: The course to update.
        category_ids: Primary keys of the categories to assign.
    """
    course.categories.set(category_ids)


def set_published_lesson_count(
    *, course_id: int, count: int, duration_minutes: int | None = None
) -> None:
    """Store the published-lesson counter (and total duration when given).

    Written via ``queryset.update`` so no ``updated_at`` churn and no race with
    concurrent field updates on the same row.

    Args:
        course_id: Primary key of the course.
        count: The new count.
        duration_minutes: New duration sum, or ``None`` to leave unchanged.
    """
    changes: dict[str, int] = {"published_lesson_count": count}
    if duration_minutes is not None:
        changes["published_duration_minutes"] = duration_minutes
    Course.objects.filter(pk=course_id).update(**changes)


def set_rating_aggregate(
    *, course_id: int, average: Decimal | None, count: int
) -> None:
    """Store the rating aggregate pushed by the reviews app.

    Args:
        course_id: Primary key of the course.
        average: Average of active reviews, or ``None`` when unreviewed.
        count: Count of active reviews.
    """
    Course.objects.filter(pk=course_id).update(
        rating_average=average, rating_count=count
    )


def delete_course(*, course: Course) -> None:
    """Delete a course and its children.

    Args:
        course: The course to delete.
    """
    course.delete()
