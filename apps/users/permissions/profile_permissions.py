"""Authorization rules for profile access.

Pure functions over primitives: no ORM, no ``request``. This keeps the rules
unit-testable and callable from both selectors and the API layer.
"""

from __future__ import annotations

from apps.users.constants import ProfileVisibility


def can_view_profile(
    *,
    owner_id: int,
    visibility: str,
    viewer_id: int | None,
    viewer_is_staff: bool = False,
) -> bool:
    """Decide whether a viewer may see a profile.

    Args:
        owner_id: Primary key of the profile's owner.
        visibility: The owner's :class:`ProfileVisibility` setting.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        ``True`` if the profile may be shown.
    """
    if viewer_id is not None and viewer_id == owner_id:
        return True
    if viewer_is_staff:
        return True
    if visibility == ProfileVisibility.PUBLIC:
        return True
    if visibility == ProfileVisibility.MEMBERS:
        return viewer_id is not None
    return False


def can_edit_profile(*, owner_id: int, viewer_id: int | None) -> bool:
    """Decide whether a viewer may modify a profile.

    Only the owner may edit; staff edit through the Django admin, which has its
    own audit trail.

    Args:
        owner_id: Primary key of the profile's owner.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.

    Returns:
        ``True`` if editing is permitted.
    """
    return viewer_id is not None and viewer_id == owner_id
