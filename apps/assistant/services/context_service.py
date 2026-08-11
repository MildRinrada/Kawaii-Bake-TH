"""Content context for the assistant, read through public cross-app APIs.

The assistant never duplicates visibility logic and never touches another
app's models directly: recipes and courses are read through their public
selectors (which apply the detail visibility rule), lessons through its
public service (which enforces the two-layer 404/403 gate). What crosses
into the ``ai`` package is a plain dict  never a Django model.

Two modes share one loader:

* **strict** (conversation creation): a hidden target raises this app's own
  404/403, so you cannot anchor a conversation to content you cannot read.
* **lenient** (every send): a target that has since vanished or been made
  private degrades to ``None``  the conversation keeps working without
  content context, and the assistant stops seeing content the viewer no
  longer can.
"""

from __future__ import annotations

from typing import Any

from apps.assistant.constants import ContextType
from apps.assistant.exceptions import ContextAccessDeniedError, ContextNotFoundError
from apps.courses.selectors import course_selector
from apps.lessons.exceptions import EnrollmentRequiredError, LessonNotVisibleError
from apps.lessons.selectors import lesson_selector
from apps.lessons.services import lesson_service
from apps.recipes.selectors import recipe_selector

# How much of each long-text field reaches the prompt. Context grounds the
# answer; it does not need to be exhaustive, and prompt size costs money.
_TEXT_LIMIT = 4000


def validate_for_creation(
    *,
    context_type: str,
    recipe_id: int | None,
    lesson_id: int | None,
    course_id: int | None,
    viewer_id: int,
    viewer_is_staff: bool,
) -> None:
    """Check the context target exists and is readable by the viewer.

    Args:
        context_type: A value of :class:`ContextType`.
        recipe_id: Target recipe id, for recipe conversations.
        lesson_id: Target lesson id, for lesson conversations.
        course_id: Target course id, for course conversations.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Raises:
        ContextNotFoundError: If the target is absent or hidden.
        ContextAccessDeniedError: If the lesson content is enrollment-gated.
    """
    build_context(
        context_type=context_type,
        recipe_id=recipe_id,
        lesson_id=lesson_id,
        course_id=course_id,
        viewer_id=viewer_id,
        viewer_is_staff=viewer_is_staff,
        strict=True,
    )


def build_context(
    *,
    context_type: str,
    recipe_id: int | None,
    lesson_id: int | None,
    course_id: int | None,
    viewer_id: int,
    viewer_is_staff: bool,
    strict: bool = False,
) -> dict[str, Any] | None:
    """Load the content context as a plain dict.

    Args:
        context_type: A value of :class:`ContextType`.
        recipe_id: Target recipe id, or ``None``.
        lesson_id: Target lesson id, or ``None``.
        course_id: Target course id, or ``None``.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.
        strict: Raise on an unreadable target instead of degrading.

    Returns:
        The context payload, or ``None`` (general conversations, or a
        vanished/hidden target in lenient mode).

    Raises:
        ContextNotFoundError: Strict mode, target absent or hidden.
        ContextAccessDeniedError: Strict mode, lesson content gated.
    """
    if context_type == ContextType.RECIPE:
        return _recipe_context(
            recipe_id=recipe_id,
            viewer_id=viewer_id,
            viewer_is_staff=viewer_is_staff,
            strict=strict,
        )
    if context_type == ContextType.LESSON:
        return _lesson_context(
            lesson_id=lesson_id,
            viewer_id=viewer_id,
            viewer_is_staff=viewer_is_staff,
            strict=strict,
        )
    if context_type == ContextType.COURSE:
        return _course_context(
            course_id=course_id,
            viewer_id=viewer_id,
            viewer_is_staff=viewer_is_staff,
            strict=strict,
        )
    return None


def _missing(*, strict: bool) -> None:
    """Handle an absent/hidden target per mode."""
    if strict:
        raise ContextNotFoundError
    return None


def _recipe_context(
    *, recipe_id: int | None, viewer_id: int, viewer_is_staff: bool, strict: bool
) -> dict[str, Any] | None:
    """Load a recipe's title, description, ingredients and steps."""
    if recipe_id is None:
        return _missing(strict=strict)
    recipe = recipe_selector.get_viewable_by_id(
        recipe_id=recipe_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if recipe is None:
        return _missing(strict=strict)
    return {
        "kind": "recipe",
        "title": recipe.title,
        "description": recipe.description[:_TEXT_LIMIT],
        "servings": recipe.servings,
        "total_minutes": recipe.total_minutes,
        "ingredients": [
            {
                "name": item.name,
                "quantity": str(item.quantity) if item.quantity is not None else None,
                "unit": item.unit,
                "note": item.note,
                "optional": item.is_optional,
            }
            for item in recipe.ingredients.all()
        ],
        "steps": [
            {"position": step.position, "body": step.body[:_TEXT_LIMIT]}
            for step in recipe.steps.all()
        ],
    }


def _lesson_context(
    *, lesson_id: int | None, viewer_id: int, viewer_is_staff: bool, strict: bool
) -> dict[str, Any] | None:
    """Load a lesson's content through lessons' two-layer gate.

    Lesson bodies are enrollment-gated, so this goes through the lessons
    app's public service  the one implementation of that gate  and
    translates its domain errors into this app's own (ADR 0008).
    """
    if lesson_id is None:
        return _missing(strict=strict)
    try:
        lesson = lesson_service.get_lesson_content(
            lesson_id=lesson_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
        )
    except LessonNotVisibleError:
        return _missing(strict=strict)
    except EnrollmentRequiredError:
        if strict:
            raise ContextAccessDeniedError from None
        return None
    return {
        "kind": "lesson",
        "title": lesson.title,
        "content": lesson.content[:_TEXT_LIMIT],
        "duration_minutes": lesson.duration_minutes,
        "course_title": lesson.course.title,
    }


def _course_context(
    *, course_id: int | None, viewer_id: int, viewer_is_staff: bool, strict: bool
) -> dict[str, Any] | None:
    """Load a course's summary and published syllabus titles."""
    if course_id is None:
        return _missing(strict=strict)
    course = course_selector.list_viewable_by_ids(
        ids=[course_id], viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    ).first()
    if course is None:
        return _missing(strict=strict)
    lessons = lesson_selector.list_published_refs(course_id=course.id)
    return {
        "kind": "course",
        "title": course.title,
        "summary": course.summary,
        "difficulty": course.difficulty,
        "lessons": [ref.title for ref in lessons],
    }
