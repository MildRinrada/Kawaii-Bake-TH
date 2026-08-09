"""Authorization rules for the question bank.

Pure functions over primitives. The bank's entire knowledge of users is the
``author_id`` comparison below — nothing here may ever join into user state.
"""

from __future__ import annotations


def can_manage_question(
    *, author_id: int, viewer_id: int | None, viewer_is_staff: bool = False
) -> bool:
    """Whether a viewer may read, edit or delete a bank question.

    Args:
        author_id: Primary key of the question's author.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        ``True`` if management is permitted.
    """
    if viewer_id is None:
        return False
    return viewer_id == author_id or viewer_is_staff
