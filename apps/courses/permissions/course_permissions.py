"""Authorization rules for course writes.

Pure functions over primitives. Read visibility lives in
``selectors/course_visibility.py`` as Q builders  see the recipes app for why
a parallel boolean would drift.
"""

from __future__ import annotations


def can_edit_course(
    *, instructor_id: int, viewer_id: int | None, viewer_is_staff: bool = False
) -> bool:
    """Whether a viewer may modify a course.

    Args:
        instructor_id: Primary key of the course's instructor.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        ``True`` if editing is permitted.
    """
    if viewer_id is None:
        return False
    return viewer_id == instructor_id or viewer_is_staff


def can_delete_course(
    *, instructor_id: int, viewer_id: int | None, viewer_is_staff: bool = False
) -> bool:
    """Whether a viewer may delete a course."""
    return can_edit_course(
        instructor_id=instructor_id,
        viewer_id=viewer_id,
        viewer_is_staff=viewer_is_staff,
    )


def can_change_status(
    *, instructor_id: int, viewer_id: int | None, viewer_is_staff: bool = False
) -> bool:
    """Whether a viewer may publish, unpublish or archive a course."""
    return can_edit_course(
        instructor_id=instructor_id,
        viewer_id=viewer_id,
        viewer_is_staff=viewer_is_staff,
    )
