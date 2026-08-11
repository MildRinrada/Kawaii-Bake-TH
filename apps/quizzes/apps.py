"""App configuration for the quizzes app."""

from __future__ import annotations

from django.apps import AppConfig


class QuizzesConfig(AppConfig):
    """Quiz definitions, attempts and scoring.

    The dependent side of the ``quizzes → questions`` boundary: a quiz
    *references* bank questions, never owns them. The only communication is
    calls into the questions app's public selectors/services  including
    ``freeze_questions()``, pushed at attempt start because this app is the
    one that knows *why* a question must freeze. See
    ``docs/adr/0010-question-bank-and-quiz-boundary.md``.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.quizzes"
    label = "quizzes"
    verbose_name = "Quizzes"
