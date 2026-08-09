"""Authorization rules for quiz writes.

Pure functions over primitives. Read visibility lives in
``selectors/quiz_visibility.py`` as Q builders.
"""

from __future__ import annotations


def can_edit_quiz(
    *, owner_id: int, viewer_id: int | None, viewer_is_staff: bool = False
) -> bool:
    """Whether a viewer may modify a quiz.

    Args:
        owner_id: Primary key of the quiz's owner.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        ``True`` if editing is permitted.
    """
    if viewer_id is None:
        return False
    return viewer_id == owner_id or viewer_is_staff


def can_delete_quiz(
    *, owner_id: int, viewer_id: int | None, viewer_is_staff: bool = False
) -> bool:
    """Whether a viewer may delete a quiz."""
    return can_edit_quiz(
        owner_id=owner_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )


def can_change_status(
    *, owner_id: int, viewer_id: int | None, viewer_is_staff: bool = False
) -> bool:
    """Whether a viewer may publish, unpublish or archive a quiz."""
    return can_edit_quiz(
        owner_id=owner_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
