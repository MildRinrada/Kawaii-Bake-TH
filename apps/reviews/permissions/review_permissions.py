"""Authorization rules for review writes.

Pure functions over primitives.
"""

from __future__ import annotations


def can_edit_review(
    *, reviewer_id: int, viewer_id: int | None, viewer_is_staff: bool = False
) -> bool:
    """Whether a viewer may edit or delete a review.

    Args:
        reviewer_id: Primary key of the review's author.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        ``True`` if permitted.
    """
    if viewer_id is None:
        return False
    return viewer_id == reviewer_id or viewer_is_staff


def can_moderate(*, viewer_is_staff: bool) -> bool:
    """Whether a viewer may change a review's moderation status."""
    return viewer_is_staff
