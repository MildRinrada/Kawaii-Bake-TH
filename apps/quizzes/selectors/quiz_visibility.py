"""Who may see which quizzes — the single source of truth.

Same design as ``recipe_visibility``/``course_visibility``, with the branch
this domain needs: an **archived quiz stays readable to anyone who has
attempted it** — a student's result history must not vanish because the
instructor tidied up (the archived-but-enrolled precedent from courses).
Starting new attempts on an archived quiz is still blocked by the status
check in the attempt service; this branch grants *reading* only.
"""

from __future__ import annotations

from django.db.models import Q

from apps.quizzes.constants import QuizScope, QuizStatus, QuizVisibility

# Matches nothing; the fail-closed default for structurally invalid requests.
MATCH_NOTHING = Q(pk__in=[])


def _publicly_listed_q(prefix: str = "") -> Q:
    """Return the condition for quizzes anyone may see in a listing."""
    return Q(
        **{
            f"{prefix}status": QuizStatus.PUBLISHED,
            f"{prefix}visibility": QuizVisibility.PUBLIC,
        }
    )


def visible_in_list_q(
    *,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
    scope: str = QuizScope.PUBLIC,
    prefix: str = "",
) -> Q:
    """Build the visibility condition for a quiz **listing**.

    Scopes are mutually exclusive, not unioned: ``mine`` pins the owner to the
    session user, and a non-staff ``all`` silently narrows to the public set
    rather than erroring (an error would confirm more exists).

    Args:
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.
        scope: One of :class:`QuizScope`.
        prefix: Relation prefix when filtering across a join, e.g. ``"quiz__"``.

    Returns:
        A ``Q`` restricting a queryset to what this viewer may list.
    """
    if scope == QuizScope.MINE:
        if viewer_id is None:
            return MATCH_NOTHING
        return Q(**{f"{prefix}owner_id": viewer_id})

    if scope == QuizScope.ALL:
        return Q() if viewer_is_staff else _publicly_listed_q(prefix)

    return _publicly_listed_q(prefix)


def visible_detail_q(
    *,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
    prefix: str = "",
) -> Q:
    """Build the visibility condition for a **single** quiz.

    Broader than the listing condition in two respects: an ``unlisted``
    published quiz is reachable by direct link (the course-integration path),
    and an archived quiz stays readable to a viewer with attempt history.

    The attempts join can produce duplicate rows (a user may have many
    attempts); single-row callers use ``.first()`` and set-returning callers
    must ``.distinct()``.

    Args:
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.
        prefix: Relation prefix when filtering across a join, e.g. ``"quiz__"``.

    Returns:
        A ``Q`` restricting a queryset to what this viewer may open.
    """
    if viewer_is_staff:
        return Q()

    condition = Q(
        **{
            f"{prefix}status": QuizStatus.PUBLISHED,
            f"{prefix}visibility__in": (
                QuizVisibility.PUBLIC,
                QuizVisibility.UNLISTED,
            ),
        }
    )

    if viewer_id is not None:
        condition |= Q(**{f"{prefix}owner_id": viewer_id})
        condition |= Q(
            **{
                f"{prefix}status": QuizStatus.ARCHIVED,
                f"{prefix}attempts__user_id": viewer_id,
            }
        )

    return condition
