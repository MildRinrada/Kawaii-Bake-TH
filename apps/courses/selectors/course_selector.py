"""Read-side queries for courses.

Also home of :class:`CourseRef`  the frozen reference the ``lessons`` app uses
instead of touching this app's model. Part of the public cross-app API.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Exists, OuterRef, Prefetch, Q, QuerySet

from apps.courses.constants import COURSE_ORDERING_MAP, EnrollmentStatus
from apps.courses.models import Course, Enrollment
from apps.courses.selectors.course_filters import CourseListFilters
from apps.courses.selectors.course_visibility import (
    visible_detail_q,
    visible_in_list_q,
)
from apps.recipe_categories.selectors import category_selector


@dataclass(frozen=True)
class CourseRef:
    """A course reference safe to hand across the app boundary.

    Carries everything ``lessons`` needs  identity for FK writes, the
    instructor for owner checks, and the state pair for its own decisions 
    without exposing the model.
    """

    id: int
    slug: str
    title: str
    instructor_id: int
    status: str
    visibility: str


def _base_list_queryset() -> QuerySet[Course]:
    """Return the queryset shape shared by every course listing."""
    return (
        Course.objects.select_related("instructor", "instructor__profile")
        .prefetch_related(
            Prefetch("categories", queryset=category_selector.ref_queryset())
        )
        .defer("description")
    )


def _annotate_enrollment(
    queryset: QuerySet[Course], *, viewer_id: int | None
) -> QuerySet[Course]:
    """Annotate each course with the viewer's enrollment state.

    One ``Exists`` subquery per flavour rather than a join  no row
    multiplication, and the card serializer never touches the ORM.
    """
    if viewer_id is None:
        return queryset

    base = Enrollment.objects.filter(course=OuterRef("pk"), user_id=viewer_id)
    return queryset.annotate(
        viewer_is_enrolled=Exists(
            base.filter(
                status__in=(EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED)
            )
        ),
        viewer_has_completed=Exists(
            base.filter(status=EnrollmentStatus.COMPLETED)
        ),
    )


def list_courses(
    *,
    filters: CourseListFilters,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
) -> QuerySet[Course]:
    """Build the course listing queryset for a viewer.

    Args:
        filters: Parsed, validated query parameters.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        A lazy queryset of visible courses, annotated with the viewer's
        enrollment state.
    """
    queryset = _base_list_queryset().filter(
        visible_in_list_q(
            viewer_id=viewer_id, viewer_is_staff=viewer_is_staff, scope=filters.scope
        )
    )

    if filters.status:
        # Intersects visibility - narrow-only, same rationale as recipes.
        queryset = queryset.filter(status=filters.status)

    if filters.search:
        queryset = queryset.filter(
            Q(title__icontains=filters.search)
            | Q(summary__icontains=filters.search)
            | Q(description__icontains=filters.search)
        )
    if filters.category_slugs:
        queryset = queryset.filter(
            categories__slug__in=filters.category_slugs
        ).distinct()
    if filters.difficulty:
        queryset = queryset.filter(difficulty__in=filters.difficulty)
    if filters.instructor_username:
        queryset = queryset.filter(
            instructor__username__iexact=filters.instructor_username
        )

    queryset = _annotate_enrollment(queryset, viewer_id=viewer_id)
    return queryset.order_by(*COURSE_ORDERING_MAP[filters.ordering])


def get_course_detail(
    *, slug: str, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> Course | None:
    """Fetch one course with everything the detail payload needs.

    Args:
        slug: The course slug.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The course, or ``None`` when absent or hidden  callers must not
        distinguish the two to the client.
    """
    queryset = (
        Course.objects.filter(
            visible_detail_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff)
        )
        .filter(slug__iexact=slug.strip())
        .select_related("instructor", "instructor__profile")
        .prefetch_related(
            Prefetch("categories", queryset=category_selector.ref_queryset())
        )
    )
    return _annotate_enrollment(queryset, viewer_id=viewer_id).first()


def get_editable_course(
    *, slug: str, viewer_id: int, viewer_is_staff: bool = False
) -> Course | None:
    """Fetch a course for a write operation.

    Write permission is decided by ``permissions/``; this only ensures the
    caller can even name the course.

    Args:
        slug: The course slug.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Returns:
        The course, or ``None``.
    """
    return (
        Course.objects.filter(
            visible_detail_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff)
        )
        .filter(slug__iexact=slug.strip())
        .first()
    )


def get_course_ref(
    *, slug: str, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> CourseRef | None:
    """Fetch a course reference for another app.

    Part of the public cross-app API (ADR 0009). Returns ``None`` when the
    course is absent **or** hidden from this viewer; the caller raises its own
    domain error for that case  never this app's.

    Args:
        slug: The course slug.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        A :class:`CourseRef`, or ``None``.
    """
    row = (
        Course.objects.filter(
            visible_detail_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff)
        )
        .filter(slug__iexact=slug.strip())
        .values("id", "slug", "title", "instructor_id", "status", "visibility")
        .first()
    )
    return CourseRef(**row) if row else None


def list_viewable_by_ids(
    *,
    ids: list[int],
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
) -> QuerySet[Course]:
    """Fetch specific courses under the **detail** visibility rule.

    Part of the public cross-app API (Phase 5)  the favorites list gathers
    ids under the detail rule (including archived-but-enrolled courses) and
    fetches the cards here, so a student's bookmarked archived course does not
    vanish. ``distinct()`` because the archived-but-enrolled branch joins
    enrollments.

    Args:
        ids: Course primary keys.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        A queryset with card prefetches and enrollment annotations applied.
    """
    if not ids:
        return Course.objects.none()
    queryset = (
        _base_list_queryset()
        .filter(
            visible_detail_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff)
        )
        .filter(pk__in=ids)
        .distinct()
    )
    return _annotate_enrollment(queryset, viewer_id=viewer_id)


@dataclass(frozen=True)
class CourseCandidateFact:
    """The scoring-relevant facts of one publicly listed course.

    Part of the public cross-app API (Phase 12)  the courses mirror of
    ``RecipeCandidateFact``. Everything here already appears on the public
    card.
    """

    id: int
    instructor_id: int
    difficulty: str
    published_at: object
    category_slugs: tuple[str, ...]


def public_candidate_facts(*, limit: int) -> list[CourseCandidateFact]:
    """Facts of the newest publicly listed courses, for recommendation.

    Applies the **anonymous public listing** rule  the recommendation feed
    must never carry unlisted, draft or archived courses, regardless of what
    the viewer could open directly (an archived course stays readable to its
    enrolled students, but is no longer something to recommend).

    Args:
        limit: Maximum number of candidates, newest first.

    Returns:
        Fact rows, newest first. Two queries regardless of ``limit``.
    """
    rows = list(
        Course.objects.filter(visible_in_list_q())
        .order_by("-published_at", "-created_at", "-id")
        .values("id", "instructor_id", "difficulty", "published_at")[:limit]
    )
    slug_map = category_slugs_for_courses(ids=[row["id"] for row in rows])
    return [
        CourseCandidateFact(
            id=row["id"],
            instructor_id=row["instructor_id"],
            difficulty=row["difficulty"],
            published_at=row["published_at"],
            category_slugs=slug_map.get(row["id"], ()),
        )
        for row in rows
    ]


@dataclass(frozen=True)
class CourseSignalFact:
    """Instructor and categories of a course the user has interacted with.

    Part of the public cross-app API (Phase 12). Not visibility-filtered:
    it describes the caller's own history (their enrollments, favorites,
    reviews) and is consumed as aggregate interest evidence only  never
    serialized.
    """

    instructor_id: int
    category_slugs: tuple[str, ...]


def signal_facts(*, ids: list[int]) -> dict[int, CourseSignalFact]:
    """Instructor and category facts for specific courses, in one query.

    Args:
        ids: Course primary keys from the caller's own interaction history.

    Returns:
        Mapping of course id to its fact (absent ids are dropped).
    """
    if not ids:
        return {}
    slugs: dict[int, list[str]] = {}
    instructors: dict[int, int] = {}
    for course_id, instructor_id, slug in (
        Course.objects.filter(pk__in=ids)
        .values_list("id", "instructor_id", "categories__slug")
        .order_by("id", "categories__slug")
    ):
        instructors[course_id] = instructor_id
        if slug is not None:
            slugs.setdefault(course_id, []).append(slug)
    return {
        course_id: CourseSignalFact(
            instructor_id=instructor_id,
            category_slugs=tuple(slugs.get(course_id, ())),
        )
        for course_id, instructor_id in instructors.items()
    }


def category_slugs_for_courses(*, ids: list[int]) -> dict[int, tuple[str, ...]]:
    """Category slugs per course, in one query.

    Args:
        ids: Course primary keys.

    Returns:
        Mapping of course id to its sorted category slugs (absent = none).
    """
    if not ids:
        return {}
    grouped: dict[int, list[str]] = {}
    for course_id, slug in (
        Course.objects.filter(pk__in=ids)
        .exclude(categories__isnull=True)
        .values_list("id", "categories__slug")
        .order_by("id", "categories__slug")
    ):
        grouped.setdefault(course_id, []).append(slug)
    return {course_id: tuple(slugs) for course_id, slugs in grouped.items()}


def slug_exists(*, slug: str, exclude_pk: int | None = None) -> bool:
    """Whether a course slug is already taken.

    Args:
        slug: The candidate slug.
        exclude_pk: A course to ignore, for update validation.

    Returns:
        ``True`` if the slug is in use.
    """
    queryset = Course.objects.filter(slug__iexact=slug.strip())
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset.exists()
