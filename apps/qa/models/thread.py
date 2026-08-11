"""The question thread entity."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models.base import TimeStampedModel
from apps.qa.constants import (
    THREAD_BODY_MAX_LENGTH,
    THREAD_TITLE_MAX_LENGTH,
    ThreadStatus,
)


class QuestionThread(TimeStampedModel):
    """One user's question about a recipe or course.

    Targets are nullable ``SET_NULL``  not reviews' CASCADE  because a
    thread contains **other users' answers**: deleting a recipe must not
    silently destroy a discussion (the rule 10/12 history mandate). The
    check constraint forbids both targets at once; the service requires
    exactly one at creation, so a NULL target only ever means "the
    content is gone", and the thread degrades to context-free.

    ``accepted_answer`` is a nullable same-app FK with ``SET_NULL``:
    replacing the accepted answer is one field UPDATE (the old unset is
    implicit  a single column cannot point at two rows), and deleting
    the accepted answer clears it at the database layer with no code to
    forget. No ``answer_count``  it aggregates live.
    """

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="question_threads",
    )
    recipe = models.ForeignKey(
        "recipes.Recipe",
        on_delete=models.SET_NULL,
        related_name="question_threads",
        null=True,
        blank=True,
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        related_name="question_threads",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=THREAD_TITLE_MAX_LENGTH)
    body = models.TextField(max_length=THREAD_BODY_MAX_LENGTH, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ThreadStatus.choices,
        default=ThreadStatus.ACTIVE,
        db_index=True,
    )
    accepted_answer = models.ForeignKey(
        "qa.QuestionAnswer",
        on_delete=models.SET_NULL,
        related_name="accepted_for",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "question thread"
        verbose_name_plural = "question threads"
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=~Q(recipe__isnull=False, course__isnull=False),
                name="qa_at_most_one_target",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "-created_at"], name="qa_thread_feed_idx"
            ),
            models.Index(
                fields=["recipe", "status", "-created_at"],
                name="qa_thread_recipe_idx",
            ),
            models.Index(
                fields=["course", "status", "-created_at"],
                name="qa_thread_course_idx",
            ),
        ]

    def __str__(self) -> str:
        """Return the thread description."""
        return f"thread {self.pk} · user {self.author_id}"
