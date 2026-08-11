"""Who may see which recipes  the single source of truth.

Both the list and the detail path build their filter from this module. The
obvious alternative, a ``can_view_recipe()`` boolean beside a separate list
filter, means one rule with two implementations, and two implementations drift.
A list needs a ``Q``, so the ``Q`` is what both paths use.

Everything here **fails closed**:

* both builders default to an anonymous, non-staff viewer;
* there is deliberately no "all recipes" builder, so no caller can bypass them;
* callers only ever ``.filter()`` further, and a filter can only narrow a set.
"""

from __future__ import annotations

from django.db.models import Q

from apps.recipes.constants import RecipeScope, RecipeStatus, RecipeVisibility

# Matches nothing. Used where a request is structurally invalid rather than
# merely empty, so the failure mode is "no results" and never "all results".
MATCH_NOTHING = Q(pk__in=[])


def _publicly_listed_q(prefix: str = "") -> Q:
    """Return the condition for recipes anyone may see in a listing."""
    return Q(
        **{
            f"{prefix}status": RecipeStatus.PUBLISHED,
            f"{prefix}visibility": RecipeVisibility.PUBLIC,
        }
    )


def visible_in_list_q(
    *,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
    scope: str = RecipeScope.PUBLIC,
    prefix: str = "",
) -> Q:
    """Build the visibility condition for a recipe **listing**.

    Scopes are mutually exclusive rather than unioned. A
    "published-public OR mine" union would splice half-finished drafts into the
    browse feed, and  more importantly  ``scope=mine`` pins ``author_id`` to
    the session user, so no combination of query parameters can widen the set
    to another author's drafts.

    Note that ``unlisted`` recipes are excluded from every public listing: that
    is the entire point of unlisted, which remains reachable by direct link.

    Args:
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.
        scope: One of :class:`RecipeScope`.
        prefix: Relation prefix when filtering across a join, e.g. ``"recipe__"``
            (the mechanism ADR 0009 introduced for courses).

    Returns:
        A ``Q`` restricting a queryset to what this viewer may list.
    """
    if scope == RecipeScope.MINE:
        # An anonymous caller has no "mine"; the view rejects this first, and
        # this branch guarantees the selector cannot leak if it ever does not.
        if viewer_id is None:
            return MATCH_NOTHING
        return Q(**{f"{prefix}author_id": viewer_id})

    if scope == RecipeScope.ALL:
        # Silently narrow rather than raise: a non-staff caller asking for
        # everything gets the public set, never an error that confirms more exists.
        return Q() if viewer_is_staff else _publicly_listed_q(prefix)

    return _publicly_listed_q(prefix)


def visible_detail_q(
    *,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
    prefix: str = "",
) -> Q:
    """Build the visibility condition for a **single** recipe.

    Broader than the listing condition in exactly one respect: an ``unlisted``
    published recipe is reachable here. Everything else that is not public
    requires ownership or staff.

    Args:
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.
        prefix: Relation prefix when filtering across a join, e.g. ``"recipe__"``.

    Returns:
        A ``Q`` restricting a queryset to what this viewer may open.
    """
    if viewer_is_staff:
        return Q()

    condition = Q(
        **{
            f"{prefix}status": RecipeStatus.PUBLISHED,
            f"{prefix}visibility__in": (
                RecipeVisibility.PUBLIC,
                RecipeVisibility.UNLISTED,
            ),
        }
    )
    if viewer_id is not None:
        condition |= Q(**{f"{prefix}author_id": viewer_id})
    return condition
