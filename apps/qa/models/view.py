"""Who has read a question thread."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models.base import TimeStampedModel


class ThreadView(TimeStampedModel):
    """One signed-in reader who has opened one thread.

    A row, not a counter (the gallery-interactions rule, ADR 0032): the
    board's "N คนอ่าน" is ``Count("views")`` over these rows, so it can
    never drift, and re-opening a thread cannot inflate it - the unique
    constraint makes recording a view idempotent.

    Only signed-in readers are recorded, and that is what the UI says.
    Counting anonymous traffic would mean minting a session cookie for
    every passer-by, which is a bigger promise than a view tally is
    worth; a number that undercounts honestly beats one that is inflated
    by refreshes and crawlers.
    """

    thread = models.ForeignKey(
        "qa.QuestionThread", on_delete=models.CASCADE, related_name="views"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="thread_views",
    )

    class Meta:
        verbose_name = "thread view"
        verbose_name_plural = "thread views"
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=["thread", "user"], name="qa_one_view_per_reader"
            ),
        ]

    def __str__(self) -> str:
        """Return the view description."""
        return f"thread {self.thread_id} read by user {self.user_id}"
