"""Who may see which courses — the single source of truth.

Same design as ``recipe_visibility``, with two additions this domain needs:

* **A ``prefix`` parameter.** The ``lessons`` app must apply the *same* rule
  across a join (``Lesson.objects.filter(course_visible_q(prefix="course__"))``).
  Exporting the Q builder with a prefix keeps one rule in one place instead of
  a second implementation that drifts.
* **An archived-but-enrolled branch.** Students keep read access to a course
  they are actively enrolled in even after it is archived; unpublishing to
  draft remains the hard kill switch.
"""

from __future__ import annotations

from django.db.models import Q

from apps.courses.constants import (
    CourseScope,
    CourseStatus,
    CourseVisibility,
    EnrollmentStatus,
)

# Matches nothing; the fail-closed default for structurally invalid requests.
MATCH_NOTHING = Q(pk__in=[])

ACCESS_GRANTING_STATUSES = (EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED)


def _publicly_listed_q(prefix: str = "") -> Q:
    """Return the condition for courses anyone may see in a listing."""
    return Q(
        **{
            f"{prefix}status": CourseStatus.PUBLISHED,
            f"{prefix}visibility": CourseVisibility.PUBLIC,
        }
    )


def visible_in_list_q(
    *,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
    scope: str = CourseScope.PUBLIC,
    prefix: str = "",
) -> Q:
    """Build the visibility condition for a course **listing**.

    Scopes are mutually exclusive, not unioned: ``mine`` pins the instructor to
    the session user so no query parameter can widen the set, and a non-staff
    ``all`` silently narrows to the public set rather than erroring (an error
    would confirm more exists).

    Args:
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.
        scope: One of :class:`CourseScope`.
        prefix: Relation prefix when filtering across a join, e.g. ``"course__"``.

    Returns:
        A ``Q`` restricting a queryset to what this viewer may list.
    """
    if scope == CourseScope.MINE:
        if viewer_id is None:
            return MATCH_NOTHING
        return Q(**{f"{prefix}instructor_id": viewer_id})

    if scope == CourseScope.ALL:
        return Q() if viewer_is_staff else _publicly_listed_q(prefix)

    return _publicly_listed_q(prefix)


def visible_detail_q(
    *,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
    prefix: str = "",
) -> Q:
    """Build the visibility condition for a **single** course.

    Broader than the listing condition in two respects: an ``unlisted``
    published course is reachable by direct link, and an **archived** course
    stays readable to a student with an active or completed enrollment — their
    progress must not vanish because the instructor tidied up.

    Args:
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.
        prefix: Relation prefix when filtering across a join, e.g. ``"course__"``.

    Returns:
        A ``Q`` restricting a queryset to what this viewer may open.
    """
    if viewer_is_staff:
        return Q()

    condition = Q(
        **{
            f"{prefix}status": CourseStatus.PUBLISHED,
            f"{prefix}visibility__in": (
                CourseVisibility.PUBLIC,
                CourseVisibility.UNLISTED,
            ),
        }
    )

    if viewer_id is not None:
        condition |= Q(**{f"{prefix}instructor_id": viewer_id})
        condition |= Q(
            **{
                f"{prefix}status": CourseStatus.ARCHIVED,
                f"{prefix}enrollments__user_id": viewer_id,
                f"{prefix}enrollments__status__in": ACCESS_GRANTING_STATUSES,
            }
        )

    return condition
