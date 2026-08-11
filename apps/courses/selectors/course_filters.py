"""The input contract for course listings."""

from __future__ import annotations

from dataclasses import dataclass

from apps.courses.constants import CourseOrdering, CourseScope


@dataclass(frozen=True)
class CourseListFilters:
    """User-supplied narrowing options for a course listing.

    Viewer identity is deliberately absent: it is a separate selector argument,
    so nothing in a query string can influence who the server thinks is asking.
    """

    search: str = ""
    category_slugs: tuple[str, ...] = ()
    difficulty: tuple[str, ...] = ()
    instructor_username: str = ""
    ordering: str = CourseOrdering.NEWEST
    scope: str = CourseScope.PUBLIC
    # Narrow-only: intersects the visibility rule (see recipes).
    status: str = ""
