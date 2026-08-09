"""Enumerations and magic values for the lessons app."""

from __future__ import annotations

from django.db import models


class LessonStatus(models.TextChoices):
    """Editorial state of a lesson.

    Two states, not three: a lesson has no audience of its own — the course
    carries visibility — so "archived" would duplicate "draft" here.
    """

    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"


class VideoProvider(models.TextChoices):
    """Where an embedded lesson video is hosted.

    External embeds only — no video infrastructure exists yet. The provider
    tells the Next.js frontend which player to render.
    """

    YOUTUBE = "youtube", "YouTube"
    VIMEO = "vimeo", "Vimeo"
    OTHER = "other", "Other"


# --------------------------------------------------------------------------
# Field limits
# --------------------------------------------------------------------------
LESSON_TITLE_MIN_LENGTH = 3
LESSON_TITLE_MAX_LENGTH = 160
LESSON_CONTENT_MAX_LENGTH = 50_000

MAX_LESSONS_PER_COURSE = 100

MIN_PROGRESS_PERCENT = 0
MAX_PROGRESS_PERCENT = 100
