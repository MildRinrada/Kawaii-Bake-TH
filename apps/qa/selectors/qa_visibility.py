"""The single visibility rule for question threads.

One prefix-parameterised ``Q`` builder (the recipes/courses mechanism) 
used by the thread list, thread detail, answer endpoints (via
``prefix="thread__"``) and search alike. There is deliberately no
``can_view_thread()`` twin implementation.
"""

from __future__ import annotations

from django.db.models import Q

from apps.qa.constants import ThreadStatus


def visible_q(
    *,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
    prefix: str = "",
) -> Q:
    """Build the thread-visibility predicate for a viewer.

    Active threads are public. Hidden threads remain visible to their
    author (they must see what moderation did  the reviews rule) and to
    staff. Deleted threads are visible to **no one**, author included:
    soft-deleted history exists for the database, never for the API.

    Args:
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.
        prefix: Relation prefix (``"thread__"``) for composing across a
            join from the answers table.

    Returns:
        A composable ``Q``.
    """
    status_field = f"{prefix}status"
    q = Q(**{status_field: ThreadStatus.ACTIVE})
    if viewer_is_staff:
        q |= Q(**{status_field: ThreadStatus.HIDDEN})
    elif viewer_id is not None:
        q |= Q(
            **{status_field: ThreadStatus.HIDDEN, f"{prefix}author_id": viewer_id}
        )
    return q
