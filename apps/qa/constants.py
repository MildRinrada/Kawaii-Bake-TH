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


class ThreadOrdering(models.TextChoices):
    """How a board page may be sorted.

    ``LATEST`` is the default and the only one that existed before: it
    answers "what is new", which on its own buries every unanswered
    question the moment anyone posts anything. ``ACTIVE`` sorts by the
    most recent answer, ``POPULAR`` by distinct readers.
    """

    LATEST = "latest", "Newest question first"
    ACTIVE = "active", "Most recently answered first"
    POPULAR = "popular", "Most read first"


# A question with no answers after this long is one the board has failed
# to answer, not one that is merely new  the UI surfaces it for help.
NEEDS_HELP_AFTER_HOURS = 24


# The states staff moderation may set  DELETED is never assignable.
THREAD_MODERATION_CHOICES = [
    (ThreadStatus.ACTIVE.value, "Active"),
    (ThreadStatus.HIDDEN.value, "Hidden"),
]

THREAD_TITLE_MAX_LENGTH = 200
THREAD_BODY_MAX_LENGTH = 4000
ANSWER_BODY_MAX_LENGTH = 4000
