"""The lesson entity."""

from __future__ import annotations

from django.db import models

from apps.core.models.base import TimeStampedModel
from apps.lessons.constants import (
    LESSON_CONTENT_MAX_LENGTH,
    LESSON_TITLE_MAX_LENGTH,
    LessonStatus,
    VideoProvider,
)


class Lesson(TimeStampedModel):
    """One unit of learning within a course.

    ``lessons`` is the dependent side of the app boundary: this FK is a lazy
    string reference (no import edge), and the ``courses`` app never uses the
    reverse accessor it creates. See ``docs/adr/0009-courses-lessons-boundary.md``.

    Lessons are **entities, not value objects**  ``LessonProgress`` rows point
    at them, so the whole-collection-replace write pattern used for recipe
    steps must never be applied here (it would cascade-delete every student's
    progress). Lessons are created, edited and deleted individually, and
    reordered by a dedicated endpoint.

    ``position`` is dense (0..n-1), server-assigned, renumbered on delete, and
    deliberately **not** unique-constrained  a non-deferrable unique breaks
    bulk renumbering mid-flight. Ordering ties break on ``id``.
    """

    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="lessons",
    )
    recipe = models.ForeignKey(
        "recipes.Recipe",
        on_delete=models.SET_NULL,
        related_name="lessons",
        null=True,
        blank=True,
        help_text="The recipe this lesson teaches, if any.",
    )
    quiz = models.ForeignKey(
        "quizzes.Quiz",
        on_delete=models.SET_NULL,
        related_name="lessons",
        null=True,
        blank=True,
        help_text=(
            "An optional quiz for this lesson  a reference only (Phase 4); "
            "quiz logic stays entirely in the quizzes app."
        ),
    )

    title = models.CharField(max_length=LESSON_TITLE_MAX_LENGTH)
    content = models.TextField(max_length=LESSON_CONTENT_MAX_LENGTH, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    duration_minutes = models.PositiveIntegerField(
        default=0, help_text="Estimated time to finish, shown on the syllabus."
    )
    is_preview = models.BooleanField(
        default=False,
        help_text="Preview lessons are readable without enrollment.",
    )
    status = models.CharField(
        max_length=20,
        choices=LessonStatus.choices,
        default=LessonStatus.DRAFT,
        db_index=True,
    )

    # External embeds only  no video infrastructure exists yet.
    video_url = models.URLField(blank=True)
    video_provider = models.CharField(
        max_length=20, choices=VideoProvider.choices, blank=True
    )
    video_duration_seconds = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "lesson"
        verbose_name_plural = "lessons"
        ordering = ("position", "id")
        indexes = [
            models.Index(fields=["course", "position"], name="lessons_order_idx"),
            models.Index(fields=["course", "status"], name="lessons_course_status_idx"),
        ]

    def __str__(self) -> str:
        """Return the lesson title."""
        return self.title

    @property
    def is_published(self) -> bool:
        """Whether the lesson appears on the public syllabus."""
        return self.status == LessonStatus.PUBLISHED
