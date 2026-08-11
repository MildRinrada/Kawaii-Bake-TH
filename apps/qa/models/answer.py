"""The answer entity."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models.base import TimeStampedModel
from apps.qa.constants import ANSWER_BODY_MAX_LENGTH


class QuestionAnswer(TimeStampedModel):
    """One user's answer on a thread.

    Answers are leaves  nothing references them except the thread's
    nullable ``accepted_answer`` pointer  so author deletion is **hard**;
    ``SET_NULL`` on that pointer means deleting the accepted answer
    reverts the thread to unanswered with zero application code. Answers
    are reachable only through their thread's visibility: a hidden or
    deleted thread takes its answers out of every API surface with it.
    """

    thread = models.ForeignKey(
        "qa.QuestionThread", on_delete=models.CASCADE, related_name="answers"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="question_answers",
    )
    body = models.TextField(max_length=ANSWER_BODY_MAX_LENGTH)

    class Meta:
        verbose_name = "answer"
        verbose_name_plural = "answers"
        # Chronological  a discussion reads top to bottom.
        ordering = ("created_at", "id")
        indexes = [
            models.Index(
                fields=["thread", "created_at"], name="qa_answer_thread_idx"
            ),
        ]

    def __str__(self) -> str:
        """Return the answer description."""
        return f"answer {self.pk} · thread {self.thread_id}"
