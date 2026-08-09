"""Test data builders for the course domain.

Thai fixtures from the first commit, as in Phase 2 — the slug machinery fails
silently on Thai with English-only test data.
"""

from __future__ import annotations

from itertools import count
from typing import Any

from django.utils import timezone

from apps.courses.constants import CourseStatus, CourseVisibility, EnrollmentStatus
from apps.courses.models import Course, Enrollment

THAI_COURSE_TITLE = "คอร์สทำขนมปังโฮมเมด"

_sequence = count(1)


def create_course(
    *,
    instructor: Any,
    title: str | None = None,
    slug: str | None = None,
    status: str = CourseStatus.DRAFT,
    visibility: str = CourseVisibility.PUBLIC,
    categories: list[Any] | None = None,
    **extra: Any,
) -> Course:
    """Create a course in a given state."""
    index = next(_sequence)
    course = Course.objects.create(
        instructor=instructor,
        title=title or f"Course {index}",
        slug=slug or f"course-{index}",
        summary=extra.pop("summary", "Learn to bake."),
        description=extra.pop(
            "description", "A thorough, hands-on baking course for home bakers."
        ),
        status=status,
        visibility=visibility,
        published_at=extra.pop("published_at", None),
        **extra,
    )
    if categories:
        course.categories.set(categories)
    return course


def create_published_course(**kwargs: Any) -> Course:
    """Create a published, publicly visible course."""
    kwargs.setdefault("status", CourseStatus.PUBLISHED)
    kwargs.setdefault("visibility", CourseVisibility.PUBLIC)
    kwargs.setdefault("published_at", timezone.now())
    return create_course(**kwargs)


def enroll_user(
    *, user: Any, course: Course, status: str = EnrollmentStatus.ACTIVE, **extra: Any
) -> Enrollment:
    """Enroll a user directly at the model layer."""
    return Enrollment.objects.create(
        user=user,
        course=course,
        status=status,
        enrolled_at=extra.pop("enrolled_at", timezone.now()),
        **extra,
    )
