"""Enumerations and magic values for the courses app."""

from __future__ import annotations

from django.db import models


class CourseStatus(models.TextChoices):
    """Editorial state of a course. Orthogonal to :class:`CourseVisibility`."""

    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class CourseVisibility(models.TextChoices):
    """Audience for a published course.

    ``UNLISTED`` is reachable by direct link but absent from listings  useful
    for share-by-link beta courses.
    """

    PUBLIC = "public", "Anyone"
    UNLISTED = "unlisted", "Anyone with the link"
    PRIVATE = "private", "Only me"


class CourseScope(models.TextChoices):
    """Which slice of courses a list request is asking for."""

    PUBLIC = "public", "Publicly visible courses"
    MINE = "mine", "Courses I teach, any status"
    ALL = "all", "Everything (staff only)"


class CourseDifficulty(models.TextChoices):
    """How demanding a course is."""

    BEGINNER = "beginner", "Beginner"
    INTERMEDIATE = "intermediate", "Intermediate"
    ADVANCED = "advanced", "Advanced"


class EnrollmentStatus(models.TextChoices):
    """Lifecycle of one user's membership of one course.

    ``DROPPED`` hides the course from "my courses" but deletes nothing  the
    row and the user's lesson progress survive re-enrollment.
    """

    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    DROPPED = "dropped", "Dropped"


class CourseOrdering(models.TextChoices):
    """Permitted values of the ``ordering`` query parameter."""

    NEWEST = "newest", "Newest first"
    OLDEST = "oldest", "Oldest first"
    TITLE = "title", "Title A–Z"
    POPULAR = "popular", "Most popular"


# Every entry ends with `-id`: without the tiebreaker, rows sharing a sort key
# reshuffle between pages. `POPULAR` is a placeholder mapped to publication date
# until enrollment counts power it  one line to change, no API change.
COURSE_ORDERING_MAP: dict[str, tuple[str, ...]] = {
    CourseOrdering.NEWEST: ("-published_at", "-created_at", "-id"),
    CourseOrdering.OLDEST: ("published_at", "created_at", "-id"),
    CourseOrdering.TITLE: ("title", "-id"),
    CourseOrdering.POPULAR: ("-published_at", "-created_at", "-id"),
}

# --------------------------------------------------------------------------
# Field limits
# --------------------------------------------------------------------------
COURSE_TITLE_MIN_LENGTH = 3
COURSE_TITLE_MAX_LENGTH = 160
COURSE_SLUG_MAX_LENGTH = 180
COURSE_SLUG_BASE_MAX_LENGTH = 160
COURSE_SUMMARY_MAX_LENGTH = 300
COURSE_DESCRIPTION_MIN_LENGTH = 30
MAX_CATEGORIES_PER_COURSE = 5

# Slug generation (same shape as recipes)
COURSE_SLUG_ATTEMPTS = 5
COURSE_SLUG_SUFFIX_BYTES = 3

# --------------------------------------------------------------------------
# Media
# --------------------------------------------------------------------------
COURSE_THUMBNAIL_UPLOAD_DIR = "courses/thumbnails"
COURSE_THUMBNAIL_MAX_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_COURSE_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
ALLOWED_COURSE_IMAGE_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})

# --------------------------------------------------------------------------
# Slugs that would shadow a route under /api/v1/courses/. Route literals are
# also declared before `<str:slug>`; this is the second line of defence.
# --------------------------------------------------------------------------
RESERVED_COURSE_SLUGS = frozenset(
    {
        "archive",
        "archived",
        "create",
        "draft",
        "drafts",
        "enroll",
        "lessons",
        "me",
        "new",
        "newest",
        "popular",
        "progress",
        "publish",
        "reorder",
        "search",
        "unenroll",
        "unpublish",
    }
)
