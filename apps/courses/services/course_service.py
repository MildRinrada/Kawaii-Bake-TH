"""Business logic for courses."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.courses.exceptions import (
    CourseNotVisibleError,
    CourseSlugImmutableError,
    CourseSlugTakenError,
    InvalidCourseCategoryError,
)
from apps.courses.models import Course
from apps.courses.permissions.course_permissions import (
    can_delete_course,
    can_edit_course,
)
from apps.courses.repositories import course_repository
from apps.courses.selectors import course_selector
from apps.courses.utils import build_course_slug_base
from apps.courses.validators import course_validator
from apps.recipe_categories.selectors import category_selector

# `status` is deliberately absent: publishing must run the completeness checks
# in publish_service. `visibility` is a plain field with no precondition.
COURSE_EDITABLE_FIELDS = frozenset(
    {
        "title",
        "summary",
        "description",
        "difficulty",
        "visibility",
        "thumbnail",
    }
)


def _resolve_category_ids(*, slugs: Sequence[str]) -> list[int]:
    """Translate category slugs into primary keys.

    Raises:
        InvalidCourseCategoryError: If any slug is unknown or inactive.
    """
    if not slugs:
        return []

    resolved = category_selector.resolve_slugs(slugs=slugs)
    missing = [slug for slug in slugs if slug not in resolved]
    if missing:
        raise InvalidCourseCategoryError(details={"category_slugs": sorted(missing)})
    return [resolved[slug] for slug in slugs]


def _core_fields(data: Mapping[str, Any]) -> dict[str, Any]:
    """Extract the editable course columns from a payload."""
    return {key: value for key, value in data.items() if key in COURSE_EDITABLE_FIELDS}


def create_course(*, instructor_id: int, data: Mapping[str, Any]) -> Course:
    """Create a course as a draft.

    Args:
        instructor_id: Primary key of the instructor.
        data: Validated payload.

    Returns:
        The created course, re-read through the detail selector.
    """
    course_validator.validate_core(data)
    category_ids = _resolve_category_ids(slugs=data.get("category_slugs") or [])

    with transaction.atomic():
        course = course_repository.create_course(
            instructor_id=instructor_id,
            slug_base=build_course_slug_base(data["title"]),
            **_core_fields(data),
        )
        course_repository.set_categories(course=course, category_ids=category_ids)

    return _require_detail(slug=course.slug, viewer_id=instructor_id)


def update_course(
    *, slug: str, viewer_id: int, viewer_is_staff: bool = False, data: Mapping[str, Any]
) -> Course:
    """Apply a partial update to a course.

    Args:
        slug: The course slug.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.
        data: Validated payload; absent keys are unchanged.

    Returns:
        The updated course, re-read through the detail selector.

    Raises:
        CourseNotVisibleError: If absent or not the caller's to edit.
        CourseSlugImmutableError: If the slug of a published course would change.
        CourseSlugTakenError: If the requested slug is in use.
    """
    course = _require_editable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    course_validator.validate_core(data)

    if "slug" in data and data["slug"] != course.slug:
        if course.slug_is_frozen and not viewer_is_staff:
            raise CourseSlugImmutableError
        if course_selector.slug_exists(slug=data["slug"], exclude_pk=course.pk):
            raise CourseSlugTakenError(details={"slug": ["Already in use."]})

    category_ids: list[int] | None = None
    if "category_slugs" in data:
        category_ids = _resolve_category_ids(slugs=data["category_slugs"])

    changes = _core_fields(data)
    if "slug" in data:
        changes["slug"] = data["slug"]

    with transaction.atomic():
        course_repository.update_course(course=course, changes=changes)
        if category_ids is not None:
            course_repository.set_categories(course=course, category_ids=category_ids)

    return _require_detail(
        slug=changes.get("slug", course.slug),
        viewer_id=viewer_id,
        viewer_is_staff=viewer_is_staff,
    )


def delete_course(*, slug: str, viewer_id: int, viewer_is_staff: bool = False) -> None:
    """Permanently delete a course and its stored thumbnail.

    Archiving is the reversible alternative. Enrollment and lesson rows cascade;
    the thumbnail file is removed explicitly, because Django deletes no files
    when a row is deleted.

    Args:
        slug: The course slug.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Raises:
        CourseNotVisibleError: If absent or not the caller's to delete.
    """
    course = _require_editable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if not can_delete_course(
        instructor_id=course.instructor_id,
        viewer_id=viewer_id,
        viewer_is_staff=viewer_is_staff,
    ):
        raise CourseNotVisibleError

    thumbnail = course.thumbnail if course.thumbnail else None
    course_repository.delete_course(course=course)
    if thumbnail:
        thumbnail.delete(save=False)


def get_course(
    *, slug: str, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> Course:
    """Fetch a course for display.

    Raises:
        CourseNotVisibleError: If absent or hidden.
    """
    return _require_detail(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )


def sync_published_lesson_count(
    *, course_id: int, count: int, duration_minutes: int | None = None
) -> None:
    """Record how many published lessons a course has, and their total length.

    **Public cross-app write API** (ADR 0009, extended by ADR 0021): called by
    the lessons app inside the same transaction as every lesson mutation. This
    app treats the values as opaque, rebuildable caches — it computes nothing
    about lessons itself.

    Args:
        course_id: Primary key of the course.
        count: The new published-lesson count.
        duration_minutes: Sum of published lessons' durations, or ``None`` to
            leave the stored value untouched (legacy callers).
    """
    course_repository.set_published_lesson_count(
        course_id=course_id, count=count, duration_minutes=duration_minutes
    )


def sync_rating_aggregate(
    *, course_id: int, average: Decimal | None, count: int
) -> None:
    """Record a course's rating aggregate.

    **Public cross-app write API** (ADR 0021): called by the reviews app at its
    mutation choke point whenever a course-targeted review changes. Opaque,
    rebuildable cache — `manage.py rebuild_rating_aggregates` reconciles.

    Args:
        course_id: Primary key of the course.
        average: Average of active reviews, or ``None`` when unreviewed.
        count: Count of active reviews.
    """
    course_repository.set_rating_aggregate(
        course_id=course_id, average=average, count=count
    )


def _require_detail(
    *, slug: str, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> Course:
    """Fetch a course or raise the 404 domain error."""
    course = course_selector.get_course_detail(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if course is None:
        raise CourseNotVisibleError
    return course


def _require_editable(
    *, slug: str, viewer_id: int, viewer_is_staff: bool = False
) -> Course:
    """Fetch a course the caller may modify; "not yours" is the same 404."""
    course = course_selector.get_editable_course(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if course is None or not can_edit_course(
        instructor_id=course.instructor_id,
        viewer_id=viewer_id,
        viewer_is_staff=viewer_is_staff,
    ):
        raise CourseNotVisibleError
    return course
