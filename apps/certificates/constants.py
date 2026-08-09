"""Enumerations and magic values for the certificates app."""

from __future__ import annotations

from django.db import models


class AchievementType(models.TextChoices):
    """What an achievement was earned for.

    ``QUIZ_MASTER`` and ``RECIPE_AUTHOR`` are declared but not yet awarded:
    content apps must not import certificates, so those awards will be
    derived by this app reading quizzes'/recipes' public selectors in a
    future phase (via ``recalculate``), never pushed by the content apps.
    """

    COURSE_COMPLETED = "course_completed", "Completed a course"
    FIRST_COURSE = "first_course", "First course completed"
    TEN_COURSES = "ten_courses", "Ten courses completed"
    QUIZ_MASTER = "quiz_master", "Quiz master"
    RECIPE_AUTHOR = "recipe_author", "Recipe author"


class CertificateStatus(models.TextChoices):
    """Verification verdict for a certificate."""

    VALID = "valid", "Valid"
    REVOKED = "revoked", "Revoked"


# KB-<year>-<six digits>, e.g. KB-2026-000001. Globally unique; the
# zero-padded sequence keeps lexicographic and numeric order identical.
CERTIFICATE_NUMBER_PREFIX = "KB"
CERTIFICATE_SEQUENCE_DIGITS = 6

# Collision retries when two issuances race for the same sequence number.
NUMBER_ALLOCATION_ATTEMPTS = 5

TEN_COURSES_THRESHOLD = 10

STUDENT_NAME_MAX_LENGTH = 150
COURSE_TITLE_MAX_LENGTH = 200
