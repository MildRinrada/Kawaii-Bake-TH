"""Enrollment business logic."""

from __future__ import annotations

import logging

from apps.courses.constants import CourseStatus, EnrollmentStatus
from apps.courses.exceptions import (
    CourseNotEnrollableError,
    CourseNotVisibleError,
    NotEnrolledError,
    OwnCourseEnrollmentError,
)
from apps.courses.models import Enrollment
from apps.courses.repositories import enrollment_repository
from apps.courses.selectors import course_selector, enrollment_selector
from apps.notifications.services import notification_service

logger = logging.getLogger("kawaiibake.courses")


def enroll(*, user_id: int, slug: str) -> tuple[Enrollment, bool]:
    """Enroll a user in a course. Idempotent.

    * no row → create ACTIVE (created=True)
    * DROPPED → reactivate  COMPLETED if the user ever finished, else ACTIVE
    * ACTIVE / COMPLETED → no-op

    No 409 on re-enroll: that would punish double-clicks and client retries,
    the same reasoning as idempotent publish.

    Args:
        user_id: Primary key of the enrolling user.
        slug: The course slug.

    Returns:
        The enrollment and whether it was newly created.

    Raises:
        CourseNotVisibleError: If the course is absent or hidden (404  never
            confirms a hidden course exists).
        CourseNotEnrollableError: If the course is not published.
        OwnCourseEnrollmentError: If the instructor is enrolling in their own.
    """
    course = course_selector.get_course_ref(slug=slug, viewer_id=user_id)
    if course is None:
        raise CourseNotVisibleError
    if course.instructor_id == user_id:
        raise OwnCourseEnrollmentError
    if course.status != CourseStatus.PUBLISHED:
        raise CourseNotEnrollableError

    enrollment, created = enrollment_repository.create_or_get(
        user_id=user_id, course_id=course.id
    )

    reactivated = not created and enrollment.status == EnrollmentStatus.DROPPED
    if reactivated:
        restored_status = (
            EnrollmentStatus.COMPLETED
            if enrollment.completed_at is not None
            else EnrollmentStatus.ACTIVE
        )
        enrollment_repository.set_status(enrollment=enrollment, status=restored_status)

    if created:
        logger.info("enrolled user_id=%s course_id=%s", user_id, course.id)
    if created or reactivated:
        # A joined-or-returned student is news to the instructor; the
        # active/completed no-op is not. Best-effort, post-commit
        # (ADR 0016)  a notification problem never fails the enrollment.
        notification_service.notify_course_enrollment(
            instructor_id=course.instructor_id,
            student_handle=enrollment.user.username,
            course_title=course.title,
            course_slug=course.slug,
        )
    return enrollment, created


def unenroll(*, user_id: int, slug: str) -> Enrollment:
    """Drop a course. Soft and idempotent  nothing is deleted.

    The enrollment row and the user's lesson progress (owned by the lessons
    app) both survive, so re-enrolling restores history.

    Args:
        user_id: Primary key of the user.
        slug: The course slug.

    Returns:
        The dropped enrollment.

    Raises:
        CourseNotVisibleError: If the course is absent or hidden.
        NotEnrolledError: If the user was never enrolled.
    """
    course = course_selector.get_course_ref(slug=slug, viewer_id=user_id)
    if course is None:
        raise CourseNotVisibleError

    enrollment = enrollment_selector.get_enrollment_row(
        user_id=user_id, course_id=course.id
    )
    if enrollment is None:
        raise NotEnrolledError

    if enrollment.status != EnrollmentStatus.DROPPED:
        enrollment_repository.set_status(
            enrollment=enrollment, status=EnrollmentStatus.DROPPED
        )
        logger.info("unenrolled user_id=%s course_id=%s", user_id, course.id)
    return enrollment


def record_course_completion(*, user_id: int, course_id: int) -> None:
    """Record that a user finished every lesson of a course.

    **Public cross-app write API** (ADR 0009): called by the lessons app, which
    owns all progress computation. This app records an idempotent fact on its
    own row and computes nothing.

    Never downgrades: a COMPLETED enrollment stays completed even if lessons
    are added later, and ``completed_at`` is stamped exactly once.

    Args:
        user_id: Primary key of the user.
        course_id: Primary key of the course.
    """
    enrollment = enrollment_selector.get_enrollment_row(
        user_id=user_id, course_id=course_id
    )
    if enrollment is None or enrollment.status != EnrollmentStatus.ACTIVE:
        return

    enrollment_repository.mark_completed(enrollment=enrollment)
    logger.info("course_completed user_id=%s course_id=%s", user_id, course_id)
