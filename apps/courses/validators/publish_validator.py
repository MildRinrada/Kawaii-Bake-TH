"""Completeness rules that only apply when publishing a course.

Deliberately not enforced on every save  a draft must be saveable while
incomplete.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from apps.courses.constants import (
    COURSE_DESCRIPTION_MIN_LENGTH,
    COURSE_TITLE_MIN_LENGTH,
)
from apps.courses.exceptions import CourseNotPublishableError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.courses.models import Course


def assert_publishable(course: Course) -> None:
    """Check that a course is complete enough to publish.

    Collects **every** failure so the frontend renders a checklist rather than
    one problem per attempt.

    The lesson requirement reads ``published_lesson_count``  this app's own
    column, pushed by the lessons app  so no other app's rows are counted here
    and the ``lessons → courses`` dependency direction holds.

    Args:
        course: The course about to be published.

    Raises:
        CourseNotPublishableError: If any requirement is unmet.
    """
    problems: dict[str, list[str]] = {}

    if len(course.title.strip()) < COURSE_TITLE_MIN_LENGTH:
        problems["title"] = ["Add a longer title."]

    if len(course.description.strip()) < COURSE_DESCRIPTION_MIN_LENGTH:
        problems["description"] = [
            f"Describe the course in at least {COURSE_DESCRIPTION_MIN_LENGTH} characters."
        ]

    if course.published_lesson_count < 1:
        problems["lessons"] = ["Add at least one published lesson."]

    if not course.thumbnail:
        problems["thumbnail"] = ["Add a thumbnail image."]

    if problems:
        raise CourseNotPublishableError(details=problems)
