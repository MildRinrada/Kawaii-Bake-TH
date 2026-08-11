"""Enumerations and magic values for the Q&A app."""

from __future__ import annotations

from django.db import models


class ThreadStatus(models.TextChoices):
    """Lifecycle of a question thread.

    ``DELETED`` is soft: the row (and every answer under it) survives as
    history, but no API surface  list, detail, search, answers  ever
    returns it. ``HIDDEN`` is staff moderation; the author still sees
    their own hidden thread, mirroring reviews.
    """

    ACTIVE = "active", "Active"
    HIDDEN = "hidden", "Hidden by moderation"
    DELETED = "deleted", "Deleted by the author"


class ThreadTargetKind(models.TextChoices):
    """What a thread is asking about."""

    RECIPE = "recipe", "Recipe"
    COURSE = "course", "Course"


# The states staff moderation may set  DELETED is never assignable.
THREAD_MODERATION_CHOICES = [
    (ThreadStatus.ACTIVE.value, "Active"),
    (ThreadStatus.HIDDEN.value, "Hidden"),
]

THREAD_TITLE_MAX_LENGTH = 200
THREAD_BODY_MAX_LENGTH = 4000
ANSWER_BODY_MAX_LENGTH = 4000
