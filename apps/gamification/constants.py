"""Enumerations and magic values for the gamification app."""

from __future__ import annotations

from django.db import models


class XPReason(models.TextChoices):
    """What a ledger entry was earned for."""

    LESSON_COMPLETED = "lesson_completed", "Lesson completed"
    COURSE_COMPLETED = "course_completed", "Course completed"
    QUIZ_COMPLETED = "quiz_completed", "Quiz completed"
    CERTIFICATE_ISSUED = "certificate_issued", "Certificate issued"
    REVIEW_WRITTEN = "review_written", "Review written"


# How many ledger entries the summary endpoint returns.
RECENT_TRANSACTIONS_LIMIT = 10
