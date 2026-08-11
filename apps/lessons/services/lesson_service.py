"""Business logic for lessons: CRUD, the content gate, and reordering."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from apps.courses.selectors import course_selector, enrollment_selector
from apps.courses.selectors.course_selector import CourseRef
from apps.lessons.constants import MAX_LESSONS_PER_COURSE
from apps.lessons.exceptions import (
    CourseNotVisibleError,
    EnrollmentRequiredError,
    InvalidLessonQuizError,
    InvalidLessonRecipeError,
    InvalidReorderError,
    LessonLimitExceededError,
    LessonNotVisibleError,
)
from apps.lessons.models import Lesson
from apps.lessons.repositories import lesson_repository
from apps.lessons.selectors import lesson_selector
from apps.lessons.validators import lesson_validator
from apps.quizzes.selectors import quiz_selector
from apps.recipes.selectors import recipe_selector

# `position` is managed by create/reorder; `status` flips through this service
# so the counter sync always runs.
LESSON_EDITABLE_FIELDS = frozenset(
    {
        "title",
        "content",
        "duration_minutes",
        "is_preview",
        "video_url",
        "video_provider",
        "video_duration_seconds",
        "recipe_id",
        "quiz_id",
        "status",
    }
)


def require_course(
    *, slug: str, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> CourseRef:
    """Resolve a course slug through the courses app's public API.

    Raises this app's own error when hidden  a callee never raises for its
    caller (ADR 0008/0009).

    Args:
        slug: The course slug.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The course reference.

    Raises:
        CourseNotVisibleError: If the course is absent or hidden.
    """
    course = course_selector.get_course_ref(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if course is None:
        raise CourseNotVisibleError
    return course


def _require_manageable_course(
    *, slug: str, viewer_id: int, viewer_is_staff: bool
) -> CourseRef:
    """Resolve a course the caller may manage lessons on.

    "Not yours" is the same 404 as "does not exist".
    """
    course = require_course(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if course.instructor_id != viewer_id and not viewer_is_staff:
        raise CourseNotVisibleError
    return course


def _validate_recipe_link(*, recipe_id: int | None, viewer_id: int) -> None:
    """Check the author can see the recipe they are linking.

    Raises:
        InvalidLessonRecipeError: If the recipe is absent or hidden.
    """
    if recipe_id is None:
        return
    visible = recipe_selector.list_by_ids(ids=[recipe_id], viewer_id=viewer_id)
    if not visible.exists():
        raise InvalidLessonRecipeError


def _validate_quiz_link(*, quiz_id: int | None, viewer_id: int) -> None:
    """Check the author can see the quiz they are linking.

    Same shape as the recipe link: a lesson holds a **reference only**  quiz
    logic (attempts, scoring, gating) stays entirely in the quizzes app.
    Any quiz the author can open qualifies, including their own drafts and
    unlisted quizzes (unlisted is the intended pairing for gated lessons).

    Raises:
        InvalidLessonQuizError: If the quiz is absent or hidden.
    """
    if quiz_id is None:
        return
    refs = quiz_selector.list_refs_by_ids(ids=[quiz_id], viewer_id=viewer_id)
    if quiz_id not in refs:
        raise InvalidLessonQuizError


def create_lesson(
    *, course_slug: str, viewer_id: int, viewer_is_staff: bool = False, data: Mapping[str, Any]
) -> Lesson:
    """Create a lesson at the end of a course.

    Args:
        course_slug: Slug of the owning course.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.
        data: Validated payload.

    Returns:
        The created lesson.

    Raises:
        CourseNotVisibleError: If the course is absent or not the caller's.
        LessonLimitExceededError: If the course is at capacity.
    """
    course = _require_manageable_course(
        slug=course_slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    lesson_validator.validate_core(data)
    _validate_recipe_link(recipe_id=data.get("recipe_id"), viewer_id=viewer_id)
    _validate_quiz_link(quiz_id=data.get("quiz_id"), viewer_id=viewer_id)

    if lesson_repository.next_position(course_id=course.id) >= MAX_LESSONS_PER_COURSE:
        raise LessonLimitExceededError

    fields = {k: v for k, v in data.items() if k in LESSON_EDITABLE_FIELDS}
    return lesson_repository.create_lesson(course_id=course.id, **fields)


def update_lesson(
    *, lesson_id: int, viewer_id: int, viewer_is_staff: bool = False, data: Mapping[str, Any]
) -> Lesson:
    """Apply a partial update to a lesson.

    Args:
        lesson_id: Primary key of the lesson.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.
        data: Validated payload; absent keys are unchanged.

    Returns:
        The updated lesson.

    Raises:
        LessonNotVisibleError: If absent or not the caller's to edit.
    """
    lesson = _require_manageable_lesson(
        lesson_id=lesson_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    lesson_validator.validate_core(data)
    if "recipe_id" in data:
        _validate_recipe_link(recipe_id=data["recipe_id"], viewer_id=viewer_id)
    if "quiz_id" in data:
        _validate_quiz_link(quiz_id=data["quiz_id"], viewer_id=viewer_id)

    changes = {k: v for k, v in data.items() if k in LESSON_EDITABLE_FIELDS}
    return lesson_repository.update_lesson(lesson=lesson, changes=changes)


def delete_lesson(
    *, lesson_id: int, viewer_id: int, viewer_is_staff: bool = False
) -> None:
    """Delete a lesson and renumber the survivors.

    Progress rows cascade with it  deleting a lesson is an instructor's
    destructive act, distinct from a student dropping a course (which deletes
    nothing).

    Raises:
        LessonNotVisibleError: If absent or not the caller's to delete.
    """
    lesson = _require_manageable_lesson(
        lesson_id=lesson_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    lesson_repository.delete_lesson(lesson=lesson)


def reorder_lessons(
    *,
    course_slug: str,
    viewer_id: int,
    viewer_is_staff: bool = False,
    ordered_ids: Sequence[int],
) -> list[Lesson]:
    """Reorder a course's lessons to match ``ordered_ids``.

    The payload must be **exactly** the course's lesson-id set  the natural
    output of a drag-and-drop UI, and full-array semantics mean concurrent
    reorders can never interleave into a corrupt order.

    Args:
        course_slug: Slug of the course.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.
        ordered_ids: Every lesson id, in the desired order.

    Returns:
        The lessons in their new order.

    Raises:
        CourseNotVisibleError: If the course is absent or not the caller's.
        InvalidReorderError: If ids are missing, duplicated or foreign  the
            diff is reported in ``details``.
    """
    course = _require_manageable_course(
        slug=course_slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )

    submitted = list(ordered_ids)
    expected = lesson_selector.lesson_ids_for_course(course_id=course.id)
    problems: dict[str, list[int]] = {}

    duplicates = sorted({i for i in submitted if submitted.count(i) > 1})
    missing = sorted(expected - set(submitted))
    foreign = sorted(set(submitted) - expected)
    if duplicates:
        problems["duplicate_ids"] = duplicates
    if missing:
        problems["missing_ids"] = missing
    if foreign:
        problems["unknown_ids"] = foreign
    if problems:
        raise InvalidReorderError(details=problems)

    lesson_repository.reorder_lessons(course_id=course.id, ordered_ids=submitted)
    return list(
        lesson_selector.list_for_course(
            course_id=course.id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
        )
    )


def get_lesson_content(
    *, lesson_id: int, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> Lesson:
    """Fetch a lesson for full-content display, enforcing the two-layer gate.

    Layer 1 (**404**): the lesson exists for this viewer  course visible,
    lesson published (or viewer owns it). Protects existence, as in Phase 2.

    Layer 2 (**403/401**): the viewer may read the content  enrolled, owner,
    staff, or the lesson is a preview. Reached only after layer 1, so it never
    confirms anything hidden; the syllabus already made this lesson public.

    Args:
        lesson_id: Primary key of the lesson.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The lesson, with its course loaded.

    Raises:
        LessonNotVisibleError: Layer 1 failure (404).
        EnrollmentRequiredError: Layer 2 failure (403; the handler maps
            anonymous callers to 401 via ``NotAuthenticated`` in the view).
    """
    lesson = lesson_selector.get_lesson(
        lesson_id=lesson_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if lesson is None:
        raise LessonNotVisibleError

    if viewer_is_staff or lesson.is_preview:
        return lesson
    if viewer_id is not None:
        if lesson.course.instructor_id == viewer_id:
            return lesson
        enrollment = enrollment_selector.get_enrollment(
            user_id=viewer_id, course_id=lesson.course_id
        )
        if enrollment is not None and enrollment.grants_access:
            return lesson

    raise EnrollmentRequiredError


def _require_manageable_lesson(
    *, lesson_id: int, viewer_id: int, viewer_is_staff: bool
) -> Lesson:
    """Fetch a lesson the caller may modify; "not yours" is the same 404."""
    lesson = lesson_selector.get_lesson(
        lesson_id=lesson_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if lesson is None:
        raise LessonNotVisibleError
    if lesson.course.instructor_id != viewer_id and not viewer_is_staff:
        raise LessonNotVisibleError
    return lesson
