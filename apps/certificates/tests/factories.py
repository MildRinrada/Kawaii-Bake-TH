"""Test data builders for the certificate domain."""

from __future__ import annotations

from itertools import count
from typing import Any

from apps.courses.tests.factories import create_published_course, enroll_user
from apps.lessons.tests.factories import create_lesson
from apps.progress.services import progress_service

_sequence = count(1)


def build_completed_course(*, student: Any, instructor: Any, **extra: Any):
    """Create a one-lesson course and complete it through the real path.

    Enrollment and lesson completion go through the production services, so
    ``CourseProgress.completed_at`` is stamped exactly as it would be live —
    certificates then read that fact.

    Returns:
        The completed course.
    """
    index = next(_sequence)
    extra.setdefault("slug", f"cert-course-{index}")
    extra.setdefault("title", f"คอร์สเบเกอรี่ {index}")
    course = create_published_course(instructor=instructor, **extra)
    lesson = create_lesson(course=course)
    enroll_user(user=student, course=course)
    progress_service.complete_lesson(user_id=student.id, lesson_id=lesson.id)
    return course
