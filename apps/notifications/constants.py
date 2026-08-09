"""Enumerations and magic values for the notifications app."""

from __future__ import annotations

from django.db import models


class NotificationEventType(models.TextChoices):
    """What happened. Exactly the wired events — new types are an
    ADR/docs change, not just another ``notify`` call (ADR 0016).
    Phase 10 shipped the first three; Phase 11 added the two Q&A events
    (ADR 0017)."""

    REVIEW_RECEIVED = "review_received", "Review received"
    COURSE_ENROLLMENT = "course_enrollment", "New course enrollment"
    ACHIEVEMENT_EARNED = "achievement_earned", "Achievement earned"
    QA_ANSWER_RECEIVED = "qa_answer_received", "Your question got an answer"
    QA_ANSWER_ACCEPTED = "qa_answer_accepted", "Your answer was accepted"


TITLE_MAX_LENGTH = 200
BODY_MAX_LENGTH = 500
ACTOR_HANDLE_MAX_LENGTH = 150
LINK_MAX_LENGTH = 300
