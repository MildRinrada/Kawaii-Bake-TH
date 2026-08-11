"""Enumerations and magic values for the quizzes app."""

from __future__ import annotations

from django.db import models


class QuizStatus(models.TextChoices):
    """Editorial state of a quiz. Orthogonal to :class:`QuizVisibility`."""

    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class QuizVisibility(models.TextChoices):
    """Audience for a published quiz.

    ``UNLISTED`` is the course-integration answer: a quiz linked from an
    enrollment-gated lesson is set unlisted, so it never appears in browse and
    is only reached through the lesson. A true course-only gate would require
    this app to know about lessons and enrollments  the forbidden direction.
    """

    PUBLIC = "public", "Anyone"
    UNLISTED = "unlisted", "Anyone with the link"
    PRIVATE = "private", "Only me"


class QuizScope(models.TextChoices):
    """Which slice of quizzes a list request is asking for."""

    PUBLIC = "public", "Publicly visible quizzes"
    MINE = "mine", "Quizzes I own, any status"
    ALL = "all", "Everything (staff only)"


class AttemptStatus(models.TextChoices):
    """Lifecycle of one attempt at one quiz."""

    IN_PROGRESS = "in_progress", "In progress"
    SUBMITTED = "submitted", "Submitted"


class QuizOrdering(models.TextChoices):
    """Permitted values of the ``ordering`` query parameter."""

    NEWEST = "newest", "Newest first"
    OLDEST = "oldest", "Oldest first"
    TITLE = "title", "Title A–Z"
    POPULAR = "popular", "Most popular"


# Every entry ends with `-id` for a stable pagination tiebreaker. `POPULAR` is
# a placeholder mapped to publication date until attempt counts power it.
QUIZ_ORDERING_MAP: dict[str, tuple[str, ...]] = {
    QuizOrdering.NEWEST: ("-published_at", "-created_at", "-id"),
    QuizOrdering.OLDEST: ("published_at", "created_at", "-id"),
    QuizOrdering.TITLE: ("title", "-id"),
    QuizOrdering.POPULAR: ("-published_at", "-created_at", "-id"),
}

# --------------------------------------------------------------------------
# Field limits
# --------------------------------------------------------------------------
QUIZ_TITLE_MIN_LENGTH = 3
QUIZ_TITLE_MAX_LENGTH = 160
QUIZ_SLUG_MAX_LENGTH = 180
QUIZ_SLUG_BASE_MAX_LENGTH = 160
QUIZ_DESCRIPTION_MIN_LENGTH = 30
DEFAULT_PASS_PERCENT = 70
MAX_QUESTIONS_PER_QUIZ = 100
DEFAULT_QUESTION_POINTS = 1

# Slug generation (same shape as recipes/courses)
QUIZ_SLUG_ATTEMPTS = 5
QUIZ_SLUG_SUFFIX_BYTES = 3

# --------------------------------------------------------------------------
# Slugs that would shadow a route under /api/v1/quizzes/. Route literals are
# also declared before `<str:slug>`; this is the second line of defence.
# --------------------------------------------------------------------------
RESERVED_QUIZ_SLUGS = frozenset(
    {
        "archive",
        "archived",
        "attempts",
        "create",
        "draft",
        "drafts",
        "me",
        "new",
        "newest",
        "popular",
        "publish",
        "questions",
        "search",
        "start",
        "submit",
        "tags",
        "unpublish",
    }
)
