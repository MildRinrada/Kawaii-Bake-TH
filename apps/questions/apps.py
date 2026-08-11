"""App configuration for the questions app."""

from __future__ import annotations

from django.apps import AppConfig


class QuestionsConfig(AppConfig):
    """The reusable question bank.

    Deliberately a **leaf**: this app imports no other feature app and knows
    nothing about quizzes, attempts, scores or gamification. That ignorance is
    what makes a question reusable  any future consumer (lesson inline
    checks, AI-generated practice) composes questions through the same public
    services this app already exposes. See
    ``docs/adr/0010-question-bank-and-quiz-boundary.md``.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.questions"
    label = "questions"
    verbose_name = "Question bank"
