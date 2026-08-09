"""Enumerations and magic values for the question bank."""

from __future__ import annotations

from django.db import models


class QuestionType(models.TextChoices):
    """How a question is asked and graded.

    All three launch types are **choice-backed**: True/False is stored as two
    ordinary answer choices, not a special mechanism, so grading stays one code
    path. Future types (short answer, AI evaluation, matching, ordering,
    fill-in-the-blank) extend this enum plus one grader and one validator each
    — types that need no choices simply have no ``AnswerChoice`` rows.
    """

    SINGLE_CHOICE = "single_choice", "Single choice"
    MULTIPLE_CHOICE = "multiple_choice", "Multiple choice"
    TRUE_FALSE = "true_false", "True / False"


class QuestionDifficulty(models.TextChoices):
    """How hard a question is — bank filtering and future adaptive quizzes."""

    EASY = "easy", "Easy"
    MEDIUM = "medium", "Medium"
    HARD = "hard", "Hard"


class QuestionScope(models.TextChoices):
    """Which slice of the bank a list request is asking for."""

    MINE = "mine", "My questions"
    ALL = "all", "Everything (staff only)"


# --------------------------------------------------------------------------
# Field limits
# --------------------------------------------------------------------------
QUESTION_TEXT_MIN_LENGTH = 5
QUESTION_TEXT_MAX_LENGTH = 1000
EXPLANATION_MAX_LENGTH = 2000
CHOICE_TEXT_MAX_LENGTH = 300
MIN_CHOICES_PER_QUESTION = 2
MAX_CHOICES_PER_QUESTION = 10
TRUE_FALSE_CHOICE_COUNT = 2
MAX_TAGS_PER_QUESTION = 10
TAG_NAME_MAX_LENGTH = 50
TAG_SLUG_MAX_LENGTH = 80
TAG_SLUG_SUFFIX_BYTES = 3
