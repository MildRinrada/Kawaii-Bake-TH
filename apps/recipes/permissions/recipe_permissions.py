"""Authorization rules for recipe writes.

Pure functions over primitives: no ORM, no ``request``.

Read visibility is **not** here. A listing needs a ``Q``, not a boolean, so both
read paths share the builders in ``selectors/recipe_visibility.py``; a second
boolean implementation of the same rule would drift from it.
"""

from __future__ import annotations


def can_edit_recipe(
    *, author_id: int, viewer_id: int | None, viewer_is_staff: bool = False
) -> bool:
    """Whether a viewer may modify a recipe.

    Args:
        author_id: Primary key of the recipe's author.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        ``True`` if editing is permitted.
    """
    if viewer_id is None:
        return False
    return viewer_id == author_id or viewer_is_staff


def can_delete_recipe(
    *, author_id: int, viewer_id: int | None, viewer_is_staff: bool = False
) -> bool:
    """Whether a viewer may delete a recipe.

    Args:
        author_id: Primary key of the recipe's author.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        ``True`` if deletion is permitted.
    """
    return can_edit_recipe(
        author_id=author_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )


def can_change_status(
    *, author_id: int, viewer_id: int | None, viewer_is_staff: bool = False
) -> bool:
    """Whether a viewer may publish, unpublish or archive a recipe.

    Args:
        author_id: Primary key of the recipe's author.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        ``True`` if the transition is permitted.
    """
    return can_edit_recipe(
        author_id=author_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
