"""Enumerations and magic values for the reviews app."""

from __future__ import annotations

from django.db import models


class ReviewStatus(models.TextChoices):
    """Moderation lifecycle of a review.

    ``DELETED`` is soft: the row survives for history and moderation audit;
    it simply stops counting anywhere. Only ``ACTIVE`` reviews are listed or
    aggregated.
    """

    ACTIVE = "active", "Active"
    HIDDEN = "hidden", "Hidden by moderation"
    DELETED = "deleted", "Deleted by the author"


class ReviewTargetKind(models.TextChoices):
    """What a review (or favorite) points at."""

    RECIPE = "recipe", "Recipe"
    COURSE = "course", "Course"


RATING_MIN = 1
RATING_MAX = 5
COMMENT_MAX_LENGTH = 2000
