"""The single visibility rule for gallery posts.

One ``Q`` builder used by list, detail and every filter — the
recipes/courses discipline: there is no second implementation to drift.
"""

from __future__ import annotations

from django.db.models import Q

from apps.gallery.constants import GalleryPostStatus


def visible_q(
    *, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> Q:
    """Build the post-visibility predicate for a viewer.

    Published posts are public; unpublished posts exist only for their
    author (and staff). There is no unlisted tier and no separate detail
    rule — a two-state showcase does not need one.

    Args:
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        A composable ``Q``.
    """
    if viewer_is_staff:
        return Q()
    q = Q(status=GalleryPostStatus.PUBLISHED)
    if viewer_id is not None:
        q |= Q(author_id=viewer_id)
    return q
