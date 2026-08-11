"""Course lifecycle transitions.

Same state machine as recipes: every transition reversible, only DELETE is
terminal, publish is idempotent and re-validates on the archived → published
path. ``published_at`` is stamped once and freezes the slug.
"""

from __future__ import annotations

import logging

from django.utils import timezone

from apps.courses.constants import CourseStatus
from apps.courses.exceptions import CourseNotVisibleError
from apps.courses.models import Course
from apps.courses.permissions.course_permissions import can_change_status
from apps.courses.repositories import course_repository
from apps.courses.selectors import course_selector
from apps.courses.validators.publish_validator import assert_publishable

logger = logging.getLogger("kawaiibake.courses")


def _require_transitionable(
    *, slug: str, viewer_id: int, viewer_is_staff: bool
) -> Course:
    """Fetch a course whose status the caller may change."""
    course = course_selector.get_editable_course(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if course is None or not can_change_status(
        instructor_id=course.instructor_id,
        viewer_id=viewer_id,
        viewer_is_staff=viewer_is_staff,
    ):
        raise CourseNotVisibleError
    return course


def publish(*, slug: str, viewer_id: int, viewer_is_staff: bool = False) -> Course:
    """Publish a course after checking completeness.

    Idempotent; ``published_at`` is stamped only the first time.

    Raises:
        CourseNotVisibleError: If absent or not the caller's to change.
        CourseNotPublishableError: If incomplete  every failure in ``details``.
    """
    course = _require_transitionable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if course.status == CourseStatus.PUBLISHED:
        return course

    assert_publishable(course)

    changes: dict[str, object] = {"status": CourseStatus.PUBLISHED}
    if course.published_at is None:
        changes["published_at"] = timezone.now()

    course_repository.update_course(course=course, changes=changes)
    logger.info("course_published course_id=%s by=%s", course.pk, viewer_id)
    return course


def unpublish(*, slug: str, viewer_id: int, viewer_is_staff: bool = False) -> Course:
    """Return a course to draft  the hard kill switch.

    Unlike archiving, a drafted course is hidden even from enrolled students.
    ``published_at`` is retained so the slug stays frozen.
    """
    course = _require_transitionable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if course.status != CourseStatus.DRAFT:
        course_repository.update_course(
            course=course, changes={"status": CourseStatus.DRAFT}
        )
        logger.info("course_unpublished course_id=%s by=%s", course.pk, viewer_id)
    return course


def archive(*, slug: str, viewer_id: int, viewer_is_staff: bool = False) -> Course:
    """Archive a course.

    Archived courses leave every listing but stay **readable to actively
    enrolled students**  their progress must not vanish because the instructor
    tidied up.
    """
    course = _require_transitionable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if course.status != CourseStatus.ARCHIVED:
        course_repository.update_course(
            course=course, changes={"status": CourseStatus.ARCHIVED}
        )
        logger.info("course_archived course_id=%s by=%s", course.pk, viewer_id)
    return course
