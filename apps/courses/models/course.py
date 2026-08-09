"""The course aggregate root."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from apps.common.utils.files import build_upload_path
from apps.core.models.base import TimeStampedModel
from apps.courses.constants import (
    COURSE_SLUG_MAX_LENGTH,
    COURSE_SUMMARY_MAX_LENGTH,
    COURSE_THUMBNAIL_UPLOAD_DIR,
    COURSE_TITLE_MAX_LENGTH,
    CourseDifficulty,
    CourseStatus,
    CourseVisibility,
)
from infrastructure.storage import get_media_storage


def thumbnail_upload_to(instance: Course, filename: str) -> str:
    """Build the storage path for a course thumbnail."""
    return build_upload_path(directory=COURSE_THUMBNAIL_UPLOAD_DIR, filename=filename)


class Course(TimeStampedModel):
    """A structured baking course.

    ``status`` and ``visibility`` are orthogonal, and ``published_at`` is
    separate from ``status``, for exactly the reasons documented on
    :class:`apps.recipes.models.recipe.Recipe`.

    **``published_lesson_count`` is the app boundary made physical.** The
    publish gate requires "lessons exist", but this app must never count
    another app's rows — that would invert the ``lessons → courses`` dependency
    and stop this app being shippable alone. Instead the ``lessons`` app pushes
    the count through ``course_service.sync_published_lesson_count()`` inside
    the same transaction as every lesson mutation. It also serves every course
    card without a join. It is a rebuildable cache, not a source of truth;
    ``manage.py recount_lessons`` reconciles it.

    Reverse accessors reserved for future apps: ``quizzes``, ``certificates``,
    ``reviews``, ``favorites``. ``lessons`` is taken by the FK on ``Lesson``.
    """

    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="courses_taught",
    )
    categories = models.ManyToManyField(
        "recipe_categories.RecipeCategory",
        related_name="courses",
        blank=True,
    )

    title = models.CharField(max_length=COURSE_TITLE_MAX_LENGTH)
    slug = models.SlugField(
        max_length=COURSE_SLUG_MAX_LENGTH,
        unique=True,
        allow_unicode=True,
        help_text="Frozen once the course is first published.",
    )
    summary = models.CharField(
        max_length=COURSE_SUMMARY_MAX_LENGTH,
        blank=True,
        help_text="One-line description shown on cards.",
    )
    description = models.TextField(blank=True)

    difficulty = models.CharField(
        max_length=20,
        choices=CourseDifficulty.choices,
        default=CourseDifficulty.BEGINNER,
    )

    status = models.CharField(
        max_length=20,
        choices=CourseStatus.choices,
        default=CourseStatus.DRAFT,
        db_index=True,
    )
    visibility = models.CharField(
        max_length=20,
        choices=CourseVisibility.choices,
        default=CourseVisibility.PUBLIC,
        db_index=True,
    )
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)

    thumbnail = models.ImageField(
        upload_to=thumbnail_upload_to,
        storage=get_media_storage,
        blank=True,
    )

    published_lesson_count = models.PositiveIntegerField(
        default=0,
        help_text=(
            "Maintained by the lessons app on every lesson mutation. "
            "Rebuild with `manage.py recount_lessons`."
        ),
    )
    published_duration_minutes = models.PositiveIntegerField(
        default=0,
        help_text=(
            "Sum of published lessons' durations. Maintained by the lessons "
            "app on every lesson mutation; rebuild with `manage.py "
            "recount_lessons`."
        ),
    )

    # Rating aggregates: opaque, rebuildable caches maintained by the
    # reviews app at its mutation choke point (ADR 0021). They exist so
    # course cards carry a rating without an N+1 or a cross-app join;
    # this app computes nothing about reviews itself. Rebuild with
    # `manage.py rebuild_rating_aggregates`.
    rating_average = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Average of active reviews; null when unreviewed.",
    )
    rating_count = models.PositiveIntegerField(
        default=0,
        help_text="Count of active reviews.",
    )

    class Meta:
        verbose_name = "course"
        verbose_name_plural = "courses"
        ordering = ("-published_at", "-created_at", "-id")
        constraints = [
            models.UniqueConstraint(Lower("slug"), name="courses_course_slug_ci_unique"),
        ]
        indexes = [
            models.Index(
                fields=["status", "visibility", "-published_at"],
                name="courses_listing_idx",
            ),
            models.Index(
                fields=["instructor", "status"], name="courses_instructor_idx"
            ),
        ]

    def __str__(self) -> str:
        """Return the course title."""
        return self.title

    @property
    def is_published(self) -> bool:
        """Whether the course is currently published."""
        return self.status == CourseStatus.PUBLISHED

    @property
    def slug_is_frozen(self) -> bool:
        """Whether the slug may no longer change."""
        return self.published_at is not None
